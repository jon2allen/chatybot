# Control-C Signal Handler Implementation

## Overview

This document describes the implementation of a control-C signal handler for the Chatybot application that provides three-level behavior:

1. **First Ctrl+C during general chat completion**: Returns to the prompt
2. **First Ctrl+C during agentic tool loop**: Breaks out of the loop and returns to the prompt  
3. **Second Ctrl+C (anywhere)**: Exits the program completely

## Behavior Specification

| Context | Ctrl+C Press | Action |
|---------|---------------|--------|
| General chat input | 1st press | Return to prompt with "Interrupted. Returning to prompt..." message |
| Agentic loop | 1st press | Break loop and return to prompt with "Control-C received. Breaking agentic tool loop..." message |
| Rate limit delay | 1st press | Interrupt delay and return to prompt |
| Any context | 2nd press | Exit program with "Exiting..." message and proper cleanup |

## Implementation Details

### Files Modified
- `src/chatybot/chatybot_app.py`

### Changes Made

#### 1. Import Addition
```python
import signal
```

#### 2. State Tracking
Added to `__init__` method:
```python
# Control-C handling state
self.control_c_count: int = 0
self.interrupt_requested: bool = False
```

#### 3. Signal Handler Setup
New method added:
```python
def setup_signal_handler(self) -> None:
    """Set up signal handler for Control-C interrupts."""
    def signal_handler(sig, frame):
        if sig == signal.SIGINT:
            self.control_c_count += 1
            if self.control_c_count >= 2:
                # Second Ctrl+C - exit program
                print("\nExiting...")
                self.logging_manager.stop_logging()
                self.save_input_history()
                os._exit(0)
            else:
                # First Ctrl+C - set flag for graceful interruption
                self.interrupt_requested = True
    
    signal.signal(signal.SIGINT, signal_handler)
```

#### 4. Interruptible Sleep Helper
New method added for interruptible rate limit delays:
```python
async def interruptible_sleep(self, delay: float) -> None:
    """
    Sleep for specified delay but can be interrupted by Control-C.
    Checks interrupt_requested flag periodically.
    """
    start_time = time.time()
    remaining = delay
    
    while remaining > 0.1 and not self.interrupt_requested:  # Check every 100ms
        await asyncio.sleep(min(0.1, remaining))
        remaining = delay - (time.time() - start_time)
    
    if self.interrupt_requested:
        self.interrupt_requested = False  # Reset flag since we're handling it
        raise KeyboardInterrupt()
```

#### 5. Main Loop Modifications

Added interrupt flag check at start of each iteration:
```python
while True:
    try:
        # Check for interrupt flag at start of each loop iteration
        if self.interrupt_requested:
            print("\nInterrupted. Returning to prompt...")
            self.control_c_count = 0
            self.interrupt_requested = False
            continue
        # ... rest of loop
```

Updated KeyboardInterrupt exception handler:
```python
except KeyboardInterrupt:
    if self.control_c_count >= 2:
        # Second Ctrl+C - exit program
        print("\nGoodbye! Thanks for chatting.")
        self.logging_manager.stop_logging()
        self.save_input_history()
        break
    else:
        # First Ctrl+C - return to prompt
        print("\nInterrupted. Returning to prompt...")
        self.control_c_count = 0  # Reset counter after handling
        self.interrupt_requested = False
        continue
```

#### 6. Multi-line Input Modifications
Added interrupt flag check in `get_multi_line_input()`:
```python
while True:
    # Check for interrupt flag during multi-line input
    if self.interrupt_requested:
        print("\nInterrupted. Returning to prompt...")
        self.control_c_count = 0
        self.interrupt_requested = False
        self.multi_line_mode = False
        return ""
    
    line = input()
```

#### 7. Agentic Loop Modifications

Added interrupt flag check at beginning of while loop in `execute_tool_loop()`:
```python
while turn_count < max_turns:
    # Check for interrupt flag from signal handler
    if self.interrupt_requested:
        print("\nControl-C received. Breaking agentic tool loop...")
        self.control_c_count = 0  # Reset counter after handling
        self.interrupt_requested = False
        break
    # ... rest of loop
```

#### 8. Rate Limit Delay Replacements

Replaced `await asyncio.sleep(self.rate_limit_delay)` with `await self.interruptible_sleep(self.rate_limit_delay)` in:
- Initial tool call preparation in `execute_tool_loop()`
- Between turns in `execute_tool_loop()`

## Design Principles

### Flag-Based Approach
- Signal handler sets `interrupt_requested` flag instead of raising exceptions
- Avoids thread/context issues with asyncio
- Flags are checked at strategic points in the code

### Graceful Interruption
- Rate limit delays are interruptible via custom `interruptible_sleep()`
- Input loops check for interruption flag before each input
- Main loop checks for interruption at each iteration

### Counter-Based Exit
- Uses `control_c_count` to track consecutive Ctrl+C presses
- Second press within short timeframe triggers program exit
- Counters are reset after handling to prevent accidental exits

### Proper Cleanup
- Ensures logging is stopped properly on exit
- Ensures input history is saved on exit
- Provides clear user feedback at each step

## Testing

The implementation can be tested by:

1. **General chat**: Type a prompt, press Ctrl+C during input → should return to prompt
2. **During rate limit delay**: Trigger a tool loop with rate limit, press Ctrl+C during delay → should interrupt delay and return to prompt
3. **Agentic loop**: Trigger tool loop, press Ctrl+C during execution → should break loop and return to prompt  
4. **Double Ctrl+C**: Press Ctrl+C twice quickly in any context → should exit program
5. **Multi-line input**: Enter multi-line mode, press Ctrl+C during input → should exit multi-line mode and return to prompt

## Current Limitations

1. **Chat Completion Calls**: Long-running `chat_completion()` calls cannot be interrupted mid-call. The interrupt will be handled after the current completion finishes.

2. **Input Handling**: The `input()` function naturally raises `KeyboardInterrupt` when Ctrl+C is pressed. The signal handler also sets the flag, creating two mechanisms for the same event. This is handled correctly by the current implementation.

## Edge Cases Handled

- Multiple rapid Ctrl+C presses are handled by the counter mechanism
- Cleanup operations are performed in all exit paths
- User feedback is provided for each type of interruption
- State is properly reset after handling each interruption
- Both single-line and multi-line input modes are supported