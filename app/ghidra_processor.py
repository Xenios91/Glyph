import re

from app.config import GlyphConfig

# === Token Cleanup/Normalization ===

def check_if_variable(token):
    """
    Checks if a token matches Ghidra decompiler auto-naming.
    Catches:
    - Simple: var1, var2
    - Stack: local_10, local_res, uStack18, stack[-0x10]
    - Typed Registers: iVar1, uVar2, pVar3, bVar1, auVar4, lVar1
    - Params: param_1, param_2
    - Special: unaff_RET, extraout_v0
    """
    patterns = [
        r"^var\d+$",                  # Simple var1, var2
        r"^local_[0-9a-fA-F]+$",      # Stack variables (local_10)
        r"^[a-z]{1,2}Var\d+$",        # iVar1, uVar2, pVar3, auVar1
        r"^param_\d+$",               # Function parameters
        r"^(?:u)?stack_?[-?0-9a-fA-F]+$", # stack_10, ustack18, stack[-0x8]
        r"^(?:unaff|extraout)_.*$"     # Unaffected registers or extra outputs
    ]
    
    combined_pattern = f"({'|'.join(patterns)})"
    return re.match(combined_pattern, token, re.IGNORECASE) is not None

def remove_comments(tokens_list):
    """Recursively removes C-style comments (/* ... */) from token list."""
    tokens_string = " ".join(tokens_list)
    result = tokens_string

    while "/*" in result:
        start = result.find("/*")
        end = result.find("*/", start)
        if end == -1:
            result = result[:start].strip()
            break
        else:
            result = result[:start] + " " + result[end + 2:]
    
    result = " ".join(result.split())
    return result.split() if result else []

def filter_tokens(tokens_list):
    """Normalizes addresses, functions, variables, and undefined types."""
    filtered = []
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

# === Decompiler Setup & Execution ===

def setup_decompiler(state, program, num_processors=GlyphConfig.get_config_value("cpu_cores") or 2, decomp_interface = None):
    """
    Initialize and configure the decompiler.
    Takes 'state' and 'program' as arguments to avoid global reliance.
    """
    from ghidra.app.decompiler import DecompInterface, DecompileOptions
    from ghidra.framework.options import OptionsService
    if decomp_interface is None:
        decomp_interface = DecompInterface()
    options = DecompileOptions()

    if state:
        tool = state.getTool()
        if tool:
            service = tool.getService(OptionsService)
            if service:
                opt = service.getOptions("Decompiler")
                opt.setInt("Max Decompiler Interfaces", num_processors)
                options.grabFromToolAndProgram(None, opt, program)

    decomp_interface.setOptions(options)
    decomp_interface.toggleCCode(True)
    decomp_interface.toggleSyntaxTree(True)
    decomp_interface.setSimplificationStyle("decompile")
    
    decomp_interface.openProgram(program)

    return decomp_interface

def get_function_tokens(function, decomp_interface):
    """Decompile a function and extract tokenized C code."""
    from ghidra.util.task import TaskMonitor
    
    try:
        decompiled = decomp_interface.decompileFunction(function, 60, TaskMonitor.DUMMY)
        if not decompiled or not decompiled.decompileCompleted():
            return []

        ccode_markup = decompiled.getCCodeMarkup()
        token_list = []
        ccode_markup.flatten(token_list)

        return [str(t) for t in token_list if str(t).strip()]
    except Exception as e:
        print(f"Error in {function.getName()}: {e}")
        return []

def decompile_all_functions(state, program):
    """Orchestrates the decompilation of the binary."""
    decomp_interface = setup_decompiler(state, program)
    functions_map = {"functions": [], "erroredFunctions": []}

    function_manager = program.getFunctionManager()
    function_iter = function_manager.getFunctions(True)

    while function_iter.hasNext():
        function = function_iter.next()
        if function.isExternal():
            continue

        tokens = get_function_tokens(function, decomp_interface)

        if not tokens:
            functions_map["erroredFunctions"].append({
                "functionName": function.getName(),
                "error": "Decompilation failed"
            })
            continue

        return_type = str(function.getReturnType())
        if "undefined" in return_type: return_type = "undefined"
        param_count = len(function.getParameters())

        filtered_tokens = filter_tokens(tokens)

        func_entry = {
            "functionName": function.getName(),
            "lowAddress": str(function.getEntryPoint()),
            "highAddress": str(function.getBody().getMaxAddress()),
            "returnType": return_type,
            "parameterCount": param_count,
            "tokenList": filtered_tokens
        }

        if any("/*" in tok for tok in tokens):
            functions_map["erroredFunctions"].append(func_entry)
        else:
            functions_map["functions"].append(func_entry)

    decomp_interface.dispose()
    return functions_map

def analyze_binary_and_decompile(binary_path) -> dict[str, list]:
    """
    Main entry point: takes a path, runs headless analysis, 
    and returns the decompiled function map.
    """
    import pyghidra

    if not pyghidra.is_started():
        pyghidra.start()

    with pyghidra.open_program(binary_path) as program:
        program.analyze() 
        return decompile_all_functions(None, program)
    
    
if __name__ == "__main__":
    analyze_binary_and_decompile("/bin/ls")
