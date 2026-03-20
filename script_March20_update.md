# Chatybot Scripting Engine Update - March 20th 

This document summarizes the comprehensive refactoring of the ChatDSL script processing engine in `src/chatybot/chatybot_app.py`, comparing the legacy version (March 15th) with the current robust architectural version.

## 1. Overview of Structural Changes
The scripting engine has transitioned from a simplistic "Split-and-Clean" approach to a **Character-by-Character Lexical State Machine**. This allows the bot to handle complex natural language punctuation and multiline structures that previously would have broken script execution.

### Logic Comparison Table

| Feature | Legacy Version (March 15) | Current Version (March 20) |
| :--- | :--- | :--- |
| **Parsing Engine** | Line-based `.split()` calls. | Character-level state machine. |
| **Comments** | Only full-line `#` comments. | Full support for **inline comments**. |
| **Quotes** | Line-constrained strings. | **Multiline quoted strings** supported. |
| **Apostrophes** | Misidentified as start of strings. | **Context-aware** (token-start only). |
| **Separators** | Fragile semicolon splitting. | Robust `;` handling via state machine. |

## 2. Advanced Feature Set
- **`/echo` Command**: Introduced direct stdout printing with full variable substitution.
- **Parameterized Scripts**: Scripts can now be called with inline variables: `/script file.chatdsl x="value"`.
- **Full Boolean Logic**: `if-then` supports `==`, `!=`, and logical `not`.
- **Command Tail Capture**: `/save`, `/file`, and `/prompt` now support filenames with spaces by capturing the full command remainder.

## 3. Script Flow Architecture
The following diagram illustrates how a script moves through the new three-stage pipeline.

```text
       +-----------------------+
       |   .chatdsl File       |
       +-----------+-----------+
                   |
                   v
+------------------+-----------------------+
| STAGE 1: Lexical Scanner/Splitter        |
| (Character-by-Character State Machine)   |
+------------------+-----------------------+
|  1. Identify Quotes (Context-aware)      |
|  2. Strip Inline Comments (#)            |
|  3. Honor Command Separators (; or \n)   |
|  4. Persist Multiline Quoted Strings     |
+------------------+-----------------------+
                   |
                   v
         List of Raw Commands
                   |
                   v
+------------------+-----------------------+
| STAGE 2: Multi-line Aggregator           |
+------------------+-----------------------+
|  Iterate commands; If /multiline is ON,  |
|  collect prompt text until ;; or a /cmd  |
+--------+---------+-----------------------+
         |
         v
+--------+---------------------------------+
| STAGE 3: Logical Execution Engine        |
| (execute_script_command)                 |
+------------------+-----------------------+
|  1. Variable Expansion: ${var} -> Value  |
|  2. Dispatch Logical Branch:             |
|                                          |
|  [ set ] ----> Update Internal Memory    |
|  [ wait] ----> Pause Execution           |
|  [ if  ] ----> Evaluate Logic (==, !=)   |
|  [ /cmd] ----> Route to Escape Handler   |
|  [Text ] ----> Send Prompt to LLM API    |
+------------------------------------------+
```

## 4. Key Logic Enhancements (execute_script_command)

*   **Robust `set` Variable Parsing**: Uses `re.S` (DOTALL) to allow variable values to span multiple lines. Includes a safety check to disallow escape characters (`\`) within values to ensure parser stability.
*   **Intelligent `if` Splitting**: Uses a whitespace-aware regex to split conditions from their `then` actions, ensuring that spaces within strings don't break the logical structure.
*   **Variable Substitution Integrity**: Regular expressions for `${varname}` substitution were verified for single-layer backslash integrity, ensuring reliable replacement in both prompts and logical comparisons.
*   **Recursive `if-then` Execution**: When an `if` condition is met, the system recursively passes the `then` command through the same logical handler, allowing for nested commands or immediate LLM prompts.
