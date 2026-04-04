"""Ghidra processor module for binary decompilation and tokenization."""

import re
from typing import Any

from app.config.settings import GlyphConfig

_VARIABLE_PATTERNS = [
    r"^var\d+$",
    r"^local_[0-9a-fA-F]+$",
    r"^[a-z]{1,2}Var\d+$",
    r"^param_\d+$",
    r"^(?:u)?stack_?[-?0-9a-fA-F]+$",
    r"^(?:unaff|extraout)_.*$",
]
_VARIABLE_REGEX = re.compile(f"({'|'.join(_VARIABLE_PATTERNS)})", re.IGNORECASE)
_COMMENT_REGEX = re.compile(r"/\*.*?\*/|//[^\n]*")


def check_if_variable(token: str) -> bool:
    """Check if a token matches Ghidra auto-naming patterns.

    Args:
        token: The token to check.

    Returns:
        True if the token matches a Ghidra auto-naming pattern.
    """
    return _VARIABLE_REGEX.match(token) is not None


def remove_comments(tokens_list: list[str]) -> list[str]:
    """Remove C-style comments from token list.

    Args:
        tokens_list: List of tokens to process.

    Returns:
        List of tokens with comments removed.
    """
    tokens_string: str = " ".join(tokens_list)
    result: str = ""
    i = 0
    while i < len(tokens_string):
        if tokens_string[i : i + 2] == "/*":
            # Found start of comment, look for closing */
            close_idx = tokens_string.find("*/", i + 2)
            if close_idx == -1:
                # Unclosed comment - stop processing
                break
            # Skip past the closed comment
            i = close_idx + 2
        else:
            result += tokens_string[i]
            i += 1
    # Clean up whitespace
    result = " ".join(result.split())
    return result.split() if result else []


def filter_tokens(tokens_list: list[str]) -> list[str]:
    """Normalize addresses, functions, variables, and undefined types.

    Args:
        tokens_list: List of tokens to filter.

    Returns:
        List of filtered and normalized tokens.
    """
    filtered: list[str] = []
    for token in tokens_list:
        if not token or not token.strip():
            continue

        if "0x" in token:
            filtered.append("HEX")
        elif token.startswith("FUN_"):
            filtered.append("FUNCTION")
        elif check_if_variable(token):
            filtered.append("VARIABLE")
        elif re.match(r"^undefined\d+$", token):
            filtered.append("undefined")
        else:
            filtered.append(token)

    return remove_comments(filtered)


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
    from ghidra.app.decompiler import DecompInterface, DecompileOptions

    if decomp_interface is None:
        decomp_interface = DecompInterface()
    options = DecompileOptions()

    decomp_interface.setOptions(options)
    decomp_interface.toggleCCode(True)
    decomp_interface.toggleSyntaxTree(True)
    decomp_interface.setSimplificationStyle("decompile")
    decomp_interface.openProgram(program)

    return decomp_interface


def get_function_tokens(function: Any, decomp_interface: Any) -> list[str]:
    """Decompile a function and extract tokenized C code.

    Args:
        function: The Ghidra function to decompile.
        decomp_interface: The decompiler interface to use.

    Returns:
        List of tokens from the decompiled function.
    """
    from ghidra.util.task import TaskMonitor
    from java.util import ArrayList

    try:
        decompiled = decomp_interface.decompileFunction(function, 60, TaskMonitor.DUMMY)
        if not decompiled or not decompiled.decompileCompleted():
            return []

        ccode_markup = decompiled.getCCodeMarkup()
        token_list = ArrayList()
        ccode_markup.flatten(token_list)

        return [str(t) for t in token_list if str(t).strip()]
    except Exception as exc:
        print("Error in %s: %s", function.getName(), exc)
        return []


def decompile_all_functions(state: Any, program: Any) -> dict[str, list]:
    """Decompile all functions in a program.

    Args:
        state: The Ghidra state.
        program: The Ghidra program to decompile.

    Returns:
        Dictionary containing functions and errored functions.
    """
    decomp_interface = setup_decompiler(state, program)
    functions_map: dict[str, list] = {"functions": [], "erroredFunctions": []}

    function_manager = program.getFunctionManager()
    function_iter = function_manager.getFunctions(True)

    while function_iter.hasNext():
        function = function_iter.next()
        if function.isExternal():
            continue

        tokens = get_function_tokens(function, decomp_interface)

        if not tokens:
            functions_map["erroredFunctions"].append(
                {"functionName": function.getName(), "error": "Decompilation failed"}
            )
            continue

        return_type = str(function.getReturnType())
        if "undefined" in return_type:
            return_type = "undefined"
        param_count = len(function.getParameters())
        filtered_tokens: list[str] = filter_tokens(tokens)

        func_entry: dict[str, Any] = {
            "functionName": function.getName(),
            "lowAddress": str(function.getEntryPoint()),
            "highAddress": str(function.getBody().getMaxAddress()),
            "returnType": return_type,
            "parameterCount": param_count,
            "tokenList": filtered_tokens,
        }

        if any("/*" in tok for tok in tokens):
            functions_map["erroredFunctions"].append(func_entry)
        else:
            functions_map["functions"].append(func_entry)

    decomp_interface.dispose()
    return functions_map


def analyze_binary_and_decompile(binary_path: str) -> dict[str, list]:
    """Analyze a binary file and return decompiled functions.

    Args:
        binary_path: Path to the binary file to analyze.

    Returns:
        Dictionary containing decompiled functions.
    """
    import pyghidra

    if not pyghidra.started():
        pyghidra.start()

    with pyghidra.open_program(binary_path, project_location="/tmp/") as flat_api:
        program = flat_api.getCurrentProgram()
        return decompile_all_functions(None, program)

