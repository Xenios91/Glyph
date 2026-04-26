# Logging Best Practices for Glyph

## Overview

Glyph uses [loguru](https://loguru.readthedocs.io/) for structured, modern Python logging. Loguru provides:

- Simple configuration with powerful defaults
- Built-in JSON formatting support
- Automatic exception handling
- Contextual data binding via `logger.bind()`
- File rotation, retention, and compression
- Sensitive data redaction
- Rate limiting and sampling filters

### Components

- **JSON Format**: Default format for structured log parsing
- **Text Format**: Human-readable format with optional colors
- **Sensitive Data Redaction**: Automatic redaction of passwords, tokens, API keys
- **Rate Limiting**: Prevents log spam from repeated messages
- **Log Sampling**: Reduces volume in high-traffic scenarios
- **Request Context**: Automatic request ID, user ID, and username propagation

### Filters

- **SensitiveDataFilter**: Redacts sensitive patterns from log messages (applied via `logger.patch()`)
- **RateLimitingFilter**: Limits messages per time window per unique key
- **SamplingFilter**: Samples log messages at a configurable rate
- **LoggingBestPracticeFilter**: Development-only validation filter

### Formatters

- **JSON Formatter**: Uses `patch()` to serialize data to `record["extra"]["_json"]` and returns template `"{extra[_json]}\n{exception}"`
- **Console Formatter**: Colored or plain text format for stdout

### Handlers

- **File Handler**: With rotation, retention, compression, and secure file permissions (0o640)
- **Console Handler**: stdout with optional colorization

## Configuration

Logging is configured via `config.yml`:

```yaml
logging:
  level: "INFO"
  format: "json"  # or "text"
  log_file: "logs/app.log"
  rotation: "50 MB"
  backup_count: 10
  console_enabled: true
  console_level: "DEBUG"
  colorize: true
  async_logging: false
  sampling_rate: 1.0
  request_tracing:
    enabled: true
  rate_limit:
    max_messages: 10
    period: 60
```

### Configuration Reference

| Setting | Default | Description |
|---------|---------|-------------|
| `level` | `"INFO"` | Log level for file handler |
| `format` | `"json"` | Log format (`"json"` or `"text"`) |
| `log_file` | `"logs/app.log"` | Path to log file |
| `rotation` | `"50 MB"` | Rotation trigger (size or time) |
| `backup_count` | `10` | Retention period in days |
| `console_enabled` | `true` | Enable console output |
| `console_level` | `"DEBUG"` | Log level for console |
| `colorize` | `true` | Enable colored output |
| `async_logging` | `false` | Use async logging via `enqueue=True` |
| `sampling_rate` | `1.0` | Sample rate (0.0 to 1.0) |

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

### Performance Timing

```python
from app.utils.performance_logger import PerformanceTimer, log_performance, PerformanceMetrics

# Context manager with threshold (only logs if > 100ms)
with PerformanceTimer("operation", threshold=100, unit="milliseconds"):
    expensive_operation()

# Decorator
@log_performance(log_level="DEBUG", unit="milliseconds", threshold=100)
def fast_operation():
    pass

# Pipeline step decorator
@log_step_performance("data_validation")
def validate_data(data):
    pass

# Aggregated metrics
metrics = PerformanceMetrics("pipeline")
with metrics.timer("step1"):
    step1()
with metrics.timer("step2"):
    step2()
metrics.log_summary()
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
log_account_lockout(user_id=1, username="admin", reason="too_many_failures")

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
| `account_lockout` | WARNING | Account locked |
| `account_unlock` | INFO | Account unlocked |
| `user_registration` | INFO | New user registered |
| `api_key_created` | INFO | API key created |
| `api_key_deleted` | INFO | API key deleted |
| `csrf_failure` | WARNING | CSRF validation failed |

### Brute-Force Detection

```python
from app.auth.security_logger import LoginFailureTracker, get_failure_tracker

# Default: 5 failures in 300 seconds triggers alert
tracker = get_failure_tracker()
count = tracker.get_failure_count("username")
is_suspicious = tracker.is_suspicious("username")

# Custom threshold
tracker = LoginFailureTracker(threshold=3, window=60)
```

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

### 3. Use Structured Logging

```python
# Good - structured context
logger.bind(user_id=user_id, action="update", resource="profile").info(
    "Resource updated"
)

# Bad - no context for filtering
logger.info("Resource updated")
```

### 4. Use `logger.exception()` for Errors

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

### 5. Conditional Logging for Expensive Operations

```python
# Good - only evaluates when DEBUG is enabled
if logger.opt(depth=1).enabled("DEBUG"):
    logger.debug("Expensive data: {}", expensive_function())

# Bad - always executes expensive operation
logger.debug("Expensive data: {}", expensive_function())
```

### Database Error Logging

```python
logger.error("Database error during {}: {}", operation, error)
# Produces structured logs with operation context
```

### Sensitive Data Redaction

Sensitive data is automatically redacted from log messages:

- Passwords
- Tokens
- API keys
- Secrets

#### Custom Patterns

```python
from app.utils.logging_config import SensitiveDataFilter

additional_patterns = [
    (r"ssn=\d{3}-\d{2}-\d{4}", "ssn=REDACTED"),
]
filter_instance = SensitiveDataFilter(additional_patterns=additional_patterns)
```

### Rate Limiting with Memory Bounds

```python
from app.utils.logging_config import RateLimitingFilter

# Limit to 10 messages per 60 seconds per unique key
rate_limiter = RateLimitingFilter(max_messages=10, period=60, max_keys=1000)
```

### Brute-Force Detection

```python
# Default: 5 failures in 300 seconds triggers alert
from app.auth.security_logger import get_failure_tracker
tracker = get_failure_tracker()
```

### Async Logging

```yaml
logging:
  async_logging: true  # Uses loguru's enqueue=True
```

### Log Sampling

```yaml
logging:
  sampling_rate: 0.5  # Sample 50% of messages
```

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
| `LOGURU_DIAGNOSE` | Enable/disable variable diagnosis | `LOGURU_DIAGNOSE=YES` |
| `LOGURU_COLORIZE` | Enable/disable colorization | `LOGURU_COLORIZE=NO` |
| `GLYPH_LOG_BEST_PRACTICE` | Enable logging validation | `GLYPH_LOG_BEST_PRACTICE=true` |

### Combined Patcher

The logging configuration uses a combined patcher that handles:
1. **Sensitive data redaction** - Automatically redacts passwords, tokens, API keys
2. **JSON serialization** - Creates structured JSON for file handlers
3. **Request context injection** - Adds request ID, user ID, username to logs

### Handler Filters

Filters are applied at the handler level:
- **RateLimitingFilter** - Prevents log spam with token bucket algorithm
- **SamplingFilter** - Samples messages for high-volume scenarios
- **ModuleLevelFilter** - Per-module log level overrides
- **LoggingBestPracticeFilter** - Development-only validation

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
