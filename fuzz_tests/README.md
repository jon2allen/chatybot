# Atheris Fuzzing for chatybot BufferManager

## Quick Start

```bash
# Install LLVM (required for libFuzzer on macOS)
brew install llvm

# Install Atheris with libFuzzer support
export PATH="/opt/homebrew/opt/llvm/bin:$PATH"
export CLANG_BIN="/opt/homebrew/opt/llvm/bin/clang"
pip install atheris

# Run a single fuzzer (using the python with atheris installed)
/opt/homebrew/opt/python@3.11/bin/python3.11 fuzz_tests/fuzz_placeholders.py fuzz_tests/corpus -atheris_runs=1000 -max_len=500

# Run all fuzzers
cd /Users/jon2allen/github/chatybot
bash fuzz_tests/run_all_fuzzers.sh
```

## Fuzzers Available

| Fuzzer | Target | Description |
|--------|--------|-------------|
| fuzz_placeholders.py | replace_placeholders(), replace_placeholders_legacy() | Tests string parsing and placeholder substitution |
| fuzz_file_loading.py | load_file_to_buffer(), load_file_to_bank() | Tests file path handling and I/O |
| fuzz_format_detection.py | detect_image_format(), detect_audio_format() | Tests MIME type detection from extensions |
| fuzz_bank_operations.py | load_file_to_bank(), load_image_to_bank(), show_*_bank(), clear_*_bank() | Tests bank operations with edge cases |

## Corpus

Seed inputs in `fuzz_tests/corpus/` directory. Currently includes:
- empty.txt
- adjacent_placeholders.txt
- all_placeholders.txt
- long_string.txt
- malformed_placeholders.txt
- nested_placeholders.txt
- normal_placeholders.txt
- special_chars.txt
- unicode.txt

Add more files to improve fuzzing effectiveness.

## Crash Artifacts

Crashes are saved in `crashes/<fuzzer>/` with timestamp filenames.

## Options

- `-atheris_runs=N`: Exit after N runs (use -1 for infinite)
- `-max_len=N`: Maximum input length
- `-artifact_prefix=PREFIX`: Crash directory prefix
- `-verbosity=N`: Verbosity level (1-5)

## Found Bugs

Document bugs in `FUZZING_BUGS.md` with:
- Fuzzer that found it
- Input that triggered it
- Stack trace
- Fix applied

## Notes

- Atheris 3.0.0 is used with `instrument_all()` for coverage tracking
- The `TypeError: 'NoneType' object is not callable` warnings are from Python's logging cleanup, not from our code
- Custom mutators are not supported in Atheris 3.0.0 (removed `Mutator` class)
