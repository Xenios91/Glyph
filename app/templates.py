"""Centralized Jinja2 template configuration.

This module provides a single, shared Jinja2Templates instance for the entire
application. Using a single instance ensures:
- Consistent auto-escaping configuration across all endpoints
- Shared template cache (reduces memory overhead)
- Consistent global filters and macros
"""

from fastapi.templating import Jinja2Templates

from app.utils.jinja_utils import configure_jinja2_templates

templates = Jinja2Templates(directory="templates")
configure_jinja2_templates(templates)
