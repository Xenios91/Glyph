# Logging Best Practices for Glyph

This document outlines the logging architecture and best practices for the Glyph application.

## Overview

Glyph uses a centralized logging configuration that provides:
- Structured JSON logging for easy parsing and analysis
- Request tracing with unique request IDs
- Log rotation with size and time-based policies
- Performance monitoring utilities
- Security event logging

## Architecture

### Components

1. **`app/utils/logging_config.py`** - Centralized logging setup
2. **`app/utils/request_context.py`** - Request context management
3. **`app/core/request_tracing.py`** - Request ID middleware
4. **`app/utils/performance_logger.py`** - Performance timing utilities
5. **`app/auth/security_logger.py`** - Security event logging

### Configuration

Logging is configured in `config.yml`:

```yaml
logging:
  level: INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
  format: json  # json or text
  file:
    path: logs/glyph.log
    max_size_mb: 50
    backup_count: 10
    rotate: size  # time, size, or both
    time_interval: midnight  # midnight, daily, weekly, monthly
  console:
    enabled: true
    level: INFO
    colorize: true
  request_tracing:
    enabled: true
    header_name: X-Request-ID
```

## Usage

### Basic Logging

```python
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

logger.info("Processing binary: %s", filename)
logger.error("Failed to process: %s", error, exc_info=True)
```

### Request Context

Request context is automatically set by the `RequestIDMiddleware`:

```python
from app.utils.request_context import get_request_context

def handle_request(request):
    ctx = get_request_context()
    logger.info("Processing request", extra={
        "request_id": ctx.request_id,
        "user_id": request.user.id
    })
```

### Performance Timing

```python
from app.utils.performance_logger import PerformanceTimer, log_performance

# Context manager
with PerformanceTimer("binary_analysis") as timer:
    result = analyze_binary(file_path)
print(f"Elapsed: {timer.elapsed:.3f}s")

# Decorator
@log_performance
async def process_binary(request: BinaryUploadRequest):
    ...

# Pipeline step decorator
@log_step_performance("data_validation")
def validate_data(data):
    ...
```

### Security Logging

```python
from app.auth.security_logger import (
    log_login_success,
    log_login_failure,
    log_permission_denied,
)

# Login events
log_login_success(user_id=user.id, username=user.username, ip_address=ip)
log_login_failure(username=username, reason="Invalid password", ip_address=ip)

# Permission events
log_permission_denied(
    user_id=user.id,
    resource="/api/admin",
    required_permission="admin"
)
```

## Log Format

### JSON Format (Default)

```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "INFO",
  "logger": "app.api.v1.endpoints.binaries",
  "message": "Binary upload started",
  "request_id": "abc123-def456",
  "user_id": 123,
  "username": "john_doe",
  "extra": {
    "file_size": 1024000,
    "filename": "sample.bin"
  }
}
```

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
# Good
logger.info("User logged in: %s", username)

# Bad - string concatenation
logger.info("User logged in: " + username)

# Bad - f-string (evaluated even if log level is too high)
logger.info(f"User logged in: {username}")
```

### 2. Never Log Sensitive Data

```python
# Good - only log first 4 chars of API key
logger.info("API key used: %s...", api_key[:4])

# Bad - never log full secrets
logger.info("Token: %s", token)  # NEVER DO THIS
```

### 3. Include Context

```python
# Good
logger.info(
    "Processing binary",
    extra={"extra_data": {"file_size": size, "filename": filename}}
)

# Bad - no context
logger.info("Processing binary")
```

### 4. Use exc_info for Exceptions

```python
# Good
try:
    process_data()
except Exception as e:
    logger.error("Failed to process data: %s", e, exc_info=True)

# Bad - no stack trace
logger.error("Failed to process data: %s", e)
```

### 5. Conditional Logging for Expensive Operations

```python
# Good
if logger.isEnabledFor(logging.DEBUG):
    debug_data = expensive_debug_operation()
    logger.debug("Debug data: %s", debug_data)

# Bad - always executes expensive operation
logger.debug("Debug data: %s", expensive_debug_operation())
```

## Request Tracing

Every request gets a unique ID that is:
- Extracted from the `X-Request-ID` header if present
- Generated as a UUID4 if not present
- Added to all log entries for that request
- Returned in the `X-Request-ID` response header

This allows you to trace a single request across multiple components:

```bash
# Filter logs by request ID
grep "abc123-def456" logs/glyph.log
```

## Log Rotation

Logs are rotated based on configuration:

- **Size-based**: Rotates when file exceeds `max_size_mb`
- **Time-based**: Rotates at specified intervals
- **Backup count**: Keeps `backup_count` rotated files
- **Compression**: Old files are compressed with gzip

## Security Considerations

1. **Never log sensitive data**:
   - Passwords
   - API keys (except first 4 chars for identification)
   - JWT tokens
   - Personal identifiable information (PII)

2. **Log file permissions**:
   - Set appropriate file permissions (640 or 600)
   - Restrict access to application user

3. **Audit trail**:
   - All authentication events are logged
   - All authorization failures are logged
   - All data modification operations should be logged

## Monitoring & Operations

### Log Analysis

Use structured JSON format for easy parsing:

```bash
# Filter by level
jq 'select(.level == "ERROR")' logs/glyph.log

# Filter by request ID
jq 'select(.request_id == "abc123")' logs/glyph.log

# Get unique users
jq -r '.username | select(. != null)' logs/glyph.log | sort -u
```

### Integration with Log Aggregation

The JSON format is compatible with:
- ELK Stack (Elasticsearch, Logstash, Kibana)
- Loki and Grafana
- CloudWatch Logs
- Datadog

## Troubleshooting

### Logs not appearing

1. Check log level in config.yml
2. Verify log directory exists and is writable
3. Check for duplicate logging setup

### Request ID not in logs

1. Verify RequestIDMiddleware is added to app
2. Check that logging is configured after middleware setup

### Performance issues

1. Use text format instead of JSON for console output
2. Reduce log level in production
3. Consider async logging for high-throughput scenarios
