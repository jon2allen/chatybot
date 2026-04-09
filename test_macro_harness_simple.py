#!/usr/bin/env python3
"""
Simplified Macro Expansion Test Harness
Tests the macro system with basic parsing
"""

import sys
import re

class MacroProcessor:
    def __init__(self):
        self.macros = {}
        self.variables = {}
    
    def load_macros(self, macro_file):
        """Load macro definitions from file"""
        try:
            with open(macro_file, 'r') as f:
                content = f.read()
            
            # Simple regex parsing for macro definitions
            macro_pattern = r'def\s+(\w+)\(([^)]*)\)\s*=\s*"([^"]*)"'
            
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('def ') and '=' in line:
                    match = re.match(macro_pattern, line)
                    if match:
                        name = match.group(1)
                        params_str = match.group(2)
                        template = match.group(3)
                        
                        # Parse parameters
                        params = []
                        if params_str.strip():
                            params = [p.strip() for p in params_str.split(',')]
                        
                        self.macros[name] = {'params': params, 'template': template}
                        print(f"Loaded macro: {name} with {len(params)} parameters")
                    else:
                        print(f"Warning: Could not parse macro definition: {line}")
        except FileNotFoundError:
            print(f"Error: Macro file {macro_file} not found")
            sys.exit(1)
        except Exception as e:
            print(f"Error loading macros: {e}")
            sys.exit(1)
    
    def expand_macro(self, macro_call):
        """Expand a single macro call"""
        try:
            # Simple regex parsing for macro invocations
            call_pattern = r'%(\w+)\(([^)]*)\)'
            match = re.match(call_pattern, macro_call.strip())
            
            if not match:
                return f"ERROR: Could not parse macro call '{macro_call}'"
            
            name = match.group(1)
            args_str = match.group(2)
            
            # Get macro definition
            if name not in self.macros:
                return f"ERROR: Macro '{name}' not defined"
            
            macro = self.macros[name]
            
            # Parse arguments
            args = []
            if args_str.strip():
                # Handle quoted arguments
                args = []
                current_arg = ''
                in_quotes = False
                quote_char = ''
                
                for char in args_str:
                    if char in ('"', "'"):
                        if in_quotes:
                            if char == quote_char:
                                in_quotes = False
                                args.append(current_arg)
                                current_arg = ''
                        else:
                            in_quotes = True
                            quote_char = char
                    elif char == ',' and not in_quotes:
                        if current_arg.strip():
                            args.append(current_arg.strip())
                        current_arg = ''
                    else:
                        current_arg += char
                
                if current_arg.strip():
                    args.append(current_arg.strip())
            
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
            # This is a macro call
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
        print("Usage: python test_macro_harness_simple.py <macro_file> <test_script>")
        print("Example: python test_macro_harness_simple.py macro.chatdsl test_macros.chatdsl")
        sys.exit(1)
    
    macro_file = sys.argv[1]
    test_script = sys.argv[2]
    
    print(f"Loading macros from {macro_file}...")
    processor = MacroProcessor()
    processor.load_macros(macro_file)
    
    print(f"\nProcessing test script {test_script}...")
    result = processor.process_file(test_script)
    
    print("\n" + "="*60)
    print("MACRO EXPANSION RESULTS:")
    print("="*60)
    print(result)
    
    # Save results to file
    output_file = "macro_expansion_results.txt"
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

if __name__ == "__main__":
    main()