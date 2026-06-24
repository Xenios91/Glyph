"""Type stubs for the pyghidra library.

These stubs provide type hints for the PyGhidra Python bindings,
which interface with Ghidra's Java API via JPype.
"""

from typing import Any

started: bool

def start() -> None: ...
def stop() -> None: ...
def open_program(
    file_path: str,
    project_location: str = ...,
    analyze: bool = ...,
) -> Any: ...
