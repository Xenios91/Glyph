"""Jinja2 utility functions for template configuration.

This module provides centralized configuration for Jinja2 templates,
including CSRF token exposure and other global template functions.
"""

from typing import Any

from fastapi.templating import Jinja2Templates


def configure_jinja2_templates(templates: Jinja2Templates) -> None:
    """Configure Jinja2 templates with global functions and context.

    This function enables auto-escaping for XSS protection and adds the CSRF
    token getter and any other global template functions to the Jinja2
    environment.

    Args:
        templates: The Jinja2Templates instance to configure.
    """
    # Enable auto-escaping for HTML templates to prevent XSS.
    # This ensures user-controlled content (e.g., binary analysis tokens)
    # is properly escaped when rendered in templates, replacing the previous
    # manual html_escape() calls in format_code().
    templates.env.autoescape = True  # type: ignore[union-attr]

    # Add CSRF token getter for templates
    def get_csrf_token(request: Any) -> str | None:
        token = getattr(request.state, "csrf_token", None)
        return token

    templates.env.globals["get_csrf_token"] = get_csrf_token  # type: ignore[union-attr]
