"""Centralized Jinja2 template configuration.

This module provides a single, shared Jinja2Templates instance for the entire
application. Using a single instance ensures:
- Consistent auto-escaping configuration across all endpoints
- Shared template cache (reduces memory overhead)
- Consistent global filters and macros
"""

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")
templates.env.autoescape = True
