# Logging Best Practices for Glyph

This document outlines the logging architecture and best practices for the Glyph application.

## Overview

Glyph uses a centralized logging configuration that provides:
- Structured JSON logging with optimized field names for reduced payload size
- Request tracing with unique request IDs via ContextVars
- Background task context propagation for correlating async logs
- Log rotation with size and time-based policies
- Performance monitoring utilities with threshold support
- Security event logging with brute-force detection
- Sensitive data redaction (tokens, passwords, connection strings, secrets)
- Rate limiting with memory bounds to prevent log spam
- Async logging for non-blocking I/O
- Log sampling for high-volume scenarios
- Per-module log level configuration
- Startup/shutdown health summary logging
- Logging best practice validation (development mode)

## Architecture

### Components

| Component | File | Purpose |
|-----------|------|---------|
| Central Config | [`app/utils/logging_config.py`](app/utils/logging_config.py) | Setup, formatters, filters, async handler |
| Request Context | [`app/utils/request_context.py`](app/utils/request_context.py) | ContextVar-based request/task tracing |
| Request Tracing | [`app/core/request_tracing.py`](app/core/request_tracing.py) | ASGI middleware for request IDs |
| Performance Logger | [`app/utils/performance_logger.py`](app/utils/performance_logger.py) | Timing decorators and context managers |
| Security Logger | [`app/auth/security_logger.py`](app/auth/security_logger.py) | Auth event logging, brute-force detection |

### Filters

| Filter | Class | Purpose |
|--------|-------|---------|
| Sensitive Data | [`SensitiveDataFilter`](app/utils/logging_config.py:37) | Redacts tokens, passwords, connection strings, secrets |
| Rate Limiting | [`RateLimitingFilter`](app/utils/logging_config.py:141) | Limits messages per period with memory bounds |
| Sampling | [`SamplingFilter`](app/utils/logging_config.py:640) | Samples a percentage of messages |
| Best Practices | [`LoggingBestPracticeFilter`](app/utils/logging_config.py:676) | Validates logging patterns (dev only) |

### Formatters

| Formatter | Class | Purpose |
|-----------|-------|---------|
| JSON | [`JSONFormatter`](app/utils/logging_config.py:267) | Optimized structured JSON with short field names |
| Colored | [`ColoredFormatter`](app/utils/logging_config.py:343) | ANSI-colored console output |

### Handlers

| Handler | Class | Purpose |
|---------|-------|---------|
| File | `RotatingFileHandler` / `TimedRotatingFileHandler` | Rotating file output with compression |
| Console | `StreamHandler` | stdout console output |
| Async | [`AsyncLogHandler`](app/utils/logging_config.py:478) | Non-blocking queue-based wrapper |

## Configuration

Logging is configured in `config.yml`:

```yaml
logging:
  level: INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
  format: json  # json or text
  file:
    path: logs/glyph.log
    max_size_mb: 50
    backup_count: 10
    rotate: size  # time or size
    time_interval: midnight  # midnight, daily, weekly, monthly
  console:
    enabled: true
    level: INFO
    colorize: true
  request_tracing:
    enabled: true
    header_name: X-Request-ID
  # Per-module log level overrides
  module_levels:
    app.database: WARNING
    app.auth: INFO
    app.processing: DEBUG
    uvicorn: INFO
  # Rate limiting to prevent log spam
  rate_limit:
    enabled: false
    max_messages: 10
    period: 60.0
    max_keys: 1000
  # Async logging for non-blocking I/O
  async_logging:
    enabled: false
    max_queue_size: 1000
  # Log sampling for high-volume scenarios
  sampling:
    enabled: false
    rate: 0.1  # Log 10% of messages when enabled
```

### Configuration Reference

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `level` | string | `"INFO"` | Root log level |
| `format` | string | `"json"` | Output format (`json` or `text`) |
| `file.path` | string | `"logs/glyph.log"` | Log file path |
| `file.max_size_mb` | int | `50` | Max file size before rotation |
| `file.backup_count` | int | `10` | Number of rotated files to keep |
| `file.rotate` | string | `"size"` | Rotation policy (`size` or `time`) |
| `file.time_interval` | string | `"midnight"` | Time rotation interval |
| `console.enabled` | bool | `true` | Enable console output |
| `console.level` | string | `"INFO"` | Console log level |
| `console.colorize` | bool | `true` | Enable ANSI colors |
| `module_levels` | dict | `{}` | Per-module level overrides |
| `rate_limit.enabled` | bool | `false` | Enable rate limiting |
| `rate_limit.max_messages` | int | `10` | Max messages per period |
| `rate_limit.period` | float | `60.0` | Rate limit window in seconds |
| `rate_limit.max_keys` | int | `1000` | Max unique message patterns tracked |
| `async_logging.enabled` | bool | `false` | Enable async logging |
| `async_logging.max_queue_size` | int | `1000` | Max queued records |
| `sampling.enabled` | bool | `false` | Enable log sampling |
| `sampling.rate` | float | `0.1` | Fraction of messages to log (0.0-1.0) |

## Usage

### Basic Logging

```python
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

logger.info("Processing binary: %s", filename)
logger.exception("Failed to process: %s", error)  # Auto-includes exc_info
```

### Structured Context with `extra_data`

```python
logger.info(
    "Processing binary",
    extra={"extra_data": {
        "file_size": size,
        "filename": filename,
        "operation": "upload",
    }}
)
```

### Request Context

Request context is automatically set by the `RequestIDMiddleware` and propagated to background tasks:

```python
from app.utils.request_context import get_request_context, set_request_context

# In request handlers (auto-set by middleware)
ctx = get_request_context()
# ctx.request_id, ctx.user_id, ctx.username available

# In background tasks (manually propagate)
set_request_context(
    request_id=original_ctx.request_id,
    task_id=job_uuid,
    user_id=original_ctx.user_id,
)
```

### Performance Timing

```python
from app.utils.performance_logger import PerformanceTimer, log_performance, PerformanceMetrics

# Context manager
with PerformanceTimer("binary_analysis") as timer:
    result = analyze_binary(file_path)
# timer.elapsed available in seconds

# Context manager with threshold (only logs if > 100ms)
with PerformanceTimer("fast_operation", unit="milliseconds", threshold=100):
    result = fast_operation()

# Decorator
@log_performance
async def process_binary(request: BinaryUploadRequest):
    ...

# Decorator with threshold
@log_performance(unit="milliseconds", threshold=500)
def expensive_operation():
    ...

# Pipeline step decorator
@log_step_performance("data_validation")
def validate_data(data):
    ...

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
    log_login_attempt,
    log_login_success,
    log_login_failure,
    log_logout,
    log_token_refresh,
    log_permission_denied,
    log_suspicious_activity,
    log_user_registration,
    log_password_change,
    log_api_key_usage,
    log_api_key_created,
    log_api_key_deleted,
    log_csrf_failure,
)

# Authentication events
log_login_attempt(username=username, ip_address=ip, user_agent=ua)
log_login_success(user_id=user.id, username=user.username, ip_address=ip)
log_login_failure(username=username, reason="Invalid password", ip_address=ip)
log_logout(user_id=user.id, username=user.username, ip_address=ip)
log_token_refresh(user_id=user.id, token_type="access", ip_address=ip)

# Authorization events
log_permission_denied(
    user_id=user.id,
    username=user.username,
    resource="/api/admin",
    required_permission="admin",
    ip_address=ip
)

# Account management
log_user_registration(user_id=user.id, username=username, ip_address=ip)
log_password_change(user_id=user.id, username=user.username, ip_address=ip)

# API key lifecycle
log_api_key_usage(user_id=user.id, api_key_prefix="glp_abc1", endpoint="/api/data", ip_address=ip)
log_api_key_created(user_id=user.id, key_id=1, key_prefix="glp_abc1", name="My Key", ip_address=ip)
log_api_key_deleted(user_id=user.id, key_id=1, name="My Key", ip_address=ip)

# Security events
log_suspicious_activity(
    user_id=user.id,
    activity_type="unusual_access_pattern",
    details={"endpoint": "/api/admin", "count": 50},
    ip_address=ip
)
log_csrf_failure(ip_address=ip, path="/api/data", method="POST")
```

### Security Event Reference

| Function | Event Type | Log Level | Description |
|----------|-----------|-----------|-------------|
| [`log_login_attempt()`](app/auth/security_logger.py:101) | `login_attempt` | INFO | Login initiated |
| [`log_login_success()`](app/auth/security_logger.py:130) | `login_success` | INFO | Successful login |
| [`log_login_failure()`](app/auth/security_logger.py:163) | `login_failure` | WARNING | Failed login (triggers brute-force detection) |
| [`log_logout()`](app/auth/security_logger.py:232) | `logout` | INFO | User logout |
| [`log_token_refresh()`](app/auth/security_logger.py:259) | `token_refresh` | INFO | Token refreshed |
| [`log_permission_denied()`](app/auth/security_logger.py:288) | `permission_denied` | WARNING | Authorization failure |
| [`log_suspicious_activity()`](app/auth/security_logger.py:320) | `suspicious_activity` | WARNING | Suspicious pattern detected |
| [`log_user_registration()`](app/auth/security_logger.py:451) | `user_registration` | INFO | New user registered |
| [`log_password_change()`](app/auth/security_logger.py:376) | `password_change` | INFO | Password changed |
| [`log_api_key_usage()`](app/auth/security_logger.py:259) | `api_key_usage` | INFO | API key used for authentication |
| [`log_api_key_created()`](app/auth/security_logger.py:477) | `api_key_created` | INFO | New API key created |
| [`log_api_key_deleted()`](app/auth/security_logger.py:503) | `api_key_deleted` | INFO | API key deleted |
| [`log_csrf_failure()`](app/auth/security_logger.py:529) | `csrf_failure` | WARNING | CSRF validation failed |
| [`log_account_lockout()`](app/auth/security_logger.py:375) | `account_lockout` | WARNING | Account locked |
| [`log_account_unlock()`](app/auth/security_logger.py:403) | `account_unlock` | INFO | Account unlocked |

### Brute-Force Detection

The [`LoginFailureTracker`](app/auth/security_logger.py:19) monitors login failures per username and IP address:

- **Recording and checking are separated** to avoid double-counting
- Default threshold: 5 failures in 300 seconds triggers alert
- Resets on successful login
- Automatically logs `suspicious_activity` when threshold is exceeded

```python
from app.auth.security_logger import get_failure_tracker

# Default: 5 failures in 300 seconds triggers alert
tracker = get_failure_tracker()

# Custom threshold
tracker = LoginFailureTracker(threshold=3, window=60.0)
```

## Log Format

### JSON Format (Default)

The JSON formatter uses optimized, shorter field names for reduced payload size. Context fields are only included when non-null (lazy evaluation):

```json
{
  "t": "2024-01-15T10:30:45.123456+00:00",
  "l": "INFO",
  "logger": "app.api.v1.endpoints.binaries",
  "msg": "Binary upload started",
  "rid": "abc123-def456",
  "uid": 123,
  "user": "john_doe",
  "tid": "task-uuid-123",
  "extra": {
    "file_size": 1024000,
    "filename": "sample.bin"
  }
}
```

**Field Reference:**

| Field | Description | Included When |
|-------|-------------|---------------|
| `t` | ISO 8601 timestamp (UTC) | Always |
| `l` | Log level | Always |
| `logger` | Logger name (module path) | Always |
| `msg` | Log message | Always |
| `rid` | Request ID | Non-null (from `X-Request-ID` header) |
| `uid` | User ID | Non-null (authenticated requests) |
| `user` | Username | Non-null (authenticated requests) |
| `tid` | Task ID | Non-null (background tasks) |
| `exc` | Exception traceback | Non-null (when exception present) |
| `stack` | Stack info | Non-null (when stack info present) |
| `extra` | Structured context data | Non-null (when `extra_data` provided) |
| `_filename` | Source filename | DEBUG level only |
| `_funcName` | Source function name | DEBUG level only |
| `_lineno` | Source line number | DEBUG level only |
| `_pathname` | Source file path | DEBUG level only |
| `_threadName` | Thread name | DEBUG level only |

### Text Format

```
2024-01-15 10:30:45,123 | INFO     | app.api.v1.endpoints.binaries | Binary upload started
```

## Log Levels

| Level | When to Use | Examples |
|-------|-------------|----------|
| DEBUG | Detailed debugging info | Variable values, function entry/exit |
| INFO | Normal operational events | Request received, task completed |
| WARNING | Unexpected but handled events | Retries, fallbacks, deprecated features |
| ERROR | Operations that failed | Database errors, API failures |
| CRITICAL | System-threatening errors | Service unavailable, data corruption |

## Best Practices

### 1. Use Parameterized Logging

```python
# Good - lazy evaluation
logger.info("User logged in: %s", username)

# Bad - string concatenation (always evaluated)
logger.info("User logged in: " + username)

# Bad - f-string (always evaluated even if log level is disabled)
logger.info(f"User logged in: {username}")
```

### 2. Never Log Sensitive Data

```python
# Good - only log first 4 chars of API key
logger.info("API key used: %s...", api_key[:4])

# Bad - never log full secrets
logger.info("Token: %s", token)  # NEVER DO THIS
```

### 3. Include Context with `extra_data`

```python
# Good - structured context for aggregation
logger.info(
    "Processing binary",
    extra={"extra_data": {"file_size": size, "filename": filename}}
)

# Bad - no context for filtering
logger.info("Processing binary")
```

### 4. Use `logger.exception()` for Unexpected Errors

```python
# Good - automatic stack trace
try:
    process_data()
except Exception as e:
    logger.exception("Failed to process data")

# Also acceptable - explicit exc_info
try:
    process_data()
except Exception as e:
    logger.error("Failed to process data: %s", e, exc_info=True)

# Bad - no stack trace for debugging
logger.error("Failed to process data: %s", e)
```

### 5. Conditional Logging for Expensive Operations

```python
import logging

# Good - only evaluates when DEBUG is enabled
if logger.isEnabledFor(logging.DEBUG):
    debug_data = expensive_debug_operation()
    logger.debug("Debug data: %s", debug_data)

# Bad - always executes expensive operation
logger.debug("Debug data: %s", expensive_debug_operation())
```

### 6. Database Error Logging

Use the `_log_db_error()` helper for consistent, structured database error logging:

```python
from app.database.sql_service import _log_db_error

# Produces structured logs with operation context
except sqlite3.Error as error:
    _log_db_error(logger, "save_model", error, {"model_name": model_name})
```

## Security Features

### Sensitive Data Redaction

The [`SensitiveDataFilter`](app/utils/logging_config.py:35) automatically redacts sensitive patterns from log messages:

| Pattern | Example | Redacted To |
|---------|---------|-------------|
| Bearer tokens | `Bearer eyJhbG...` | `Bearer [REDACTED]` |
| Database connection strings | `postgresql://user:pass@host/db` | `[CONNECTION_STRING_REDACTED]` |
| Password assignments | `password=secret123` | `password=[REDACTED]` |
| Token/secret assignments | `token=abc123` | `token=[REDACTED]` |
| API keys | `api_key=key123` | `api_key=[REDACTED]` |
| JWT/OAuth secrets | `jwt_secret=mysecret` | `jwt_secret=[REDACTED]` |
| Emails in sensitive context | `password_user@domain.com` | `[REDACTED]` |

This filter is applied to all log handlers by default.

#### Custom Patterns

```python
from app.utils.logging_config import SensitiveDataFilter

custom_filter = SensitiveDataFilter(
    additional_patterns=[
        (r'SECRET_KEY=\S+', 'SECRET_KEY=[REDACTED]'),
        (r'STRIPE_KEY=\S+', 'STRIPE_KEY=[REDACTED]'),
    ]
)
```

### Rate Limiting with Memory Bounds

The [`RateLimitingFilter`](app/utils/logging_config.py:107) prevents log spam by limiting messages per time window:

- Configurable message count per period
- Token bucket algorithm per unique message key
- Memory-bounded with `max_keys` limit (default: 1000)
- Periodic cleanup every 5 minutes
- LRU eviction when key limit exceeded
- Summary logging every 100 suppressed messages

```python
from app.utils.logging_config import setup_logging

setup_logging(
    rate_limit=True,
    rate_limit_max=10,
    rate_limit_period=60.0,
    rate_limit_max_keys=1000,
)
```

### Brute-Force Detection

The security logger includes a [`LoginFailureTracker`](app/auth/security_logger.py:19) that:
- Tracks login failures per username and IP
- Triggers `suspicious_activity` alerts after threshold exceeded
- Resets on successful login

```python
from app.auth.security_logger import get_failure_tracker

# Default: 5 failures in 300 seconds triggers alert
tracker = get_failure_tracker()
```

## Request Tracing

Every request gets a unique ID that is:
- Extracted from the `X-Request-ID` header if present
- Generated as a UUID4 if not present
- Added to all log entries for that request (as `rid` field)
- Returned in the `X-Request-ID` response header
- Propagated to background tasks (as `tid` field for task-specific ID)

This allows you to trace a single request across multiple components:

```bash
# Filter logs by request ID
grep "abc123-def456" logs/glyph.log
```

## Background Task Context Propagation

Background tasks (EventWatcher, TaskService) propagate request context, allowing you to correlate background task logs with the originating HTTP request:

```python
from app.utils.request_context import get_request_context

# In background task callbacks, context is automatically propagated
ctx = get_request_context()
# ctx.request_id - original request ID
# ctx.task_id - background task UUID
# ctx.user_id - originating user ID
# ctx.username - originating username
```

The JSON formatter includes the `tid` (task ID) field when a task context is active, enabling correlation of background work with the original request via `rid`.

## Log Rotation

Logs are rotated based on configuration:

- **Size-based**: Rotates when file exceeds `max_size_mb`
- **Time-based**: Rotates at specified intervals (`midnight`, `daily`, `weekly`, `monthly`)
- **Backup count**: Keeps `backup_count` rotated files
- **Compression**: Old files are compressed with gzip (Python 3.9+)
- **File permissions**: Set to 0640 (owner read/write, group read)

## Security Considerations

1. **Never log sensitive data**:
   - Passwords
   - API keys (except first 4 chars for identification)
   - JWT tokens
   - Database connection strings
   - Personal identifiable information (PII)

2. **Log file permissions**:
   - Set to 0640 (owner read/write, group read)
   - Restrict access to application user

3. **Audit trail**:
   - All authentication events are logged
   - All authorization failures are logged
   - All data modification operations should be logged

## Advanced Features

### Per-Module Log Levels

Override log levels for specific modules without changing the global level:

```yaml
logging:
  module_levels:
    app.database: WARNING      # Reduce database noise
    app.auth: INFO             # Keep auth detailed
    app.processing: DEBUG      # Detailed processing logs
    uvicorn: INFO              # Server logs
    sqlalchemy: WARNING        # Reduce ORM noise
```

Module levels are applied during `setup_logging()` and take precedence over the root level for matching logger names.

### Async Logging

Enable non-blocking async logging to avoid I/O blocking in request paths:

```yaml
logging:
  async_logging:
    enabled: true
    max_queue_size: 1000
```

The [`AsyncLogHandler`](app/utils/logging_config.py:424) queues log records and processes them asynchronously, yielding to the event loop between records. Key behaviors:

- Falls back to synchronous processing when no event loop is running (startup/shutdown)
- Automatically flushes queue on `close()`
- Bounded queue prevents memory exhaustion (drops oldest records when full)

### Log Sampling

Reduce log volume in high-traffic scenarios by sampling a percentage of messages:

```yaml
logging:
  sampling:
    enabled: true
    rate: 0.1  # Log 10% of messages
```

The [`SamplingFilter`](app/utils/logging_config.py:496) uses a counter-based approach:
- `rate=1.0` logs all messages
- `rate=0.1` logs approximately 10% of messages
- `rate=0.0` logs nothing

### Logging Best Practice Filter

A development-only filter validates logging best practices at runtime:

```python
from app.utils.logging_config import setup_logging

# Enable in development
setup_logging(best_practice_filter=True)
```

The [`LoggingBestPracticeFilter`](app/utils/logging_config.py:532) warns about:
- Unformatted braces in log messages (potential f-string misuse)
- Error-level logs without `exc_info=True`

Warnings are deduplicated and written to stderr. This filter is disabled by default in production.

### Startup Health Summary

On application startup, a structured log entry is emitted with logging configuration details:

```json
{
  "t": "2024-01-15T10:30:00.000000+00:00",
  "l": "INFO",
  "logger": "glyph.startup",
  "msg": "Logging initialized",
  "extra": {
    "event": "startup",
    "log_level": "INFO",
    "handlers": ["RotatingFileHandler", "StreamHandler"],
    "handler_count": 2
  }
}
```

Call [`log_startup_summary()`](app/utils/logging_config.py:586) after `setup_logging()` to emit this entry.

## Monitoring & Operations

### Log Analysis Commands

Use the optimized JSON field names for log analysis:

```bash
# Filter by level
jq 'select(.l == "ERROR")' logs/glyph.log

# Filter by request ID
jq 'select(.rid == "abc123")' logs/glyph.log

# Filter by task ID (background tasks)
jq 'select(.tid == "task-uuid")' logs/glyph.log

# Get unique users
jq -r '.user // empty' logs/glyph.log | sort -u

# Filter by event type
jq 'select(.extra.event == "startup")' logs/glyph.log

# Get all database operations
jq 'select(.extra.operation != null)' logs/glyph.log

# Get performance metrics
jq 'select(.extra.performance != null)' logs/glyph.log

# Count errors by logger
jq -s '[.[] | select(.l == "ERROR")] | group_by(.logger) | map({logger: .[0].logger, count: length})' logs/glyph.log

# Get login failures
jq 'select(.extra.event == "login_failure")' logs/glyph.log

# Get suspicious activity alerts
jq 'select(.extra.event == "suspicious_activity")' logs/glyph.log
```

### Integration with Log Aggregation

The JSON format is compatible with:

| Platform | Notes |
|----------|-------|
| ELK Stack | Map `t` to `@timestamp`, `l` to `level` |
| Loki/Grafana | Use `l` as level label, `rid` for request tracing |
| CloudWatch | Structured JSON parsed automatically |
| Datadog | Auto-detects JSON, maps fields to attributes |

### Field Mapping for Log Aggregators

When configuring log aggregators, use these field mappings:

| Standard Field | Glyph Field |
|----------------|-------------|
| timestamp | `t` |
| level | `l` |
| logger | `logger` |
| message | `msg` |
| request_id | `rid` |
| user_id | `uid` |
| username | `user` |
| task_id | `tid` |
| exception | `exc` |
| context | `extra` |

## Troubleshooting

### Logs Not Appearing

1. Check `level` in `config.yml` matches expected verbosity
2. Check `module_levels` overrides for the specific module
3. Verify log directory exists and is writable
4. Check for duplicate `setup_logging()` calls (handlers are cleared on each call)
5. Verify `sampling.enabled` is not filtering out messages

### Request ID Not in Logs

1. Verify `RequestIDMiddleware` is added to the app (should be first middleware)
2. Check that `include_context=True` in JSONFormatter (default)
3. Verify the `X-Request-ID` header is being sent or generated

### Background Task Logs Missing Context

1. Verify `set_request_context()` is called before background work
2. Check that `task_id` is set for background task identification
3. Look for `tid` field in JSON output for task correlation

### Performance Issues

1. Use `text` format instead of `json` for console output in development
2. Increase `level` to `WARNING` or `ERROR` in production to reduce volume
3. Use `sampling` to reduce log volume for high-traffic endpoints
4. Enable `async_logging` to avoid I/O blocking in request paths
5. Use `threshold` in performance logging to reduce noise
6. Enable `rate_limit` to prevent log spam from repeated errors

### Sensitive Data Appearing in Logs

1. Verify `SensitiveDataFilter` is applied (automatic by default)
2. Add custom patterns via `SensitiveDataFilter(additional_patterns=[...])`
3. Review log messages for accidental secret exposure
4. Check that connection strings are not logged during database initialization

### Rate Limiter Memory Growth

1. Monitor `max_keys` setting (default: 1000)
2. Check that periodic cleanup is running (every 5 minutes)
3. Increase `period` to reduce key count if needed

## API Reference

### `setup_logging()`

```python
def setup_logging(
    level: str = "INFO",
    format: str = "json",
    log_file: str | None = "logs/glyph.log",
    max_size_mb: int = 50,
    backup_count: int = 10,
    rotate: str = "size",
    time_interval: str = "midnight",
    console_enabled: bool = True,
    console_level: str = "INFO",
    colorize: bool = True,
    rate_limit: bool = False,
    rate_limit_max: int = 10,
    rate_limit_period: float = 60.0,
    rate_limit_max_keys: int = 1000,
    module_levels: dict[str, str] | None = None,
    async_logging: bool = False,
    async_max_queue: int = 1000,
    sampling_enabled: bool = False,
    sampling_rate: float = 1.0,
    best_practice_filter: bool = False,
) -> None:
```

### `get_logger(name: str) -> logging.Logger`

Returns a named logger instance. Use `__name__` as the argument for module-level loggers.

### `log_startup_summary() -> None`

Emits a structured startup log entry with current logging configuration details.

### `setup_logging_from_config() -> None`

Loads logging configuration from `config.yml` and applies it via `setup_logging()`.
