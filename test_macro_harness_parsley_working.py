#!/usr/bin/env python3
"""
Macro Expansion Test Harness using Parsley (Working Version)
Tests the macro system with Parsley grammar parsing
"""

import sys
import re
from parsley import makeGrammar

class MacroProcessor:
    def __init__(self):
        # Simple grammar for macro definitions using Parsley
        # Based on Parsley tutorial examples
        self.definition_grammar = makeGrammar("""
        macro_def = 'def' ws ident:name ws '(' ws param_list?:params ws ')' ws '=' ws string:template -> (name, params or [], template)
        param_list = param:p (ws ',' ws param)*:ps -> [p] + ps
        param = ident
        ident = <letter (letter | digit | '_')*>
        letter = 'a' | 'b' | 'c' | 'd' | 'e' | 'f' | 'g' | 'h' | 'i' | 'j' | 'k' | 'l' | 'm' | 'n' | 'o' | 'p' | 'q' | 'r' | 's' | 't' | 'u' | 'v' | 'w' | 'x' | 'y' | 'z' | 'A' | 'B' | 'C' | 'D' | 'E' | 'F' | 'G' | 'H' | 'I' | 'J' | 'K' | 'L' | 'M' | 'N' | 'O' | 'P' | 'Q' | 'R' | 'S' | 'T' | 'U' | 'V' | 'W' | 'X' | 'Y' | 'Z'
        digit = '0' | '1' | '2' | '3' | '4' | '5' | '6' | '7' | '8' | '9'
        string = '"' <(~'"' anything)*>:s '"' -> s
        ws = ' '*
        """, {})
        
        # Simple grammar for macro invocations using Parsley
        self.invocation_grammar = makeGrammar("""
        macro_call = '%' ws ident:name ws '(' ws arg_list?:args ws ')' -> (name, args or [])
        arg_list = arg:a (ws ',' ws arg)*:rest -> [a] + rest
        arg = string | version | ident | number
        version = <digit+ ('.' (digit | ident))+>
        number = <digit+>
        string = '"' <(~'"' anything)*>:s '"' -> s
        ident = <letter (letter | digit | '_')*>
        letter = 'a' | 'b' | 'c' | 'd' | 'e' | 'f' | 'g' | 'h' | 'i' | 'j' | 'k' | 'l' | 'm' | 'n' | 'o' | 'p' | 'q' | 'r' | 's' | 't' | 'u' | 'v' | 'w' | 'x' | 'y' | 'z' | 'A' | 'B' | 'C' | 'D' | 'E' | 'F' | 'G' | 'H' | 'I' | 'J' | 'K' | 'L' | 'M' | 'N' | 'O' | 'P' | 'Q' | 'R' | 'S' | 'T' | 'U' | 'V' | 'W' | 'X' | 'Y' | 'Z'
        digit = '0' | '1' | '2' | '3' | '4' | '5' | '6' | '7' | '8' | '9'
        ws = ' '*
        """, {})
        
        self.macros = {}
        self.variables = {}
    
    def load_macros(self, macro_file):
        """Load macro definitions from file using Parsley"""
        try:
            with open(macro_file, 'r') as f:
                content = f.read()
            
            # Parse each line for macro definitions using Parsley
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
            # Parse the macro invocation using Parsley
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
    
    def process_line(self, line):
        """Process a single line, expanding any macros"""
        if line.startswith('%'):
            # This is a macro call - use Parsley to parse it
            return self.expand_macro(line.strip())
        elif line.startswith('set ') and '=' in line:
            # This is a variable assignment
            parts = line.split('=', 1)
            var_name = parts[0].replace('set', '').strip()
            var_value = parts[1].strip().strip('"').strip("'")
            self.variables[var_name] = var_value
            return f"# SET {var_name} = {var_value}"
        else:
            # Regular line, check for variable substitution
            result = line
            for var_name, var_value in self.variables.items():
                result = result.replace(f'${{{var_name}}}', var_value)
            return result
    
    def process_file(self, input_file):
        """Process a chat script file"""
        try:
            with open(input_file, 'r') as f:
                content = f.read()
            
            # Handle multiline blocks
            lines = content.split('\n')
            output_lines = []
            in_multiline = False
            multiline_buffer = []
            
            for line in lines:
                if line.strip() == '/multiline':
                    in_multiline = True
                    multiline_buffer = []
                    continue
                elif line.strip() == ';' and in_multiline:
                    in_multiline = False
                    # Process the multiline buffer
                    for ml_line in multiline_buffer:
                        output_lines.append(self.process_line(ml_line))
                    continue
                
                if in_multiline:
                    multiline_buffer.append(line)
                else:
                    output_lines.append(self.process_line(line))
            
            return '\n'.join(output_lines)
            
        except FileNotFoundError:
            print(f"Error: Input file {input_file} not found")
            sys.exit(1)
        except Exception as e:
            print(f"Error processing file: {e}")
            sys.exit(1)

def main():
    if len(sys.argv) != 3:
        print("Usage: python test_macro_harness_parsley_working.py <macro_file> <test_script>")
        print("Example: python test_macro_harness_parsley_working.py macro.chatdsl test_macros.chatdsl")
        sys.exit(1)
    
    macro_file = sys.argv[1]
    test_script = sys.argv[2]
    
    print(f"Loading macros from {macro_file} using Parsley...")
    processor = MacroProcessor()
    processor.load_macros(macro_file)
    
    print(f"\nProcessing test script {test_script} using Parsley...")
    result = processor.process_file(test_script)
    
    print("\n" + "="*60)
    print("MACRO EXPANSION RESULTS (Parsley-based):")
    print("="*60)
    print(result)
    
    # Save results to file
    output_file = "macro_expansion_results_parsley.txt"
    with open(output_file, 'w') as f:
        f.write(result)
    
    print(f"\nResults saved to {output_file}")
    
    # Basic statistics
    original_lines = len(open(test_script).readlines())
    expanded_lines = len(result.split('\n'))
    
    print(f"\nStatistics:")
    print(f"  Original lines: {original_lines}")
    print(f"  Expanded lines: {expanded_lines}")
    print(f"  Macros loaded: {len(processor.macros)}")
    print(f"  Parser: Parsley grammar-based")

if __name__ == "__main__":
    main()