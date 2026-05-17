"""Processing module for Glyph application.

Provides the pipeline framework for binary analysis workflows, including
task management, Ghidra integration, and pluggable processing steps.

Components:
    pipeline: Core pipeline framework (PipelineContext, PipelineStep, ProcessingPipeline).
    steps: Concrete step implementations (validation, tokenization, filtering, etc.).
    task_management: Task execution and event watching.
    ghidra_processor: Ghidra decompilation and tokenization.
"""
