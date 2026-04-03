# FastAPI Code Improvements for Glyph

## Executive Summary

This document identifies code patterns in the Glyph project that don't follow FastAPI best practices and provides recommendations for improvement using FastAPI's built-in features and libraries.

---

## 1. Background Task Management

### Current Issue
The application uses a custom `TaskService` with a background thread and `ProcessPoolExecutor` for task management:

```python
# app/services/task_service.py
class TaskService:
    service_queue: queue.Queue = queue.Queue()
    
    @classmethod
    def start_service(cls) -> None:
        while True:
            task = cls.service_queue.get(block=True)
            task[1].result()
            cls.service_queue.task_done()
```

### FastAPI Standard Approach
Use FastAPI's `BackgroundTasks` for request-scoped background work and consider `Celery` or `ARQ` for long-running tasks:

```python
from fastapi import BackgroundTasks
from app.processing.task_management import Trainer

@router.post("/task")
async def handle_task(
    background_tasks: BackgroundTasks,
    request: TaskRequest
):
    """Submit task for background processing."""
    if request.type == "training":
        background_tasks.add_task(Trainer().start_training, request)
    elif request.type == "prediction":
        background_tasks.add_task(Predictor().start_prediction, request)
    
    return create_success_response(
        data={"uuid": request.uuid},
        message="Task submitted successfully"
    )
```

**Benefits:**
- Automatic task lifecycle management tied to request
- Better error handling and logging
- No need for custom queue management
- Cleaner separation of concerns

---

## 2. Dependency Injection

### Current Issue
Database sessions and settings are accessed directly without using FastAPI's dependency injection:

```python
# app/api/v1/endpoints/binaries.py
def validate_binary_mime_type(file_content: bytes) -> None:
    settings = get_settings()  # Direct access
    # ...
```

### FastAPI Standard Approach
Use `Depends()` for dependency injection:

```python
from fastapi import Depends
from sqlalchemy.orm import Session
from app.database.session_handler import get_session

def get_db_session(database: str = "models") -> Session:
    """Dependency for database session."""
    with get_session(database) as session:
        yield session

@router.get("/getFunction")
async def get_function(
    model_name: str = Query(...),
    function_name: str = Query(...),
    db: Session = Depends(get_db_session)
):
    """Get function details using injected database session."""
    # Use db session for queries
```

**Benefits:**
- Automatic dependency lifecycle management
- Easier testing with mock dependencies
- Clear dependency graph
- Reusable dependencies across endpoints

---

## 3. Request Validation with Pydantic

### Current Issue
Query parameters are validated manually after retrieval:

```python
# app/api/v1/endpoints/models.py
@router.delete("/deleteModel")
async def delete_model(modelName: str = Query(...)):
    model_name = modelName.strip()
    
    if not model_name:
        return create_error_response(...)  # Manual validation
```

### FastAPI Standard Approach
Use Pydantic validators with `Annotated` types:

```python
from typing_extensions import Annotated
from pydantic import StringConstraints

ModelName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64)
]

@router.delete("/deleteModel")
async def delete_model(model_name: ModelName):
    """Delete model - validation handled automatically."""
    MLPersistanceUtil.delete_model(model_name)
    return create_success_response(...)
```

**Benefits:**
- Automatic validation before endpoint execution
- Better OpenAPI documentation
- Type-safe validation
- Reduced boilerplate code

---

## 4. Response Model Consistency

### Current Issue
Endpoints return tuples of `(response, status_code)` instead of using FastAPI's response models:

```python
# app/api/v1/endpoints/binaries.py
@router.post("/uploadBinary", response_model=SuccessResponse[dict])
async def post_upload_binary(...):
    # Returns tuple instead of just response
    return create_error_response(...), 400
```

### FastAPI Standard Approach
Use `HTTPException` for error cases and let FastAPI handle status codes:

```python
from fastapi import HTTPException

@router.post("/uploadBinary", response_model=SuccessResponse[dict])
async def post_upload_binary(...):
    """Upload binary with proper error handling."""
    if not binary_file.filename:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code="NO_FILE_FOUND",
                error_message="no file found"
            ).model_dump()
        )
    
    # Success case - just return the response
    return create_success_response(...)
```

**Benefits:**
- Consistent error handling
- Better OpenAPI documentation
- Cleaner endpoint code
- Automatic status code handling

---

## 5. File Upload Handling

### Current Issue
File uploads are read and written manually:

```python
# app/api/v1/endpoints/binaries.py
file_content = await binary_file.read()
with open(file_path, "wb") as f:
    f.write(file_content)
```

### FastAPI Standard Approach
Use `StreamingResponse` for downloads and proper file handling:

```python
from fastapi import UploadFile, File
from fastapi.responses import StreamingResponse
import shutil

@router.post("/uploadBinary")
async def upload_binary(
    binary_file: UploadFile = File(...)
):
    """Upload binary with streaming support."""
    file_path = Path(upload_folder) / f"{uuid.uuid4()}"
    
    # Stream file directly to disk
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(binary_file.file, buffer)
    
    return create_success_response(data={"uuid": str(file_path)})
```

For downloads:
```python
@router.get("/download/{file_uuid}")
async def download_binary(file_uuid: str):
    """Download binary file."""
    file_path = Path(upload_folder) / file_uuid
    
    return StreamingResponse(
        open(file_path, "rb"),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={file_uuid}"}
    )
```

**Benefits:**
- Memory efficient for large files
- Better streaming support
- Cleaner file handling

---

## 6. Database Session Management

### Current Issue
Database sessions use a context manager pattern that doesn't integrate with FastAPI's async model:

```python
# app/database/session_handler.py
@contextmanager
def get_session(database: str = "models") -> Generator[Session, None, None]:
    session = session_factories[database]()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

### FastAPI Standard Approach
Use async session generator with `Depends()`:

```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite+aiosqlite:///models.db"
engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Async database session dependency."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

**Benefits:**
- Proper async/await support
- Better integration with FastAPI
- Improved performance for I/O operations
- Cleaner dependency injection

---

## 7. Exception Handling

### Current Issue
Exception handlers return both HTML and JSON based on Accept header:

```python
# main.py
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    accept = request.headers.get("Accept", "")
    if "text/html" in accept:
        return templates.TemplateResponse(...)
    return JSONResponse(...)
```

### FastAPI Standard Approach
Use `Request` dependency to determine response type:

```python
from fastapi import Request, Response
from fastapi.responses import HTMLResponse, JSONResponse

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with content negotiation."""
    is_html_request = request.url.path in ["/", "/main", "/config", "/models", "/predictions"]
    
    if is_html_request:
        return HTMLResponse(
            content=templates.TemplateResponse(
                "error.html",
                {"request": request, "message": f"Error {exc.status_code}: {exc.detail}"}
            ),
            status_code=exc.status_code
        )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )
```

**Benefits:**
- Clearer separation of API and web routes
- Better content negotiation
- More maintainable exception handling

---

## 8. API Router Organization

### Current Issue
Router tags are set at the router level, not at the endpoint level:

```python
# app/api/router.py
api_v1_router.include_router(binaries.router, prefix="/binaries", tags=["binaries"])
```

### FastAPI Standard Approach
Set tags at the endpoint level for better documentation:

```python
# app/api/v1/endpoints/binaries.py
router = APIRouter(prefix="/binaries", tags=["Binaries"])

@router.post("/uploadBinary")
async def upload_binary(...):
    """Upload a binary file for analysis."""
    pass
```

**Benefits:**
- Better OpenAPI documentation organization
- More granular control over documentation
- Easier to add/remove endpoints from documentation

---

## 9. WebSocket Support for Real-time Updates

### Current Issue
Task status is polled via HTTP requests:

```python
# app/api/v1/endpoints/status.py
@router.get("/getStatus")
async def get_status(uuid: str = Query(...)):
    status = Trainer().get_status(uuid)
    # ...
```

### FastAPI Standard Approach
Add WebSocket support for real-time status updates:

```python
from fastapi import WebSocket, WebSocketDisconnect

@router.websocket("/ws/status/{task_uuid}")
async def task_status_websocket(websocket: WebSocket, task_uuid: str):
    """WebSocket endpoint for real-time task status updates."""
    await websocket.accept()
    
    try:
        while True:
            status = Trainer().get_status(task_uuid)
            await websocket.send_json({"uuid": task_uuid, "status": status})
            
            if status in ["completed", "failed"]:
                break
            
            await asyncio.sleep(1)  # Poll interval
    except WebSocketDisconnect:
        logging.info(f"WebSocket disconnected for task {task_uuid}")
```

**Benefits:**
- Real-time status updates
- Better user experience
- Reduced server load from polling

---

## 10. Request/Response Hooks

### Current Issue
No middleware for request logging, tracing, or correlation IDs:

```python
# main.py - No middleware configured
app = FastAPI(...)
```

### FastAPI Standard Approach
Add middleware for request handling:

```python
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to add request ID to all requests."""
    
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

app.add_middleware(RequestIDMiddleware)
```

**Benefits:**
- Request tracing and correlation
- Better logging and debugging
- Improved observability

---

## 11. OpenAPI Documentation Customization

### Current Issue
Basic API documentation with minimal customization:

```python
# main.py
app = FastAPI(
    title="Glyph API",
    description="Binary analysis and powered by machine learning",
    version="0.0.2",
)
```

### FastAPI Standard Approach
Enhanced documentation configuration:

```python
app = FastAPI(
    title="Glyph API",
    description="""
## Binary Analysis and Machine Learning Platform

Glyph is an architecture-independent binary analysis tool that uses NLP techniques 
for function fingerprinting across different system architectures.

### Features
- Binary upload and analysis
- Machine learning model training
- Function name prediction
- Real-time task status monitoring
    """,
    version="0.0.2",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    terms_of_service="https://example.com/terms",
    contact={
        "name": "Glyph Team",
        "email": "support@example.com"
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT"
    }
)
```

**Benefits:**
- Better API documentation
- Professional appearance
- Clearer API usage guidelines

---

## 12. Security Improvements

### Current Issue
File upload validation is done manually:

```python
# app/api/v1/endpoints/binaries.py
def validate_binary_mime_type(file_content: bytes) -> None:
    mime_type = magic.from_buffer(file_content[:1024], mime=True)
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(...)
```

### FastAPI Standard Approach
Use FastAPI's built-in validation with custom dependencies:

```python
from fastapi import Depends, UploadFile, File
from typing_extensions import Annotated

class BinaryFileValidator:
    """Dependency for binary file validation."""
    
    ALLOWED_MIME_TYPES = {
        'application/x-executable',
        'application/x-object',
        'application/octet-stream',
        'application/x-elf',
        'application/x-dosexec',
        'application/x-sharedlib',
    }
    
    def validate(self, file: UploadFile, content: bytes) -> None:
        mime_type = magic.from_buffer(content[:1024], mime=True)
        if mime_type not in self.ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"File type '{mime_type}' not allowed"
            )

def validate_binary_file(
    file: UploadFile,
    validator: BinaryFileValidator = Depends()
) -> Annotated[UploadFile, Depends(validator.validate)]:
    """Validate uploaded binary file."""
    return file
```

**Benefits:**
- Reusable validation logic
- Better separation of concerns
- Easier testing

---

## Summary of Recommendations

| Priority | Area | Current Approach | Recommended Approach |
|----------|------|------------------|---------------------|
| High | Background Tasks | Custom queue + thread | FastAPI BackgroundTasks |
| High | Dependency Injection | Direct access | `Depends()` |
| High | Validation | Manual checks | Pydantic validators |
| Medium | Response Handling | Tuple returns | HTTPException |
| Medium | Database Sessions | Sync context manager | Async session generator |
| Medium | File Uploads | Manual read/write | StreamingResponse |
| Low | Real-time Updates | HTTP polling | WebSocket |
| Low | Request Tracing | None | Middleware |

---

## Implementation Priority

1. **Immediate (Week 1)**
   - Implement dependency injection for database sessions
   - Add Pydantic validators for query parameters
   - Convert error handling to use HTTPException

2. **Short-term (Week 2-3)**
   - Migrate to FastAPI BackgroundTasks
   - Add request ID middleware
   - Enhance OpenAPI documentation

3. **Long-term (Week 4+)**
   - Implement async database sessions
   - Add WebSocket support for real-time updates
   - Refactor file upload handling

---

## References

- [FastAPI Background Tasks](https://fastapi.tiangolo.com/background-tasks/)
- [FastAPI Dependencies](https://fastapi.tiangolo.com/dependencies/)
- [FastAPI Pydantic Integration](https://fastapi.tiangolo.com/pydantic/)
- [FastAPI Exception Handlers](https://fastapi.tiangolo.com/exception-handlers/)
- [FastAPI WebSocket](https://fastapi.tiangolo.com/websockets/)
