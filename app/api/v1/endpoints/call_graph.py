"""Call graph endpoints for Glyph API v1.

Provides endpoints for generating and querying function call graphs
from decompiled binary data.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_active_user
from app.database.models import User
from app.utils.responses import (
    create_success_response,
    create_error_response,
    SuccessResponse,
)
from loguru import logger


router = APIRouter()


class CallGraphEdge(BaseModel):
    """A single edge in the call graph.

    Attributes:
        caller: Name of the calling function.
        callee: Name of the called function.
        call_count: Number of times caller invokes callee.
    """

    caller: str
    callee: str
    call_count: int


class CallGraphNode(BaseModel):
    """A node in the call graph.

    Attributes:
        name: Function name.
        entrypoint: Memory address.
        callers: Functions that call this function.
        callees: Functions called by this function.
    """

    name: str
    entrypoint: str
    callers: list[str]
    callees: list[str]


class CallGraphResponse(BaseModel):
    """Response schema for call graph generation.

    Attributes:
        binary_id: Database ID of the parent binary.
        nodes: All functions in the graph.
        edges: All call relationships.
        total_nodes: Number of functions in the graph.
        total_edges: Number of call relationships.
        entry_points: Functions with no callers (potential entry points).
    """

    binary_id: int
    nodes: list[CallGraphNode]
    edges: list[CallGraphEdge]
    total_nodes: int
    total_edges: int
    entry_points: list[str] = Field(default_factory=list)


@router.get(
    "/{binary_id}/graph",
    response_model=SuccessResponse[CallGraphResponse],
    summary="Generate call graph",
    description=(
        "Generate a function call graph for the specified binary by parsing "
        "decompiled C code for call sites. Returns all nodes (functions) and "
        "edges (call relationships) in the graph."
    ),
)
async def get_call_graph(
    binary_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> SuccessResponse[CallGraphResponse]:
    """Generate and return the call graph for a binary."""
    from app.database.sql_service import SQLUtil
    from app.services.call_graph_service import CallGraphService

    # Verify binary exists and user has access
    binary = await SQLUtil.get_binary(binary_id)
    if binary is None:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code="BINARY_NOT_FOUND",
                error_message="Binary not found",
            ).model_dump(),
        )

    if binary.uploaded_by != current_user.id:
        raise HTTPException(
            status_code=403,
            detail=create_error_response(
                error_code="ACCESS_DENIED",
                error_message="Access denied",
            ).model_dump(),
        )

    # Generate call graph
    graph = await CallGraphService.generate_call_graph(binary_id)

    # Find entry points
    entry_points = CallGraphService.find_entry_points(graph)

    graph_dict = graph.to_dict()

    response = CallGraphResponse(
        binary_id=binary_id,
        nodes=[
            CallGraphNode(
                name=n["name"],
                entrypoint=n["entrypoint"],
                callers=n["callers"],
                callees=n["callees"],
            )
            for n in graph_dict["nodes"]
        ],
        edges=[
            CallGraphEdge(
                caller=e["caller"],
                callee=e["callee"],
                call_count=e["call_count"],
            )
            for e in graph_dict["edges"]
        ],
        total_nodes=graph_dict["total_nodes"],
        total_edges=graph_dict["total_edges"],
        entry_points=entry_points,
    )

    logger.info(
        "Call graph generated for binary {}: {} nodes, {} edges",
        binary_id,
        response.total_nodes,
        response.total_edges,
    )

    return create_success_response(
        data=response,
        message="Call graph generated successfully",
    )


class FunctionCallersResponse(BaseModel):
    """Response schema for function callers query.

    Attributes:
        function_name: Name of the queried function.
        callers: Functions that call this function.
        caller_count: Number of unique callers.
    """

    function_name: str
    callers: list[str]
    caller_count: int


@router.get(
    "/{binary_id}/callers/{function_name}",
    response_model=SuccessResponse[FunctionCallersResponse],
    summary="Get function callers",
    description=(
        "Get all functions that call the specified function within a binary. "
        "Generates the call graph on-demand if not cached."
    ),
)
async def get_function_callers(
    binary_id: int,
    function_name: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> SuccessResponse[FunctionCallersResponse]:
    """Get all callers for a specific function."""
    from app.database.sql_service import SQLUtil
    from app.services.call_graph_service import CallGraphService

    # Verify binary exists and user has access
    binary = await SQLUtil.get_binary(binary_id)
    if binary is None:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code="BINARY_NOT_FOUND",
                error_message="Binary not found",
            ).model_dump(),
        )

    if binary.uploaded_by != current_user.id:
        raise HTTPException(
            status_code=403,
            detail=create_error_response(
                error_code="ACCESS_DENIED",
                error_message="Access denied",
            ).model_dump(),
        )

    graph = await CallGraphService.generate_call_graph(binary_id)
    callers = CallGraphService.get_function_callers(graph, function_name)

    if function_name not in graph.nodes:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code="FUNCTION_NOT_FOUND",
                error_message=f"Function '{function_name}' not found in binary",
            ).model_dump(),
        )

    return create_success_response(
        data=FunctionCallersResponse(
            function_name=function_name,
            callers=callers,
            caller_count=len(callers),
        ),
        message=f"Found {len(callers)} caller(s) for '{function_name}'",
    )


class FunctionCalleesResponse(BaseModel):
    """Response schema for function callees query.

    Attributes:
        function_name: Name of the queried function.
        callees: Functions called by this function.
        callee_count: Number of unique callees.
    """

    function_name: str
    callees: list[str]
    callee_count: int


@router.get(
    "/{binary_id}/callees/{function_name}",
    response_model=SuccessResponse[FunctionCalleesResponse],
    summary="Get function callees",
    description=(
        "Get all functions called by the specified function within a binary. "
        "Generates the call graph on-demand if not cached."
    ),
)
async def get_function_callees(
    binary_id: int,
    function_name: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> SuccessResponse[FunctionCalleesResponse]:
    """Get all callees for a specific function."""
    from app.database.sql_service import SQLUtil
    from app.services.call_graph_service import CallGraphService

    # Verify binary exists and user has access
    binary = await SQLUtil.get_binary(binary_id)
    if binary is None:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code="BINARY_NOT_FOUND",
                error_message="Binary not found",
            ).model_dump(),
        )

    if binary.uploaded_by != current_user.id:
        raise HTTPException(
            status_code=403,
            detail=create_error_response(
                error_code="ACCESS_DENIED",
                error_message="Access denied",
            ).model_dump(),
        )

    graph = await CallGraphService.generate_call_graph(binary_id)
    callees = CallGraphService.get_function_callees(graph, function_name)

    if function_name not in graph.nodes:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code="FUNCTION_NOT_FOUND",
                error_message=f"Function '{function_name}' not found in binary",
            ).model_dump(),
        )

    return create_success_response(
        data=FunctionCalleesResponse(
            function_name=function_name,
            callees=callees,
            callee_count=len(callees),
        ),
        message=f"Found {len(callees)} callee(s) for '{function_name}'",
    )
