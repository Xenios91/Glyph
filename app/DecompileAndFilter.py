from ghidra.app.decompiler import DecompInterface, DecompileOptions, CCodeMarkup
from ghidra.util.task import TaskMonitor
from ghidra.program.model.listing import CodeUnit
from java.lang import String
import re


# === Token Cleanup/Normalization ===

def check_if_variable(token):
    """
    Checks if token looks like a variable (var*, stack*, local*, etc.)
    Replicates Java checkIfVariable logic.
    """
    return re.match(r"^(?:\d{0,3}\w{1})var\d+$|^(?:\w{0,2})stack\d*$|^(?:\w{0,2})local\d*$", token, re.IGNORECASE) is not None


def remove_comments(tokens_list):
    """
    Recursively removes C-style comments (/* ... */) from token list.
    Replicates Java removeComments() logic.
    """
    tokens_string = " ".join(tokens_list)
    result = tokens_string

    # Keep removing comments until none remain
    while "/*" in result:
        start = result.find("/*")
        end = result.find("*/", start)
        
        if end == -1:
            # No closing comment — remove from start to end of string
            result = result[:start].strip()
        else:
            # Remove comment including delimiters
            result = result[:start] + " " + result[end + 2:]
    
    # Normalize spacing and split back to tokens
    result = " ".join(result.split())  # collapse whitespace
    return result.split() if result else []


def filter_tokens(tokens_list):
    """
    Normalizes tokens in list:
    - Replaces addresses (0x...) → "HEX"
    - Replaces function names (FUN_...) → "FUNCTION"
    - Replaces variables (varX, stackX, localX, etc.) → "VARIABLE"
    - Replaces undefinedX → "undefined"
    - Then removes comments recursively.
    """
    filtered = []

    for token in tokens_list:
        if not token or token.strip() == "":
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

def setup_decompiler():
    """Initialize and configure the decompiler"""
    decomp_interface = DecompInterface()
    options = DecompileOptions()

    tool = state.getTool()
    if tool:
        service = tool.getService(OptionsService.class)
        if service:
            opt = service.getOptions("Decompiler")
            options.grabFromToolAndProgram(None, opt, currentProgram)

    decomp_interface.setOptions(options)
    decomp_interface.toggleCCode(True)
    decomp_interface.toggleSyntaxTree(True)
    decomp_interface.setSimplificationStyle("decompile")

    return decomp_interface


def get_function_tokens(function, decomp_interface):
    """
    Decompile a function and extract tokenized C code as list of strings.
    """
    try:
        monitor = TaskMonitor.DUMMY
        decompiled = decomp_interface.decompileFunction(function, 60, monitor)

        # Get the C code markup and flatten it to tokens
        ccode_markup = decompiled.getCCodeMarkup()
        token_list = []
        ccode_markup.flatten(token_list)

        # Convert each token to string and filter out blanks
        tokens = []
        for token in token_list:
            token_str = str(token)
            if token_str and token_str.strip():
                tokens.append(token_str)

        return tokens
    except Exception as e:
        print(f"Error decompiling function {function.getName()}: {e}")
        return []


def decompile_all_functions():
    """
    Decompile all non-external functions in current binary.
    Returns dict: {
        'functions': [list of clean token lists],
        'erroredFunctions': [list of error dicts]
    }
    """
    decomp_interface = setup_decompiler()
    functions_map = {
        "functions": [],
        "erroredFunctions": []
    }

    function_manager = currentProgram.getFunctionManager()
    function_iter = function_manager.getFunctions(True)

    while function_iter.hasNext():
        function = function_iter.next()

        if function.isExternal():
            continue

        tokens = get_function_tokens(function, decomp_interface)

        if not tokens:
            functions_map["erroredFunctions"].append({
                "functionName": function.getName(),
                "lowAddress": str(function.getEntryPoint()),
                "highAddress": str(function.getBody().getMaxAddress()),
                "error": "No tokens generated"
            })
            continue

        # Try to extract return type, param count, etc. (original Java code did this too)
        try:
            return_type = str(function.getReturnType())
            if "undefined" in return_type:
                return_type = "undefined"
            param_count = len(function.getParameters())
        except:
            return_type = "undefined"
            param_count = 0

        # Apply token cleaning/filtering
        filtered_tokens = filter_tokens(tokens)

        func_entry = {
            "functionName": function.getName(),
            "lowAddress": str(function.getEntryPoint()),
            "highAddress": str(function.getBody().getMaxAddress()),
            "returnType": return_type,
            "parameterCount": param_count,
            "tokenList": filtered_tokens
        }

        # Check if decompilation appears to have warnings/comments
        if any("/*" in tok for tok in tokens):
            functions_map["erroredFunctions"].append(func_entry)
        else:
            functions_map["functions"].append(func_entry)

    decomp_interface.dispose()
    return functions_map


# === Main Execution ===
if __name__ == "__main__":
    print("=== Decompiling and token-filtering all functions in current binary ===")
    result = decompile_all_functions()

    success_count = len(result["functions"])
    error_count = len(result["erroredFunctions"])
    print(f"\nTotal functions: {success_count + error_count}")
    print(f"Successfully processed: {success_count}")
    print(f"Failed/error-annotated: {error_count}")

    print("\n=== First successful function ===")
    if result["functions"]:
        func = result["functions"][0]
        print(f"Function: {func['functionName']}")
        print(f"Address: {func['lowAddress']} - {func['highAddress']}")
        print(f"Return type: {func['returnType']}, Params: {func['parameterCount']}")
        print(f"First 10 tokens: {func['tokenList'][:10]}")
        # Full list of tokens (optional)
        # print(f"Full tokens: {func['tokenList']}")

    print("\n=== First errored function ===")
    if result["erroredFunctions"]:
        err = result["erroredFunctions"][0]
        print(f"Function: {err['functionName']}")
        print(f"Error reason: {err.get('error', 'Contains /* ... */ comments')}")
        print(f"First 10 tokens: {err['tokenList'][:10]}")
