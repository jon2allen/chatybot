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

## Remediation Options

### Option 1: Script-Level Fix (Explicit `/session history off`)
Add `/session history off` near the top of affected scripts (e.g. after variable declarations).
- **Pros:** Completely non-breaking; explicitly declares script intent; works identically across all versions.
- **Example:**
  ```chatdsl
  # Initialize variables
  set model1 = "mistral_1"
  set model2 = "nvidia_1"
  /session history off
  ```

### Option 2: Script-Level Clear (`/clearhistory` between model switches)
Keep session history active, but inject `/clearhistory` prior to each `/model` switch or test phase.
- **Pros:** Keeps history active within each model's individual sub-conversation if multi-turn interaction is needed.
- **Cons:** More invasive to edit; requires multiple insertions per script.

### Option 3: Engine-Level Automatic Reset on Model Switch (`chat_config.toml` or CLI flag)
Introduce an engine-level setting (e.g. `auto_clear_on_model_switch = true` or `/model --clean`) that automatically resets chat history when a script or interactive user switches models.
- **Pros:** Solves the problem automatically for all current and future scripts without having to edit individual files.
- **Cons:** Might surprise users who legitimately want multi-turn conversations across model switches (e.g. asking Model B to critique Model A's previous turn directly in conversation).

---

## Candidate Inventory Summary

| Category | Candidate Scripts |
| :--- | :---: |
| Category 1: City & Tech Comparison Suite | 7 scripts |
| Category 2: Algorithm, Poetry & Logic Generation | 7 scripts |
| Category 3: Multi-Model Benchmark Suites | 6 scripts |
| Category 4: Image & Vision Test Suite | 1 script |
| Category 5: Cookbook Multi-Model & Fuzz Recipes | 6 recipes (12 files) |
| **Total Candidates Identified** | **27 unique scripts (33 files)** |
