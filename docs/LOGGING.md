# Logging Best Practices for Glyph

## Overview

Glyph uses [loguru](https://loguru.readthedocs.io/) for structured, modern Python logging. Loguru provides:

- Simple configuration with powerful defaults
- Built-in JSON formatting support
- Automatic exception handling
- Contextual data binding via `logger.bind()`
- File rotation, retention, and compression
- Sensitive data redaction
- Thread-safe enqueued logging

### Components

- **JSON Format**: Default format for structured log parsing
- **Text Format**: Human-readable format with optional colors
- **Sensitive Data Redaction**: Automatic redaction of passwords, tokens, API keys
- **Request Context**: Automatic request ID, user ID, and username propagation via ContextVars

### Patcher

- **SensitiveDataPatcher**: Redacts sensitive patterns from log messages (applied via `logger.configure(patcher=...)`).

### Handlers

- **File Handler**: With rotation, retention, compression, secure file permissions (0o640), and `enqueue=True` for thread safety
- **Console Handler**: stdout with optional colorization

## Configuration

Logging is configured via `config.yml`:

```yaml
logging:
  level: "INFO"
  format: "json"  # or "text"
  file:
    path: "logs/glyph.log"
    rotation: "50 MB"
    retention: "10 days"
  console:
    enabled: true
    level: "INFO"
    colorize: true
  request_tracing:
    enabled: true
    header_name: X-Request-ID
  module_levels:
    app.database: WARNING
    app.auth: INFO
```

### Configuration Reference

| Setting | Default | Description |
|---------|---------|-------------|
| `level` | `"INFO"` | Log level for file handler |
| `format` | `"json"` | Log format (`"json"` or `"text"`) |
| `file.path` | `"logs/glyph.log"` | Path to log file |
| `file.rotation` | `"50 MB"` | Loguru rotation string (e.g., `"50 MB"`, `"00:00"`, `"1 week"`) |
| `file.retention` | `"10 days"` | Loguru retention string (e.g., `"10 days"`, `"1 month"`) |
| `console.enabled` | `true` | Enable console output |
| `console.level` | `"INFO"` | Log level for console |
| `console.colorize` | `true` | Enable colored output |

### Basic Logging

```python
from loguru import logger

logger.debug("Debug message: {}", value)
logger.info("User logged in: {}", username)
logger.warning("Configuration missing, using default")
logger.error("Failed to connect: {}", error)
logger.exception("An error occurred")  # Automatically includes traceback
```

### Structured Context with `logger.bind()`

```python
from loguru import logger

# Bind contextual data to log messages
logger.bind(user_id=user_id, username=username).info(
    "User performed action: {}", action,
)
```

### Request Context

```python
from app.utils.request_context import set_request_context, get_request_context, clear_request_context

# In middleware
set_request_context(request_id=request_id, user_id=user_id, username=username)

# Context is automatically added to log output via patch
logger.info("Processing request")

# In background tasks (manually propagate)
ctx = get_request_context()
# Use ctx.request_id, ctx.user_id, ctx.username
```

### Security Logging

```python
from app.auth.security_logger import (
    log_login_success, log_login_failure, log_logout,
    log_permission_denied, log_suspicious_activity,
)

# Authentication events
log_login_success(user_id=1, username="admin")
log_login_failure(username="admin", reason="invalid_password")

# Authorization events
log_permission_denied(user_id=1, username="user", resource="/admin", required_permission="admin")

# Account management
log_password_change(user_id=1, username="admin")

# API key lifecycle
log_api_key_created(user_id=1, key_id=1, key_prefix="sk-abc", name="My Key")
log_api_key_deleted(user_id=1, key_id=1, name="My Key")

# Security events
log_suspicious_activity(user_id=1, activity_type="brute_force", details={"attempts": 10})
```

### Security Event Reference

| Event | Level | Description |
|-------|-------|-------------|
| `login_attempt` | INFO | Login attempt initiated |
| `login_success` | INFO | Successful login |
| `login_failure` | WARNING | Failed login attempt |
| `logout` | INFO | User logout |
| `token_refresh` | DEBUG | Token refreshed |
| `api_key_usage` | DEBUG | API key used |
| `permission_denied` | WARNING | Access denied |
| `suspicious_activity` | WARNING | Suspicious activity detected |
| `password_change` | INFO | Password changed |
| `user_registration` | INFO | New user registered |
| `api_key_created` | INFO | API key created |
| `api_key_deleted` | INFO | API key deleted |
| `csrf_failure` | WARNING | CSRF validation failed |

### JSON Format (Default)

```json
{"t": "2024-01-01T00:00:00", "l": "INFO", "logger": "app.module", "msg": "User logged in", "user_id": 1, "username": "admin"}
```

### Text Format

```
2024-01-01 00:00:00.000 | INFO     | app.module | User logged in
```

## Log Levels

| Level | Use Case |
|-------|----------|
| `DEBUG` | Detailed diagnostic information |
| `INFO` | Normal operational events |
| `WARNING` | Unexpected situations that don't cause failure |
| `ERROR` | Operational failures |
| `CRITICAL` | System-level failures |

### Best Practices

### 1. Use `{}` Formatting (Not `%s`)

```python
# Good - loguru style
logger.info("User {} logged in from {}", username, ip_address)

# Bad - old style (won't work with loguru)
logger.info("User %s logged in from %s", username, ip_address)
```

### 2. Never Log Secrets

```python
# Bad - never log full secrets
logger.info("Password: {}", password)
logger.info("Token: {}", api_token)

# Good - structured context for aggregation
logger.bind(user_id=user_id).info("User authenticated")
```

### 3. Use Structured Logging with `logger.bind()`

```python
# Good - structured context, concise message
logger.bind(user_id=user_id, action="update", resource="profile").info(
    "Resource updated"
)

# Bad - no context for filtering
logger.info("Resource updated")
```

### 4. Avoid Repeating Bound Data in Messages

When using `logger.bind()`, the bound fields are already available in structured
log output. Keep messages concise rather than repeating data:

```python
# Good - data in bind, message is event description
logger.bind(user_id=user_id, username=username).info("Login successful")

# Bad - repeats data already in structured context
logger.bind(user_id=user_id, username=username).info(
    "Login successful: {} (user_id={})", username, user_id
)
```

### 5. Use `logger.exception()` for Errors

```python
try:
    process_data()
except Exception:
    # Good - automatic stack trace
    logger.exception("Failed to process data")

# Also acceptable - explicit exc_info
logger.error("Failed to process data: {}", exc)

# Bad - no stack trace for debugging
logger.error("Something went wrong")
```

### 6. Use `logger.catch()` for Automatic Exception Handling

Loguru provides `logger.catch()` as a decorator or context manager to automatically
catch, log, and optionally re-raise exceptions. This eliminates boilerplate try/except blocks:

```python
from loguru import logger

# As a decorator - logs and re-raises by default
@logger.catch
def process_data(data):
    # No try/except needed
    result = risky_operation(data)
    return result

# As a context manager
with logger.catch:
    risky_operation()

# Custom message and level
@logger.catch(message="Processing failed", reraise=False)
def process_data(data):
    risky_operation(data)
    # Exception is logged but NOT re-raised
```

For HTTP endpoints, use the project's `@catch_http_exception` decorator from
`app.utils.logging_utils` which logs and converts exceptions to HTTP responses.

### 7. Use `logger.opt(lazy=True)` for Expensive Debug Operations

When logging expensive computations, use `lazy=True` to defer evaluation until
the log level is confirmed. This avoids unnecessary computation when the level
is disabled:

```python
# Good - lambda is only called if DEBUG is enabled
logger.opt(lazy=True).debug("Token sample: {}", lambda: tokens[0][:100] if tokens else "empty")
logger.opt(lazy=True).debug("Label distribution: {}", lambda: np.bincount(y).tolist())

# Bad - always executes expensive operation regardless of log level
logger.debug("Token sample: {}", tokens[0][:100])
```

### 8. Direct `logger.exception()` for Database Errors

Use `logger.exception()` directly with bound context instead of helper functions:

```python
# Good - direct, clear, and structured
except sqlite3.Error:
    logger.exception("Failed to save model '{}'", model_name)

# Bad - unnecessary wrapper function
except sqlite3.Error as error:
    _log_db_error("save_model", error, {"model_name": model_name})
```

### Sensitive Data Redaction

Sensitive data is automatically redacted from log messages:

- Passwords
- Tokens
- API keys
- Secrets

### Per-Module Log Levels

Module-level log level overrides can be configured:

```python
from app.utils.logging_config import create_module_level_filter

module_levels = {
    "uvicorn": "WARNING",
    "fastapi": "INFO",
}
filter_func = create_module_level_filter(module_levels)
```

## Request Tracing

```python
# X-Request-ID header is automatically added to requests
# Filter logs by request ID
logger.bind(request_id=request_id).info("Processing request")
```

## Loguru Configuration

### Using `logger.configure()`

Glyph uses Loguru's `logger.configure()` method for declarative logging setup. This replaces the traditional `logger.remove()` + `logger.add()` pattern with a single configuration call:

```python
from loguru import logger

logger.configure(
    handlers=[
        {
            "sink": "logs/app.log",
            "level": "INFO",
            "format": "{time} | {level} | {message}",
            "rotation": "50 MB",
            "retention": "10 days",
        },
        {
            "sink": sys.stdout,
            "level": "DEBUG",
            "format": "<green>{time}</> | <level>{level}</> | {message}",
            "colorize": True,
        }
    ],
    patcher=my_patcher_function,  # Global patcher for all handlers
)
```

### Environment Variables

Loguru supports several environment variables that can override configuration:

| Variable | Description | Example |
|----------|-------------|---------|
| `LOGURU_LEVEL` | Override default log level | `LOGURU_LEVEL=DEBUG` |
| `LOGURU_FORMAT` | Override default format | `LOGURU_FORMAT="{time} {message}"` |
| `LOGURU_DIAGNOSE` | Enable/disable variable diagnosis in exceptions | `LOGURU_DIAGNOSE=YES` |
| `LOGURU_COLORIZE` | Enable/disable colorization | `LOGURU_COLORIZE=NO` |
| `LOGURU_ENQUEUE` | Enable/disable enqueued file logging (thread-safe) | `LOGURU_ENQUEUE=NO` |

### Combined Patcher

The logging configuration uses a combined patcher that handles:
1. **Sensitive data redaction** - Automatically redacts passwords, tokens, API keys
2. **Request context injection** - Adds request ID, user ID, username to logs from ContextVars

Note: JSON serialization is handled by `serialize=True` on the file handler, not the patcher.

### Handler Filters

Filters are applied at the handler level:
- **ModuleLevelFilter** - Per-module log level overrides

## Security Considerations

1. **Never log secrets** - Passwords, tokens, API keys are automatically redacted
2. **Use `diagnose=False`** - Disables variable diagnosis in production (security best practice)
3. **File permissions** - Log files are created with `0o640` permissions (owner read/write, group read)
4. **Backtrace enabled** - Full traceback for debugging
5. **Exception info** - Loguru automatically captures exceptions

## Summary of Key Changes from Standard Logging

| Standard Logging | Loguru |
|-----------------|--------|
| `logging.getLogger(__name__)` | `from loguru import logger` |
| `logger.info("msg: %s", val)` | `logger.info("msg: {}", val)` |
| `extra={"extra_data": {...}}` | `logger.bind(**data).info(...)` |
| `exc_info=True` | Automatic (or `logger.exception()`) |
| `logging.INFO` | `"INFO"` (string) |
| Custom `Filter` class | Callable class with `__call__(self, record)` |
| `handler.setFormatter()` | `format=` parameter in `add()` or `configure()` |
| `TimedRotatingFileHandler` | `rotation="50 MB"` parameter |
| `logging.handlers.MemoryHandler` | `enqueue=True` parameter |
| `logging.basicConfig()` | `logger.configure()` method |
| `logging.config.dictConfig()` | `logger.configure(handlers=[...])` |
| `logger.addFilter()` | `filter=` parameter in handler config |
| `LoggerAdapter` | `logger.bind()` or `logger.patch()` |
| `logger.isEnabledFor()` | `logger.opt(lazy=True)` |
