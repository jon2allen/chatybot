# Macro Feature Implementation Plan

## Overview
Implement a macro system using the parsley module that allows users to define reusable text snippets in a `macros.dsl` file and expand them in chat scripts using `%macro_name(args)` syntax.

## Scope

### In Scope
- Create `macros.dsl` file format and parsing logic
- Implement macro definition syntax: `def macro_name(params) = "template {params}"`
- Implement macro invocation syntax: `%macro_name(args)`
- Process macros during script execution
- Support for `/multiline` chat commands
- Integration with existing chat DSL system

### Out of Scope
- Nested macro definitions
- Recursive macro expansion
- Macro importing/exporting between files
- Complex control flow in macros

## Technical Design

### File Structure
```
chatybot/
├── macros.dsl              # Macro definitions
├── parsley_module.py       # Parsley grammar and processing
├── chat_processor.py       # Chat script processing
└── ...
```

### Macro Definition Syntax
```
def language(type) = "you are an expert in {type} language"
def greeting(name) = "Hello {name}! Welcome to our system."
```

### Macro Invocation Syntax
```
%language(pascal)
%greeting(John)
```

### Expansion Examples
```
Input:  %language(pascal)
Output: you are an expert in pascal language

Input:  %greeting(John)
Output: Hello John! Welcome to our system.
```

## Implementation Steps

1. **Create parsley grammar for macro definitions**
   ```python
   # Grammar for macro definitions
   macro_def = 'def' ws name:ident '(' params:param_list? ')' ws '=' ws template:string -> (name, params or [], template)
   param_list = param (',' ws param)* -> list
   param = ident
   ident = letter (letter | digit)*
   letter = anything:x ?(x.isalpha() or x == '_') -> x
   digit = anything:x ?(x.isdigit()) -> x
   string = '"' (anything:x ?(x != '"') -> x)* '"' -> ''.join
   ws = (' ' | '\t' | '\n')*
   ```

2. **Create parsley grammar for macro invocations**
   ```python
   # Grammar for macro invocations
   macro_call = '%' name:ident '(' args:arg_list? ')' -> (name, args or [])
   arg_list = arg (',' ws arg)* -> list
   arg = string | ident | number
   number = digit+
   ```

3. **Implement macro processor**
   - Load macros from `macros.dsl` file using parsley grammar
   - Process chat scripts to find and expand macros
   - Handle string formatting with provided arguments using Python's `.format()` method

4. **Integrate with chat system**
   - Modify script execution to pre-process macros before other DSL processing
   - Support macro expansion in `/multiline` commands by processing each line
   - Ensure macros work with existing chat DSL features through proper ordering

5. **Error handling**
   - Undefined macro errors with clear messages
   - Argument count mismatches with expected vs actual counts
   - Circular reference detection (basic) using expansion tracking
   - File not found/parse errors with helpful error messages

## Testing Plan

### Test Cases
1. Basic macro definition and invocation
   ```python
   # Test case: def language(type) = "you are an expert in {type} language"
   # Invocation: %language(pascal)
   # Expected: "you are an expert in pascal language"
   ```

2. Multiple parameters in macros
   ```python
   # Test case: def greeting(name, title) = "Hello {title} {name}!"
   # Invocation: %greeting(John, Dr)
   # Expected: "Hello Dr John!"
   ```

3. Macro with no parameters
   ```python
   # Test case: def signature = "Best regards,\nThe Team"
   # Invocation: %signature()
   # Expected: "Best regards,\nThe Team"
   ```

4. Undefined macro error
   ```python
   # Test case: %nonexistent(arg)
   # Expected: Error message "Macro 'nonexistent' not defined"
   ```

5. Argument count mismatch error
   ```python
   # Test case: def single_arg(x) = "{x}"
   # Invocation: %single_arg(a, b)
   # Expected: Error message "Expected 1 argument, got 2"
   ```

6. Macro expansion in multiline chat
   ```python
   # Test case: /multiline\n%language(python)\n%language(java)
   # Expected: Both macros expanded on separate lines
   ```

7. Multiple macros in same script
   ```python
   # Test case: %greeting(World) and %signature()
   # Expected: Both macros expanded correctly
   ```

8. Macro with special characters in template
   ```python
   # Test case: def special = "Price: $100\nDiscount: 20%"
   # Invocation: %special()
   # Expected: "Price: $100\nDiscount: 20%"
   ```

### Test Files
- `test_macros.dsl` - Sample macro definitions
  ```
  def language(type) = "you are an expert in {type} language"
  def greeting(name) = "Hello {name}! Welcome to our system."
  def signature = "Best regards,\nThe Team"
  ```

- `test_chat_script.chat` - Test script with macro invocations
  ```
  %language(pascal)
  %greeting(John)
  %signature()
  ```

- `test_macro_processor.py` - Unit tests for processor

## Timeline

1. Day 1: Research parsley module, create basic grammar
2. Day 2: Implement macro definition parsing
3. Day 3: Implement macro invocation and expansion
4. Day 4: Integration with chat system
5. Day 5: Testing and bug fixing
6. Day 6: Documentation and examples

## Dependencies

- Python 3.8+
- Parsley module
- Existing chatybot codebase

## Risks and Mitigations

1. **Parsley learning curve**: Allocate extra time for grammar development
2. **Integration issues**: Test incrementally with existing system
3. **Performance**: Profile macro expansion for large scripts
4. **Syntax conflicts**: Ensure macro syntax doesn't conflict with existing DSL

## Success Criteria

- Macros can be defined in `macros.dsl` file
- Macros can be invoked using `%macro_name(args)` syntax
- Macro expansion works correctly during script execution
- All test cases pass
- No breaking changes to existing functionality
- Documentation is complete and accurate

## Open Questions

1. Should macros support default parameter values?
2. Should there be a limit on macro expansion depth?
3. How should macro definition errors be reported to users?
4. Should macros be able to call other macros?
