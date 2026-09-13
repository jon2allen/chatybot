# ChatDSL Scripts Session History Remediation

## Executive Summary
Scripts created prior to the introduction of the `/session` system (and `/session history` auto-management) assume stateless or isolated prompt executions. When session history is enabled by default (`enable_chat_history = True`), every prompt and completion is preserved and re-sent to subsequent models in the conversation context.

In multi-model comparison scripts, benchmark suites, and iterative generation loops, this causes:
1. **Context Contamination across Models:** When switching models via `/model`, Model B receives Model A's prompt and answers as prior conversation turns.
2. **Context Bloat & Duplicate Prompts:** In judge workflows, the judge model receives all intermediate prompts, responses, and filebank injections duplicated in the context window.
3. **Loop Accumulation:** In `foreach` or iterative test loops, test case $N$ contains all previous test cases $1 \dots N-1$, corrupting independent test evaluations.

Adding `/session history off` near the top of these scripts (immediately following variable definitions or before the first prompt) restores stateless, independent prompt execution.

---

## Root Cause Analysis

### How Session History Appends
1. User or script sends a prompt (e.g. `/prompt ${question_file}` or `/multiline`).
2. Completion response is returned by Model 1 and appended to `app.chat_history` as `(prompt, response)`.
3. Script executes `/model ${model2}` to test Model 2 on the same questions.
4. When Model 2 is invoked, `ChatybotApp` formats the full `chat_history` into the messages payload.
5. **Result:** Model 2 sees:
   - User: Question generation instructions
   - Assistant: (Questions generated)
   - User: The 10 questions
   - Assistant: Model 1's detailed answers
   - User: The 10 questions (again)
6. Model 2 becomes confused, often commenting on Model 1's answers, refusing to re-answer, or repeating Model 1's hallucinations.

---

## Affected Candidate Scripts

### Category 1: City & Technology Comparison Suites (Direct `nanjing5.chatdsl` Pattern)
All scripts in this category follow an identical 4-phase template:
- Phase 1: Generate 10 evaluation questions $\rightarrow$ save to question file.
- Phase 2: Run Model 1 on question file $\rightarrow$ save to results 1.
- Phase 3: Run Model 2 on question file $\rightarrow$ save to results 2 (**contaminates with Model 1 history**).
- Phase 4: Load results into `{filebank1}` and `{filebank2}` and prompt judge (**judge receives all prior turns plus filebanks**).

| Script Path | Models Evaluated | Target Topic |
| :--- | :--- | :--- |
| [`nanjing5.chatdsl`](file:///Users/jon2allen/github/chatybot/nanjing5.chatdsl) | `mistral_1` vs `nvidia_1` | Nanjing street food |
| [`beijing5.chatdsl`](file:///Users/jon2allen/github/chatybot/beijing5.chatdsl) | `mistral_1` vs `nvidia_1` | Beijing street food |
| [`bulgaria5.chatdsl`](file:///Users/jon2allen/github/chatybot/bulgaria5.chatdsl) | `mistral_1` vs `nvidia_1` | Bulgarian street food & cuisine |
| [`london5.chatdsl`](file:///Users/jon2allen/github/chatybot/london5.chatdsl) | `mistral_1` vs `nanbeige_local` | London street food |
| [`rome5.chatdsl`](file:///Users/jon2allen/github/chatybot/rome5.chatdsl) | `mistral_1` vs `nanbeige_local` | Rome street food |
| [`rome52.chatdsl`](file:///Users/jon2allen/github/chatybot/rome52.chatdsl) | `mistral_1` vs `nanbeige_local` | Rome street food (alternate prompt) |
| [`nvme.chatdsl`](file:///Users/jon2allen/github/chatybot/nvme.chatdsl) | `mistral_1` vs `nvidia_1` | NVMe storage architecture |

---

### Category 2: Algorithm, Poetry & Logic Generation Comparisons
These scripts compare complex multi-part outputs (compilable code, Tang poems, logic problem solutions) across models, then evaluate them with an LLM judge:

| Script Path | Models Evaluated | Issue Description |
| :--- | :--- | :--- |
| [`cpp_algorithms.chatdsl`](file:///Users/jon2allen/github/chatybot/cpp_algorithms.chatdsl) | `gemma4_llamacpp_1` vs `qwen3_llamacpp_1` (Judge: `mistral_1`) | Generates 10 C++ algorithms; Model 2 receives Model 1's code in history, leading to copycat implementations. Judge receives 20 algorithms in history plus filebanks. |
| [`pascal_algorithms.chatdsl`](file:///Users/jon2allen/github/chatybot/pascal_algorithms.chatdsl) | `gemma4_llamacpp_1` vs `qwen3_llamacpp_1` (Judge: `mistral_1`) | Generates 10 Pascal algorithms; Model 2 receives Model 1's code. |
| [`dufu_poetry_analysis.chatdsl`](file:///Users/jon2allen/github/chatybot/dufu_poetry_analysis.chatdsl) | `gemma4_llamacpp_1` vs `qwen3_llamacpp_1` (Judge: `mistral_1`) | Generates 5 Du Fu style Tang poems; Model 2 sees Model 1's Chinese text, pinyin, and translation. |
| [`dufu_tang_poems2.chatdsl`](file:///Users/jon2allen/github/chatybot/dufu_tang_poems2.chatdsl) | `gemma4_llamacpp_1` vs `qwen3_llamacpp_1` (Judge: `mistral_1`) | Alternate Tang poem generation; Model 2 polluted by Model 1's output. |
| [`logic_problems.chatdsl`](file:///Users/jon2allen/github/chatybot/logic_problems.chatdsl) | `gemma4_llamacpp_1` vs `qwen3_llamacpp_1` (Judge: `mistral_1`) | Judge generates 4 problems; Model 1 solves; Model 2 sees Model 1's solutions; Judge receives all previous solution attempts. |
| [`old_logic_promblems/logic_problems.chatdsl`](file:///Users/jon2allen/github/chatybot/old_logic_promblems/logic_problems.chatdsl) | `gemma4_llamacpp_1` vs `qwen3_llamacpp_1` (Judge: `mistral_1`) | Legacy copy of logic problems script. |
| [`fibo.chatdsl`](file:///Users/jon2allen/github/chatybot/fibo.chatdsl) | Single model (iterative language generation) | Sequentially prompts for Fibonacci implementations in C, Pascal, Python, Ada, Fortran. Each subsequent language prompt carries all prior implementations in history. |

---

### Category 3: Multi-Model Benchmark Suites in `dsl_test/`
These scripts test model compliance against novel synthetic state machines (Vortex DSL) or run identical historical battle queries across multiple model engines for database persistence:

| Script Path | Models Evaluated | Issue Description |
| :--- | :--- | :--- |
| [`dsl_test/test_think_dsl.chatdsl`](file:///Users/jon2allen/github/chatybot/dsl_test/test_think_dsl.chatdsl) | `mistral_35` vs `qwen123b` (Judge: `mistral_1`) | Phase 1 runs Model A on Vortex DSL; Phase 2 runs Model B on identical prompt with Model A's trace table in context. |
| [`dsl_test/test_vortex_dsl.chatdsl`](file:///Users/jon2allen/github/chatybot/dsl_test/test_vortex_dsl.chatdsl) | `${model_a}` vs `${model_b}` (Judge: `${judge_model}`) | Model B receives Model A's trace table. |
| [`dsl_test/test_vortex_dsl_advanced.chatdsl`](file:///Users/jon2allen/github/chatybot/dsl_test/test_vortex_dsl_advanced.chatdsl) | `${model_a}` vs `${model_b}` (Judge: `${judge_model}`) | Multi-phase advanced Vortex rules; contamination across phases and models. |
| [`dsl_test/vietnam_war_1968.chatdsl`](file:///Users/jon2allen/github/chatybot/dsl_test/vietnam_war_1968.chatdsl) | `nvidia_1`, `mistral_1`, `devstral_1`, `gemma_3`, `nemotron_super_49b` | Loops through 5 models querying the exact same question `What battles Vietnam war in 1968` and logging each to TinyDB. Model 5 receives 4 prior answers in history. |
| [`dsl_test/ww1_battles_1917.chatdsl`](file:///Users/jon2allen/github/chatybot/dsl_test/ww1_battles_1917.chatdsl) | `nvidia_1`, `mistral_1`, `devstral_1`, `gemma_3`, `nemotron_super_49b` | 5 models queried on identical prompt for DB logging; each model receives prior models' responses. |
| [`dsl_test/civil_war_1865.chatdsl`](file:///Users/jon2allen/github/chatybot/dsl_test/civil_war_1865.chatdsl) | `nvidia_mistral_small4` (3 queries) | Sends the same query 3 times with `/wait 10` and `/dblog`. Query 2 and 3 carry previous turns in history. |

---

### Category 4: Image Accuracy & Vision Test Suite
| Script Path | Vision Model / Judge | Issue Description |
| :--- | :--- | :--- |
| [`test_images/accuracytest.chatdsl`](file:///Users/jon2allen/github/chatybot/test_images/accuracytest.chatdsl) | `openrouter_image` / `elephant` | Line 4 explicitly notes: `All context passed via filebanks and variables (no reliance on chat history)`. It tests 15 images in sequence. Without `/session history off`, image 15 carries all 14 preceding image analyses and judge evaluations, causing massive token bloat and context exhaustion. |

---

### Category 5: Cookbook Recipes in `doc/cookbook/` & `src/chatybot/doc/cookbook/`
Tutorial cookbook recipes demonstrating multi-model comparisons and edge-case fuzzing:

| Recipe Path | Pattern | Issue Description |
| :--- | :--- | :--- |
| [`doc/cookbook/04_1_comparison_pattern.chatdsl`](file:///Users/jon2allen/github/chatybot/doc/cookbook/04_1_comparison_pattern.chatdsl) | `mistral_1` vs `gemma_3` (Judge: `gemini_flash`) | Phase B runs Model 2 with identical prompt; Model 2 receives Model 1's quiz questions and answers. |
| [`doc/cookbook/04_2_comparison_template.chatdsl`](file:///Users/jon2allen/github/chatybot/doc/cookbook/04_2_comparison_template.chatdsl) | Parameterized `${model1}` vs `${model2}` | Model 2 receives Model 1's study guide. |
| [`doc/cookbook/04_3_effort_abtest.chatdsl`](file:///Users/jon2allen/github/chatybot/doc/cookbook/04_3_effort_abtest.chatdsl) | `devstral_1` (`low` vs `high` effort) | Tests same prompt under different effort levels; `effort=high` run receives `effort=low` run in history. |
| [`doc/cookbook/14_3_judge_ensemble.chatdsl`](file:///Users/jon2allen/github/chatybot/doc/cookbook/14_3_judge_ensemble.chatdsl) | `mistral_1`, `gemma_3`, `gemini_flash` | 3 models answer same question `${q}`; Gemma and Gemini receive prior models' answers. |
| [`doc/cookbook/14_6_prompt_fuzzer.chatdsl`](file:///Users/jon2allen/github/chatybot/doc/cookbook/14_6_prompt_fuzzer.chatdsl) | Fuzzing edge-case payloads in `foreach` loop | Each payload execution leaks into subsequent iterations, breaking payload isolation. |
| [`doc/cookbook/14_9_self_improve_macro.chatdsl`](file:///Users/jon2allen/github/chatybot/doc/cookbook/14_9_self_improve_macro.chatdsl) | Iterative macro refinement | Round 2 prompt carries Round 1 baseline and critique in history. |

*(Note: All cookbook recipes are mirrored identically under `src/chatybot/doc/cookbook/`.)*

---

## Remediation Status: Option 1 Implemented Across All 33 Files

All 27 unique scripts (33 files including cookbook mirrors) have been remediated with `/session history off`:
- Category 1: 7 comparison suites (`nanjing5`, `beijing5`, `bulgaria5`, `london5`, `rome5`, `rome52`, `nvme`)
- Category 2: 7 algorithm, poetry, and logic suites (`cpp_algorithms`, `pascal_algorithms`, `dufu_poetry_analysis`, `dufu_tang_poems2`, `logic_problems`, legacy copy, `fibo`)
- Category 3: 6 benchmark suites (`test_think_dsl`, `test_vortex_dsl`, `test_vortex_dsl_advanced`, `vietnam_war_1968`, `ww1_battles_1917`, `civil_war_1865`)
- Category 4: 1 image accuracy suite (`test_images/accuracytest`)
- Category 5: 6 cookbook comparison & fuzz recipes (12 files under `doc/cookbook/` and `src/chatybot/doc/cookbook/`)

---

## Deep Dive: What Scripts Benefit from `/session` vs What Cannot

### 1. Scripts That BENEFIT from `/session` (History ON)

These scripts fundamentally require conversational state accumulation, multi-turn decision making, and feedback loops.

#### A. Autonomous Agentic Tool Loops (`/tool loop`)
In an agentic workflow, the model calls tools (e.g. `list_directory`, `read_file`, `write_file`, `run_command`). The tool execution output is sent back as a tool result message. The model must see the prior prompt, its own tool invocation, and the tool execution output in conversation history to decide what tool to invoke next or finalize its answer.

**Concrete Example:**
```chatdsl
# Agentic tool use MUST have session history enabled:
/tools enable list_directory,read_file,write_file,run_command
/tool loop 10

/multiline
Inspect test_auth.py, read the implementation in auth.py, fix the failing token validation test, and verify by running pytest.
;;
```
*Why `/session` is needed here:* Without session history, each turn in the tool loop would forget the previous tool call and its stdout/stderr, causing an infinite loop or immediate failure.

#### B. Multi-Turn Interactive Refinement (Single Model)
Scripts orchestrating an iterative interview, progressive elaboration, or conversational debugging with a single model.

**Concrete Example:**
```chatdsl
# Single-model multi-turn reasoning:
/model devstral_1
Design a high-throughput event processing architecture for IoT telemetry.
;;

# Turn 2 relies on Turn 1 context:
Now identify the top 3 failure modes in that architecture and provide Kafka configuration settings to mitigate each.
;;
```

---

### 2. Scripts That CANNOT Benefit from `/session` (Require `/session history off`)

These scripts require pure, stateless, independent evaluation of each prompt.

#### A. Multi-Model Comparisons and A/B Benchmarks
Scripts that evaluate Model A and Model B on the exact same task, followed by an evaluation judge.

**Concrete Example:**
```chatdsl
# MUST disable session history:
/session history off

set prompt = "Implement an LRU Cache in Python with O(1) get and put operations."

/model gemma4_llamacpp_1
${prompt}
/save gemma_lru.txt

# Model switch:
/model qwen3_llamacpp_1
${prompt}
/save qwen_lru.txt

# Judge evaluation via clean filebanks:
/model mistral_1
/filebank1 gemma_lru.txt
/filebank2 qwen_lru.txt
Compare the performance, cleanliness, and edge-case handling of Candidate A and Candidate B:
Candidate A: {filebank1}
Candidate B: {filebank2}
/save judge_verdict.txt
```
*Why `/session` fails here:* If history were ON, Qwen would receive Gemma's implementation in its prompt context. Qwen would either copy Gemma's approach or critique Gemma rather than generating its own independent solution.

#### B. Synthetic Rule-Compliance Benchmarks (e.g. Vortex DSL)
Evaluating zero-shot reasoning against synthetic, unseen state machines. If Model B sees Model A's state trace table, the test ceases to be zero-shot.

#### C. Batch Test Matrices & Prompt Fuzzing (`foreach`)
Loops that fuzz an API gateway or prompt template with varying attack payloads or test cases. Leaking Payload $N-1$ into Payload $N$ ruins test isolation.

#### D. Database Persistence Pipelines (`/dblog`)
Scripts querying 5 different models on historical facts and saving records into TinyDB. History retention causes subsequent models to see previous models' database entries.

---

## Summary Checklist for Script Authors

| Script Type | Recommended Setting | Rationale |
| :--- | :---: | :--- |
| `/tool loop` & Agentic Tool Execution | `/session history on` | Model must see previous tool calls & outputs |
| Multi-Turn Conversational Refinement | `/session history on` | Turn $N$ references ideas from Turn $N-1$ |
| Multi-Model Comparative Benchmarking | `/session history off` | Prevents cross-model context contamination |
| LLM-as-a-Judge Workflows | `/session history off` | Judge should only see filebanks, not generation history |
| `foreach` Test Loops & Fuzzing | `/session history off` | Ensures test case isolation across iterations |
| Batch `/dblog` Multi-Model Surveys | `/session history off` | Ensures pure answers from each engine |

