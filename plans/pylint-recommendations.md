# Pylint Recommendations Report

**Generated:** 2026-04-02  
**Pylint Version:** 2.17.4  
**Overall Score:** 8.64/10

## Summary

The codebase has a good overall score of 8.64/10. The issues found are primarily style-related and can be categorized as follows:

| Category | Count | Priority |
|----------|-------|----------|
| Naming Convention (C0103) | ~30 | Low |
| Trailing Whitespace (C0303) | ~25 | Low |
| Line Too Long (C0301) | ~15 | Low |
| Missing Docstrings (C0114, C0115, C0116) | ~10 | Medium |
| Broad Exception Caught (W0718) | ~15 | High |
| Logging F-String Interpolation (W1203) | ~15 | Medium |
| Unused Imports (W0611) | ~5 | Low |
| Raise Missing From (W0707) | ~5 | Medium |
| Duplicate Code (R0801) | 3 instances | Medium |
| Too Many Arguments/Locals (R0913, R0914) | ~3 | Medium |

---

## High Priority Issues

### 1. Broad Exception Caught (W0718)

Catching `Exception` is too general and can hide bugs. Use specific exceptions instead.

**Files affected:**
- [`app/database/session_handler.py`](app/database/session_handler.py:40)
- [`app/database/sql_service.py`](app/database/sql_service.py:164)
- [`app/database/repositories/model_repository.py`](app/database/repositories/model_repository.py:110)
- [`app/database/repositories/prediction_repository.py`](app/database/repositories/prediction_repository.py:98)
- [`app/services/task_service.py`](app/services/task_service.py:30)
- [`app/api/v1/endpoints/binaries.py`](app/api/v1/endpoints/binaries.py:110)
- [`app/api/v1/endpoints/models.py`](app/api/v1/endpoints/models.py:46)
- [`app/api/v1/endpoints/predictions.py`](app/api/v1/endpoints/predictions.py:57)
- [`app/processing/ghidra_processor.py`](app/processing/ghidra_processor.py:146)

**Recommendation:**
```python
# Instead of:
try:
    # code
except Exception as e:
    logger.error(f"Error: {e}")

# Use specific exceptions:
try:
    # code
except (ValueError, TypeError) as e:
    logger.error("Validation error: %s", e)
except FileNotFoundError as e:
    logger.error("File not found: %s", e)
```

---

### 2. Logging F-String Interpolation (W1203)

Using f-strings in logging functions prevents lazy evaluation. Use `%` formatting instead.

**Files affected:**
- [`app/database/session_handler.py`](app/database/session_handler.py:39)
- [`app/database/repositories/model_repository.py`](app/database/repositories/model_repository.py:87)
- [`app/database/repositories/prediction_repository.py`](app/database/repositories/prediction_repository.py:99)
- [`app/api/v1/endpoints/predictions.py`](app/api/v1/endpoints/predictions.py:58)
- [`app/processing/steps.py`](app/processing/steps.py:44)

**Recommendation:**
```python
# Instead of:
logger.error(f"Error occurred: {e}")

# Use:
logger.error("Error occurred: %s", e)
```

---

### 3. Duplicate Code (R0801)

Duplicate code blocks found between API endpoints and web endpoints.

**Locations:**
- [`app/api/v1/endpoints/models.py:202-225`](app/api/v1/endpoints/models.py:202) and [`app/web/endpoints/web.py:165-186`](app/web/endpoints/web.py:165)

**Recommendation:**
Extract the common logic into a shared utility function in [`app/utils/common.py`](app/utils/common.py) or create a base class for handling prediction details.

---

## Medium Priority Issues

### 4. Missing Docstrings (C0114, C0115, C0116)

**Files affected:**
- [`app/web/endpoints/web.py`](app/web/endpoints/web.py:1) - Missing module docstring
- [`app/api/v1/endpoints/tasks.py`](app/api/v1/endpoints/tasks.py:1) - Missing module docstring
- [`app/api/v1/endpoints/binaries.py`](app/api/v1/endpoints/binaries.py:1) - Missing module docstring
- [`app/api/v1/endpoints/status.py`](app/api/v1/endpoints/status.py:1) - Missing module docstring
- [`app/api/v1/endpoints/models.py`](app/api/v1/endpoints/models.py:1) - Missing module docstring
- [`app/api/v1/endpoints/config.py`](app/api/v1/endpoints/config.py:1) - Missing module docstring
- [`app/api/v1/endpoints/predictions.py`](app/api/v1/endpoints/predictions.py:1) - Missing module docstring
- [`app/utils/responses.py`](app/utils/responses.py:24) - Missing function docstring

**Recommendation:**
Add module-level docstrings describing the purpose of each module:
```python
"""
Module description explaining what this module does.

This module provides endpoints for...
"""
```

---

### 5. Raise Missing From (W0707)

When re-raising exceptions, use `from e` to preserve the exception chain.

**Files affected:**
- [`app/web/endpoints/web.py`](app/web/endpoints/web.py:164)
- [`app/api/v1/endpoints/binaries.py`](app/api/v1/endpoints/binaries.py:44)
- [`app/processing/steps.py`](app/processing/steps.py:74)

**Recommendation:**
```python
# Instead of:
except Exception as e:
    raise HTTPException(status_code=400, detail="Error")

# Use:
except Exception as e:
    raise HTTPException(status_code=400, detail="Error") from e
```

---

### 6. Too Many Arguments/Locals (R0913, R0914)

**Files affected:**
- [`app/services/request_handler.py`](app/services/request_handler.py:140) - 6 arguments
- [`app/api/v1/endpoints/binaries.py`](app/api/v1/endpoints/binaries.py:83) - 6 arguments, 22 local variables

**Recommendation:**
Consider using a dataclass or Pydantic model to group related parameters:
```python
from pydantic import BaseModel

class UploadBinaryRequest(BaseModel):
    binary_file: UploadFile
    training_data: str
    model_name: str
    ml_class_type: str
    task_name: str

async def post_upload_binary(request: UploadBinaryRequest):
    # Implementation
```

---

## Low Priority Issues

### 7. Naming Convention (C0103)

Variables and arguments should follow snake_case naming convention.

**Common violations:**
- `modelName` → `model_name`
- `taskName` → `task_name`
- `functionName` → `function_name`
- `binaryFile` → `binary_file`
- `trainingData` → `training_data`
- `mlClassType` → `ml_class_type`
- Single-letter exception variables (`e`) → `exc` or `error`

**Files affected:**
- [`app/web/endpoints/web.py`](app/web/endpoints/web.py:136)
- [`app/api/v1/endpoints/models.py`](app/api/v1/endpoints/models.py:21)
- [`app/api/v1/endpoints/predictions.py`](app/api/v1/endpoints/predictions.py:70)
- [`app/api/v1/endpoints/binaries.py`](app/api/v1/endpoints/binaries.py:85)

---

### 8. Trailing Whitespace (C0303)

Remove trailing whitespace from lines.

**Files affected:**
- [`app/web/endpoints/web.py`](app/web/endpoints/web.py:110)
- [`app/database/models.py`](app/database/models.py:31)
- [`app/utils/secure_deserializer.py`](app/utils/secure_deserializer.py:131)
- [`app/api/v1/endpoints/binaries.py`](app/api/v1/endpoints/binaries.py:45)

**Recommendation:**
Configure your editor to automatically strip trailing whitespace on save.

---

### 9. Line Too Long (C0301)

Lines exceeding 100 characters should be wrapped.

**Files affected:**
- [`app/web/endpoints/web.py`](app/web/endpoints/web.py:9)
- [`app/database/models.py`](app/database/models.py:39)
- [`app/utils/persistence_util.py`](app/utils/persistence_util.py:385)

**Recommendation:**
Break long lines using parentheses or backslash continuation:
```python
# Instead of:
result = some_function(arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8)

# Use:
result = some_function(
    arg1, arg2, arg3,
    arg4, arg5, arg6,
    arg7, arg8
)
```

---

### 10. Unused Imports (W0611)

Remove unused imports to clean up the code.

**Files affected:**
- [`app/database/repositories/model_repository.py`](app/database/repositories/model_repository.py:7) - Unused `Session`
- [`app/utils/secure_deserializer.py`](app/utils/secure_deserializer.py:17) - Unused `joblib`
- [`app/api/v1/endpoints/status.py`](app/api/v1/endpoints/status.py:1) - Unused `HTTPException`
- [`app/api/v1/endpoints/predictions.py`](app/api/v1/endpoints/predictions.py:3) - Unused `HTTPException`
- [`app/processing/ghidra_processor.py`](app/processing/ghidra_processor.py:6) - Unused `GlyphConfig`

---

## Additional Notes

### Import Errors (E0401)
The following import errors are expected and can be ignored as they relate to optional dependencies:
- `ghidra.app.decompiler` - Only available when Ghidra is installed
- `pyghidra` - Optional dependency
- `java.util` - Java library accessed through pyghidra

### Too Few Public Methods (R0903)
Several data classes have no methods, which is expected for SQLAlchemy models and Pydantic models:
- [`app/database/models.py`](app/database/models.py:20) - Model, Prediction, Function
- [`app/services/request_handler.py`](app/services/request_handler.py:11) - DataHandler, TrainingRequest, GhidraRequest, Prediction

These can be suppressed with a comment:
```python
class Model(Base):
    """Database model for ML models."""
    # pylint: disable=too-few-public-methods
    ...
```

---

## Recommended Fix Order

1. **High Priority:** Fix broad exception handling (W0718)
2. **High Priority:** Fix logging f-string interpolation (W1203)
3. **Medium Priority:** Extract duplicate code (R0801)
4. **Medium Priority:** Add missing docstrings (C0114, C0115, C0116)
5. **Medium Priority:** Add `from e` to re-raised exceptions (W0707)
6. **Low Priority:** Fix naming conventions (C0103)
7. **Low Priority:** Remove trailing whitespace (C0303)
8. **Low Priority:** Wrap long lines (C0301)
9. **Low Priority:** Remove unused imports (W0611)

---

## Quick Fix Commands

```bash
# Remove trailing whitespace from all Python files
find app -name "*.py" -exec sed -i 's/[[:space:]]*$//' {} +

# Add final newlines to files missing them
find app -name "*.py" -exec sh -c 'test -n "$(tail -c1 "$1")" && echo "" >> "$1"' _ {} +

# Remove trailing newlines from files with extra ones
find app -name "*.py" -exec sed -i -e :a -e '/^\n*$/{$d;N;ba' -e '}' {} +
```
