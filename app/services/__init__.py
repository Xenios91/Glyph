"""Services module for Glyph application.

Contains business logic services that orchestrate the processing pipeline.

Components:
    request_handler: Request data processing (TrainingRequest, PredictionRequest, GhidraRequest).
    binary_upload_service: Binary upload and Ghidra analysis orchestration.
    prediction_service: ML prediction persistence and retrieval.
    code_reuse_detector: In-memory code reuse similarity computation.
    binary_similarity_service: Batch pairwise binary similarity computation.
    call_graph_service: Call graph extraction from decompiled code.
    dangerous_function_scanner: Dangerous function catalog scanning.
    llm_analysis_service: LLM-assisted analysis of dangerous function findings.
"""
