# Chatybot Agentic Loop Context Explosion & Duplication Issue

## Overview
During multi-step evaluation runs (such as evaluating procedural vs. object-oriented implementations using `gemma_4_27` or `cohere_north`), the LLM client payloads suffer from exponential token bloat. In reasoning models (like Gemma 27B), this context explosion triggers infinite meta-reasoning loops inside the `<thought>` blocks, causing the model to hang or timeout.

---

## The Core Problem: Nested Context Duplication

On every turn of Chatybot's autonomous tool loop, the system instruction templates, tool definition schemas, and loop reminders are appended to the user prompt. 

Because Chatybot constructs the chat completion request by appending past turns (role `user` and role `assistant`) directly into the payload, the historical user prompts keep their original prepended contexts. This leads to recursive duplication of instructions.

### 1. Duplicated Elements Per Turn
* **`=== AVAILABLE TOOLS ===` Schema Block**: The complete specification of all tools (approx. 2,000 tokens) is prepended to the user content of **every single turn**. By Turn 4 of a step, the model has ingested the identical tool specification **4 times** in a single payload.
* **System & Loop Behavior Instructions**:
  ```text
  1. You can output one or more tool calls in a single turn if they can be executed in parallel or sequence. Use the JSON format enclosed in ```json ... ```.
  2. Do NOT output any conversational text, descriptions, planning thoughts, or explanations before or after the tool calls. Your entire response must be ONLY the JSON tool call block(s).
  3. Only output natural language/conversation when you have finished all tool executions and are ready to present the final result to the user.
  ```
* **Tool Loop Reminder**:
  ```text
  (Reminder: You are in a tool loop. You MUST output ONLY the JSON tool call(s) wrapped in ```json and ``` code fences. Do NOT write any conversational text, descriptions, or explanations before or after the JSON block.)
  ```
  This reminder is appended to every single user-role message containing command outputs.
* **Cross-Role Pollution**: The tool context is present in both the active `system` message and recursively in the historical strings of the `user` messages.

---

## Impact on Models

### Gemma 4 (27B) — *Hangs & Infinite Reasoning Loops*
* **Symptom**: Gemma 4 successfully completes Steps 1 and 2, but hangs on Step 3 or Step 4.
* **Mechanism**: When Step 4 starts, the cumulative history payload size exceeds **17,000 tokens** (consisting largely of duplicated tool lists and system instructions). Gemma gets confused by the repeated instructions inside the user history, causing it to fall into repetitive meta-reasoning loops inside its internal `<thought>` block (e.g. repeating commands like `I will run ls -F... I will checkout branch... Actually let me checkout first` indefinitely) without ever outputting the JSON tool call.
* **Performance Profile**: High response latency (typical turns take 15–33 seconds) because it must parse massive redundant contexts and write long thought tokens.

### Cohere North — *High Speed, Heavy Bloat*
* **Symptom**: North completes the script successfully without hanging.
* **Mechanism**: North has a large context window (128k) and does not output internal reasoning tokens. However, by Turn 11 of Step 3, the payload carries over **22,000 tokens of redundant schemas**, significantly inflating API cost and processing overhead.
* **Performance Profile**: Extremely fast response times (typically under 1.5 seconds per turn), but vulnerable to occasional schema slips (e.g. calling `run_command` with an empty `{}` arguments block) before self-correcting.

---

## Payload Visual Representation (Turn 3 Example)

```json
[
  {
    "role": "system",
    "content": "[Tool Context + System Message]"
  },
  {
    "role": "user",
    "content": "[Tool Context / Schemas] + Please list the files..."
  },
  {
    "role": "assistant",
    "content": "<thought>...</thought> {\"tool\": \"list_directory\"}"
  },
  {
    "role": "user",
    "content": "Tool execution results... + [Tool Context / Schemas] + (Reminder: You are in a tool loop...)"
  },
  {
    "role": "assistant",
    "content": "<thought>...</thought> {\"tool\": \"run_command\"}"
  },
  {
    "role": "user",
    "content": "Tool execution results... + [Tool Context / Schemas] + (Reminder: You are in a tool loop...)"
  }
]
```

---

## Concrete Log Examples of What Was Observed

### 1. The Gemma 27B Repetitive Thought Loop
When the payload got too large in Step 3/4, the model's `<thought>` block began looping on the same reasoning sequence indefinitely instead of outputting the JSON tool call:
```text
Let's check `blockchain-non-oo` and `main` files.
I'll use `ls -F` for both.
I'll use `git checkout` for each.
Actually, I'll just do:
`git checkout blockchain-non-oo && ls -F && git checkout main && ls -F`
Wait, I can't do two commands in one `run_command` if they are separate tool calls, but I can chain them.
Actually, I'll just do one at a time.

Wait, I'll check `blockchain-non-oo` first.
Then `main`.
... [Repeated verbatim indefinitely] ...
```

### 2. The Duplicated Payload Logs
Below is the actual log format showing how the tool definitions (`=== AVAILABLE TOOLS ===`) accumulate inside a single request's messages array.

By the time the model is on Turn 3 of Step 2, the message array sent to the API contains multiple duplicate tool lists:
```json
[
  {
    "role": "user",
    "content": "\n=== AVAILABLE TOOLS ===\nYou have access to the following tools...\n\n**list_directory**\n...\n**run_command**\n...\n=== END TOOLS ===\n\nPlease list the files..."
  },
  {
    "role": "assistant",
    "content": "<thought>...</thought>\n```json\n{\"tool\": \"list_directory\"}\n```"
  },
  {
    "role": "user",
    "content": "Tool execution results:\n...\n\n=== AVAILABLE TOOLS ===\nYou have access to the following tools...\n\n**list_directory**\n...\n**run_command**\n...\n=== END TOOLS ===\n\n(Reminder: You are in a tool loop...)"
  }
]
```

---

## Suggested Remediation
1. **Sanitize History Formatting**: When rebuilding `temp_history` from `self.chat_history`, strip the prepended `TOOL_CONTEXT` block and the trailing `(Reminder: ...)` strings from previous user messages. Only the active, latest user message should contain the current tool schemas and loop instructions.
2. **Session Cleansers**: Introduce a `/clear` or `/reset_history` command in Chatybot to allow scripts to clean the chat history between evaluation steps when historical context is no longer needed.
