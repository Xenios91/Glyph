

def format_code(code: str) -> str:
    '''
    Formats C code for browser display
    '''
    function_signature = code.split("{")[0].strip()
    function_signature = (f"{function_signature}" + " \n{\n")

    function_body = " { ".join(code.split("{")[1:])
    function_body = function_body.replace("{", "\n{\n")
    function_body = function_body.replace("}", "\n}\n")
    function_body = function_body.replace(" ( ", "(")
    function_body = function_body.replace(" ) ", ")")
    function_body = function_body.replace(" ;", ";")
    function_body = function_body.replace(";", ";\n")
    function_body = function_body.replace("\n \n", "\n")

    formatted_code = f"{function_signature}{function_body}"

    return formatted_code
