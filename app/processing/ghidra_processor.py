"""Ghidra processor module for binary decompilation and tokenization."""

from collections.abc import Iterable
from typing import Any, cast

from loguru import logger


def setup_decompiler(
    state: Any,
    program: Any,
    num_processors: int = 2,
    decomp_interface: Any = None,
) -> Any:
    """Initialize and configure the decompiler.

    Args:
        state: The Ghidra state.
        program: The Ghidra program to decompile.
        num_processors: Number of processors to use.
        decomp_interface: Optional existing decompiler interface.

    Returns:
        Configured decompiler interface.

    """
    DecompInterface: type[Any]
    DecompileOptions: type[Any]
    try:
        from ghidra.app.decompiler import DecompileOptions, DecompInterface
    except ImportError:
        DecompInterface = type("DecompInterface", (), {})
        DecompileOptions = type("DecompileOptions", (), {})

    if decomp_interface is None:
        decomp_interface = cast(Any, DecompInterface())
    options = cast(Any, DecompileOptions())

    decomp_interface.setOptions(options)
    decomp_interface.toggleCCode(True)
    decomp_interface.toggleSyntaxTree(True)
    decomp_interface.setSimplificationStyle("decompile")
    decomp_interface.openProgram(program)

    return decomp_interface


def get_function_tokens(function: Any, decomp_interface: Any) -> tuple[list[str], str]:
    """Decompile a function and extract tokens plus raw C code.

    Args:
        function: The Ghidra function to decompile.
        decomp_interface: The decompiler interface to use.

    Returns:
        A tuple of (token_list, raw_c_code).

    """
    _TaskMonitor: Any
    try:
        import ghidra.util.task as _task_module

        _TaskMonitor = cast(Any, _task_module.TaskMonitor)
    except ImportError:
        _TaskMonitor = type("TaskMonitor", (), {"DUMMY": None})

    _ArrayList: type[Any]
    try:
        import java.util as _java_util

        _ArrayList = cast(Any, _java_util.ArrayList)
    except ImportError:
        _ArrayList = type("ArrayList", (), {})

    monitor: Any = _TaskMonitor.DUMMY
    try:
        decompiled = decomp_interface.decompileFunction(function, 60, monitor)
        if not decompiled or not decompiled.decompileCompleted():
            return [], ""

        ccode_markup = decompiled.getCCodeMarkup()
        token_list: Any = _ArrayList()
        ccode_markup.flatten(token_list)

        tokens = [str(t) for t in cast(Iterable[Any], token_list) if str(t).strip()]

        # Also extract plain C source for raw storage
        try:
            plain_c = decompiled.getPlainC()
            raw_code = str(plain_c) if plain_c else ""
        except Exception:
            raw_code = " ".join(tokens)  # Fallback to joined tokens

        return tokens, raw_code
    except Exception:
        logger.exception("Decompilation error for function {}", function.getName())
        return [], ""


def decompile_all_functions(state: Any, program: Any) -> dict[str, list[Any]]:
    """Decompile all functions in a program.

    Args:
        state: The Ghidra state.
        program: The Ghidra program to decompile.

    Returns:
        Dictionary containing functions and errored functions.

    """
    decomp_interface = setup_decompiler(state, program)
    functions_map: dict[str, list[Any]] = {"functions": [], "erroredFunctions": []}

    function_manager = program.getFunctionManager()
    function_iter = function_manager.getFunctions(True)

    while function_iter.hasNext():
        function = function_iter.next()
        if function.isExternal():
            continue

        tokens, raw_code = get_function_tokens(function, decomp_interface)

        if not tokens:
            functions_map["erroredFunctions"].append(
                {"functionName": function.getName(), "error": "Decompilation failed"},
            )
            continue

        return_type = str(function.getReturnType())
        if "undefined" in return_type:
            return_type = "undefined"
        param_count = len(function.getParameters())

        func_entry: dict[str, Any] = {
            "functionName": function.getName(),
            "lowAddress": str(function.getEntryPoint()),
            "highAddress": str(function.getBody().getMaxAddress()),
            "returnType": return_type,
            "parameterCount": param_count,
            "tokenList": tokens,
            "raw_code": raw_code,
        }

        functions_map["functions"].append(func_entry)

    decomp_interface.dispose()
    return functions_map


def analyze_binary_and_decompile(binary_path: str) -> dict[str, list[Any]]:
    """Analyze a binary file and return decompiled functions.

    Opens the program with auto-analysis disabled, then runs analysis
    synchronously to avoid background threads outliving the context manager
    and producing 'File is closed' errors.

    Args:
        binary_path: Path to the binary file to analyze.

    Returns:
        Dictionary containing decompiled functions.

    """
    pyghidra: Any
    try:
        import pyghidra
    except ImportError:
        pyghidra = type(
            "pyghidra", (), {"started": lambda: False, "start": lambda: None, "open_program": lambda *a, **k: None},
        )

    if not pyghidra.started():
        pyghidra.start()

    with pyghidra.open_program(binary_path, project_location="/tmp/", analyze=False) as flat_api:
        program = flat_api.getCurrentProgram()

        try:
            from ghidra.program.util import GhidraProgramUtilities

            if GhidraProgramUtilities.shouldAskToAnalyze(program):
                flat_api.analyzeAll(program)
        except ImportError:
            flat_api.analyzeAll(program)

        return decompile_all_functions(None, program)
