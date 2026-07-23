# Script Parameter Implementation

## Overview

This document describes the implementation of parameter passing functionality for the `/script` command in Chatybot. The feature allows scripts to receive up to three variables (x, y, z) that can be accessed within the script execution context.

## Feature Description

The `/script` command now supports optional parameters that are passed to the script as variables:

```bash
/script <file> [x="value"] [y="value"] [z="value"]
```

### Key Features

- **Parameter Variables**: x, y, z
- **Quoted Values**: Support for values with spaces: `x="hello world"`
- **Unquoted Values**: Support for simple values: `x=hello`
- **Variable Access**: Scripts access parameters using `${x}`, `${y}`, `${z}` syntax
- **Backward Compatibility**: Existing scripts without parameters continue to work

## Implementation Details

### Files Modified

1. **`src/chatybot/chatybot_app.py`** - Main implementation
   - Lines 1293-1330: Updated `/script` command handler
   - Line 1439: Updated help text

### Technical Implementation

#### Parameter Parsing Logic

The implementation uses regex-based parameter extraction:

```python
# Regex pattern for parameter matching
param_pattern = r'(^|\s+)([xyz])\s*=\s*("[^"]*"|'"'"'[^'"'"']*'"'"'|\S+)'
```

This pattern matches:
- `(^|\s+)`: Start of string or whitespace (separator)
- `([xyz])`: Variable name (x, y, or z)
- `\s*=\s*`: Equals sign with optional whitespace
- `("[^"]*"|'[^']*'|\S+)`: Value that is either:
  - Quoted string: `"..."` or `'...'`
  - Unquoted single word: `\S+`

#### Parameter Extraction Process

1. **Command Parsing**: Extract script path and remaining command string
2. **Script Path Extraction**: Handle both quoted and unquoted script paths
3. **Parameter Extraction**: Use regex to find all parameter assignments
4. **Variable Setup**: Set extracted parameters as script variables
5. **Script Execution**: Execute script with variables available

#### Code Flow

```python
# Extract script path and parameters
remaining_command = command[len(cmd):].strip()
script_path_match = re.match(r'("[^"]*"|'"'"'[^'"'"']*'"'"'|\S+)', remaining_command)

if script_path_match:
    actual_script_path = script_path_match.group(1).strip('"\'')
    params_string = remaining_command[len(script_path_match.group(1)):].strip()

# Extract parameters using regex
params = {}
for match in re.finditer(param_pattern, params_string):
    var_name = match.group(2)  # Group 2 is the variable name
    var_value = match.group(3).strip('"\'')  # Remove surrounding quotes
    params[var_name] = var_value

# Set parameters as script variables
for var_name, var_value in params.items():
    self.buffer_manager.set_script_var(var_name, var_value)

# Execute script
await self.execute_script(actual_script_path)
```

## Usage Examples

### Basic Usage

```bash
# Pass all three parameters
/script myscript.dsl x="hello world" y=test z="123"

# Pass only some parameters
/script myscript.dsl x=hello z=world

# No parameters (backward compatible)
/script myscript.dsl
```

### Script Example

```bash
# test_script.dsl
/echo "Received parameters:"
/echo "x = ${x}"
/echo "y = ${y}"
/echo "z = ${z}"

/if "${x}"
  /echo "x parameter is set!"
/endif
```

### Command Line Usage

```bash
# Execute script with parameters
/script test_script.dsl x="Hello World" y=test z=123

# Execute script with quoted path and parameters
/script "my script.dsl" x=value1 y="value with spaces"
```

## Testing

### Test Cases Covered

1. **All Parameters**: `x="hello" y="world" z="123"`
2. **Partial Parameters**: `x=hello z=world`
3. **Quoted Values**: `x="hello world" y="test value"`
4. **Unquoted Values**: `x=hello y=world`
5. **Mixed Quoting**: `x="quoted" y=unquoted`
6. **No Parameters**: Backward compatibility
7. **Script Path with Spaces**: `"script name.dsl" x=value`

### Test Results

All test cases pass successfully:
- ✅ Parameter extraction works correctly
- ✅ Variable setting works correctly  
- ✅ Variable access within scripts works
- ✅ Backward compatibility maintained
- ✅ Error handling for malformed commands

## Backward Compatibility

The implementation maintains full backward compatibility:

- Existing `/script <file>` commands work unchanged
- No parameters = no variables set = existing behavior
- Script variable system remains unchanged
- Help text updated to show new functionality

## Error Handling

The implementation includes robust error handling:

- Malformed parameter syntax is ignored gracefully
- Missing parameters don't cause errors
- Script execution continues even if parameter parsing fails
- Clear usage message for incorrect command syntax

## Performance Impact

Minimal performance impact:
- Regex parsing only occurs during `/script` command execution
- No impact on other commands or normal operation
- Variable setting uses existing efficient mechanisms

## Future Enhancements

Possible future improvements:

1. **More Variables**: Support for additional variables beyond x, y, z
2. **Type Conversion**: Automatic type conversion for numeric values
3. **Parameter Validation**: Optional parameter validation
4. **Default Values**: Support for default parameter values
5. **Named Parameters**: More flexible parameter naming

## Conclusion

The script parameter implementation provides a clean, backward-compatible way to pass variables to scripts. It leverages the existing variable system and maintains the simplicity of the Chatybot command interface while adding powerful scripting capabilities.