## Updated README for chatybot.py

---

## **Overview**
`chatybot.py` is a command-line chatbot interface that interacts with various language models using the OpenAI API (or compatible APIs). It provides a flexible and interactive way to chat with AI models, supports file input for context, and includes multiple customizable features.

---

## **New Features and Updates**

### **1. Enhanced Command System**
The chatbot now supports an expanded set of commands for better usability:
- **`/help`**: Display the help message with all available commands.
- **`/file <path>`**: Load a text file into the buffer for context.
- **`/showfile [all]`**: Display the first 100 characters of the file buffer or the entire file if `all` is specified.
- **`/clearfile`**: Clear the file buffer.
- **`/model <alias>`**: Switch to a different model using its alias.
- **`/listmodels`**: List all available models from the TOML configuration file.
- **`/logging <start|end>`**: Start or stop logging chat sessions.
- **`/save <file>`**: Save the last chat completion to a file.
- **`/codeonly`**: Enable code-only mode (generates code without explanations).
- **`/codeoff`**: Disable code-only mode.
- **`/multiline`**: Toggle multi-line input mode (use `;;` to end input).
- **`/system <message>`**: Set a custom system message for the model.
- **`/temp <value>`**: Set the temperature for the current model (0.0-2.0).
- **`/maxtokens <value>`**: Set the max tokens for the current model.
- **`/stream`**: Toggle streaming responses.
- **`/quit`**: Exit the program.

---

### **2. Multi-Line Input Mode**
- Users can now enter multi-line prompts by enabling **`/multiline`** mode.
- Input is terminated by entering `;;` on a new line.

---

### **3. Streaming Responses**
- Users can toggle streaming responses using the **`/stream`** command.
- Streaming provides real-time output from the model.

---

### **4. Custom System Messages**
- Users can set a custom system message using the **`/system <message>`** command.
- This message is included in the prompt to guide the model's behavior.

---

### **5. Temperature and Max Tokens Control**
- Users can adjust the **temperature** and **max tokens** for the current model using the **`/temp`** and **`/maxtokens`** commands.
- Temperature controls the randomness of the model's output (0.0-2.0).
- Max tokens limits the length of the model's response.

---

### **6. Code-Only Mode**
- Users can enable **`/codeonly`** mode to generate code without explanations or descriptions.
- This is useful for quickly generating code snippets.

---

### **7. Logging**
- Users can start or stop logging chat sessions using the **`/logging <start|end>`** command.
- Logs are saved with a timestamp for easy reference.

---

### **8. File Buffer System**
- Users can load a file into the buffer using the **`/file <path>`** command.
- The file content is automatically included in the prompt for context.
- The buffer can be cleared using **`/clearfile`**.

---

### **9. Input History**
- The chatbot now supports input history, allowing users to navigate previous inputs using the **Tab** key.
- Input history is saved to `.chat_history` for persistence across sessions.

---

## **Workflow**
1. Start the application: `python3 chatybot.py`.
2. The system loads the configuration and initializes the default model.
3. Enter prompts or commands.
   - For chat prompts, the system combines the prompt with the file buffer (if any) and sends it to the model.
   - For commands, the system executes the appropriate action (e.g., load file, switch model, etc.).
4. The model's response is displayed in the terminal.

---

## **Technical Highlights**
- **Type hints** for better code maintainability.
- **Environment variable support** for API keys.
- **Configurable model parameters** (temperature, max tokens, etc.).
- **File content integration** for context.
- **Command-line interface with readline support** for better input handling.
- **Error handling** for file operations and API calls.