# Reasoning History Mode

## Problem

Some models served via vLLM or Hugging Face TGI (e.g. `reflection/Beam-1.0-501B-A23B`) enforce chain-of-thought integrity across multi-turn conversations. Their Jinja chat templates reject assistant turns that are missing reasoning:

```
openai.BadRequestError: Error code: 400 - {
  'error': {
    'code': '400',
    'message': "The assistant turn at messages[2] is missing its reasoning. Dropping reasoning from earlier turns degrades this model's output. Send it back in 'reasoning_content', or set allow_missing_thinking=true to skip this check.",
    'type': 'Bad Request'
  }
}
```

Chatybot strips `<think>`/`<thought>`/`<thinking>` blocks from past assistant responses to save tokens. When the stripped turn is sent to a strict-template model, the server returns 400 Bad Request.

## Solution: `/reasoning_history`

A new command controls how past assistant reasoning is transmitted in chat history:

```
/reasoning_history [strip|keep|field|auto]
```

### Modes

| Mode | Behavior | Tokens | Strict-template safe |
|------|----------|--------|---------------------|
| `auto` (default) | Strips thinking tags; if the server returns the "missing reasoning" 400, retries once with `allow_missing_thinking=true` | Low | Yes (via retry) |
| `strip` | Strips thinking tags, no retry (legacy behavior) | Low | No |
| `keep` | Keeps raw `<think>` tags inside assistant `content` | High | Yes |
| `field` | Passes reasoning via `reasoning_content` on assistant messages | Medium | Yes (if server supports the field) |

### How `auto` works

1. Past assistant turns are built with thinking tags stripped (same as today).
2. The request is sent to the server.
3. If the server returns a 400 indicating missing reasoning in prior turns, Chatybot retries with `allow_missing_thinking = true` and backfills `reasoning_content` across all prior assistant messages.
4. The retry succeeds because both `allow_missing_thinking=true` and `reasoning_content` satisfy strict Jinja template validators (e.g. Beam, DeepSeek).

This approach avoids hardcoding model name lists (e.g. `"beam" in model_name`). Any strict-template model that follows the same error convention is handled automatically.

### When to use each mode

- **`auto`** (recommended): Best for most users. Token-efficient and self-healing.
- **`strip`**: Use only if you know your model doesn't enforce reasoning integrity and you want the old behavior without retry overhead.
- **`keep`**: Use if your model requires reasoning in `content` and you don't care about token cost.
- **`field`**: Use if your server supports the OpenAI-compatible `reasoning_content` field on assistant messages. Note: this only works if thinking text was retained in storage (see `session_strip_thinking`).

### Interaction with `session_strip_thinking`

Chatybot's session storage has its own setting (`session_strip_thinking`) that controls whether thinking text is saved at all:

- `"separate"` (default): Thinking is stored separately and is available for `field` mode.
- `"true"`: Thinking is stripped at storage time. `field` mode cannot reconstruct `reasoning_content` from already-discarded text.
- `"false"`: Thinking is kept inline in the response.

If you want to use `field` mode, ensure `session_strip_thinking` is not set to `"true"`.

## Implementation

- **State**: `self.reasoning_history_mode` in `ChatybotApp.__init__` (default: `"auto"`)
- **History builder**: `chat_completion()` in `chatybot_app.py` — respects the mode when constructing past assistant messages
- **Retry**: `_create_with_reasoning_retry()` in `chatybot_app.py` — wraps `client.chat.completions.create()` and retries on the specific 400
- **Error detection**: `_is_missing_reasoning_error()` — matches the error message pattern without hardcoding model names
- **Command**: `/reasoning_history` in `commands/models.py`
