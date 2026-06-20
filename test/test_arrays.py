#!/usr/bin/env python3
"""
Unit tests for Array feature in Chatybot (Native Storage Version)
"""

import pytest
import os
import asyncio
from unittest.mock import MagicMock, patch
from src.chatybot.buffer_manager import BufferManager
from src.chatybot.chatybot_app import ChatybotApp


class TestArrayFeature:
    """Test suite for the array parsing, storing, and macro iteration features"""

    @pytest.fixture
    def manager(self):
        """Create a fresh BufferManager instance"""
        return BufferManager()

    @pytest.fixture
    def app(self):
        """Create a ChatybotApp instance with patched components"""
        with patch('src.chatybot.chatybot_app.readline'):
            application = ChatybotApp()
            application.buffer_manager = BufferManager(app=application)
            application.chat_history = []
            application.macros = {}
            application.setup_macro_grammars()
            return application

    def test_replace_placeholders_with_array(self, manager):
        """Test that placeholders like ${var} substitute newline-joined array contents when referencing an array"""
        data = ["line1", "line2", "line3"]
        manager.set_script_var("my_arr", data)

        prompt = "Header\n${my_arr}\nFooter"
        text, images = manager.replace_placeholders(prompt)

        assert "line1\nline2\nline3" in text
        assert "Header\nline1\nline2\nline3\nFooter" == text

    def test_replace_placeholders_legacy_with_array(self, manager):
        """Test the legacy placeholder replacement for arrays"""
        data = ["a", "b"]
        manager.set_script_var("my_arr", data)

        prompt = "${my_arr}"
        result = manager.replace_placeholders_legacy(prompt)
        assert result == "a\nb"

    def test_dump_variables_and_memory_usage_with_array(self, manager, capsys):
        """Test dumping array variables displays elements and memory calculation includes array items"""
        data = ["hello", "world"]
        manager.set_script_var("my_arr", data)

        # Dump variables
        manager.dump_variables("my_arr")
        captured = capsys.readouterr()
        assert "SCRIPT_VAR 'my_arr': ['hello', 'world']" in captured.out

        # Memory usage
        manager.show_memory_usage()
        captured = capsys.readouterr()
        assert "my_arr[] (2 items)" in captured.out

    def test_set_script_command_with_array(self, app):
        """Test parsing and assigning an array variable via standard script command syntax"""
        # Execute "set cities[] = ['London', 'New York', 'Tokyo']"
        command = "set cities[] = ['London', 'New York', 'Tokyo']"
        
        # We need a dummy handler since execute_script_command expects one
        dummy_handler = MagicMock()
        
        result = asyncio.run(app.execute_script_command(command, dummy_handler))
        assert result is True
        
        # Check that 'cities' is defined in script_vars as a list
        assert "cities" in app.buffer_manager.script_vars
        assert app.buffer_manager.script_vars["cities"] == ["London", "New York", "Tokyo"]

    def test_setvar_escape_command_with_array(self, app):
        """Test setting an array variable interactively using the /setvar escape command"""
        command = "/setvar items[] = ['gold', 'silver', 'bronze']"
        result = asyncio.run(app.handle_escape_command(command))
        assert result is True

        assert "items" in app.buffer_manager.script_vars
        assert app.buffer_manager.script_vars["items"] == ["gold", "silver", "bronze"]

    def test_setvar_invalid_array_format(self, app, capsys):
        """Test error handling when setting an array with invalid format"""
        # Pass something that isn't a Python literal list
        command = "/setvar bad_arr[] = {not a list}"
        result = asyncio.run(app.handle_escape_command(command))
        assert result is True # Handled but prints error
        
        captured = capsys.readouterr()
        assert "Error: Invalid array format" in captured.out
        assert "bad_arr" not in app.buffer_manager.script_vars

    def test_macro_expansion_with_single_array(self, app):
        """Test that calling a macro with an array expands the macro once for each array element"""
        # Define macro
        app.macros["greet"] = {
            "params": ["name"],
            "template": "Hello ${name}!"
        }
        
        # Set script var directly
        app.buffer_manager.set_script_var("guests", ["Alice", "Bob", "Charlie"])

        # Expand macro with variable argument
        expanded = app.expand_macro("%greet(${guests})")
        
        expected = "Hello Alice!\nHello Bob!\nHello Charlie!"
        assert expanded == expected

    def test_macro_expansion_with_multiple_arrays(self, app):
        """Test macro expansion with multiple arrays, aligning elements and padding missing ones"""
        # Define macro
        app.macros["pair"] = {
            "params": ["x", "y"],
            "template": "Left: ${x}, Right: ${y}"
        }

        # Set script vars
        app.buffer_manager.set_script_var("left_side", ["A", "B"])
        app.buffer_manager.set_script_var("right_side", ["1", "2", "3"])

        # Expand macro
        expanded = app.expand_macro("%pair(${left_side}, ${right_side})")
        
        expected = (
            "Left: A, Right: 1\n"
            "Left: B, Right: 2\n"
            "Left: , Right: 3"
        )
        assert expanded == expected

    def test_macro_expansion_with_mixed_array_and_scalar(self, app):
        """Test macro expansion where some arguments are arrays and others are scalars (replicated)"""
        app.macros["describe"] = {
            "params": ["category", "item"],
            "template": "Category: ${category}, Item: ${item}"
        }

        app.buffer_manager.set_script_var("fruit_list", ["apple", "banana"])

        # category is a scalar literal "Fruit", item is an array variable
        expanded = app.expand_macro("%describe(Fruit, ${fruit_list})")

        expected = (
            "Category: Fruit, Item: apple\n"
            "Category: Fruit, Item: banana"
        )
        assert expanded == expected

    def test_parser_array_declaration(self):
        """Test that the parser parses set var[] = [1, 2, 'three'] into the correct AST structure"""
        from src.chatybot.chatdsl_parse import Tokenizer, TParser
        
        script = "set my_arr[] = [1, 2, \"three\"]"
        tokenizer = Tokenizer()
        tokens = tokenizer.tokenize(script)
        parser = TParser(tokens)
        ast = parser.parse()

        assert len(ast) == 1
        assert ast[0]["type"] == "set_command"
        assert ast[0]["var"] == "my_arr[]"
        assert ast[0]["val"] == [1, 2, "three"]

    def test_parser_array_declaration_with_identifiers(self):
        """Test that the parser parses set var[] = [x, y] where elements are identifiers"""
        from src.chatybot.chatdsl_parse import Tokenizer, TParser
        
        script = "set my_arr[] = [x, y]"
        tokenizer = Tokenizer()
        tokens = tokenizer.tokenize(script)
        parser = TParser(tokens)
        ast = parser.parse()

        assert len(ast) == 1
        assert ast[0]["type"] == "set_command"
        assert ast[0]["var"] == "my_arr[]"
        assert ast[0]["val"] == ["x", "y"]

    @pytest.mark.anyio
    async def test_setvar_unquoted_placeholders(self, app):
        """Test /setvar command with unquoted placeholders containing multiline content, leading zeros, and quotes."""
        # 1. Set filebank1 content with potentially problematic characters (leading zeros, quotes, newlines)
        problematic_content = '0123\n"quoted text"\n007'
        app.buffer_manager.file_banks["filebank1"] = problematic_content

        # 2. Run /setvar with unquoted {filebank1}
        await app.handle_escape_command('/setvar testarray3[] = ["bob", "mary", "alice", {filebank1}]')
        
        array_data = app.buffer_manager.script_vars["testarray3"]
        assert array_data == ["bob", "mary", "alice", problematic_content]

        # 3. Set a script variable to {filebank1}
        await app.handle_escape_command('/setvar rpt {filebank1}')
        assert app.buffer_manager.script_vars["rpt"] == problematic_content

        # 4. Run /setvar with unquoted ${rpt}
        await app.handle_escape_command('/setvar testarray4[] = ["bob", "mary", "alice", ${rpt}]')
        
        array_data2 = app.buffer_manager.script_vars["testarray4"]
        assert array_data2 == ["bob", "mary", "alice", problematic_content]

    @pytest.mark.anyio
    async def test_script_command_unquoted_placeholders(self, app):
        """Test script command (set) with unquoted placeholders containing problematic characters."""
        problematic_content = '0123\n"quoted text"\n007'
        app.buffer_manager.file_banks["filebank1"] = problematic_content

        async def dummy_handler(prompt):
            return ""

        # Run script command set with unquoted {filebank1}
        await app.execute_script_command('set testarray5[] = ["bob", "mary", "alice", {filebank1}]', dummy_handler)
        
        array_data = app.buffer_manager.script_vars["testarray5"]
        assert array_data == ["bob", "mary", "alice", problematic_content]

        # Set a script variable to the filebank content
        await app.execute_script_command('set rpt = {filebank1}', dummy_handler)
        # Run script command set with unquoted ${rpt}
        await app.execute_script_command('set testarray6[] = ["bob", "mary", "alice", ${rpt}]', dummy_handler)
        
        array_data2 = app.buffer_manager.script_vars["testarray6"]
        assert array_data2 == ["bob", "mary", "alice", problematic_content]

    def test_get_variable_value_subscripts(self, app):
        """Test retrieving array elements using get_variable_value."""
        app.buffer_manager.script_vars["testarray"] = ["bob", "mary", "alice"]

        # Valid indexes
        assert app.buffer_manager.get_variable_value("testarray[0]") == "bob"
        assert app.buffer_manager.get_variable_value("testarray[1]") == "mary"
        assert app.buffer_manager.get_variable_value("testarray[-1]") == "alice"

        # Out of bounds
        with pytest.raises(IndexError, match="Index 10 out of bounds"):
            app.buffer_manager.get_variable_value("testarray[10]")

        # Subscripting non-array variable
        app.buffer_manager.script_vars["scalar"] = "hello"
        with pytest.raises(ValueError, match="is not an array"):
            app.buffer_manager.get_variable_value("scalar[0]")

        # Missing variable
        with pytest.raises(KeyError, match="Variable 'nonexistent' not found"):
            app.buffer_manager.get_variable_value("nonexistent[0]")

    def test_placeholder_replacement_subscripts(self, app):
        """Test placeholder replacement with array subscripts in prompts."""
        app.buffer_manager.script_vars["testarray"] = ["bob", "mary", "alice"]

        # Braced subscripts
        replaced = app.buffer_manager.replace_placeholders_legacy("Hello ${testarray[1]} and ${testarray[-1]}")
        assert replaced == "Hello mary and alice"

        # Unbraced subscripts
        replaced2 = app.buffer_manager.replace_placeholders_legacy("Hello $testarray[0] and $testarray[2]")
        assert replaced2 == "Hello bob and alice"

    def test_dump_variables_subscripts(self, app, capsys):
        """Test the /dump command with array subscripts."""
        app.buffer_manager.script_vars["testarray3"] = ["bob", "mary", "alice"]

        # Valid dump of subscript
        app.buffer_manager.dump_variables("testarray3[1]")
        captured = capsys.readouterr()
        assert "SCRIPT_VAR 'testarray3[1]': mary" in captured.out

        # Out of bounds dump
        app.buffer_manager.dump_variables("testarray3[10]")
        captured = capsys.readouterr()
        assert "Error: Index 10 out of bounds for array 'testarray3' of length 3." in captured.out

        # Non-array dump subscript
        app.buffer_manager.script_vars["scalar"] = "hello"
        app.buffer_manager.dump_variables("scalar[0]")
        captured = capsys.readouterr()
        assert "Error: Variable 'scalar' is not an array." in captured.out

        # Non-existent variable
        app.buffer_manager.dump_variables("nonexistent[0]")
        captured = capsys.readouterr()
        assert "Error: Variable 'nonexistent[0]' not found." in captured.out

    def test_dump_special_variables(self, app, capsys):
        """Test dumping special variables like LAST_RESPONSE and CHAT_HISTORY with/without braces."""
        app.chat_history = [("hello", "Sure! Here are five cities in Spain: ...")]

        # 1. Plain
        app.buffer_manager.dump_variables("LAST_RESPONSE", chat_history=app.chat_history)
        captured = capsys.readouterr()
        assert "SCRIPT_VAR 'LAST_RESPONSE': Sure! Here are five cities in Spain: ..." in captured.out

        # 2. Braced
        app.buffer_manager.dump_variables("{LAST_RESPONSE}", chat_history=app.chat_history)
        captured = capsys.readouterr()
        assert "SCRIPT_VAR 'LAST_RESPONSE': Sure! Here are five cities in Spain: ..." in captured.out

        # 3. Dollar Braced
        app.buffer_manager.dump_variables("${LAST_RESPONSE}", chat_history=app.chat_history)
        captured = capsys.readouterr()
        assert "SCRIPT_VAR 'LAST_RESPONSE': Sure! Here are five cities in Spain: ..." in captured.out

    @pytest.mark.anyio
    async def test_setvar_and_script_command_subscripts(self, app):
        """Test /setvar and script commands resolving subscripts."""
        app.buffer_manager.script_vars["testarray3"] = ["bob", "mary", "alice"]

        # 1. /setvar tst1 testarray3[1] - direct unprefixed subscript
        await app.handle_escape_command('/setvar tst1 testarray3[1]')
        assert app.buffer_manager.script_vars["tst1"] == "mary"

        # 2. /setvar tst2 ${testarray3[-1]}
        await app.handle_escape_command('/setvar tst2 ${testarray3[-1]}')
        assert app.buffer_manager.script_vars["tst2"] == "alice"

        # 3. Script command set (direct unprefixed subscript)
        async def dummy_handler(prompt):
            return ""
        await app.execute_script_command('set tst3 = testarray3[0]', dummy_handler)
        assert app.buffer_manager.script_vars["tst3"] == "bob"

        # 4. Script command set with braced subscript
        await app.execute_script_command('set tst4 = ${testarray3[1]}', dummy_handler)
        assert app.buffer_manager.script_vars["tst4"] == "mary"

    @pytest.mark.anyio
    async def test_mem_detail_command(self, app, capsys):
        """Test `/mem detail` output details."""
        app.buffer_manager.file_buffer = "line1\nline2"
        app.buffer_manager.script_vars["my_list"] = ["itemA", "itemB"]
        app.chat_history = [("hello", "hi there")]

        await app.handle_escape_command('/mem detail')
        captured = capsys.readouterr()

        assert "FILE_BUFFER" in captured.out
        assert "2 lines, 2 words" in captured.out
        assert "Preview: \"line1 line2...\"" in captured.out
        assert "my_list[] (2 items)" in captured.out
        assert "[0] 0.00 KB | itemA" in captured.out
        assert "CHAT_HISTORY" in captured.out
        assert "Total exchanges: 1" in captured.out
        assert "User: 0.00 KB | hello..." in captured.out

    @pytest.mark.anyio
    async def test_mem_debug_command(self, app, capsys):
        """Test `/mem debug` output details."""
        app.buffer_manager.script_vars["my_list"] = ["itemA", "itemB"]
        app.buffer_manager.script_vars["my_scalar"] = "hello"

        await app.handle_escape_command('/mem debug')
        captured = capsys.readouterr()

        assert "--- SCRIPT_VARS DEBUG METADATA ---" in captured.out
        assert "my_list" in captured.out
        assert "array" in captured.out
        assert "list" in captured.out
        assert "Length: 2 items" in captured.out
        assert "my_scalar" in captured.out
        assert "text" in captured.out
        assert "str" in captured.out
        assert "hello" in captured.out

    @pytest.mark.anyio
    async def test_execute_test17_chatdsl_script(self, app):
        """Test executing dsl_test/test17_array_memory_detail.chatdsl script."""
        import os
        script_path = os.path.join("dsl_test", "test17_array_memory_detail.chatdsl")
        
        assert os.path.exists(script_path)
        
        await app.execute_script(script_path)
        
        assert "testarray5" in app.buffer_manager.script_vars
        assert "testarray6" in app.buffer_manager.script_vars
        assert "testarray7" in app.buffer_manager.script_vars
        assert "testi" in app.buffer_manager.script_vars
        
        assert len(app.buffer_manager.script_vars["rpt"]) > 0
        
        assert app.buffer_manager.image_banks["imagebank1"].startswith("data:image/jpeg;base64,")
        assert app.buffer_manager.image_banks["imagebank2"].startswith("data:image/jpeg;base64,")
        
        arr5 = app.buffer_manager.script_vars["testarray5"]
        assert arr5[0] == "bob"
        assert arr5[1] == "mary"
        assert arr5[2] == "Jon"
        assert arr5[3] == "${rpt}"

        arr7 = app.buffer_manager.script_vars["testarray7"]
        assert len(arr7) == 4
        assert arr7[0] == "bob"
        assert arr7[1] == "mary"
        assert arr7[2] == "Jon"
        assert arr7[3] == app.buffer_manager.script_vars["rpt"]
