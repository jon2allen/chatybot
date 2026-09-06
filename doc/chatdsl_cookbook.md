# ChatDSL Cookbook

A task-oriented, recipe-driven companion to the ChatDSL reference docs. Where
[`chatdsl_guide_v1.md`](chatdsl_guide_v1.md) describes *what the language is*,
this cookbook shows *how to build things with it* — one runnable recipe at a
time.

Every recipe ships a complete `.chatdsl` script in [`cookbook/`](cookbook/) plus
a prose walkthrough. Recipes use only commands and idioms confirmed in the
existing examples, parser, and docs.

> **Status:** English-first, structured to mirror the multilingual guide set so
> it can be translated later. Recipes are runnable but require user
> verification against live model endpoints — model aliases (`mistral_1`,
> `gemma_3`, `gemini_flash`, `devstral_1`, `bge_reranker_f16`, ...) are taken
> from the repo's existing examples and profiles; substitute your own.

---

## Table of Contents

- [How to use this cookbook](#how-to-use-this-cookbook)
- [Chapter 1 — Foundations](#chapter-1--foundations)
- [Chapter 2 — Control Flow](#chapter-2--control-flow)
- [Chapter 3 — Context & Buffer Patterns](#chapter-3--context--buffer-patterns)
- [Chapter 4 — Multi-Model Comparison](#chapter-4--multi-model-comparison)
- [Chapter 5 — Rerank & Retrieval](#chapter-5--rerank--retrieval)
- [Chapter 6 — Database & Persistent Memory](#chapter-6--database--persistent-memory)
- [Chapter 7 — Shell Execution & Automation](#chapter-7--shell-execution--automation)
- [Chapter 8 — Tool Loops & Agentic Mode](#chapter-8--tool-loops--agentic-mode)
- [Chapter 9 — Image Generation & Vision](#chapter-9--image-generation--vision)
- [Chapter 10 — Profiles & Reusable Setups](#chapter-10--profiles--reusable-setups)
- [Chapter 11 — Macros & Reusable Prompts](#chapter-11--macros--reusable-prompts)
- [Chapter 12 — Localization & Multilingual Authoring](#chapter-12--localization--multilingual-authoring)
- [Chapter 13 — Diagnostics, Debugging & Performance](#chapter-13--diagnostics-debugging--performance)
- [Chapter 14 — Novel Use Cases](#chapter-14--novel-use-cases)
- [Appendix A — Recipe index](#appendix-a--recipe-index)
- [Appendix B — Cross-reference map](#appendix-b--cross-reference-map)
- [Appendix C — Common pitfalls checklist](#appendix-c--common-pitfalls-checklist)
- [Appendix D — Where to go next](#appendix-d--where-to-go-next)

---

## How to use this cookbook

**Prerequisites**
- Chatybot installed and on your `PATH` (`chatybot`, `chatdsl_parse`).
- API keys configured in `~/.config/chatybot/chat_config.toml`.
- The recipe's required input files (noted per recipe) in your working
  directory, or pass them via the `x=`, `y=`, `z=` script parameters.

**Running a recipe**
```
chat --> /script doc/cookbook/<recipe>.chatdsl x=... y=... z=...
```
The `x`/`y`/`z` parameters are the standard ChatDSL script-parameter slots.
Recipes that accept parameters show the `Usage:` line in their header comment.

**Conventions**
- `#` starts a full-line or inline comment (outside `/multiline` bodies).
- `${name}` is a script variable; `{filebankN}` and `{imagebankN}` are buffer
  references inside prompts; `{param}` (no `$`) is a macro template parameter.
- `/echo` prints to stdout with variable expansion and makes no LLM call — use
  it to mark progress.
- Recipes build on earlier ones. Chapter 1 is prerequisite for Chapters 2-4;
  Chapter 5's rerank recipes build on each other; Chapter 14 composes everything.

**Recipe format**
```
### N.M Recipe Title
Goal · Commands exercised · Script path · Run command · Walkthrough · Variations
```

---

## Chapter 1 — Foundations

Warm-up recipes that establish the mental model: a line is a command, a chat
input, or a comment; the main buffer is one-shot; file banks persist.

### 1.1 First automation
- **Goal:** switch model, set a system role, ask one question, save the answer.
- **Commands:** `/model`, `/system`, chat input, `/save`, `/echo`.
- **Script:** `cookbook/01_1_first_automation.chatdsl`
- **Run:** `/script doc/cookbook/01_1_first_automation.chatdsl`

```dsl
/model mistral_1
/system "You are a concise technical writer."
What are the three tiers of a modern web application? Answer in three bullet points.
/save 01_1_web_tiers.txt
/echo "Saved to 01_1_web_tiers.txt"
```

**Walkthrough**
1. `/model` selects the active LLM alias for subsequent prompts.
2. `/system` sets the system message; it persists across prompts until changed.
3. A bare line (no `/`, not `set`/`if`/`wait`/`#`) is a chat input sent to the LLM.
4. `/save` writes the last LLM response to a file.
5. `/echo` is a local print with variable expansion — no model call.

**Variations:** swap `/model gemini_flash` for a different vendor; add `/temp 0.3` before the prompt.

### 1.2 Contextual analysis
- **Goal:** load a file into the main buffer and ask the LLM to analyze it.
- **Commands:** `set`, `if`, `/file`, `/save`.
- **Script:** `cookbook/01_2_contextual_analysis.chatdsl`
- **Run:** `/script doc/cookbook/01_2_contextual_analysis.chatdsl x=api_specs.json`

```dsl
if ${x} != "" then set file_path = ${x}
if ${file_path} == "" then set file_path = "api_specs.json"
set report = "01_2_report.txt"

/file ${file_path}
Identify all endpoint security vulnerabilities in this file. Summarize each with severity and a fix.
/save ${report}
/echo "Report written to ${report}"
```

**Walkthrough**
1. The two-step `if` guard assigns the parameter `x` if non-empty, else a default.
2. `/file` loads a file into the **main buffer**, which is prepended to the *next* prompt and then consumed — it does not persist like a file bank.
3. The prompt line follows immediately; the buffer text is injected before it.

**Variations:** point `x` at a markdown spec; ask for a different analysis (e.g., "list all undocumented endpoints").

### 1.3 Two file banks, parameterized compare
- **Goal:** load two files into persistent banks and reference both in one prompt.
- **Commands:** `/filebank1`, `/filebank2`, `{filebankN}` references, `/save`.
- **Script:** `cookbook/01_3_two_filebanks.chatdsl`
- **Run:** `/script doc/cookbook/01_3_two_filebanks.chatdsl x=original_v1.py y=refactored_v2.py`

```dsl
if ${x} != "" then set f1 = ${x}
if ${f1} == "" then set f1 = "original_v1.py"
if ${y} != "" then set f2 = ${y}
if ${f2} == "" then set f2 = "refactored_v2.py"

/filebank1 ${f1}
/filebank2 ${f2}

Analyze the differences between {filebank1} and {filebank2}.
List every performance optimization introduced in the second version.
/save 01_3_refactor_analysis.txt
```

**Walkthrough**
1. `/filebankN` loads a file into a persistent slot (1-5) that survives across LLM calls until overwritten or cleared.
2. `{filebank1}` is a *prompt-level* reference (note: no `$`) — the bank's text is substituted into the prompt.
3. Two parameters (`x`, `y`) make the script reusable.

**Variations:** add a third bank for a test suite; ask the model to produce a unified version.

### 1.4 Multiline prompts done right
- **Goal:** send a structured multi-line prompt using the `/multiline` toggle.
- **Commands:** `/multiline`, `;;` terminator.
- **Script:** `cookbook/01_4_multiline_prompts.chatdsl`
- **Run:** `/script doc/cookbook/01_4_multiline_prompts.chatdsl`

```dsl
/model mistral_1
/multiline
Summarize the following points as one paragraph each:
1. Economic impact of remote work
2. Social changes from remote work
3. Environmental effects of remote work
;;
/multiline
/save 01_4_summary.txt
```

**Walkthrough**
1. `/multiline` opens a block; the block ends at a line containing `;;` (or a second `/multiline`).
2. Blank lines inside the block are preserved as part of the prompt.
3. Inside a multiline body, `#` is **text**, not a comment; `\` escapes are not allowed in values.

**Variations:** use the alternate terminator (a second `/multiline`) to close the block.

### 1.5 Variables & substitution
- **Goal:** define variables, interpolate them, inspect with `/dump`.
- **Commands:** `set` (quoted strings), `${name}`, `/dump`, `/echo`.
- **Script:** `cookbook/01_5_variables_substitution.chatdsl`
- **Run:** `/script doc/cookbook/01_5_variables_substitution.chatdsl`

```dsl
set topic = "transformer attention"
set count = 3
set prompt_intro = "You are a patient tutor. Explain in plain language."

/dump topic
/echo "Asking for ${count} points on ${topic}"
${prompt_intro}
List ${count} key ideas behind ${topic}.
/save 01_5_explainer.txt
```

**Walkthrough**
1. `set name = "value"` defines a script-scoped variable; quoted strings may span multiple lines.
2. `${name}` expands inside commands, file paths, and chat-input lines.
3. `/dump topic` prints one variable; `/dump all` prints every variable.

**Variations:** use `/dump all` at the end to confirm final state; add `set count = 5` to lengthen the output.

---

## Chapter 2 — Control Flow

The biggest gap in the existing examples: only `for_test1.chatdsl` exercises
loops and procedures. These recipes fill that gap.

### 2.1 Conditional defaults for script params
- **Goal:** robust parameter handling with fallbacks (the `translate.chatdsl` idiom).
- **Commands:** `if ... then set`, `==`, `!=`, empty-string check.
- **Script:** `cookbook/02_1_param_defaults.chatdsl`
- **Run:** `/script doc/cookbook/02_1_param_defaults.chatdsl x=english.txt y=spanish z=output.txt`

```dsl
if ${x} != "" then set source = ${x}
if ${source} == "" then set source = "english.txt"
if ${y} != "" then set target_lang = ${y}
if ${target_lang} == "" then set target_lang = "spanish"
if ${z} != "" then set output_file = ${z}
if ${output_file} == "" then set output_file = "02_1_output.txt"

/file ${source}
/model gemini_flash
Translate the following into ${target_lang}:
/save ${output_file}
/echo "Translated to ${target_lang} -> ${output_file}"
```

**Walkthrough**
1. Every `if` is single-line: `if cond then cmd`. There is no `else` — emulate with mutually exclusive conditions.
2. The two-step guard (assign from param, then assign default if empty) makes parameters optional.
3. Order matters: the default check must follow the param assignment.

**Variations:** add a fourth param for tone; branch model choice on `target_lang`.

### 2.2 if / not / == / != branching
- **Goal:** branch behavior on a feature-toggle variable.
- **Commands:** `if`, `not`, `==`, `!=`, `/model`, `/temp`.
- **Script:** `cookbook/02_2_if_branching.chatdsl`
- **Run:** `/script doc/cookbook/02_2_if_branching.chatdsl x=creative`

```dsl
if ${x} != "" then set mode = ${x}
if ${mode} == "" then set mode = "factual"

if ${mode} == "creative" then /temp 1.2
if ${mode} == "factual" then /temp 0.3
if not ${mode} == "creative" then /model mistral_1
if ${mode} == "creative" then /model gemini_flash

Write a short paragraph about the invention of the printing press.
/save 02_2_press.txt
```

**Walkthrough**
1. `not` negates a comparison: `if not ${mode} == "creative" then ...`.
2. Multiple `if`s are independent; there is no `else if` chain.
3. Numeric and string equality both use `==`.

**Variations:** add a `debug` mode that turns on `/trace tps on`.

### 2.3 foreach over range()
- **Goal:** iterate a numeric sequence, run one prompt per step, accumulate.
- **Commands:** `foreach ... in range(...) ... endfor`, `${num}`, `/save`.
- **Script:** `cookbook/02_3_foreach_range.chatdsl`
- **Run:** `/script doc/cookbook/02_3_foreach_range.chatdsl`

```dsl
/model mistral_1
foreach num in range(1:4:1)
  /echo "Generating table for x=${num}"
  Generate the multiplication table for ${num} up to 10.
  /save 02_3_table_${num}.txt
endfor
/echo "Done"
```

**Walkthrough**
1. `range(start:end:step)` yields a numeric sequence; the loop variable is `${num}`.
2. The loop body is the indented lines between `foreach` and `endfor`.
3. `/save` per iteration writes distinct files via the interpolated `${num}`.

**Variations:** change the step (`range(2:20:2)` for evens); accumulate into one file by appending in the prompt.

### 2.4 foreach over lines() with break
- **Goal:** process a buffer line-by-line and stop at a sentinel.
- **Commands:** `/filebank`, `foreach ... in lines(...)`, `break`, `if`.
- **Script:** `cookbook/02_4_foreach_lines_break.chatdsl`
- **Run:** `/script doc/cookbook/02_4_foreach_lines_break.chatdsl x=config.env`

```dsl
if ${x} != "" then set src = ${x}
if ${src} == "" then set src = "config.env"
/filebank1 ${src}
foreach line in lines({filebank1})
  if ${line} == "END" then break
  /echo "Processing: ${line}"
endfor
/echo "Stopped at sentinel"
```

**Walkthrough**
1. `lines(text)` splits a text block into lines, yielding one line per iteration.
2. `break` exits the nearest enclosing `foreach`.
3. The buffer must be loaded into a bank (or a variable) to be iterated; `lines({filebank1})` reads the bank.
4. The empty-line guard (`if ${line} == "" then break`) handles trailing newlines.

**Variations:** accumulate matching lines into a `set found = ""` summary variable.

### 2.5 Procedures: defproc / endproc / local / /proc
- **Goal:** define a reusable procedure with a parameter and local state.
- **Commands:** `defproc`, `local`, `foreach`, `break`, `endproc`, `/proc`.
- **Script:** `cookbook/02_5_procedures.chatdsl`
- **Run:** `/script doc/cookbook/02_5_procedures.chatdsl`

```dsl
defproc find_and_stop(target)
  local found = false
  foreach num in range(10:50:10)
    if ${num} == ${target} then break
    /echo "checking ${num} (looking for ${target})"
    /dump num
  endfor
  /echo "done searching for ${target}"
endproc

/proc find_and_stop target="30"
/proc find_and_stop target="20"
```

**Walkthrough**
1. `defproc name(params)` ... `endproc` defines a procedure; params are passed by name at the call site.
2. `local` declares a procedure-scoped variable that does not leak to the caller.
3. `break` works inside a proc's loop; the proc can be invoked multiple times with different args.

**Variations:** return a value by `set`-ting a script variable the caller reads after the call.

---

## Chapter 3 — Context & Buffer Patterns

### 3.1 The /clearfile discipline
- **Goal:** show why `/clearfile` before re-loading prevents context pollution.
- **Commands:** `/clearfile`, `/file`, `/showfile`, `/save`.
- **Script:** `cookbook/03_1_clearfile_discipline.chatdsl`
- **Run:** `/script doc/cookbook/03_1_clearfile_discipline.chatdsl`

```dsl
/model mistral_1
/file a.txt
Summarize document A in two sentences.
/save 03_1_sum_a.txt

/clearfile
/file b.txt
Summarize document B in two sentences.
/save 03_1_sum_b.txt
/echo "Both summaries saved"
```

**Walkthrough**
1. Without `/clearfile`, stale main-buffer text can bleed into the next prompt.
2. `/showfile all` inspects the current buffer for debugging.
3. File banks are cleared with `/filebankN clear`, not `/clearfile`.

**Variations:** add `/showfile all` between the two phases to observe the buffer state.

### 3.2 Five file banks in parallel
- **Goal:** load spec + two refs + two prior outputs, reference all five in one prompt.
- **Commands:** `/filebank1..5`, `{filebankN}`.
- **Script:** `cookbook/03_2_five_filebanks.chatdsl`
- **Run:** `/script doc/cookbook/03_2_five_filebanks.chatdsl`

```dsl
/filebank1 spec.md
/filebank2 ref_a.md
/filebank3 ref_b.md
/filebank4 prior_run_1.txt
/filebank5 prior_run_2.txt

/model mistral_1
/multiline
Using {filebank1} as the spec, cross-check {filebank2} and {filebank3}, and reconcile the discrepancies between {filebank4} and {filebank5}. Produce a unified report.
;;
/multiline
/save 03_2_unified_report.txt
```

**Walkthrough**
1. Banks survive across calls until overwritten or cleared.
2. Each `{filebankN}` reference substitutes that bank's full text into the prompt.
3. Useful for multi-source synthesis where you want all context visible at once.

**Variations:** load a sixth source into the main buffer via `/file` for a 6-way synthesis.

### 3.3 Sparse-context retrieval
- **Goal:** multiple `/rerank` queries → `/setvar {LAST_RESPONSE}` → stitch into a final prompt.
- **Commands:** `/model`, `/filebank1`, `/documents filebank=1`, `/rerank`, `/setvar {LAST_RESPONSE}`.
- **Script:** `cookbook/03_3_sparse_context.chatdsl`
- **Run:** `/script doc/cookbook/03_3_sparse_context.chatdsl`

```dsl
/model bge_reranker_f16
/filebank1 10_foods.txt
/documents filebank=1

/rerank "German cake dessert with cherries" top_n=1 split=line items=2 return=text
/setvar german_dessert {LAST_RESPONSE}

/rerank "Spanish seafood rice dish" top_n=1 split=line items=2 return=text
/setvar spanish_dish {LAST_RESPONSE}

/model mistral_1
/clearfile
/multiline
Plan a fusion menu using:
German: ${german_dessert}
Spanish: ${spanish_dish}
;;
/multiline
/save 03_3_fusion_menu.txt
```

**Walkthrough**
1. Use a reranker model (`bge_reranker_f16`) for extraction, a generative model for synthesis.
2. `{LAST_RESPONSE}` captures the rerank output into a variable for later injection.
3. `top_n=1` keeps the context sparse — only the single most relevant chunk per query.

**Variations:** add a third rerank query; raise `top_n` for denser context.

### 3.4 notemode + codeonly
- **Goal:** get just code blocks saved to files, suppress prose.
- **Commands:** `/codeonly`, `/notemode`, `/save`.
- **Script:** `cookbook/03_4_notemode_codeonly.chatdsl`
- **Run:** `/script doc/cookbook/03_4_notemode_codeonly.chatdsl`

```dsl
/model mistral_1
/codeonly
/notemode on
Write a Python function that returns the nth Fibonacci number.
/save 03_4_fib.py
/notemode off
/codeoff
/echo "Code extracted to 03_4_fib.py"
```

**Walkthrough**
1. `/codeonly` instructs the model to skip conversational filler.
2. `/notemode on` auto-extracts code blocks from the response on `/save`, writing just the code.
3. Turn both off afterward to restore normal output for later prompts.

**Variations:** request multiple files; `/notemode` will extract each fenced block.

---

## Chapter 4 — Multi-Model Comparison

This is the flagship pattern that `dufu_poetry_analysis.chatdsl`,
`logic_problems.chatdsl`, `cpp_algorithms.chatdsl`, `nvme.chatdsl`, and
`beijing5.chatdsl` all hand-roll. These recipes abstract and name it.

### 4.1 The comparison pattern, step by step
- **Goal:** the canonical shape — run 2 models on an identical prompt, judge, score.
- **Commands:** `set`, `/model`, `/multiline`, `/save`, `/filebank1..3`, `{filebankN}`.
- **Script:** `cookbook/04_1_comparison_pattern.chatdsl`
- **Run:** `/script doc/cookbook/04_1_comparison_pattern.chatdsl`

```dsl
set model1 = "mistral_1"
set model2 = "gemma_3"
set judge = "gemini_flash"
set out = "04_1_compare"

/model ${model1}
/multiline
Generate 5 quiz questions about photosynthesis with answers.
;;
/multiline
/save ${out}_m1.txt
/filebank1 ${out}_m1.txt

/model ${model2}
/multiline
Generate 5 quiz questions about photosynthesis with answers.
;;
/multiline
/save ${out}_m2.txt
/filebank2 ${out}_m2.txt

/model ${judge}
/multiline
Compare {filebank1} vs {filebank2} for scientific accuracy. Score each 0-10 per question and pick an overall winner.
;;
/multiline
/save ${out}_verdict.txt
/echo "Comparison complete: ${out}_verdict.txt"
```

**Walkthrough**
1. Five phases: configure → run A → run B → judge → verdict.
2. The prompt text for A and B is **identical**, isolating the model as the only variable.
3. Banks aggregate the per-model outputs so the judge sees both in one prompt.

**Variations:** add a third contestant model; produce a markdown scoring table in the judge prompt.

### 4.2 Reusable comparison template
- **Goal:** parameterized so a user drops in their own topic/models.
- **Script:** `cookbook/04_2_comparison_template.chatdsl`
- **Run:** `/script doc/cookbook/04_2_comparison_template.chatdsl x="photosynthesis" y=mistral_1 z=gemma_3`

```dsl
if ${x} != "" then set topic = ${x}
if ${topic} == "" then set topic = "the water cycle"
if ${y} != "" then set model1 = ${y}
if ${model1} == "" then set model1 = "mistral_1"
if ${z} != "" then set model2 = ${z}
if ${model2} == "" then set model2 = "gemma_3"
set judge = "gemini_flash"

/model ${model1}
Generate a study guide on ${topic}.
/save 04_2_a.txt
/filebank1 04_2_a.txt

/model ${model2}
Generate a study guide on ${topic}.
/save 04_2_b.txt
/filebank2 04_2_b.txt

/model ${judge}
/multiline
Compare {filebank1} and {filebank2} for clarity, accuracy, and completeness on ${topic}. Give scores and a winner.
;;
/multiline
/save 04_2_verdict.txt
```

**Walkthrough**
1. Three parameters (`x`=topic, `y`=model A, `z`=model B) drive the whole script.
2. Swap any alias without editing the body — useful for recurring benchmarks.

**Variations:** wrap the A/B runs in a `foreach` over an array of models for an N-way comparison.

### 4.3 Reasoning-effort A/B
- **Goal:** same prompt under different `/effort` levels, compare quality.
- **Commands:** `/effort`, `/reasoning`, `/model`, `/save`, `/filebank`.
- **Script:** `cookbook/04_3_effort_abtest.chatdsl`
- **Run:** `/script doc/cookbook/04_3_effort_abtest.chatdsl`

```dsl
/model devstral_1
/reasoning on
/effort low
/multiline
Design a rate-limiter for a public API. Explain trade-offs.
;;
/multiline
/save 04_3_low.txt
/filebank1 04_3_low.txt

/effort high
/multiline
Design a rate-limiter for a public API. Explain trade-offs.
;;
/multiline
/save 04_3_high.txt
/filebank2 04_3_high.txt

/model gemini_flash
/multiline
Compare {filebank1} (effort=low) and {filebank2} (effort=high). Which design is more robust and why?
;;
/multiline
/save 04_3_verdict.txt
```

**Walkthrough**
1. `/effort` only affects reasoning-capable models; `/reasoning on` enables the reasoning phase.
2. The identical prompt isolates the effort level as the only variable.

**Variations:** add `/thinking on` to expose the reasoning trace in the saved output.

---

## Chapter 5 — Rerank & Retrieval

### 5.1 rerank basics
- **Goal:** tour `top_n`, `split`, and `return` modes.
- **Commands:** `/documents filebank=1`, `/rerank`, `/setvar {LAST_RESPONSE}`.
- **Script:** `cookbook/05_1_rerank_basics.chatdsl`
- **Run:** `/script doc/cookbook/05_1_rerank_basics.chatdsl`

```dsl
/model bge_reranker_f16
/filebank1 10_foods.txt
/documents filebank=1

/rerank "dessert" top_n=3 split=line return=text
/setvar hits {LAST_RESPONSE}
/echo "Top 3 lines:"
/echo "${hits}"

/rerank "seafood" top_n=2 split=sentence return=summ
/setvar summ {LAST_RESPONSE}
/echo "Summary:"
/echo "${summ}"
```

**Walkthrough**
1. `split=line|sentence|paragraph` controls how the source is chunked.
2. `return=text` returns the raw chunk; `return=summ` returns a summary of the chunk.
3. `top_n` sets how many results to return.

**Variations:** try `split=paragraph` on a prose document; compare `text` vs `summ` outputs.

### 5.2 Rerank a filebank
- **Goal:** generate content, then rerank it.
- **Script:** `cookbook/05_2_rerank_filebank.chatdsl`
- **Run:** `/script doc/cookbook/05_2_rerank_filebank.chatdsl`

```dsl
/model mistral_1
/multiline
List 30 European dishes, one per line with a short description.
;;
/multiline
/save 05_2_dishes.txt

/filebank1 05_2_dishes.txt
/model bge_reranker_f16
/documents filebank=1
/rerank "chicken dish" top_n=1 split=line items=1 return=text
/setvar chicken {LAST_RESPONSE}
/echo "Chicken pick: ${chicken}"
```

**Walkthrough**
1. A generative model produces a candidate set; a reranker selects from it.
2. `items=1` returns a single best match.

**Variations:** run several rerank queries (vegetarian, dessert) over the same bank.

### 5.3 Rerank a directory
- **Goal:** `/documents dir=` with batched limits for large corpora.
- **Commands:** `/documents dir="..."`, `limit_batch_size`, `limit_top_n`, `max_limit`.
- **Script:** `cookbook/05_3_rerank_directory.chatdsl`
- **Run:** `/script doc/cookbook/05_3_rerank_directory.chatdsl`

```dsl
/model bge_reranker_f16
/documents dir="."
/rerank "macro definition grammar" top_n=2 limit_top_n=3 max_limit=10 return=summ
/setvar found {LAST_RESPONSE}
/echo "Found:"
/echo "${found}"
```

**Walkthrough**
1. Batched top-N pre-filter keeps memory bounded: `limit_batch_size` is the window, `limit_top_n` keeps the longest chunks per batch, `max_limit` caps total chunks.
2. For a large book, raise `max_limit` based on the split mode (line mode needs more; sentence mode fewer). See [`BATCH_N_WALKTHROUGH.md`](BATCH_N_WALKTHROUGH.md) for the scaling math.

**Variations:** set `split=line` and a larger `max_limit` to query a whole book.

### 5.4 Rerank from a variable / CHAT_HISTORY
- **Goal:** `/documents var=CHAT_HISTORY` reranks over the live chat history.
- **Script:** `cookbook/05_4_rerank_var.chatdsl`
- **Run:** `/script doc/cookbook/05_4_rerank_var.chatdsl`

```dsl
/model bge_reranker_f16
/documents var=CHAT_HISTORY
/rerank "image generation" top_n=3 split=sentence return=text
/setvar recall {LAST_RESPONSE}
/echo "Recalled:"
/echo "${recall}"
```

**Walkthrough**
1. `var=CHAT_HISTORY` treats the conversation so far as the corpus.
2. `var=<name>` reranks any variable's contents the same way.

**Variations:** rerank a long `set transcript = "..."` variable you built from prior outputs.

### 5.5 Rerank from a DB
- **Goal:** `/documents db=<name>` combined with `/setdb`.
- **Script:** `cookbook/05_5_rerank_db.chatdsl`
- **Run:** `/script doc/cookbook/05_5_rerank_db.chatdsl`

```dsl
/setdb knowledge_base
/model bge_reranker_f16
/documents db=knowledge_base
/rerank "encryption standards" top_n=3 return=text
/setvar kb_hits {LAST_RESPONSE}
/echo "KB hits:"
/echo "${kb_hits}"
```

**Walkthrough**
1. The DB source pulls stored documents as the rerank corpus.
2. Pair with `/searchdb` for a hybrid recall (vector search + rerank).

**Variations:** `/dblog` the rerank results back into the DB to grow the knowledge base.

### 5.6 Generate-then-rerank pipeline
- **Goal:** LLM produces candidates → rerank filters → LLM assembles a menu.
- **Script:** `cookbook/05_6_generate_then_rerank.chatdsl`
- **Run:** `/script doc/cookbook/05_6_generate_then_rerank.chatdsl`

The full four-step pipeline (generate 60 dishes → load to bank → three rerank
queries for veg/chicken/dessert → generative model assembles a 3-course menu).
See the script for the complete listing; it generalizes `generate_and_rerank_menu.chatdsl`.

**Walkthrough**
1. **Generate:** a generative model writes a large candidate list to a file.
2. **Index:** load that file into a filebank and set it as the document source.
3. **Extract:** run one rerank query per desired category, capturing each with `/setvar {LAST_RESPONSE}`.
4. **Assemble:** switch back to a generative model and inject all three picks into a final menu prompt.

**Variations:** add more categories; use `return=summ` to summarize each pick before assembly.

---

## Chapter 6 — Database & Persistent Memory

### 6.1 Create/connect a DB
- **Goal:** `/setdb`, `/dblist`, `/dblog` the response loop.
- **Script:** `cookbook/06_1_db_connect.chatdsl`
- **Run:** `/script doc/cookbook/06_1_db_connect.chatdsl`

```dsl
/dblist
/setdb research_log
/model mistral_1
Summarize the latest NIST guidance on password length in three bullets.
/save 06_1_pw.txt
/dblog
/echo "Response logged to research_log"
```

**Walkthrough**
1. `/dblist` shows existing TinyDB stores; `/setdb` connects (creating the DB if absent).
2. `/dblog` appends the last LLM response to the active DB.

**Variations:** run `/dbprint` to dump the DB contents to stdout or a file.

### 6.2 Search & inject (Research-Log pattern)
- **Goal:** `/searchdb` → `/loadvar` → `${history}` in prompt → `/dblog`.
- **Script:** `cookbook/06_2_search_inject.chatdsl`
- **Run:** `/script doc/cookbook/06_2_search_inject.chatdsl`

```dsl
/setdb research_log
/searchdb "password guidance 2024"
/loadvar history ALL
/model mistral_1
/multiline
Given prior research: ${history}
What is the recommended transition plan for password policy?
;;
/multiline
/dblog
```

**Walkthrough**
1. `/searchdb` runs a vector query; `/loadvar history ALL` loads all hits into a variable.
2. Inject `${history}` into the prompt; `/dblog` persists the new response, growing the KB.

**Variations:** `/loadvar history 1-5` to load only the top 5 hits.

### 6.3 Export a variable to a file
- **Goal:** `/savevar` to file; round-trip into a rerank source.
- **Script:** `cookbook/06_3_export.chatdsl`
- **Run:** `/script doc/cookbook/06_3_export.chatdsl`

```dsl
/setdb research_log
/searchdb "rate limiting"
/loadvar rl ALL
/savevar rl 06_3_rate_limiting.json
/echo "Exported to 06_3_rate_limiting.json"
```

**Walkthrough**
1. `/savevar name path` writes a variable's contents to a file.
2. The exported file can be loaded into a filebank and used as a rerank source.

**Variations:** export to `.txt` and rerank it with `/documents filebank=1`.

---

## Chapter 7 — Shell Execution & Automation

The `/run` command and its capture variables are documented but appear in no
existing example script. These recipes fill that gap.

### 7.1 /run and capturing output
- **Goal:** run a shell command and use its captured outputs.
- **Commands:** `/run`, `${RUN_COMPLETION}`, `${RUN_ERROR}`, `${RUN_EXIT_CODE}`, `${LAST_COMPLETION}`.
- **Script:** `cookbook/07_1_run_capture.chatdsl`
- **Run:** `/script doc/cookbook/07_1_run_capture.chatdsl`

```dsl
/run date +%Y-%m-%d
/echo "stdout: ${RUN_COMPLETION}"
/echo "exit: ${RUN_EXIT_CODE}"
/run ls -1 *.txt
/echo "files:"
/echo "${LAST_COMPLETION}"
```

**Walkthrough**
1. `/run` executes a shell command and captures stdout in `${RUN_COMPLETION}`, stderr in `${RUN_ERROR}`, and the exit code in `${RUN_EXIT_CODE}`.
2. `${LAST_COMPLETION}` is an alias for the most recent stdout.
3. Each `/run` overwrites the capture variables.

**Variations:** branch on `${RUN_EXIT_CODE}` with an `if` to handle command failure.

### 7.2 Safe vs unsafe mode
- **Goal:** `/run_safe`, `/run_unsafe askfirst`.
- **Script:** `cookbook/07_2_run_safe.chatdsl`
- **Run:** `/script doc/cookbook/07_2_run_safe.chatdsl`

```dsl
/run_safe
/run echo "safe path confirmed"
/run_unsafe askfirst
/run echo "unsafe path confirmed"
/run_safe
```

**Walkthrough**
1. `/run_safe` blocks dangerous commands; `/run_unsafe` disables the guard.
2. `askfirst` adds a Y/N confirmation prompt before each command in unsafe mode.
3. Re-enable safe mode at the end to leave the session in a guarded state.

**Variations:** use `askfirst` permanently in interactive sessions for a safety net.

### 7.3 Data pipeline: shell → prompt → save
- **Goal:** capture git log via `/run`, feed into a prompt, save a summary.
- **Script:** `cookbook/07_3_data_pipeline.chatdsl`
- **Run:** `/script doc/cookbook/07_3_data_pipeline.chatdsl`

```dsl
/run git log --oneline -20
/setvar log {LAST_COMPLETION}
/model mistral_1
/multiline
Summarize the recent activity from this git log:
${log}
;;
/multiline
/save 07_3_activity.txt
```

**Walkthrough**
1. `/run` output is captured into a variable with `/setvar ... {LAST_COMPLETION}`.
2. The variable is injected into a multiline prompt for the LLM to synthesize.

**Variations:** add a second `/run git diff --stat` and include both in the prompt.

---

## Chapter 8 — Tool Loops & Agentic Mode

### 8.1 Enabling tools
- **Goal:** turn on tools and configure limits.
- **Commands:** `/tool on|off|list|enable|disable|auto|max_turns|rate_limit`.
- **Script:** `cookbook/08_1_tool_enable.chatdsl`
- **Run:** `/script doc/cookbook/08_1_tool_enable.chatdsl`

```dsl
/tool on
/tool enable all
/tool auto on
/tool max_turns 30
/tool rate_limit 2
/tool list
```

**Walkthrough**
1. `/tool on` loads tool schemas into the system prompt; `/tool enable all` activates every tool.
2. `/tool auto on` lets the model loop on tool outputs; `max_turns` caps the loop; `rate_limit` paces turns.
3. `/tool list` shows the active tool set.

**Variations:** `/tool disable run_command` to remove shell access for a read-only session.

### 8.2 Autonomous tool loop & live prompt editing
- **Goal:** run an agentic loop, inspect prompt context, and live-tune system instructions or tool definitions mid-session.
- **Commands:** `/tool on`, `/tool enable`, `/tool auto`, `/tool max_turns`, `/tool prompt`, `/tool prompt live_edit`, `/tool loop`.
- **Script:** `cookbook/08_2_tool_loop.chatdsl`
- **Run:** `/script doc/cookbook/08_2_tool_loop.chatdsl`

```dsl
/model devstral_1
/tool on
/tool enable all
/tool auto on
/tool max_turns 50
/tool prompt
/tool loop 50 force
```

**Walkthrough**
1. `/tool prompt` prints the active tool context and agentic instructions before you launch — review them here.
2. `/tool prompt live_edit` (or `/tool prompt edit_live`) opens your configured text editor (using `$VISUAL`, `$EDITOR`, or `tools_config.toml` setting). You can edit tool schemas above the marker and custom system instructions below the marker; changes take effect immediately for the active session.
3. `/tool loop 50 force` runs up to 50 autonomous turns; `force` skips per-turn confirmation.
4. Interrupt safely with the session's interrupt key if it goes off track.

**Variations:**
- `/tool prompt live_edit` — Open live editor to customize injected tool descriptions or agentic behavior on the fly.
- `/tool prompt` — Verify active overrides with the `[Live Edit Override Active]` banner.
- To revert overrides and restore `tools_config.toml` defaults, clear the text in the live editor or reset the session.

### 8.3 Agentic scratchpad & disposable script execution (/tool scratch)
- **Goal:** provide a safe, isolated directory where models can write, test, and run disposable scripts (Python/Bash) without cluttering or altering project repository files.
- **Commands:** `/tool on`, `/tool auto on`, `/tool scratch on`, `/tool scratch status`, `/tool scratch clean`, `/tool scratch off`.
- **Script:** `cookbook/08_3_tool_scratch.chatdsl`

```dsl
/model devstral_1
/tool on
/tool auto on
/tool scratch on

# Ask the model to generate and execute a scratch script
chat --> Write a quick python script in scratch to compute first 15 fibonacci numbers and print them

# Check files written in the scratchpad area
/tool scratch status

# Clean up all disposable artifacts when finished
/tool scratch clean
```

**Walkthrough**
1. `/tool scratch on` creates a dedicated temporary directory (`~/.local/share/chatybot/sessions/<id>/scratch/` or global fallback `~/.local/share/chatybot/scratch/`) and injects its path and usage instructions into the system prompt.
2. The model writes its scripts using `write_file` and runs them via `run_command` (e.g. `python3 "<scratch_dir>/<file>"`).
3. `/tool scratch status` lists the generated scripts and file counts.
4. `/tool scratch clean` deletes disposable artifacts from the scratch directory.

---


## Chapter 9 — Image Generation & Vision

No existing example generates or reads images. These recipes cover both.

### 9.1 Generate & save an image
- **Goal:** basic image generation.
- **Commands:** `/imagine`, `/imagesize`, `/imagequality`, `/imagedir`, `/saveimage`, `/listimages`.
- **Script:** `cookbook/09_1_image_generate.chatdsl`
- **Run:** `/script doc/cookbook/09_1_image_generate.chatdsl`

```dsl
/imagesize 1024x1024
/imagequality hd
/imagedir images/
/imagine sunset over a calm mountain lake, cinematic
/saveimage images/09_1_lake.jpg
/listimages
```

**Walkthrough**
1. `/imagesize` and `/imagequality` set generation parameters; `/imagedir` sets the output folder.
2. `/imagine` generates from a text prompt; `/saveimage` persists the last generated image.
3. `/listimages` shows saved images and their metadata.

**Variations:** try `/imagequality standard` for faster, cheaper generation.

### 9.2 Image banks in prompts (vision)
- **Goal:** load an image and describe it in a prompt.
- **Commands:** `/loadimage`, `/imagebank1`, `{imagebank1}`.
- **Script:** `cookbook/09_2_image_vision.chatdsl`
- **Run:** `/script doc/cookbook/09_2_image_vision.chatdsl` (run 9.1 first)

```dsl
/loadimage images/09_1_lake.jpg imagebank1
/model mistral_1
Describe the mood, lighting, and composition of {imagebank1}. Suggest three caption variants.
/save 09_2_captions.txt
```

**Walkthrough**
1. `/loadimage path imagebankN` loads an image into an image bank with base64 MIME encoding.
2. `{imagebank1}` references the image in the prompt for a vision-capable model.

**Variations:** load two images into banks 1 and 2 and ask the model to compare them.

### 9.3 Batch image generation
- **Goal:** `foreach` over prompts → `/imagine` → `/saveimage` each.
- **Script:** `cookbook/09_3_batch_images.chatdsl`
- **Run:** `/script doc/cookbook/09_3_batch_images.chatdsl`

```dsl
/imagedir images/
foreach num in range(1:4:1)
  /imagine abstract wallpaper ${num}, geometric, 4k
  /saveimage images/09_3_wp_${num}.jpg
endfor
/listimages
```

**Walkthrough**
1. The loop variable `${num}` personalizes each prompt and output filename.
2. `/listimages` at the end confirms all four were saved.

**Variations:** use an array `set prompts[] = [...]` of full prompt strings and iterate with `foreach p in ${prompts}`.

---

## Chapter 10 — Profiles & Reusable Setups

### 10.1 Authoring a profile
- **Goal:** show the profile file format with metadata and a configured environment.
- **Script:** `cookbook/10_1_profile_author.chatdsl`
- **Run:** copy to `~/.config/chatybot/profiles/` and `/profile use cookbook_demo`

```dsl
# @name: Cookbook Demo Profile
# @description: Minimal coding-focused profile for the cookbook
# @version: 1.0

/model devstral_1
/temp 0.2
/tool auto on
/tool on
/tool max_turns 50
/trace tps on
/reasoning on
/effort medium
/system You are a careful coding assistant. Prefer minimal diffs and verify before claiming.

# ============================================================================
# USER CUSTOM CONTENT / MESSAGES / VARIABLES BELOW THIS LINE
# Note: Profile editor will not modify content below this line.
# ============================================================================
```

**Walkthrough**
1. `@name`, `@description`, `@version` are metadata comments the profile manager reads.
2. The body is ordinary ChatDSL that runs when the profile loads.
3. The "USER CUSTOM CONTENT BELOW THIS LINE" marker signals where the profile editor stops modifying.

**Variations:** add `/context_limit 8000` and `/auto_truncate on` for cost control.

### 10.2 The three built-in profiles

A narrative recipe (no script). Chatybot ships three profiles in
`src/chatybot/profiles/`:

| Profile | Model | Tools | Reasoning | Effort | Best for |
|---------|-------|-------|-----------|--------|----------|
| `general` | `mistral_1` | off | off | — | General assistance, no tools |
| `coding` | `devstral_1` | auto on, max_turns 75 | on | none | Coding, debugging |
| `explorer` | (current) | run/run_safe/setdb **disabled** | off | — | Read-only codebase exploration |

**Commands:** `/profile list`, `/profile use <name>`, `/profile clone <name>`,
`/profile delete <name>`, `/profile export <name> <path>`, `/profile import <path>`,
`/profile show`, `/profile edit`.

**When to pick which:** use `general` for chat, `coding` for agentic development,
`explorer` when you want to guarantee no side effects.

### 10.3 Dynamic Sourcing with `/source`
- **Goal:** Execute an environment setup script directly into the live interactive session without exiting, preserving variables, model switches, and auto-loading companion macros.
- **Commands:** `/source <file>`, `set <var> = <val>`, `/model`, `/tool`, `/system`, `/echo`.
- **Script:** `cookbook/10_3_source_setup.chatdsl`
- **Run:** `/source doc/cookbook/10_3_source_setup.chatdsl`

```dsl
# Setup project environment dynamically
set project_name = "antigravity_core"
set api_env = "staging"

/model mistral_1
/temp 0.3
/tool auto on
/tool on
/system "You are an assistant for project ${project_name} in ${api_env} environment."

/echo "Environment '${project_name}' (${api_env}) sourced successfully."
```

**Walkthrough**
1. `/source` reads and executes every line directly in the active REPL session.
2. Unlike running in a subshell, the variables `${project_name}` and `${api_env}`, the model switch to `mistral_1`, and tool toggles persist in your prompt after the command completes.
3. If a companion `macro.chatdsl` is present in the same directory, Chatybot automatically discovers, compiles, and registers its macros.
4. Preprocessing: localized commands (e.g. `/origen`, `/sorgente`, `/加载脚本`, `/مصدر`) are translated on the fly.

### 10.4 Codifying Live Sessions into Scripts with `/chatdsl history`
- **Goal:** Convert an active interactive exploration session or series of model prompts into an executable, repeatable `.chatdsl` workflow script.
- **Commands:** `/chatdsl history [range|last N] [filename.chatdsl]`, `/script`.
- **Script:** `cookbook/10_4_export_session.chatdsl`
- **Run:** `/chatdsl history` or `/chatdsl history 1-4 release_flow.chatdsl`

```dsl
# Generated ChatDSL workflow: release_flow.chatdsl
# Codified from active session (4 steps)

# Step 1
/model devstral_1
# Step 2
/tool auto on
# Step 3
/run git log -n 5 --oneline
# Step 4
Summarize the recent 5 git commits above and create release notes for version 1.2.0.
```

**Walkthrough**
1. **Interactive Picklist:** Running `/chatdsl history` without parameters displays a numbered menu of all turns and slash commands run in the active session.
2. **Selective Export:** Enter selections such as `1-3,5`, `last 3`, or `all` to extract exactly the winning prompts and settings from your exploratory chat.
3. **Multiline Formatting:** Multiline user prompts are automatically wrapped inside `/multiline` ... `;;` ... `/multiline` blocks.
4. **Execution:** The generated script can be executed immediately or shared with team members using `/script release_flow.chatdsl`.

---

## Chapter 11 — Macros & Reusable Prompts

No existing example script invokes a macro with `%name(...)`. These recipes
fix that.

### 11.1 Defining & invoking macros
- **Goal:** `def`/`%` and the `{param}` vs `${param}` distinction.
- **Commands:** `def name(params) = "..."`, `%name(args)`.
- **Script:** `cookbook/11_1_macro_define.chatdsl`
- **Run:** `/script doc/cookbook/11_1_macro_define.chatdsl`

```dsl
def expert(topic) = "You are a world-class expert in {topic}. Answer with rigor and citations."
def regen() = "Regenerate the previous answer with more detail."

/model mistral_1
%expert(transformer attention)
Explain multi-head attention intuitively.
/save 11_1_attention.txt
%regen()
/save 11_1_attention_v2.txt
```

**Walkthrough**
1. `def name(params) = "template"` defines a macro; invoke with `%name(args)`.
2. Inside macro templates, parameters are `{param}` (no `$`) — distinct from script variables `${name}`.
3. No-param macros are invoked with `%name()`.

**Variations:** define a multi-arg macro `def compare(a, b) = "Compare {a} and {b}..."`.

### 11.2 The bundled macro library

A narrative recipe. `src/chatybot/macro.chatdsl` ships 32 default macros,
grouped by purpose:

| Group | Example macros |
|-------|----------------|
| No-param commands | `regen()`, `build()`, `test()`, `deploy()`, `cleanup()` |
| Language expertise | `language_expert(type)`, `language_comparison(lang1, lang2)`, `language_learning_tips(language)` |
| Code review | `code_review_language(language)`, `code_explanation(language)`, `debug_help(language, purpose, error)` |
| Project & architecture | `system_design(project_type)`, `api_specification(api_name)`, `project_plan(project)` |
| Documentation | `doc_template(component)`, `readme_template(project)`, `changelog_entry(version, changes)` |
| Learning & tutorials | `tutorial_outline(topic)`, `cheatsheet(technology)`, `interview_questions(technology)` |
| Business & product | `business_plan(product)`, `product_specification(product)`, `market_analysis(product)` |
| Creative writing | `story_ideas(genre)`, `character_profile(name, role)`, `worldbuilding_guide(setting)` |

Invoke any of them with `%name(args)` after startup (they load automatically from
`macro.chatdsl`). `src/chatybot/menu.chatdsl` adds menu-specific macros
(`elegant_menu`, `multi_language_menu`, `regional_menu`).

### 11.3 Custom macro file + /reloadmacros
- **Goal:** author a project macro set and reload it at runtime.
- **Commands:** `/reloadmacros [file]`.
- **Script:** `cookbook/11_3_custom_macros.chatdsl`
- **Run:** `/script doc/cookbook/11_3_custom_macros.chatdsl` (requires `my_macros.chatdsl` defining `my_review(language)`)

```dsl
/reloadmacros my_macros.chatdsl
/filebank1 some_code.py
/model mistral_1
%my_review(python)
Review the code in {filebank1} for bugs.
/save 11_3_review.txt
```

**Walkthrough**
1. Macros load from `macro.chatdsl` at startup; `/reloadmacros file` swaps in a custom set.
2. Place a project macro file alongside your scripts and reload it before use.

**Variations:** keep the default set and add your own by reloading a combined file.

---

## Chapter 12 — Localization & Multilingual Authoring

Aliases are verified in [`multilingual_cross_reference.md`](multilingual_cross_reference.md)
for EN/ES/FR/ZH/IT. Arabic (AR) is listed in `chatdsl_guide_v1.md` but not in
the cross-reference table; verify AR aliases before using them.

### 12.1 Switching script language
- **Goal:** `/language es` and write with localized command aliases.
- **Commands:** `/language`, localized aliases (`/modelo`, `/sistema`, `/guardar`).
- **Script:** `cookbook/12_1_language_switch.chatdsl`
- **Run:** `/script doc/cookbook/12_1_language_switch.chatdsl`

```dsl
/language es
/modelo mistral_1
/sistema "Eres un traductor preciso."
Traduce la siguiente frase al ingles: "El cielo esta nublado."
/guardar 12_1_traduccion.txt
```

**Walkthrough**
1. `/language` switches the command alias set; aliases come from `translations.json`.
2. The script body (prompts) is still your own text — only the slash-command keywords are localized.

**Variations:** try `/language fr` with `/modele`, `/systeme`, `/sauvegarder`.

### 12.2 One task, five languages
- **Goal:** run the same translation recipe under EN/ES/FR/ZH/IT.
- **Script:** `cookbook/12_2_five_languages.chatdsl`
- **Run:** `/script doc/cookbook/12_2_five_languages.chatdsl`

```dsl
set phrase = "The sky is cloudy."

/language en
/model mistral_1
Translate to Spanish: ${phrase}
/save 12_2_en.txt

/language es
/modelo mistral_1
Traduce al ingles: ${phrase}
/save 12_2_es.txt

/language fr
/modele mistral_1
Traduire en anglais: ${phrase}
/save 12_2_fr.txt

/language zh
/模型 mistral_1
翻译成英文: ${phrase}
/save 12_2_zh.txt

/language it
/modello mistral_1
Traduci in inglese: ${phrase}
/save 12_2_it.txt
```

**Walkthrough**
1. Behavior is identical across locales; only the command keywords differ.
2. Each block writes a distinct output file, producing a per-locale asset set.

**Variations:** wrap the five blocks in a `foreach` over a locale array (see recipe 14.8).

---

## Chapter 13 — Diagnostics, Debugging & Performance

### 13.1 Tracing
- **Goal:** turn on traces and read them.
- **Commands:** `/trace tps|rawpayload|rerank|agentic_loop on|off`.
- **Script:** `cookbook/13_1_tracing.chatdsl`
- **Run:** `/script doc/cookbook/13_1_tracing.chatdsl`

```dsl
/trace tps on
/trace rawpayload on
/model mistral_1
Say hello.
/trace tps off
/trace rawpayload off
```

**Walkthrough**
1. `/trace tps` reports tokens-per-second; `/trace rawpayload` dumps the raw API payload.
2. Turn traces off after the region of interest to reduce log noise.

**Variations:** `/trace rerank on` to inspect rerank scoring; `/trace agentic_loop on` for tool-loop debugging.

### 13.2 Inspecting state
- **Goal:** `/dump all`, `/mem detail`, `/showfile all`, `/debug response`.
- **Script:** `cookbook/13_2_inspect.chatdsl`
- **Run:** `/script doc/cookbook/13_2_inspect.chatdsl`

```dsl
set a = "hello"
/file some.txt
/dump all
/mem detail
/showfile all
/debug response
```

**Walkthrough**
1. `/dump all` prints every script variable; `/mem detail` shows buffer and variable memory sizes.
2. `/showfile all` prints the full main buffer; `/debug response` exposes the raw last response.

**Variations:** add `/dbprint` when a DB is active to dump its contents.

### 13.3 Performance & rate limits
- **Goal:** `wait` pacing, `/context_limit`, `/auto_truncate`, `/maxtokens` budgeting.
- **Script:** `cookbook/13_3_performance.chatdsl`
- **Run:** `/script doc/cookbook/13_3_performance.chatdsl`

```dsl
/context_limit 8000
/auto_truncate on
/maxtokens 1500
/model mistral_1
wait 1
Write a detailed overview of HTTP caching headers.
/save 13_3_out.txt
wait 2
/model gemini_flash
Summarize the previous overview in three bullets.
/save 13_3_out2.txt
```

**Walkthrough**
1. `wait N` paces between bursts to avoid provider rate limits.
2. `/context_limit` + `/auto_truncate` cap context cost; `/maxtokens` bounds completion length.

**Variations:** set `/auto_truncate 50` to keep only 50% of context above the limit.

### 13.4 Context budget inspection & CSV trace exports
- **Goal:** inspect context utilization with `/context` and export structured session/tool metrics via `/session export csv`.
- **Script:** `cookbook/13_4_context_and_csv_export.chatdsl`
- **Run:** `/script doc/cookbook/13_4_context_and_csv_export.chatdsl`

```dsl
/context_limit 12000
/auto_truncate on
/session start context_trace_demo

/model mistral_1
Explain the architecture of LSM trees in database storage engines.

# Inspect context utilization breakdown (session history vs buffers)
/context
/context session

/model gemini_flash
What are the trade-offs of LSM trees compared to B-Trees?

# Export session metrics and conversation turns to CSV
/session export csv 13_4_session_turns.csv -t
/echo "Exported session conversation turns to 13_4_session_turns.csv"
```

**Walkthrough**
1. `/context` displays token counts, buffer sizes, and percentage of active context limit used.
2. `/context session` isolates the token count from session history.
3. `/session export csv <file> -t` produces a `QUOTE_ALL` CSV containing timestamps, TPS, timing, prompts, responses, and reasoning traces for spreadsheet or database ingestion.
4. For agentic tool loops, `/tool export csv <file>` or `/tool history csv <file>` exports step-by-step tool execution traces and timings.

---

## Chapter 14 — Novel Use Cases

Compositions with no counterpart among the existing ~40 repo examples. Each
combines feature areas the repo never combines.

### 14.1 Autonomous research agent
- **Combines:** `/tool loop` + `/documents dir=` + `/rerank` + `/setdb` + `/dblog`.
- **Script:** `cookbook/14_1_research_agent.chatdsl`
- **Run:** `/script doc/cookbook/14_1_research_agent.chatdsl`

```dsl
/setdb research_log
/model devstral_1
/tool on
/tool enable all
/tool auto on
/tool max_turns 30
/tool rate_limit 2
/system You are a research agent. Use file tools to read documents in the working directory, then synthesize a 5-bullet briefing on "rate limiting". After synthesizing, state READY TO LOG.
/tool loop 30 force
/dblog
/echo "Briefing logged to research_log DB"
```

**Walkthrough**
1. The agentic loop autonomously reads files and synthesizes; the repo shows tool loops and rerank separately, never chained.
2. `/dblog` persists the final synthesis into the DB for later retrieval (recipe 6.2).

### 14.2 Iterative image refinement loop
- **Combines:** `/imagine` + `/loadimage` vision + `foreach`.
- **Script:** `cookbook/14_2_image_refine_loop.chatdsl`
- **Run:** `/script doc/cookbook/14_2_image_refine_loop.chatdsl x="a poster about ocean conservation"`

```dsl
if ${x} != "" then set prompt = ${x}
if ${prompt} == "" then set prompt = "a poster about ocean conservation"
set critique = ""

/imagedir images/
/imagesize 1024x1024
foreach pass in range(1:4:1)
  /model mistral_1
  /imagine ${prompt} version ${pass}, incorporating: ${critique}
  /saveimage images/14_2_pass_${pass}.jpg
  /loadimage images/14_2_pass_${pass}.jpg imagebank1
  /model gemini_flash
  Critique this image for composition and color balance. Give 3 concrete improvements in one line: {imagebank1}
  /save 14_2_critique_${pass}.txt
  /setvar critique {LAST_RESPONSE}
endfor
/echo "Refinement loop done"
```

**Walkthrough**
1. Each iteration feeds the previous critique back into the next `/imagine` prompt — a feedback loop the repo never shows.
2. Initialize `set critique = ""` so the first iteration has an empty critique to incorporate.

### 14.3 LLM-as-judge ensemble vote
- **Combines:** multi-model generation + `/documents var=` + `/rerank`.
- **Script:** `cookbook/14_3_judge_ensemble.chatdsl`
- **Run:** `/script doc/cookbook/14_3_judge_ensemble.chatdsl`

```dsl
set q = "Explain why the sky is blue, concisely."

/model mistral_1
${q}
/save 14_3_a.txt

/model gemma_3
${q}
/save 14_3_b.txt

/model gemini_flash
${q}
/save 14_3_c.txt

/filebank1 14_3_a.txt
/filebank2 14_3_b.txt
/filebank3 14_3_c.txt
/setvar answers "${filebank1} --- ${filebank2} --- ${filebank3}"
/model bge_reranker_f16
/documents var=answers
/rerank "${q}" top_n=1 split=paragraph return=text
/setvar best {LAST_RESPONSE}
/echo "Best answer (rerank-voted):"
/echo "${best}"
```

**Walkthrough**
1. Three models answer; their outputs are concatenated into one variable and treated as a corpus.
2. The reranker scores each chunk against the question as the query — cheaper and faster than an LLM judge.
3. The `set answers` concatenation trick feeds multiple files as one variable.

### 14.4 CI/CD changelog generator
- **Combines:** `/run` capture + LLM synthesis + `/save`.
- **Script:** `cookbook/14_4_changelog_gen.chatdsl`
- **Run:** `/script doc/cookbook/14_4_changelog_gen.chatdsl`

```dsl
/run git log --oneline -30
/setvar log {LAST_COMPLETION}
/run git diff --stat HEAD~10
/setvar diffstat {LAST_COMPLETION}
/model mistral_1
/multiline
You are a release engineer. From this git log and diffstat, draft a CHANGELOG.md entry for the next release. Group changes into Added/Changed/Fixed. Omit cosmetic commits.

Log:
${log}

Diffstat:
${diffstat}
;;
/multiline
/save CHANGELOG_draft.md
/echo "Draft changelog written to CHANGELOG_draft.md"
```

**Walkthrough**
1. Two `/run` captures compose into one prompt — `/run` is undocumented in any existing example.
2. Produces a ready-to-edit release doc; extendable to `/run gh pr create` (user-authorizes).

### 14.5 Batch file processor
- **Combines:** `/run` + `lines()` + `foreach` over a discovered file list.
- **Script:** `cookbook/14_5_batch_processor.chatdsl`
- **Run:** `/script doc/cookbook/14_5_batch_processor.chatdsl x=src_notes`

```dsl
if ${x} != "" then set dir = ${x}
if ${dir} == "" then set dir = "src_notes"
/run ls -1 ${dir}
/setvar filelist {LAST_COMPLETION}
/model gemini_flash
foreach name in lines(${filelist})
  if ${name} == "" then break
  /file ${dir}/${name}
  Translate to French and keep the structure.
  /save out_fr/${name}
  /clearfile
endfor
/echo "Batch done"
```

**Walkthrough**
1. `ls -1` yields one filename per line, ideal for `lines()`.
2. Per-file `/file` + `/save` + `/clearfile` keeps contexts isolated.
3. The empty-line guard prevents trailing-newline artifacts.

### 14.6 Prompt fuzz tester
- **Combines:** array payloads + `foreach` + variable injection.
- **Script:** `cookbook/14_6_prompt_fuzzer.chatdsl`
- **Run:** `/script doc/cookbook/14_6_prompt_fuzzer.chatdsl`

```dsl
/model mistral_1
set cases[] = ["", "   ", "a]b{c}", "9999999999999999", "null", "undefined"]
foreach payload in ${cases}
  /setvar input ${payload}
  /multiline
  You are an API gateway. Parse the user payload and respond with {"ok":true} or {"ok":false,"reason":"..."}. Payload: ${input}
  ;;
  /multiline
  /save 14_6_fuzz_${payload}.txt
  /echo "tested payload='${input}' -> see 14_6_fuzz_${payload}.txt"
endfor
/echo "Fuzz pass complete; inspect outputs for graceful failures"
```

**Walkthrough**
1. An array variable `set cases[] = [...]` feeds `foreach`.
2. Each iteration runs a hostile payload through the same prompt template; saved outputs form a regression set.
3. This ties to the repo's [`conditiona_error_injection.md`](../conditiona_error_injection.md) design notes on graceful error handling.

### 14.7 Hierarchical document summarization
- **Combines:** multi-pass rerank reduction.
- **Script:** `cookbook/14_7_hier_summary.chatdsl`
- **Run:** `/script doc/cookbook/14_7_hier_summary.chatdsl` (requires `big_report.txt`)

```dsl
/model bge_reranker_f16
/filebank1 big_report.txt
/documents filebank=1

/rerank "key findings and recommendations" top_n=5 split=paragraph return=text
/setvar chunk1 {LAST_RESPONSE}
/rerank "risks and mitigations" top_n=5 split=paragraph return=text
/setvar chunk2 {LAST_RESPONSE}

/model mistral_1
/multiline
Summarize each passage in 2 sentences:
Findings: ${chunk1}
Risks: ${chunk2}
;;
/multiline
/save 14_7_summary.txt
/filebank2 14_7_summary.txt

/model bge_reranker_f16
/documents filebank=2
/rerank "executive overview" top_n=1 split=paragraph return=summ
/setvar exec {LAST_RESPONSE}
/echo "Executive summary:"
/echo "${exec}"
/save 14_7_exec.txt
```

**Walkthrough**
1. First rerank pass selects relevant slices from the large doc; the LLM summarizes them.
2. Second rerank pass (over the summary) distills an executive overview — rerank as reduction, scalable to more passes for very long docs.

### 14.8 Multi-locale marketing copy pipeline
- **Combines:** `/language` + `foreach` over locales + content gen.
- **Script:** `cookbook/14_8_locale_marketing.chatdsl`
- **Run:** `/script doc/cookbook/14_8_locale_marketing.chatdsl x="a solar-powered portable charger"`

```dsl
if ${x} != "" then set product = ${x}
if ${product} == "" then set product = "a solar-powered portable charger"
set locales[] = ["en", "es", "fr", "zh", "it"]
foreach loc in ${locales}
  /language ${loc}
  /model mistral_1
  Write a 3-line launch tagline and a short product description for: ${product}. Target a consumer audience.
  /save 14_8_copy_${loc}.txt
endfor
/echo "Localized assets written for: ${locales}"
```

**Walkthrough**
1. `/language` switches command aliases per iteration; the prompt asks for output in the target locale.
2. Produces one file per locale — a translatable asset bundle.
3. Only EN/ES/FR/ZH/IT aliases are verified; add AR after confirming its aliases.

### 14.9 Self-improving prompt via macro + judge
- **Combines:** macros (`def`/`%`) + `/reloadmacros` + judge + filebank compare.
- **Script:** `cookbook/14_9_self_improve_macro.chatdsl`
- **Run:** `/script doc/cookbook/14_9_self_improve_macro.chatdsl` (requires `my_macros.chatdsl` defining `expert_answer(topic)`)

```dsl
/reloadmacros my_macros.chatdsl
/model mistral_1
%expert_answer(rust ownership)
/save 14_9_r1.txt
/filebank1 14_9_r1.txt

/model gemini_flash
/multiline
Critique this answer about rust ownership for technical correctness and clarity. Output ONLY a rewritten, better prompt template that would fix the weaknesses, in the form: def expert_answer(topic) = "..."
;;
/multiline
/save my_macros_v2.chatdsl

/reloadmacros my_macros_v2.chatdsl
/model mistral_1
%expert_answer(rust ownership)
/save 14_9_r2.txt
/filebank2 14_9_r2.txt

/model gemini_flash
/multiline
Compare {filebank1} (round 1) and {filebank2} (round 2). Did the rewritten prompt improve the answer? Score both 0-10.
;;
/multiline
/save 14_9_verdict.txt
```

**Walkthrough**
1. The judge emits a new `def` statement as text, saved to a macro file.
2. `/reloadmacros` swaps in the improved macro; a two-round A/B shows whether meta-prompting helped.
3. Generalizes to more rounds via `foreach`.

### 14.10 Personal knowledge base harvester
- **Combines:** `/run` + per-file `/rerank` + `/dblog` + `/searchdb`.
- **Script:** `cookbook/14_10_kb_harvester.chatdsl`
- **Run:** `/script doc/cookbook/14_10_kb_harvester.chatdsl x=notes`

```dsl
if ${x} != "" then set notes_dir = ${x}
if ${notes_dir} == "" then set notes_dir = "notes"
/setdb my_kb
/run find ${notes_dir} -name "*.md"
/setvar notes {LAST_COMPLETION}
/model bge_reranker_f16
foreach path in lines(${notes})
  if ${path} == "" then break
  /file ${path}
  /documents filebank=1
  /rerank "distributed systems consistency" top_n=2 split=paragraph return=summ
  /dblog
  /clearfile
endfor

/setdb my_kb
/searchdb "consensus algorithms"
/loadvar recall ALL
/model mistral_1
/multiline
Using only the retrieved notes: ${recall}
Summarize the consensus algorithms mentioned and who discussed them.
;;
/multiline
/save 14_10_kb_brief.txt
```

**Walkthrough**
1. `/run find` discovers notes; per-file rerank keeps only relevant slices and `/dblog` persists them.
2. The final `/searchdb` + `/loadvar` turns the KB into an answer — an ingest → index → retrieve → answer pipeline in one script.

---

## Appendix A — Recipe index

| # | Recipe | Commands exercised | Generalizes / source |
|---|--------|---------------------|----------------------|
| 1.1 | First automation | `/model` `/system` `/save` `/echo` | technical guide L1 |
| 1.2 | Contextual analysis | `set` `if` `/file` `/save` | L2 |
| 1.3 | Two file banks | `/filebank1-2` `{filebankN}` | L3 |
| 1.4 | Multiline prompts | `/multiline` `;;` | new |
| 1.5 | Variables & substitution | `set` `${name}` `/dump` | new |
| 2.1 | Param defaults | `if ... then set` `==` `!=` | translate.chatdsl |
| 2.2 | if / not branching | `if` `not` `/model` `/temp` | new |
| 2.3 | foreach over range | `foreach` `range()` `endfor` | for_test1 (range) |
| 2.4 | foreach over lines + break | `lines()` `break` | new |
| 2.5 | Procedures | `defproc` `local` `/proc` `endproc` | for_test1 (defproc) |
| 3.1 | /clearfile discipline | `/clearfile` `/showfile` | new |
| 3.2 | Five file banks | `/filebank1-5` | new |
| 3.3 | Sparse-context retrieval | `/rerank` `/setvar {LAST_RESPONSE}` | sparse_context_example |
| 3.4 | notemode + codeonly | `/notemode` `/codeonly` | new |
| 4.1 | Comparison pattern | `/model` `/filebank1-3` judge | dufu/logic_problems |
| 4.2 | Reusable comparison template | params `x/y/z` | new |
| 4.3 | Reasoning-effort A/B | `/effort` `/reasoning` | new |
| 5.1 | rerank basics | `/rerank` `top_n` `split` `return` | new |
| 5.2 | Rerank a filebank | `/documents filebank=` | generate_and_rerank_menu |
| 5.3 | Rerank a directory | `/documents dir=` `limit_*` | BATCH_N_WALKTHROUGH |
| 5.4 | Rerank var/CHAT_HISTORY | `/documents var=` | new |
| 5.5 | Rerank from a DB | `/documents db=` `/setdb` | new |
| 5.6 | Generate-then-rerank | full pipeline | generate_and_rerank_menu |
| 6.1 | Create/connect a DB | `/setdb` `/dblist` `/dblog` | technical guide DB |
| 6.2 | Search & inject | `/searchdb` `/loadvar` | Research-Log pattern |
| 6.3 | Export | `/savevar` | new |
| 7.1 | /run and capture | `/run` `${RUN_*}` | new |
| 7.2 | Safe vs unsafe | `/run_safe` `/run_unsafe` | new |
| 7.3 | Data pipeline | `/run` + prompt | new |
| 8.1 | Enabling tools | `/tool on/enable/auto/max_turns` | new |
| 8.2 | Autonomous loop & live edit | `/tool loop` `/tool prompt [live_edit]` | new |
| 9.1 | Generate & save image | `/imagine` `/saveimage` | new |
| 9.2 | Image banks (vision) | `/loadimage` `{imagebankN}` | new |
| 9.3 | Batch images | `foreach` + `/imagine` | new |
| 10.1 | Authoring a profile | `@name` metadata | sys_default.chatdsl |
| 10.2 | Built-in profiles | `/profile use` | general/coding/explorer |
| 10.3 | Dynamic sourcing with /source | `/source` state retention | new |
| 10.4 | Codifying session history | `/chatdsl history` | new |
| 11.1 | Defining & invoking macros | `def` `%name()` | macro.chatdsl |
| 11.2 | Bundled macro library | (narrative) | macro.chatdsl, menu.chatdsl |
| 11.3 | Custom macro file | `/reloadmacros` | new |
| 12.1 | Switching script language | `/language` localized aliases | new |
| 12.2 | One task, five languages | `/language` x5 | new |
| 13.1 | Tracing | `/trace` | new |
| 13.2 | Inspecting state | `/dump` `/mem` `/showfile` `/debug` | new |
| 13.3 | Performance & rate limits | `wait` `/context_limit` `/auto_truncate` | new |
| 14.1 | Autonomous research agent | `/tool loop` + `/rerank` + `/dblog` | novel |
| 14.2 | Iterative image refinement | `/imagine` + vision + `foreach` | novel |
| 14.3 | LLM-as-judge ensemble vote | multi-model + `/rerank` vote | novel |
| 14.4 | CI/CD changelog generator | `/run git` + synthesis | novel |
| 14.5 | Batch file processor | `/run ls` + `lines()` + `foreach` | novel |
| 14.6 | Prompt fuzz tester | array + `foreach` + injection | novel |
| 14.7 | Hierarchical summarization | multi-pass rerank reduction | novel |
| 14.8 | Multi-locale marketing | `/language` + `foreach` locales | novel |
| 14.9 | Self-improving prompt macro | `%macro` + judge + `/reloadmacros` | novel |
| 14.10 | Personal KB harvester | `/run` + `/rerank` + `/dblog` + `/searchdb` | novel |

---

## Appendix B — Cross-reference map

| Cookbook chapter | Corresponding section in `chatdsl_guide_v1.md` |
|------------------|----------------------------------------------|
| 1 Foundations | Tutorials 1-3; Getting Started |
| 2 Control Flow | Scripting Keywords; Control Flow |
| 3 Context & Buffers | File Buffer Commands; Best Practices |
| 4 Multi-Model Comparison | Tutorial 3: Multi-Model Evaluation |
| 5 Rerank & Retrieval | (covered in `RERANK_FEATURE_SPEC.md`, `BATCH_N_WALKTHROUGH.md`) |
| 6 Database | HowTo: Database Integration; Database Commands |
| 7 Shell Execution | HowTo: Shell Execution & Capturing Output |
| 8 Tool Loops | HowTo: Set Up Tool Calling Loop; Tool Loop Commands |
| 9 Image Generation | HowTo: Image Generation Workflow; Image Generation Commands |
| 10 Profiles | HowTo: Profile Management; Profile Commands |
| 11 Macros | Macro Syntax; `chatdsl_macro_implementation.md` |
| 12 Localization | Multi-Language Support; `multilingual_cross_reference.md` |
| 13 Diagnostics | Diagnostics & Monitoring; Diagnostics Commands |
| 14 Novel Use Cases | (no existing counterpart) |

---

## Appendix C — Common pitfalls checklist

- **Multiline terminator:** a block opened with `/multiline` ends at a line containing `;;` *or* a second `/multiline`. Don't mix.
- **Three brace syntaxes, don't confuse them:**
  - `${name}` — script variable.
  - `{filebankN}` / `{imagebankN}` — buffer references inside prompts.
  - `{param}` — macro template parameter (no `$`).
- **`/clearfile` hygiene:** the main buffer is one-shot but stale text can leak if you don't clear between phases. Banks need `/filebankN clear`.
- **Quote paths that may contain spaces:** `/save "${dir}/${file}"`.
- **No `\` escapes** in variable values — they're disallowed for prompt stability.
- **`if` is single-line only:** `if cond then cmd`. No `else`; emulate with mutually exclusive conditions.
- **Comments inside `/multiline` bodies are text**, not comments — `#` only comments outside a block.
- **`/echo` is local:** it prints with variable expansion and makes no LLM call.

---

## Appendix D — Where to go next

- [`chatdsl_guide_v1.md`](chatdsl_guide_v1.md) — the comprehensive reference (keyword tables, error messages, best practices).
- [`CHATDSL_TECHNICAL_GUIDE.md`](CHATDSL_TECHNICAL_GUIDE.md) — core concepts, buffer system, the comparison pattern.
- [`chatdsl_skill.md`](chatdsl_skill.md) — skill-oriented reference.
- [`RERANK_FEATURE_SPEC.md`](RERANK_FEATURE_SPEC.md) — full rerank options and sources.
- [`BATCH_N_WALKTHROUGH.md`](BATCH_N_WALKTHROUGH.md) — batched directory rerank scaling.
- [`multilingual_cross_reference.md`](multilingual_cross_reference.md) — command alias tables for EN/ES/FR/ZH/IT.
- [`chatdsl_macro_implementation.md`](chatdsl_macro_implementation.md) — macro grammar and implementation.
- Multilingual guides: `chatdsl_guide_v1_chinese.md`, `_french.md`, `_italian.md`, `_spanish.md`, `_arabic.md`.
