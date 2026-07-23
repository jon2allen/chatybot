# Mistral AI Reasoning Formats: Comprehensive Comparison

## Overview

Mistral AI offers multiple approaches to reasoning and structured output, each serving different use cases. This document provides a comprehensive comparison of the three main formats: **Structured Content (List Format)**, **`<think>` Tags**, and **`<thought>` Tags**.

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Structured Content (List Format) - The Novel Approach](#1-structured-content-list-format---the-novel-approach)
3. [Think Tags (`<think>`)](#2-think-tags)
4. [Thought Tags (`<thought>`)](#3-thought-tags)
5. [Detailed Comparison Matrix](#detailed-comparison-matrix)
6. [When to Use Each Format](#when-to-use-each-format)
7. [Technical Implementation Details](#technical-implementation-details)
8. [Real-World Examples](#real-world-examples)
9. [Historical Context & Evolution](#historical-context--evolution)
10. [Best Practices](#best-practices)
11. [Migration Guide](#migration-guide)

---

## Executive Summary

Mistral AI has evolved through **three distinct reasoning formats**, each representing a different philosophy:

| Format | Official Support | Innovation Level | Primary Use Case |
|--------|-----------------|------------------|------------------|
| **Structured Content (List)** | ✅ Yes | ⭐⭐⭐⭐⭐ **Novel** | API responses with `reasoning_effort="high"` |
| **`<think>` Tags** | ✅ Yes | ⭐⭐⭐ | Text-based reasoning markers |
| **`<thought>` Tags** | ❌ No (Community) | ⭐⭐ | Legacy/custom implementations |

**Key Insight**: Mistral's **Structured Content (List Format)** is the **breakthrough innovation** of 2026. It represents a paradigm shift from **string-based markers** (`<think>`, `<thought>`) to **structured data** that cleanly separates thinking from final output at the API level.

---

## 1. Structured Content (List Format) - The Novel Approach

### What It Is

**Mistral's newest and most innovative reasoning format**, introduced with **Mistral Medium 3.5** and **Mistral Small 4** in April 2026. Instead of embedding reasoning markers within text strings, the API returns a **list of structured content blocks**, each with a `type` field that explicitly categorizes the content.

This is a **fundamental architectural change** that treats reasoning as first-class data rather than embedded text.

### Format Specification

```json
{
  "choices": [{
    "message": {
      "role": "assistant",
      "content": [
        {
          "type": "thinking",
          "thinking": [
            {"type": "text", "text": "Let me break this down carefully..."},
            {"type": "text", "text": "First, I need to understand the problem..."},
            {"type": "text", "text": "The key insight is that..."}
          ]
        },
        {
          "type": "text",
          "text": "Final answer: The solution is 42."
        }
      ]
    }
  }]
}
```

### Key Characteristics

| Feature | Description |
|---------|-------------|
| **Data Structure** | List of dictionaries with explicit `type` keys |
| **Separation** | Complete separation of thinking vs. final text |
| **Nested Structure** | `thinking` field contains a list of text blocks |
| **Machine-Readable** | Trivially parseable without regex |
| **Extensible** | Can add new content types (images, tool calls, citations) |
| **API Requirement** | Requires `reasoning_effort` parameter |

### Supported Models

- ✅ `mistral-medium-3.5` (includes `mistral-medium-2604`)
- ✅ `mistral-small-latest`
- ✅ `mistral-small-4`
- ✅ `magistral-medium-latest`
- ✅ `magistral-small-latest`
- ❌ `mistral-large-2512` (older, pre-reasoning)
- ❌ `mistral-medium-2312` (older)

### Advantages

1. **✅ Explicit Structure**: No ambiguity - thinking and text are separate, typed entities
2. **✅ Programmatic Access**: Extract thinking or answer with simple dictionary access
3. **✅ Multiple Blocks**: Can have interleaved thinking and text blocks
4. **✅ Future-Proof**: Extensible to multimodal (images, audio) and tool calls
5. **✅ No String Parsing**: No fragile regex needed
6. **✅ Clean Separation**: Thinking doesn't pollute the final answer
7. **✅ Standard Compliant**: Follows modern API design patterns

### Disadvantages

1. **⚠️ Breaking Change**: Existing code expecting `string` content will crash
2. **⚠️ Complexity**: More complex to handle than simple strings
3. **⚠️ New Models Only**: Requires Mistral's 2026 models
4. **⚠️ SDK Support**: May require updated SDKs

### Real-World Example

From actual API response with `mistral-medium-2604` and `reasoning_effort="high"`:

```json
{
  "content": [
    {
      "type": "thinking",
      "thinking": [
        {"type": "text", "text": "Let me break this down carefully. "},
        {"type": "text", "text": "The key is that every time a register is targeted..."}
      ]
    },
    {
      "type": "text",
      "text": "Step | Command | X | Y | Z | Notes\n---|---|---|---|---|---\n..."
    }
  ]
}
```

### Code Handling Example

```python
# Python - Handling Mistral's structured content
message = response.choices[0].message

if isinstance(message.content, list):
    # New structured format
    thinking_parts = []
    text_parts = []
    
    for block in message.content:
        if block.get("type") == "thinking":
            # Extract all thinking text
            thinking = block.get("thinking", [])
            if isinstance(thinking, list):
                for t in thinking:
                    if isinstance(t, dict):
                        thinking_parts.append(t.get("text", ""))
            elif isinstance(thinking, str):
                thinking_parts.append(thinking)
        elif block.get("type") == "text":
            text_parts.append(block.get("text", ""))
    
    full_thinking = "".join(thinking_parts)
    final_answer = "".join(text_parts)
else:
    # Legacy string format
    full_thinking = ""
    final_answer = message.content
```

---

## 2. `<think>` Tags

### What It Is

Mistral's **official XML-style reasoning markers** used in **text-based responses**. When `reasoning_effort="high"` is set, the model embeds its reasoning process within `<think>` and `</think>` tags, followed by the final answer.

This is the **transitional format** between string-based responses and structured content.

### Format Specification

```text
<think>
Let me break this down carefully.
The key is that every time a register is targeted...
The key insight is that...
</think>

Final answer: The solution is 42.
```

### Key Characteristics

| Feature | Description |
|---------|-------------|
| **Data Structure** | Plain text with XML-style tags |
| **Separation** | Tags delimit thinking from answer |
| **Parsing** | Requires string parsing/regex |
| **Compatibility** | Works with older string-based code |
| **Human Readable** | Easy to read in raw form |

### Supported Models

- ✅ `mistral-medium-3.5` (with `reasoning_effort`)
- ✅ `mistral-small-latest` (with `reasoning_effort`)
- ✅ `magistral-medium-latest` (always uses reasoning)
- ✅ `magistral-small-latest` (always uses reasoning)
- ❌ Older models without reasoning support

### Advantages

1. **✅ Human Readable**: Easy to read and understand in raw form
2. **✅ Backward Compatible**: Works with existing string-handling code
3. **✅ Simple**: No complex data structures
4. **✅ Familiar**: Similar to other AI reasoning formats

### Disadvantages

1. **⚠️ String Parsing Required**: Need regex to extract thinking
2. **⚠️ Fragile**: Tags can be nested or malformed
3. **⚠️ Ambiguous**: Thinking and answer mixed in one string
4. **⚠️ Not Machine-Optimized**: Harder to parse programmatically

### Code Handling Example

```python
import re

# Extract thinking from <think> tags
content = message.content  # This is a string

# Find all <think>...</think> blocks
thinking_matches = re.findall(r'<think>(.*?)</think>', content, re.DOTALL)
full_thinking = "\n".join(thinking_matches)

# Remove thinking tags to get final answer
final_answer = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
```

---

## 3. `<thought>` Tags

### What It Is

**Community-driven/legacy format** using `<thought>` and `</thought>` tags. This was **never officially supported** by Mistral AI but was used in:
- Early community implementations
- Custom reasoning systems
- Third-party wrappers
- Local model implementations (Ollama, etc.)

### Format Specification

```text
<thought>
Let me think about this...
The problem seems to be...
</thought>

The answer is: 42
```

### Key Characteristics

| Feature | Description |
|---------|-------------|
| **Official Support** | ❌ No - community only |
| **Data Structure** | Plain text with XML-style tags |
| **Origin** | Community/third-party implementations |
| **Compatibility** | Varies by implementation |
| **Standardization** | None - varies by user |

### Supported Models/Implementations

- ⚠️ Some local Mistral models via Ollama
- ⚠️ Custom implementations
- ⚠️ Third-party wrappers
- ❌ **Not** official Mistral API

### Advantages

1. **✅ Familiar to some users**: Used in other AI systems
2. **✅ Simple concept**: Easy to understand

### Disadvantages

1. **❌ Not Official**: Never supported by Mistral
2. **❌ Inconsistent**: No standard format
3. **❌ Deprecated**: Being replaced by official formats
4. **❌ Confusing**: Similar to `<think>` but different

### Comparison: `<think>` vs `<thought>`

| Aspect | `<think>` | `<thought>` |
|--------|-----------|-------------|
| **Official** | ✅ Yes | ❌ No |
| **Mistral API** | ✅ Supported | ❌ Not supported |
| **Reasoning Effort** | ✅ Works with `reasoning_effort` | ❌ No |
| **Standardization** | ✅ Consistent | ❌ Varies |
| **Future** | ✅ Actively developed | ❌ Deprecated |

---

## Detailed Comparison Matrix

| Feature | Structured Content (List) | `<think>` Tags | `<thought>` Tags |
|---------|--------------------------|----------------|------------------|
| **Official Support** | ✅ Yes | ✅ Yes | ❌ No |
| **Introduced** | April 2026 | 2025 | Pre-2025 |
| **Data Type** | List of dicts | String | String |
| **Separation** | ✅ Explicit | ⚠️ Tag-based | ⚠️ Tag-based |
| **Parsing** | ✅ Trivial (dict access) | ⚠️ Regex required | ⚠️ Regex required |
| **Machine-Readable** | ✅ Excellent | ⚠️ Good | ⚠️ Good |
| **Human-Readable** | ⚠️ Requires formatting | ✅ Excellent | ✅ Excellent |
| **Extensible** | ✅ Yes (new types) | ❌ No | ❌ No |
| **Multimodal Ready** | ✅ Yes | ❌ No | ❌ No |
| **Tool Calls** | ✅ Compatible | ❌ No | ❌ No |
| **Backward Compatible** | ❌ No (breaking) | ✅ Yes | ✅ Yes |
| **Performance** | ✅ Fast (direct access) | ⚠️ Slower (regex) | ⚠️ Slower (regex) |
| **Error Handling** | ✅ Robust | ⚠️ Fragile | ⚠️ Fragile |
| **API Version** | v1 (2026) | v1 (2025+) | Varies |
| **Model Support** | Medium 3.5+, Small 4 | Medium 3.5+, Small Latest | Community only |
| **Future-Proof** | ✅ Yes | ⚠️ Limited | ❌ No |

---

## When to Use Each Format

### Use Structured Content (List Format) When:

- ✅ You're using **Mistral Medium 3.5** or **Mistral Small 4**
- ✅ You need **programmatic access** to reasoning vs. answer
- ✅ You want **clean separation** of thinking and output
- ✅ You're building **production applications**
- ✅ You need **future extensibility** (multimodal, tools)
- ✅ You want **maximum reliability** in parsing

### Use `<think>` Tags When:

- ✅ You're using **older code** that expects strings
- ✅ You want **human-readable** raw output
- ✅ You need **backward compatibility**
- ✅ You're using **Magistral models** (always use reasoning)
- ✅ You prefer **simplicity** over structure

### Use `<thought>` Tags When:

- ⚠️ You're using a **custom implementation**
- ⚠️ You have **legacy code** that can't be changed
- ⚠️ You're working with **third-party wrappers** that use it
- ❌ **Not recommended** for new projects

---

## Technical Implementation Details

### How Mistral Decides the Format

```
User Request
    ↓
Model: mistral-medium-2604?
    ↓
reasoning_effort set?
    ↓
    ├── NO → String response (plain text)
    └── YES → Structured Content (list format)
```

### Format Detection in Code

```python
def handle_mistral_response(message):
    content = message.content
    
    if isinstance(content, list):
        # Structured Content Format (2026+)
        return extract_from_structured(content)
    elif isinstance(content, str):
        if '<think>' in content:
            # Think Tags Format
            return extract_from_think_tags(content)
        elif '<thought>' in content:
            # Thought Tags Format (legacy)
            return extract_from_thought_tags(content)
        else:
            # Plain text (no reasoning)
            return {"thinking": "", "answer": content}
```

### chatybot Implementation

The chatybot code now handles all three formats:

```python
# In chatybot_app.py, line ~890
content = message.content or ""

# Handle Mistral's structured content (list of dicts with type: 'thinking' or 'text')
if isinstance(content, list):
    text_parts = []
    for item in content:
        if isinstance(item, dict):
            if item.get("type") == "text":
                text_parts.append(item.get("text", ""))
            elif item.get("type") == "thinking" and self.show_thinking:
                thinking_text = item.get("thinking", "")
                if isinstance(thinking_text, list):
                    for t in thinking_text:
                        if isinstance(t, dict):
                            text_parts.append(t.get("text", ""))
                elif isinstance(thinking_text, str):
                    text_parts.append(thinking_text)
    content = "".join(text_parts)
```

---

## Real-World Examples

### Example 1: Structured Content Response

**Request:**
```python
client.chat.complete(
    model="mistral-medium-2604",
    messages=[{"role": "user", "content": "What is 2+2?"}],
    reasoning_effort="high"
)
```

**Response:**
```json
{
  "content": [
    {
      "type": "thinking",
      "thinking": [
        {"type": "text", "text": "This is a simple arithmetic problem. "},
        {"type": "text", "text": "2 + 2 = 4"}
      ]
    },
    {
      "type": "text",
      "text": "The answer is 4."
    }
  ]
}
```

### Example 2: `<think>` Tags Response

**Request:**
```python
client.chat.complete(
    model="mistral-medium-2312",  # Older model
    messages=[{"role": "user", "content": "What is 2+2?"}],
    reasoning_effort="high"
)
```

**Response:**
```text
<think>
This is a simple arithmetic problem.
2 + 2 = 4
</think>

The answer is 4.
```

### Example 3: Plain Text (No Reasoning)

**Request:**
```python
client.chat.complete(
    model="mistral-medium-2604",
    messages=[{"role": "user", "content": "What is 2+2?"}],
    reasoning_effort="none"
)
```

**Response:**
```json
{
  "content": "The answer is 4."
}
```

---

## Historical Context & Evolution

### Timeline

| Date | Event | Format Introduced |
|------|-------|-------------------|
| 2024 | Mistral Large 1 | Plain text only |
| Early 2025 | Reasoning Models | `<think>` tags (Magistral) |
| Mid 2025 | Mistral Small Latest | `<think>` tags with `reasoning_effort` |
| **April 2026** | **Mistral Medium 3.5** | **Structured Content (List)** ⭐ |
| May 2026 | Mistral Small 4 | Structured Content |

### Evolution Philosophy

1. **Phase 1 (2024)**: Plain text - no reasoning visibility
2. **Phase 2 (2025)**: String-based markers (`<think>`) - reasoning as embedded text
3. **Phase 3 (2026)**: **Structured data** - reasoning as first-class citizen

Mistral's Structured Content represents a **paradigm shift** from treating reasoning as **formatted text** to treating it as **structured data**. This aligns with modern API design principles where data is explicitly typed and separated.

---

## Best Practices

### For Application Developers

1. **✅ Always check the content type**
   ```python
   if isinstance(content, list):
       # Handle structured format
   else:
       # Handle string format
   ```

2. **✅ Use `reasoning_effort` for complex tasks**
   ```python
   # For reasoning-heavy tasks
   response = client.chat.complete(..., reasoning_effort="high")
   
   # For simple tasks
   response = client.chat.complete(..., reasoning_effort="none")
   ```

3. **✅ Extract thinking and answer separately**
   ```python
   thinking = extract_thinking(response)
   answer = extract_answer(response)
   ```

4. **✅ Handle both formats gracefully**
   ```python
   def get_answer(response):
       content = response.choices[0].message.content
       if isinstance(content, list):
           # Extract text blocks
           return "".join([b["text"] for b in content if b.get("type") == "text"])
       else:
           # Remove think tags
           return re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
   ```

### For Model Prompting

1. **✅ Use structured prompts for structured output**
   ```
   Think step by step, then provide the final answer.
   ```

2. **✅ Be explicit about format expectations**
   ```
   Provide your reasoning in <think> tags, then the final answer.
   ```

3. **❌ Avoid mixing formats**
   ```
   # Bad - mixing formats
   <think>Reasoning...</think>
   [THINK]More reasoning[/THINK]
   
   # Good - consistent format
   <think>All reasoning here...</think>
   ```

---

## Migration Guide

### From `<think>` Tags to Structured Content

**Before:**
```python
# Old code expecting string with <think> tags
content = response.choices[0].message.content
thinking = re.findall(r'<think>(.*?)</think>', content, re.DOTALL)
answer = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
```

**After:**
```python
# New code handling both formats
content = response.choices[0].message.content

if isinstance(content, list):
    # Structured format
    thinking_parts = []
    answer_parts = []
    for block in content:
        if block.get("type") == "thinking":
            thinking = block.get("thinking", [])
            if isinstance(thinking, list):
                thinking_parts.extend([t.get("text", "") for t in thinking if isinstance(t, dict)])
        elif block.get("type") == "text":
            answer_parts.append(block.get("text", ""))
    thinking = "".join(thinking_parts)
    answer = "".join(answer_parts)
else:
    # Legacy string format
    thinking = "".join(re.findall(r'<think>(.*?)</think>', content, re.DOTALL))
    answer = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
```

### From `<thought>` Tags to Structured Content

**Before:**
```python
# Custom code using <thought> tags
thinking = re.findall(r'<thought>(.*?)</thought>', content, re.DOTALL)
```

**After:**
```python
# Migrate to official formats
# Option 1: Use reasoning_effort with official models
response = client.chat.complete(..., reasoning_effort="high")

# Option 2: Handle both official formats
if isinstance(content, list):
    # Structured format
    ...
elif '<think>' in content:
    # Official think tags
    ...
else:
    # Plain text
    ...
```

---

## Conclusion

Mistral AI's **Structured Content (List Format)** represents a **novel and superior approach** to reasoning output. It solves the fundamental problems of string-based formats:

1. **Ambiguity**: No more parsing text to find reasoning
2. **Fragility**: No more regex that can break
3. **Extensibility**: Can easily add new content types
4. **Separation**: Clean division between thinking and answer

While `<think>` tags were a good transitional solution, and `<thought>` tags served the community, **Structured Content is the future** of AI reasoning output.

### Recommendation

| Scenario | Recommended Format |
|----------|-------------------|
| New projects | **Structured Content** |
| Existing projects | Handle both Structured + `<think>` |
| Legacy systems | `<think>` tags (with migration plan) |
| Custom implementations | Migrate to official formats |

---

## References

- [Mistral Reasoning Documentation](https://docs.mistral.ai/capabilities/reasoning)
- [Mistral Adjustable Reasoning](https://docs.mistral.ai/studio-api/conversations/reasoning/adjustable)
- [Mistral Medium 3.5 Release](https://mistral.ai/news/vibe-remote-agents-mistral-medium-3-5)
- [Mistral API Changelog](https://docs.mistral.ai/resources/changelogs)
- [Hugging Face: Mistral Medium 3.5](https://huggingface.co/mistralai/Mistral-Medium-3.5-128B)

---

*Document created: 2026 | Last updated: 2026 | Mistral AI Format Comparison v1.0*
