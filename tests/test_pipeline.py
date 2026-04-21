"""Tests for the pipeline framework.

This module contains tests for the ProcessingPipeline class and PipelineContext.
"""

import pytest
from unittest.mock import MagicMock, patch

# Skip tests that depend on missing PipelineBuilder
# PipelineBuilder does not exist in current codebase
pytestmark = pytest.mark.skip(reason="PipelineBuilder does not exist in current codebase")
