# Walkthrough: Batched Top-N Pre-filtering Implementation

We successfully implemented **Option B** (Batched Top-N pre-filtering) for directory document sources in the `/rerank` command.

## Summary of Changes

### 1. Command Parser Extensions
Exposed parameters in [chatybot_app.py](file:///Users/jon2allen/github/chatybot_rerank/src/chatybot/chatybot_app.py):
*   `limit_batch_size` (default: `64`): Window size for grouped text chunk ingestion.
*   `limit_top_n` (default: `3`): Maximum candidate chunks retained (by length descending) per batch.
*   `max_limit` (default: `64`): Global ceiling for total chunks collected.

### 2. Pre-Filtering Pipeline
If `source_type == "dir"`, we initialize a `DirectoryTextProcessor` and call its `process_with_batched_top_n` method. This returns a size-restricted subset of the longest chunks, bypassing the need to feed large directories recursively or entirely into memory and network requests.

### 3. Result Index Mapping
When the reranker returns the ranked results in in-memory mode, we resolve the item's relative `index` back to the corresponding element in the `pre_filtered_chunks` array, ensuring metadata like the original source `filename` and `chunk_id` are preserved and displayed correctly.

---

## Verification and Results

We executed the DSL test script `test_rerank_batched.chatdsl` with the following configuration:
```text
/documents dir="."
/rerank "Parsley grammar macro definition" top_n=1 limit_top_n=1 max_limit=5 return=text
```

### Execution Log output:
```text
Ingesting directory '.' with Batched Top-N pre-filtering (limit_batch_size=64, limit_top_n=1, max_limit=5)...
  Batch 1: Processed 64 chunks, selected top 1 (by length)
    Top 1: ID=16, File=10_foods.txt, Length=163 chars
  Batch 2: Processed 64 chunks, selected top 1 (by length)
    Top 1: ID=65, File=60_generated_dishes.txt, Length=125 chars
  Batch 3: Processed 64 chunks, selected top 1 (by length)
    Top 1: ID=187, File=CHATDSL_TECHNICAL_GUIDE.md, Length=200 chars
  Batch 4: Processed 64 chunks, selected top 1 (by length)
    Top 1: ID=228, File=CHATDSL_TECHNICAL_GUIDE.md, Length=538 chars
  Batch 5: Processed 64 chunks, selected top 1 (by length)
    Top 1: ID=318, File=README.md, Length=1647 chars
WARNING: Reached max_limit of 5 collected chunks. Collected 5 chunks. Some files may not have been fully processed.
Reranking documents from dir='.' using sinjab/bge-reranker-large-F16-GGUF:F16...
```

*   **Limit Enforcement**: The processor successfully stopped reading files upon reaching the `max_limit` of 5 collected chunks and outputted the warning.
*   **Result Resolution**: The output resolved the matched item index to `File: README.md (Chunk: 318)` and printed its raw contents to stdout.

### 2. Large Scale Verification (Conrad Chance)
We verified limits on the copied Gutenberg book `conrad_chance.txt` (~14,000 lines) by running:
```text
/documents dir="test/conrad_test"
/rerank "captain on a sea voyage adventure" top_n=2 limit_top_n=3 max_limit=10 return=summ
```

#### Results log:
```text
Ingesting directory 'test/conrad_test' with Batched Top-N pre-filtering (limit_batch_size=64, limit_top_n=3, max_limit=10)...
  Batch 1: Processed 64 chunks, selected top 3 (by length)
    Top 1: ID=3, File=conrad_chance.txt, Length=540 chars
    Top 2: ID=24, File=conrad_chance.txt, Length=434 chars
    Top 3: ID=4, File=conrad_chance.txt, Length=282 chars
  Batch 2: Processed 64 chunks, selected top 3 (by length)
    Top 1: ID=67, File=conrad_chance.txt, Length=399 chars
    Top 2: ID=99, File=conrad_chance.txt, Length=320 chars
    Top 3: ID=91, File=conrad_chance.txt, Length=298 chars
  Batch 3: Processed 64 chunks, selected top 3 (by length)
    Top 1: ID=171, File=conrad_chance.txt, Length=293 chars
    Top 2: ID=160, File=conrad_chance.txt, Length=210 chars
    Top 3: ID=143, File=conrad_chance.txt, Length=209 chars
  Batch 4: Processed 64 chunks, selected top 3 (by length)
    Top 1: ID=222, File=conrad_chance.txt, Length=236 chars
    Top 2: ID=194, File=conrad_chance.txt, Length=189 chars
    Top 3: ID=207, File=conrad_chance.txt, Length=168 chars
  -> Partial add: 1 chunks (reached limit)
WARNING: Reached max_limit of 10 collected chunks. Collected 10 chunks. Some files may not have been fully processed.
Reranking documents from dir='test/conrad_test' using sinjab/bge-reranker-large-F16-GGUF:F16...
```
*   **Verification**: The pre-filtering processed 4 batches (256 chunks total) and capped the ingestion at `max_limit=10`.
*   **Index Translation**: The reranker matched index 8 and index 4, which were correctly mapped back to their original document names and chunk IDs:
    *   Rank 1: `File: conrad_chance.txt (Chunk: 143)`
    *   Rank 2: `File: conrad_chance.txt (Chunk: 99)`

## Processing Large Books (Scaling the Limits)
To query the entire book of *Chance* without hitting the warning ceiling, we must calculate the appropriate overrides for `max_limit` based on the splitting mode.

### 1. In Line-by-Line Mode (`split=line`, `item=1`)
*   **Book Lines**: 13,962 lines.
*   **Total Batches**: $13,962 / 64 \approx 218$ batches.
*   **Retention**: Retaining 3 items per batch yields $\approx 654$ chunks.
*   **Required Configuration**: Set `max_limit=700`.
    ```text
    /rerank "captain on a sea voyage adventure" split=line limit_top_n=3 max_limit=700
    ```

### 2. In Sentence Mode (`split=sentence`, `item=1`)
*   **Book Sentences**: $\approx 9,000$ sentences.
*   **Total Batches**: $9,000 / 64 \approx 140$ batches.
*   **Retention**: Retaining 3 items per batch yields $\approx 420$ chunks.
*   **Required Configuration**: Set `max_limit=500`.
    ```text
    /rerank "captain on a sea voyage adventure" split=sentence limit_top_n=3 max_limit=500
    ```


