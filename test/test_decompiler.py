import pytest
from unittest import mock

# Mock Ghidra Imports to prevent immediate import errors if not in headless session
with mock.patch.dict('sys.modules', {
    'ghidra.app.decompiler': mock.MagicMock(),
    'ghidra.util.task': mock.MagicMock(),
    'ghidra.program.model.listing': mock.MagicMock(),
}):
    from ghidra.app.decompiler import DecompInterface, DecompileOptions, CCodeMarkup
    from ghidra.util.task import TaskMonitor
    from java.lang import String

# ... (rest of module imports if needed)


def check_if_variable(token):
    """Implementation from your script"""
    import re
    return re.match(r"^(?:\d{0,3}\w{1})var\d+$|^(?:\w{0,2})stack\d*$|^(?:\w{0,2})local\d*$", token, re.IGNORECASE) is not None


def remove_comments(tokens_list):
    """Implementation from your script"""
    tokens_string = " ".join(tokens_list)
    result = tokens_string
    
    while "/*" in result:
        start = result.find("/*")
        end = result.find("*/", start)
        if end == -1:
            result = result[:start].strip()
        else:
            result = result[:start] + " " + result[end + 2:]
    
    result = " ".join(result.split())
    return result.split() if result else []


def filter_tokens(tokens_list):
    """Tests the full normalization and cleaning pipeline."""
    import re
    
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


class TestCheckIfVariable:
    """Tests the regex logic for identifying variables."""
    
    def test_valid_variables(self):
        assert check_if_variable("var1") is True
        assert check_if_variable("VAR5") is True
        assert check_if_variable("stack0") is True
        assert check_if_variable("local100") is True
    
    def test_invalid_variables(self):
        assert check_if_variable("int") is False
        assert check_if_variable("FUN_main") is False
        assert check_if_variable("printf") is False
    
    def test_edge_case_numbered_vars(self):
        assert check_if_variable("v123var456") is True 


class TestRemoveComments:
    """Tests C-style comment removal logic."""

    @staticmethod
    def run(tokens_list):
        return remove_comments(tokens_list)

    def test_remove_simple_comment(self):
        tokens = ["x", "/* this is a comment */", "y"]
        expected = ["x", "y"]
        assert TestRemoveComments.run(tokens) == expected

    def test_remove_nested_comments_no_close(self):
        tokens = ["start", "/* unclosed", "comment", "end"]
        expected = ["start", "unclosed", "comment", "end"]
        result = TestRemoveComments.run(tokens)
        assert len(result) == 4
    
    def test_remove_inline_comments(self):
        tokens = ["int", "x", "=/* comment */", "5;"]
        expected = ["int", "x", "=", "5;"]
        assert TestRemoveComments.run(tokens) == expected
        

class TestFilterTokens:
    """Tests the full normalization and cleaning pipeline."""

    def test_filter_clean_variables(self):
        tokens = [
            "int", 
            "var1", 
            "stack0", 
            "local3", 
            "/* comment */", 
            "0x401000"
        ]
        result = filter_tokens(tokens)
        assert any("VARIABLE" in r for r in result)
        assert any("HEX" in r for r in result)

    def test_filter_mixed_types(self):
        tokens = [
            "FUN_main", 
            "var1", 
            "0xdeadbeef", 
            "printf",
            "undefined_var"
        ]
        result = filter_tokens(tokens)
        
        assert any("FUNCTION" in r for r in result)
        assert any("VARIABLE" in r for r in result)
        assert any("HEX" in r for r in result)
        assert any("undefined" in r.lower() for r in result)


class TestIntegrationFlow:
    """Tests the orchestration logic with mocked Ghidra components."""

    @pytest.fixture
    def mock_decompiler(self):
        return mock.MagicMock(spec=DecompilerInterface)

    @pytest.fixture
    def mock_function(self):
        func = mock.MagicMock()
        func.getName.return_value = "main"
        func.isExternal.return_value = False
        func.getEntryPoint.return_value = mock.MagicMock().__str__ = lambda: "0x401000"
        body_mock = mock.MagicMock()
        body_mock.getMaxAddress.return_value = mock.MagicMock().__str__ = lambda: "0x401020"
        func.getBody.return_value = body_mock
        return func

    @pytest.fixture
    def mock_decomp_markup(self):
        markup = mock.MagicMock()
        markup.flatten.return_value = None 
        return markup

    @pytest.fixture
    def mock_decompile_interface(self, mock_decompiler):
        mock_decompiler.getCCodeMarkup.return_value = mock.MagicMock()
        mock_decomp_markup = mock_decompiler.getCCodeMarkup.return_value
        mock_decomp_markup.flatten.side_effect = lambda tokens: None
        
        return mock_decompiler

    @pytest.mark.skip(reason="Requires Ghidra environment to setup decompiler globally")
    def test_setup_decompiler(self, mock_decompile_interface):
        with mock.patch('ghidra.app.decompiler.DecompilerInterface') as MockDCI:
            instance = mock.MagicMock()
            MockDCI.return_value = instance
            
            result = setup_decompiler()
            
            assert isinstance(result, DecompInterface)
    
    @pytest.mark.skip(reason="Requires Ghidra environment")
    def test_get_function_tokens_logic(self, mock_function):
        with mock.patch('ghidra.app.decompiler.DecompilerInterface') as MockDCI:
            decomp_interface = mock.MagicMock()
            
            ccode_markup = mock.MagicMock()
            decomp_interface.decompileFunction.return_value.getCCodeMarkup.return_value = ccode_markup
            
            token_list = []
            ccode_markup.flatten(token_list)
            
            result = filter_tokens(token_list)
            
            assert isinstance(result, list)
