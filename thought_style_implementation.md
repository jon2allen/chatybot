# Thought Style Implementation Guide

## Overview
This document describes the implementation of the `/thoughtstyle` command for Gemma-4 model support.

## Command Specification

### Basic Usage
```bash
/thoughtstyle [none|gemma4]
```

### Supported Values
- `none` - Default behavior, no special formatting (default)
- `gemma4` - Enable Gemma-4 specific prompt formatting
- `nanbeige` - Enable Nanbeige specific prompt formatting
- `nanbeige_code` - Enable Nanbeige code-specific prompt formatting

### Examples
```bash
# Enable Gemma-4 formatting
/thoughtstyle gemma4

# Enable Nanbeige formatting
/thoughtstyle nanbeige

# Enable Nanbeige code formatting
/thoughtstyle nanbeige_code

# Disable special formatting  
/thoughtstyle none

# Check current setting
/thoughtstyle
```

## Activation Conditions

The Gemma-4 specific formatting is applied when **ALL** of these conditions are met:

1. **Reasoning is off**: `/reasoning off` (reasoning_mode = False)
2. **Thought style is gemma4**: `/thoughtstyle gemma4` (thoughtstyle = "gemma4")
3. **Using Gemma-4 model**: Model name contains "gemma-4"

## Effects When Activated

### Gemma-4 Style
When all conditions are met, the system modifies the prompt structure:

#### System Prompt
**Preserves existing system prompts and appends Gemma-4 specific instructions:**

- **If no existing system prompt**: Creates default + gemma4 instructions
  ```
  you are a helpful assitant. disable reasoning and thought. </thought off>
  ```

- **If existing system prompt**: Appends gemma4 instructions
  ```
  [existing_prompt] disable reasoning and thought. </thought off>
  ```

#### User Prompt
Prefixes user messages with:
```
<no thought> 
```

### Nanbeige Style
When activated, wraps user prompts with Nanbeige-specific formatting:

#### User Prompt
Transforms user messages as follows:
```
Input: "describe Zhou enlai in 2 short paragraphs."
Output: "<think> </think> describe Zhou enlai in 2 short paragraphs. response answer only, final answer only. skip thought generation /no_think /response"
```

**Key characteristics:**
- No changes to system prompt
- Works with any model (no model-specific restrictions)
- Always applied when thoughtstyle is set to "nanbeige"

### Nanbeige Code Style
When activated, wraps user prompts with Nanbeige code-specific formatting:

#### User Prompt
Transforms user messages as follows:
```
Input: "give me an Pascal language version of an array reverse"
Output: "<think></think> give me an Pascal language version of an array reverse, no comentary or explaination. use response tokens only. code only, code only"
```

**Key characteristics:**
- No changes to system prompt
- Works with any model (no model-specific restrictions)
- Always applied when thoughtstyle is set to "nanbeige_code"
- Designed for code generation with minimal commentary
- **Note:** May only generate thinking tokens - this is an artifact/quirk of the model

## Example Payload

**Input**: `give me a LISP program that mimics the hindu shuffle in cards`

**Resulting Payload**:
```json
{
  "model": "gemma-4-26b-a4b-it",
  "messages": [
    {
      "role": "system",
      "content": "you are a helpful assitant. disable reasoning and thought. </thought off>"
    },
    {
      "role": "user",
      "content": "<no thought> give me a LISP program that mimics the hindu shuffle in cards"
    }
  ],
  "temperature": 0.7
}
```

## Implementation Details

### Files Modified

1. **src/chatybot/chatybot_app.py**
   - Added `self.thoughtstyle` state variable
   - Added command handler for `/thoughtstyle`
   - Added logic in `chat_completion` method
   - Updated help text

2. **src/chatybot/chatdsl_parse.py**
   - Added "thoughtstyle" to `VALID_ESCAPE_COMMANDS`

3. **README.md**
   - Added command documentation

### Code Flow

```
User Input → Command Parser → State Management → Chat Completion
                              ↓
                    (thoughtstyle state stored)
                              ↓
            (applied in chat_completion when conditions met)
```

## Testing

### Test Coverage
- ✅ Command parsing and validation
- ✅ State management
- ✅ Integration with reasoning mode
- ✅ Model detection
- ✅ System prompt modification
- ✅ User prompt prefixing
- ✅ Error handling

### Test Files
- `test_thoughtstyle.py` - Basic functionality
- `test_thoughtstyle_integration.py` - Integration tests
- `test_end_to_end.py` - Complete workflow

## Compatibility

- **Backward Compatible**: Default value is "none", preserving existing behavior
- **Model-Specific**: Only affects Gemma-4 models when conditions are met
- **Non-Intrusive**: Other models and configurations work exactly as before

## Troubleshooting

### Command not recognized
- Ensure "thoughtstyle" is in `VALID_ESCAPE_COMMANDS` set
- Check for typos in command name

### Formatting not applied
- Verify `/reasoning off` is set
- Verify `/thoughtstyle gemma4` is set
- Confirm using a Gemma-4 model (name contains "gemma-4")

### Invalid value error
- Only "none" and "gemma4" are supported
- Command is case-insensitive

## Future Enhancements

Potential extensions:
- Additional thought styles for other models
- Custom thought style configurations
- Model-specific thought style presets

## References

- Based on requirements from `gemma_thought.txt`
- Follows existing escape command patterns
- Compatible with current Gemma-4 API specifications