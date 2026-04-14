#!/usr/bin/env python3
"""
Parsley-based Macro System - Fixed Version
Builds up the macro grammar step by step
"""

import sys
from parsley import makeGrammar

# Test 1: Simple macro definition with string template
print("Testing macro definition with string template...")
try:
    macro_grammar = makeGrammar("""
    macro_def = 'def' name:ident '(' param:ident ')' '=' template:string -> (name, param, template)
    ident = <letter (letter | digit | '_')*>
    letter = 'a' | 'b' | 'c' | 'd' | 'e' | 'f' | 'g' | 'h' | 'i' | 'j' | 'k' | 'l' | 'm' | 'n' | 'o' | 'p' | 'q' | 'r' | 's' | 't' | 'u' | 'v' | 'w' | 'x' | 'y' | 'z' | 'A' | 'B' | 'C' | 'D' | 'E' | 'F' | 'G' | 'H' | 'I' | 'J' | 'K' | 'L' | 'M' | 'N' | 'O' | 'P' | 'Q' | 'R' | 'S' | 'T' | 'U' | 'V' | 'W' | 'X' | 'Y' | 'Z'
    digit = '0' | '1' | '2' | '3' | '4' | '5' | '6' | '7' | '8' | '9'
    string = '"' <(~'"' anything)*> '"' -> ''.join
    """, {})
    
    test_line = 'def test(param) = "template with {param}"'
    result = macro_grammar(test_line).macro_def()
    print(f"Macro definition works: {result}")
    
except Exception as e:
    print(f"Macro definition failed: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Macro definition with multiple parameters
print("\nTesting macro definition with multiple parameters...")
try:
    multi_param_grammar = makeGrammar("""
    macro_def = 'def' name:ident '(' params:param_list? ')' '=' template:string -> (name, params or [], template)
    param_list = param (',' param)* -> list
    param = ident
    ident = <letter (letter | digit | '_')*>
    letter = 'a' | 'b' | 'c' | 'd' | 'e' | 'f' | 'g' | 'h' | 'i' | 'j' | 'k' | 'l' | 'm' | 'n' | 'o' | 'p' | 'q' | 'r' | 's' | 't' | 'u' | 'v' | 'w' | 'x' | 'y' | 'z' | 'A' | 'B' | 'C' | 'D' | 'E' | 'F' | 'G' | 'H' | 'I' | 'J' | 'K' | 'L' | 'M' | 'N' | 'O' | 'P' | 'Q' | 'R' | 'S' | 'T' | 'U' | 'V' | 'W' | 'X' | 'Y' | 'Z'
    digit = '0' | '1' | '2' | '3' | '4' | '5' | '6' | '7' | '8' | '9'
    string = '"' <(~'"' anything)*> '"' -> ''.join
    """, {})
    
    test_line1 = 'def test(param) = "template with {param}"'
    test_line2 = 'def test(param1, param2) = "template with {param1} and {param2}"'
    
    result1 = multi_param_grammar(test_line1).macro_def()
    result2 = multi_param_grammar(test_line2).macro_def()
    
    print(f"Single param works: {result1}")
    print(f"Multiple params work: {result2}")
    
except Exception as e:
    print(f"Multi-param macro definition failed: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Macro invocation grammar
print("\nTesting macro invocation...")
try:
    invocation_grammar = makeGrammar("""
    macro_call = '%' name:ident '(' args:arg_list? ')' -> (name, args or [])
    arg_list = arg (',' arg)* -> list
    arg = string | ident
    ident = <letter (letter | digit | '_')*>
    letter = 'a' | 'b' | 'c' | 'd' | 'e' | 'f' | 'g' | 'h' | 'i' | 'j' | 'k' | 'l' | 'm' | 'n' | 'o' | 'p' | 'q' | 'r' | 's' | 't' | 'u' | 'v' | 'w' | 'x' | 'y' | 'z' | 'A' | 'B' | 'C' | 'D' | 'E' | 'F' | 'G' | 'H' | 'I' | 'J' | 'K' | 'L' | 'M' | 'N' | 'O' | 'P' | 'Q' | 'R' | 'S' | 'T' | 'U' | 'V' | 'W' | 'X' | 'Y' | 'Z'
    digit = '0' | '1' | '2' | '3' | '4' | '5' | '6' | '7' | '8' | '9'
    string = '"' <(~'"' anything)*> '"' -> ''.join
    """, {})
    
    test_call1 = '%test(arg1)'
    test_call2 = '%test("hello world")'
    test_call3 = '%test(arg1, arg2)'
    
    result1 = invocation_grammar(test_call1).macro_call()
    result2 = invocation_grammar(test_call2).macro_call()
    result3 = invocation_grammar(test_call3).macro_call()
    
    print(f"Single arg call works: {result1}")
    print(f"String arg call works: {result2}")
    print(f"Multiple arg call works: {result3}")
    
except Exception as e:
    print(f"Macro invocation failed: {e}")
    import traceback
    traceback.print_exc()

print("\nParsley macro system tests complete!")

# Now create a complete macro processor using Parsley
class ParsleyMacroProcessor:
    def __init__(self):
        # Grammar for macro definitions
        self.definition_grammar = makeGrammar("""
        macro_def = 'def' name:ident '(' params:param_list? ')' '=' template:string -> (name, params or [], template)
        param_list = param (',' param)* -> list
        param = ident
        ident = <letter (letter | digit | '_')*>
        letter = 'a' | 'b' | 'c' | 'd' | 'e' | 'f' | 'g' | 'h' | 'i' | 'j' | 'k' | 'l' | 'm' | 'n' | 'o' | 'p' | 'q' | 'r' | 's' | 't' | 'u' | 'v' | 'w' | 'x' | 'y' | 'z' | 'A' | 'B' | 'C' | 'D' | 'E' | 'F' | 'G' | 'H' | 'I' | 'J' | 'K' | 'L' | 'M' | 'N' | 'O' | 'P' | 'Q' | 'R' | 'S' | 'T' | 'U' | 'V' | 'W' | 'X' | 'Y' | 'Z'
        digit = '0' | '1' | '2' | '3' | '4' | '5' | '6' | '7' | '8' | '9'
        string = '"' <(~'"' anything)*> '"' -> ''.join
        """, {})
        
        # Grammar for macro invocations
        self.invocation_grammar = makeGrammar("""
        macro_call = '%' name:ident '(' args:arg_list? ')' -> (name, args or [])
        arg_list = arg (',' arg)* -> list
        arg = string | ident
        ident = <letter (letter | digit | '_')*>
        letter = 'a' | 'b' | 'c' | 'd' | 'e' | 'f' | 'g' | 'h' | 'i' | 'j' | 'k' | 'l' | 'm' | 'n' | 'o' | 'p' | 'q' | 'r' | 's' | 't' | 'u' | 'v' | 'w' | 'x' | 'y' | 'z' | 'A' | 'B' | 'C' | 'D' | 'E' | 'F' | 'G' | 'H' | 'I' | 'J' | 'K' | 'L' | 'M' | 'N' | 'O' | 'P' | 'Q' | 'R' | 'S' | 'T' | 'U' | 'V' | 'W' | 'X' | 'Y' | 'Z'
        digit = '0' | '1' | '2' | '3' | '4' | '5' | '6' | '7' | '8' | '9'
        string = '"' <(~'"' anything)*> '"' -> ''.join
        """, {})
        
        self.macros = {}
    
    def load_macros(self, macro_file):
        """Load macro definitions from file using Parsley"""
        try:
            with open(macro_file, 'r') as f:
                content = f.read()
            
            # Parse each line for macro definitions
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('def ') and '=' in line:
                    try:
                        parsed = self.definition_grammar(line).macro_def()
                        name, params, template = parsed
                        self.macros[name] = {'params': params, 'template': template}
                        print(f"Loaded macro: {name} with {len(params)} parameters")
                    except Exception as e:
                        print(f"Warning: Could not parse macro definition: {line}")
                        print(f"Error: {e}")
        except FileNotFoundError:
            print(f"Error: Macro file {macro_file} not found")
            sys.exit(1)
        except Exception as e:
            print(f"Error loading macros: {e}")
            sys.exit(1)
    
    def expand_macro(self, macro_call):
        """Expand a single macro call using Parsley"""
        try:
            # Parse the macro invocation
            parsed = self.invocation_grammar(macro_call).macro_call()
            name, args = parsed
            
            # Get macro definition
            if name not in self.macros:
                return f"ERROR: Macro '{name}' not defined"
            
            macro = self.macros[name]
            
            # Check argument count
            if len(args) != len(macro['params']):
                return f"ERROR: Macro '{name}' expects {len(macro['params'])} arguments, got {len(args)}"
            
            # Create parameter mapping
            param_mapping = {}
            for param, arg in zip(macro['params'], args):
                param_mapping[param] = arg
            
            # Format the template
            try:
                expanded = macro['template'].format(**param_mapping)
                return expanded
            except Exception as e:
                return f"ERROR: Format error in macro '{name}': {e}"
                
        except Exception as e:
            return f"ERROR: Could not parse macro call '{macro_call}': {e}"

# Test the complete system
print("\nTesting complete Parsley macro system...")
try:
    processor = ParsleyMacroProcessor()
    
    # Test loading a simple macro
    test_macro_file = "test_macros_simple.chatdsl"
    with open(test_macro_file, 'w') as f:
        f.write('def test(param) = "Hello {param}!"\n')
        f.write('def multi(a, b) = "Values: {a} and {b}"\n')
    
    processor.load_macros(test_macro_file)
    
    # Test expanding macros
    result1 = processor.expand_macro('%test(world)')
    result2 = processor.expand_macro('%multi(1, 2)')
    
    print(f"Macro expansion 1: {result1}")
    print(f"Macro expansion 2: {result2}")
    
    print("\nComplete Parsley macro system works!")
    
except Exception as e:
    print(f"Complete system test failed: {e}")
    import traceback
    traceback.print_exc()