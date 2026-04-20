"""Jinja2 utility functions for template configuration.

This module provides centralized configuration for Jinja2 templates,
including CSRF token exposure and other global template functions.
"""

import logging

from fastapi.templating import Jinja2Templates

logger = logging.getLogger(__name__)


def configure_jinja2_templates(templates: Jinja2Templates) -> None:
    """Configure Jinja2 templates with global functions and context.

    This function adds the CSRF token getter and any other global
    template functions to the Jinja2 environment.

    Args:
        templates: The Jinja2Templates instance to configure.
    """
    # Add CSRF token getter for templates
    def get_csrf_token(request):
        token = getattr(request.state, "csrf_token", None)
        logger.debug(f"get_csrf_token called: request.state exists={hasattr(request, 'state')}, token={token[:8] + '...' if token else None}")
        return token
    
    templates.env.globals["get_csrf_token"] = get_csrf_token
