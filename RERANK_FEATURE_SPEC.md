# Chatybot Feature Specification: Semantic Reranking

## 1. Overview
This document specifies the integration of the **`EasyRerank`** semantic document reranking library into **`chatybot`**. This feature enables users to specify a dataset, perform real-time semantic scoring against a target query, and feed highly relevant context directly into LLM chats.

> [!NOTE]
> **Status:** Planning / Specification phase. **No changes have been made to the implementation codebase.**

---

## 2. Feature Objectives
*   **Context Compression**: Allow users to filter massive directories or databases down to the most relevant information blocks, staying well within LLM context limits and saving token costs.
*   **Database Search Upgrades**: Add semantic relevance scoring to local database records stored in TinyDB.
*   **Flexible Source Integration**: Support diverse document sources including database tables, environment/script variables, and local disk folders.

---

## 3. Command Specifications

### A. `/documents` Command
Specifies the active dataset or corpus that `chatybot` will evaluate during the next reranking process.

```text
/documents <source_type>=<identifier>
```

#### Supported Sources:
| Argument Syntax | Example | Purpose & Behavior |
|:---|:---|:---|
| `db=<name>` | `/documents db=history` | Connects to a TinyDB database or table matching `<name>` and fetches its records as in-memory documents. |
| `var=<name>` | `/documents var=search_results` | Pulls the document collection from the active Chatybot script variable `${search_results}` (supports both list formats and JSON strings). |
| `var=CHAT_HISTORY` | `/documents var=CHAT_HISTORY` | **Special Built-in Variable**: Pulls the live chat session message history. It treats each message turn (e.g., user prompt or assistant response) as an individual candidate block to allow semantic search over past conversation. |
| `dir="<path>"` | `/documents dir="./Madison"` or `/documents dir="./Madison Speeches"` | Specifies a relative or absolute directory path containing `.txt` files. Wrap in double quotes as a string to support spaces. |

> [!IMPORTANT]
> Executing `/documents` does **not** perform reranking immediately. It registers the target source in the application state (`self.rerank_documents_source`) and parses the text into candidate elements in the background.

---

### B. `/rerank` Command
Executes semantic relevance scoring on the active `/documents` source against a query and returns either a formatted summary or raw concatenated text.

```text
/rerank "<query>" [, top_n=<number>] [, item=<sentences>] [, return=<summ|text>] [, full_doc=<true|false>]
```

#### Parameters:
*   `"<query>"`: The semantic search query (must be wrapped in double quotes).
*   `top_n=<number>` *(Optional, Default: `1`)*: The maximum number of top results to return and display.
*   `item=<sentences>` *(Optional, Default: `1`)*: Specifies the number of sentences grouped per text chunk (maps to the candidate chunk size for reranking).
*   `return=<summ|text>` *(Optional, Default: `summ`)*:
    *   `return=summ`: Summary mode. Prints the clean, formatted ASCII results table (Rank, Score, Source, Snippet) to stdout and appends it to the virtual chat history.
    *   `return=text`: Plain text mode. Returns only the plain text of the top `top_n` matched items concatenated together. Ideal for scripting, placing into variables with `/setvar`, and injecting directly into prompts.
*   `full_doc=<true|false>` *(Optional, Default: `false`)*:
    *   `full_doc=false`: Returns the exact matching sub-document text chunk (the `item` sentences that were evaluated) when `return=text` is selected.
    *   `full_doc=true`: If the active source is a database (`db=<name>`), it will look up the parent record by its `doc_id` and return the **entire parent document content** instead of just the 2-sentence chunk. For other sources (`dir` or `var`), it defaults to returning the full file text or full variable item content respectively.

> [!NOTE]
> ### 🔍 Unified Sub-Document Sentence Chunking:
> By default, Chatybot assumes **sub-document sentence-based chunking** across all document sources to ensure maximum semantic search accuracy:
> 1. **Directory Files (`dir="<path>"`)**: Splits files into sentence chunks of `item` size.
> 2. **Database Tables (`db=<name>`)**: Splits the `content` field of each database record into sentence chunks of `item` size, preserving a reference linkage back to the parent `doc_id` and metadata.
> 3. **Chat History (`var=CHAT_HISTORY`)**: Splits the text of each past message turn (user/assistant content) into sentence chunks of `item` size, preserving role attribution.
> 4. **In-Memory Lists (`var=<name>`)**: Splits individual string elements in the list into sentence chunks of `item` size.

#### Operational Behavior:
1.  Verify that a `/documents` source has been set. If empty, return: `ERROR: No document source specified. Use "/documents <source>" first.`
2.  Invoke `EasyRanker` from the `EasyRerank` library.
3.  Calculate scores using the active reranker model.
4.  Cache the results internally in `self.latest_rerank_results` so they can be referenced or automatically injected into subsequent chat prompts.
5.  Render a premium ASCII table displaying the ranks, scores, source file/index reference, and clean text snippets.
6.  **Append to Chat History (`self.chat_history`)**: Log the `/rerank` execution as a virtual conversation turn. The query serves as the user message (e.g., `"[Rerank Query] separation of powers"`), and the formatted ASCII results table serves as the assistant response.

> [!TIP]
> ### 💡 Key Advantages of Virtual Chat Appending:
> * **Immediate Saving**: Running `/save results.txt` directly after `/rerank` will write the full ASCII ranking report to a file.
> * **Persistent Logging**: Running `/dblog` immediately after `/rerank` will save the full results table into your active TinyDB history.
> * **Contextual Follow-up**: The LLM will have access to the ranked results in the thread history, allowing you to ask natural follow-up questions like: *"Summarize the top match in the list."*

### C. `/trace rerank` Command
Enables or disables debugging output for the reranking processor.

```text
/trace rerank <on|off>
```

*   **`on`**: Rerank tracing enabled. If a rerank command is executed with `return=text`, the system will **still print the ASCII results summary table** directly to the console for interactive debugging and value verification. The chat history and captured variables remain clean and unaffected (containing only the plain text).
*   **`off`**: Standard behavior (default). No summary tables are printed when `return=text` is specified.

---

### D. `/model` & Configuration Specifications
`chatybot` uses the `/model` command to switch between active models. To support semantic reranking, the target model must be rerank-capable.

#### Rules:
1.  **Strict Capability Enforcement**: The active model configuration in `chat_config.toml` must explicitly be marked with a capability flag, or route to a known rerank endpoint.
2.  **Initial Pass**: Supports dedicated reranking cross-encoders natively integrated in `EasyRerank`:
    *   **Local**: `llama.cpp` server loaded with a reranker model (like `jina-reranker-v3-Q4_K_M.gguf`) running with `--rerank` enabled (defaults to `localhost:8080`).
    *   **Remote**: Jina AI's Cloud API (`jina-reranker-v3`) initialized with a `JINA_API_KEY`.
3.  **Future Roadmap**: We will later explore how to make standard generative LLMs (such as OpenAI, Gemini, or Claude models) act like rerankers via custom system prompt generation or structured outputs.

---

## 4. Technical Architecture

### State Flow Diagram
```text
                     +---------------------------------------+
                     |              USER INPUT               |
                     |       "/documents dir=./speeches"     |
                     +-------------------+-------------------+
                                         |
                                         v
                     +-------------------+-------------------+
                     |          chatybot_app.py              |
                     | 1. Parses "/documents" arguments.     |
                     | 2. Sets self.rerank_source = speeches |
                     | 3. Initializes DirectoryTextProcessor |
                     +---------------------------------------+
                                         |
                                         v
                     +-------------------+-------------------+
                     |              USER INPUT               |
                     |  "/rerank "separation of powers",     |
                     |            top_n=3, item=2"           |
                     +-------------------+-------------------+
                                         |
                                         v
                     +-------------------+-------------------+
                     |          chatybot_app.py              |
                     |  - Validates active model is rerank-  |
                     |    capable.                           |
                     |  - Routes call to EasyRanker.         |
                     +-------------------+-------------------+
                                         |
                                         v
                     +-------------------+-------------------+
                     |            EasyRanker                 |
                     |  1. Chunks Speeches into 2-sentence   |
                     |     items (item=2).                   |
                     |  2. Calls local llama.cpp or Jina API.|
                     |  3. Scores and sorts chunks.          |
                     +-------------------+-------------------+
                                         | (Reranked Data Structure)
                                         v
                     +-------------------+-------------------+
                     |          chatybot_app.py              |
                     |  - Renders ASCII Console Table.       |
                     |  - Caches matches in state.           |
                     |  - Injects top_n into next prompt!    |
                     +---------------------------------------+
```

---

## 5. Configuration Updates (`chat_config.toml`)
To define rerank-capable models, `chat_config.toml` will be updated to include an explicit `type = "reranker"` attribute.

```toml
# Example of a Local Reranker model entry
[models.local_jina_rerank]
name = "jinaai/jina-reranker-v3"
type = "reranker"
base_url = "http://localhost:8080/v1/rerank"

# Example of a Remote Cloud Reranker model entry
[models.remote_jina_rerank]
name = "jina-reranker-v3"
type = "reranker"
base_url = "https://api.jina.ai/v1/rerank"
api_key = "MISTRAL_API_KEY" # Points to env var or file
```

---

## 6. Verification & Implementation Steps

Once the planning phase is approved, implementation will proceed as follows:

1.  **Update `config_manager.py`**:
    *   Add validation to parse and register `type = "reranker"` model configurations.
2.  **Update `chatybot_app.py`**:
    *   Import `EasyRanker` from `EasyRerank`.
    *   Introduce state variables: `self.rerank_documents_source` and `self.latest_rerank_results`.
    *   Add regex/line parsing rules for `/documents` and `/rerank` in command routing.
    *   Write the command handlers (`handle_documents_command` and `handle_rerank_command`).
3.  **Prompt Variable Binding**:
    *   Add a placeholder `${latest_rerank}` in `BufferManager.replace_placeholders` to easily inject the top-scoring content blocks into any standard chat prompt automatically.
4.  **Variable Capture Integration (`/setvar` update)**:
    *   Implement the `{LAST_RESPONSE}` placeholder inside the `/setvar` command in `chatybot_app.py`. When processed, it will extract the assistant content from the last item in `self.chat_history` (which supports saving standard responses as well as `/rerank` ASCII tables) and assign it to the target script variable.
