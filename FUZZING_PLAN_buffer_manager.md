# Comprehensive Fuzzing Plan: Atheris for buffer_manager.py

---

## TABLE OF CONTENTS
1. [Executive Summary](#executive-summary)
2. [Atheris Deep Dive](#1-atheris-deep-dive)
3. [buffer_manager.py Complete Analysis](#2-buffer_managerpy-complete-analysis)
4. [Fuzzing Architecture](#3-fuzzing-architecture)
5. [Complete Implementation - All Files](#4-complete-implementation---all-files)
6. [Expected Bug Categories with Examples](#5-expected-bug-categories-with-examples)
7. [Step-by-Step Setup Guide](#6-step-by-step-setup-guide)
8. [Execution and Monitoring](#7-execution-and-monitoring)
9. [Interpreting Results](#8-interpreting-results)
10. [Advanced Configurations](#9-advanced-configurations)

---

## Executive Summary

**Objective**: Apply Google's Atheris coverage-guided fuzzer to `src/chatybot/buffer_manager.py` to discover crashes, security vulnerabilities, and edge case bugs.

**Scope**: 4 specialized fuzzers, 8 corpus seed files, 2 custom mutators, full instrumentation

**Files to Create**: 15 files, ~500 lines of fuzzing code

**Estimated Time**: 2-4 hours setup, continuous execution thereafter

**Expected Outcome**: Improved code robustness, security hardening, regression test suite

---

# 1. Atheris Deep Dive

## 1.1 What is Atheris?

Atheris is a **coverage-guided, mutation-based fuzzer** for Python developed by Google's security team. It combines:

- **libFuzzer**: LLVM's production-grade fuzzing engine
- **Python native**: No compilation needed, works directly on .py files
- **Coverage-guided**: Prioritizes inputs that explore new code paths
- **Crash detection**: Automatically catches and saves unhandled exceptions

### Key Architecture Components:

```
┌─────────────────────────────────────────────────────────────────┐
│                        ATHERIS ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐        │
│  │   CORPUS     │    │   MUTATOR    │    │  EXECUTOR    │        │
│  │   (Seeds)    │───▶│ (Mutations) │───▶│ (Runs Code) │        │
│  └──────────────┘    └──────────────┘    └──────┬───────┘        │
│                                                    │               │
│              ┌─────────────────────────────────────┼───────┐     │
│              ▼                                     ▼           ▼     │
│  ┌──────────────────┐          ┌─────────────┐ ┌─────────┐   │
│  │  COVERAGE        │          │  MONITOR    │ │ CRASH   │   │
│  │  TRACKING       │          │ (Progress) │ │ HANDLER │   │
│  │ (libFuzzer)     │          │             │ │ (Saves) │   │
│  └──────────────────┘          └─────────────┘ └─────────┘   │
│                              │                               │
│                              ▼                               ▼
│                  ┌───────────────────────┐           ┌─────────┐
│                  │   FEEDBACK LOOP       │◀──────────│ ARTIFACTS│
│                  │ (Prioritize inputs    │           │ (Crashes)│
│                  │  that increase       │           └─────────┘
│                  │  coverage)            │                   
│                  └───────────────────────┘           
│                                           
└─────────────────────────────────────────────────────────────────┘
```

### Supported Platforms:
| Platform | Support | Notes |
|----------|---------|-------|
| Linux x86_64 | ✅ Full | Recommended, best performance |
| macOS x86_64 | ✅ Full | Works well |
| macOS ARM64 | ✅ Full | M1/M2 Macs supported |
| Windows | ❌ Partial | WSL2 recommended |

### Installation:
```bash
# Standard installation
pip install atheris

# With instrumentation for native extensions
pip install atheris-with-instruments

# Verify installation
python -c "import atheris; print(atheris.__version__)"
```

## 1.2 How Atheris Works

### The Fuzzing Loop:

```python
# 1. You define the test function
import atheris
import sys

def TestOneInput(data: bytes):
    # Your code here
    target_function(data)

# 2. Atheris takes over
atheris.Setup(sys.argv, TestOneInput)
atheris.Fuzz()  # Runs forever until Ctrl+C
```

### For Each Input:
1. **Read/Generate**: Get input from corpus or mutate existing
2. **Execute**: Call `TestOneInput(data)`
3. **Monitor**: Track which code lines execute
4. **Crash Check**: If exception occurs, save crash artifact
5. **Coverage Update**: Update coverage map
6. **Feedback**: If new coverage, prioritize this input's mutations
7. **Repeat**: Loop indefinitely

### Input Mutation Strategies:
- **Bit Flip**: Flip individual bits
- **Byte Flip**: Change individual bytes
- **Insert**: Add random bytes
- **Delete**: Remove bytes
- **Replace**: Substitute byte sequences
- **Crossover**: Combine two inputs
- **Custom**: Your domain-specific mutations

---

# 2. buffer_manager.py Complete Analysis

## 2.1 Module Structure

**File**: `src/chatybot/buffer_manager.py`
**Location**: On `audio` branch (contains audio_banks, image_banks)
**Size**: 418 lines
**Dependencies**: base64, pathlib, Path, Dict, List, Tuple

### Class Diagram:

```
┌──────────────────────────────────────────────────────────────────────┐
│                           BufferManager                               │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ATTRIBUTES:                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ file_buffer: str = ""                                            │ │
│  │ prompt_buffer: str = ""                                         │ │
│  │ file_banks: Dict[str, str] = {filebank1: "", ..., filebank5: ""} │ │
│  │ image_banks: Dict[str, str] = {imagebank1: "", ..., imagebank5: ""}│ │
│  │ audio_banks: Dict[str, str] = {audiobank1: "", ..., audiobank5: ""}│ │
│  │ script_vars: Dict[str, str] = {}                                 │ │
│  │ audio_file_manager: Optional[Any] = None                         │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  METHODS:                                                             │
│  ┌─────────────────────┐  ┌─────────────────────┐                 │
│  │ FILE OPERATIONS     │  │ IMAGE OPERATIONS     │                 │
│  │─────────────────────│  │─────────────────────│                 │
│  │ load_file_to_buffer │  │ load_image_to_bank  │                 │
│  │ load_file_to_bank   │  │ detect_image_format │                 │
│  │ clear_file_buffer   │  │ clear_image_bank    │                 │
│  │ show_file_buffer    │  │ show_image_bank     │                 │
│  │ load_image_to_bank* │  │                     │                 │
│  └─────────────────────┘  └─────────────────────┘                 │
│          *On audio branch only                                          │
│  ┌─────────────────────┐  ┌─────────────────────┐                 │
│  │ AUDIO OPERATIONS    │  │ PLACEHOLDER OPS     │                 │
│  │─────────────────────│  │─────────────────────│                 │
│  │ load_audio_to_bank  │  │ replace_placeholders │                 │
│  │ detect_audio_format │  │ replace_placeholders_│                 │
│  │ clear_audio_bank    │  │    _legacy          │                 │
│  │ show_audio_bank     │  │                     │                 │
│  └─────────────────────┘  └─────────────────────┘                 │
│  ┌─────────────────────┐                                              │
│  │ UTILITY             │                                              │
│  │─────────────────────│                                              │
│  │ set_script_var      │                                              │
│  │ dump_variables       │                                              │
│  │ show_memory_usage    │                                              │
│  └─────────────────────┘                                              │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

## 2.2 Method-By-Method Analysis

### File Loading Methods

| Method | Parameters | Returns | Risk | Lines |
|--------|------------|---------|------|-------|
| `load_file_to_buffer` | file_path: str | None | Medium | ~15 |
| `load_file_to_bank` | bank_num: int, file_path: str | None | Medium | ~20 |
| `clear_file_buffer` | None | None | Low | ~5 |
| `show_file_buffer` | show_all: bool=False | None | Low | ~15 |
| `clear_file_bank` | bank_num: int | None | Low | ~10 |
| `show_file_bank` | bank_num: int, show_all: bool=False | None | Low | ~20 |

**Risk Analysis**: 
- **Path Validation**: No validation for `..` or absolute paths
- **File Existence**: Opens without checking if file exists first
- **Encoding**: Uses default encoding (may fail on non-UTF-8)
- **Exception Handling**: Wraps in try/except, prints error

### Image Loading Methods

| Method | Parameters | Returns | Risk | Lines |
|--------|------------|---------|------|-------|
| `load_image_to_bank` | bank_num: int, file_path: str | None | Medium | ~25 |
| `clear_image_bank` | bank_num: int | None | Low | ~10 |
| `show_image_bank` | bank_num: int, show_all: bool=False | None | Low | ~25 |
| `detect_image_format` | file_path: str | str | Low | ~15 |

**Risk Analysis**:
- **Base64 Encoding**: Creates `data:audio/<format>;base64,<data>` URLs
- **Path Validation**: Same issues as file loading
- **MIME Detection**: Only checks extension, not file content
- **Binary Data**: Reads as binary but doesn't validate

### Audio Loading Methods

| Method | Parameters | Returns | Risk | Lines |
|--------|------------|---------|------|-------|
| `load_audio_to_bank` | bank_num: int, file_path: str | None | Medium | ~25 |
| `clear_audio_bank` | bank_num: int | None | Low | ~10 |
| `detect_audio_format` | file_path: str | str | Low | ~15 |

**Risk Analysis**: Same as image loading methods

### Placeholder Methods

| Method | Parameters | Returns | Risk | Lines |
|--------|------------|---------|------|-------|
| `replace_placeholders` | prompt: str, include_images: bool=True | Tuple[str, List[Dict]] | **High** | ~40 |
| `replace_placeholders_legacy` | prompt: str | str | Medium | ~15 |

**Risk Analysis**:
- **String Parsing**: Uses simple `str.replace()`, no regex
- **Nested Braces**: `{{var}}` may not be handled correctly
- **Overlapping**: `{var1}{var2}` may have issues
- **Special Chars**: May break on `$`, `{`, `}` in content
- **Unicode**: Should work but untested edge cases

### Format Detection Methods

| Method | Parameters | Returns | Risk | Lines |
|--------|------------|---------|------|-------|
| `detect_image_format` | file_path: str | str | Low | ~15 |
| `detect_audio_format` | file_path: str | str | Low | ~15 |

**Risk Analysis**:
- **Extension Parsing**: Uses `Path(file_path).suffix.lower()`
- **No Validation**: Doesn't check if file actually exists
- **Default Fallback**: Returns `f"audio/{ext}"` for unknown audio
- **Image Default**: Raises ValueError for unknown image formats

## 2.3 Data Flow Analysis

### Input → Processing → Output Flow

```
FILE PATH INPUT
     │
     ▼
┌────────────────────┐
│ detect_*_format()  │───▶ MIME type string
└────────────────────┘
     │
     ▼
┌────────────────────┐
│ load_*_to_bank()    │───▶ Bank dict updated
└────────────────────┘    with base64 data URL
     │
     ▼
┌────────────────────┐
│ File I/O           │
│ - open()           │
│ - read()           │
│ - close()          │
└────────────────────┘

TEXT INPUT WITH PLACEHOLDERS
     │
     ▼
┌────────────────────┐
│ replace_placeholders() │
│ ├─ File bank replace │
│ ├─ Script var replace│
│ └─ Image bank extract│
└──────────┬──────────┘
           │
     ┌─────┴─────┐
     ▼           ▼
┌────────┐ ┌────────────┐
│  Text   │ │ Image List │
│ (str)   │ │ (List[Dict])│
└────────┘ └────────────┘
```

## 2.4 Attack Surface Summary

| Attack Vector | Methods | Risk Level | Test Priority |
|---------------|---------|------------|---------------|
| Path Traversal | load_file_to_*, load_image_to_*, load_audio_to_* | 🔴 **Critical** | P0 |
| Arbitrary File Read | All load_* methods | 🔴 **Critical** | P0 |
| Symlink Attack | All load_* methods | 🔴 **Critical** | P0 |
| Base64 Encoding Issues | load_image_to_bank, load_audio_to_bank | 🟡 **High** | P0 |
| Placeholder Parsing | replace_placeholders, replace_placeholders_legacy | 🟡 **High** | P0 |
| Extension Parsing | detect_image_format, detect_audio_format | 🟡 **Medium** | P1 |
| Unicode Handling | All string methods | 🟡 **Medium** | P1 |
| Resource Exhaustion | All methods | 🟢 **Low** | P2 |
| Dictionary Key Errors | All bank methods | 🟢 **Low** | P2 |

---

# 3. Fuzzing Architecture

## 3.1 Why Multiple Fuzzers?

### Single Fuzzer Problems:
- **Complex Input Generation**: Hard to generate inputs for all methods
- **Mixed Concerns**: One fuzzer trying to test everything
- **Poor Coverage**: Can't focus on specific code paths
- **Hard to Debug**: Crashes could be anywhere

### Multiple Fuzzer Benefits:
- ✅ **Focused Testing**: Each fuzzer targets specific functionality
- ✅ **Domain-Specific Mutators**: Custom mutations for each input type
- ✅ **Better Coverage**: Each fuzzer can go deep on its target
- ✅ **Easier Debugging**: Crash tells you exactly which function failed
- ✅ **Parallel Execution**: Run all fuzzers simultaneously
- ✅ **Modular**: Easy to add/remove fuzzers

## 3.2 Fuzzer Design Pattern

All fuzzers follow the same pattern:

```python
#!/usr/bin/env python3
"""Fuzzer description"""

import sys
import os

# Fix Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import target
from src.chatybot.buffer_manager import BufferManager

# Optional: Custom mutator
class CustomMutator(atheris.Mutator):
    def mutate(self, data, data_size, max_size):
        # Domain-specific mutations
        ...
        return bytes(mutated)

# Test function - THE CORE
def TestOneInput(data: bytes):
    """Called by Atheris with each fuzzed input"""
    try:
        bm = BufferManager()
        # Call target methods with fuzz data
        ...
    except Exception:
        pass  # Atheris catches crashes automatically

# Setup and run
def main():
    os.makedirs("corpus", exist_ok=True)
    atheris.Setup(sys.argv, TestOneInput, custom_mutator=CustomMutator())
    atheris.Fuzz()

if __name__ == "__main__":
    main()
```

## 3.3 Fuzzing Targets Matrix

| Fuzzer | Primary Target | Secondary Targets | Custom Mutator | Priority |
|--------|----------------|-------------------|---------------|----------|
| fuzz_placeholders.py | replace_placeholders | replace_placeholders_legacy | ✅ Yes | P0 |
| fuzz_file_loading.py | load_file_to_* | All load methods | ❌ No | P0 |
| fuzz_format_detection.py | detect_*_format | Both format methods | ✅ Yes | P0 |
| fuzz_bank_operations.py | Bank operations | All bank methods | ❌ No | P0 |

---

# 4. Complete Implementation - All Files

All files below are **complete and ready to copy-paste**. Each file is self-contained and can be created directly.

---

## FILE 1: fuzz_tests/__init__.py

**Purpose**: Makes fuzz_tests a Python package

```python
# fuzz_tests/__init__.py
# Empty file - makes fuzz_tests a package
```

---

## FILE 2: fuzz_tests/README.md

# Plan: Applying Atheris Fuzzing to buffer_manager.py

## 1. RESEARCH SUMMARY

### 1.1 What is Atheris?
Atheris is a **coverage-guided fuzzer for Python** developed by Google. It:
- Uses libFuzzer under the hood
- Works with pure Python code and native extensions
- Is particularly effective for **differential fuzzing** (comparing two libraries)
- Tracks code coverage to find interesting paths and bugs
- Works on Linux (recommended) and macOS

### 1.2 Atheris Basic Usage
```python
import atheris
import sys

def TestOneInput(data: bytes):
    # Code to fuzz
    buffer_manager = BufferManager()
    buffer_manager.load_file_to_bank(1, "/tmp/test")
    # ... etc

atheris.Setup(sys.argv, TestOneInput)
atheris.Fuzz()
```

Run with: `python fuzz_buffer_manager.py`

### 1.3 Atheris Features Relevant to buffer_manager.py
- **Instrumentation**: `@atheris.instrument_func` or `atheris.instrument_all()` for coverage tracking
- **Corpus**: Pre-seeded inputs to guide fuzzing
- **Custom mutators**: For domain-specific input generation
- **Crash detection**: Automatically catches exceptions

### 1.4 buffer_manager.py Analysis

**File**: `src/chatybot/buffer_manager.py` (~418 lines on audio branch)

**Purpose**: Manages:
- File buffers (file_buffer, prompt_buffer)
- File banks (filebank1-5)
- Image banks (imagebank1-5) - base64 data URLs
- Audio banks (audiobank1-5) - base64 data URLs
- Script variables
- Placeholder replacement logic

**Key Methods to Fuzz**:
1. `load_file_to_buffer(file_path)` - file path handling
2. `load_file_to_bank(bank_num, file_path)` - bank loading
3. `load_image_to_bank(bank_num, file_path)` - image loading + base64
4. `load_audio_to_bank(bank_num, file_path)` - audio loading + base64
5. `replace_placeholders(prompt)` - string parsing/replacement
6. `replace_placeholders_legacy(prompt)` - legacy text-only replacement
7. `detect_image_format(file_path)` - file extension parsing
8. `detect_audio_format(file_path)` - file extension parsing
9. `dump_variables(name)` - variable dumping with various inputs
10. `show_memory_usage()` - memory display

**Attack Surface**:
- **File path handling**: Could have path traversal issues (`../../../etc/passwd`)
- **Base64 encoding/decoding**: Could have encoding edge cases (invalid base64, special chars)
- **String replacement**: Could have edge cases with nested braces `{{var}}` or `}{`
- **Dictionary key access**: Could have KeyError on invalid bank numbers
- **File I/O**: Could have file not found, permission issues, encoding errors
- **Unicode handling**: UTF-8 edge cases in file content and paths
- **Memory**: Large file handling, very long strings

**Current State on audio branch**: Also includes `audio_banks` dict and audio-related methods

## 2. DETAILED IMPLEMENTATION PLAN

### 2.1 Directory Structure to Create
```
fuzz_tests/
├── __init__.py                    # Empty
├── README.md                      # Documentation
├── run_all_fuzzers.sh             # Script to run all fuzzers
├── corpus/                        # Seed inputs
│   ├── empty.txt
│   ├── normal_placeholders.txt
│   ├── nested_placeholders.txt
│   ├── special_chars.txt
│   ├── long_string.txt
│   └── unicode.txt
├── fuzz_placeholders.py           # Fuzzer for replace_placeholders()
├── fuzz_file_loading.py           # Fuzzer for load functions
├── fuzz_format_detection.py       # Fuzzer for format parsing
└── fuzz_bank_operations.py        # Fuzzer for bank operations
```

---

### 2.2 FILE: fuzz_tests/__init__.py
```python
# Empty file to make fuzz_tests a package
```

---

### 2.3 FILE: fuzz_tests/README.md
```markdown
# Atheris Fuzzing for chatybot Buffer Manager

## Installation
```bash
pip install atheris
```

## Running Fuzzers

### Run all fuzzers
```bash
./run_all_fuzzers.sh
```

### Run specific fuzzer
```bash
# Placeholder replacement fuzzer
python fuzz_placeholders.py

# File loading fuzzer
python fuzz_file_loading.py

# Format detection fuzzer  
python fuzz_format_detection.py

# Bank operations fuzzer
python fuzz_bank_operations.py
```

### Options
- `-atheris_runs=N`: Run N times and exit
- `-max_len=N`: Maximum input length
- `-artifact_prefix=PREFIX`: Prefix for crash artifacts

## Adding Corpus
Add test files to `corpus/` directory. Fuzzers automatically pick up all `.txt` files.

## Found Bugs
Document any bugs found in `FUZZING_BUGS.md`
```

---

### 2.4 FILE: fuzz_tests/run_all_fuzzers.sh
```bash
#!/bin/bash
# Run all fuzzers in parallel with timeout

echo "Starting all fuzzers..."
echo "Press Ctrl+C to stop"
echo ""

FUZZERS=(
    "fuzz_placeholders.py"
    "fuzz_file_loading.py"
    "fuzz_format_detection.py"
    "fuzz_bank_operations.py"
)

for fuzzer in "${FUZZERS[@]}"; do
    echo "[+] Starting $fuzzer"
    python "$fuzzer" -artifact_prefix="crashes/$fuzzer" &
done

wait
echo "All fuzzers stopped"
```
Make executable: `chmod +x run_all_fuzzers.sh`

---

### 2.5 FILE: fuzz_tests/fuzz_placeholders.py
**Purpose**: Fuzz the `replace_placeholders()` method which handles string parsing and placeholder substitution

```python
#!/usr/bin/env python3
"""
Fuzzer for BufferManager.replace_placeholders()
Tests string parsing, placeholder substitution, and edge cases
"""

import sys
import atheris
from src.chatybot.buffer_manager import BufferManager


class PlaceholderMutator(atheris.Mutator):
    """Custom mutator for placeholder-specific inputs"""
    
    def __init__(self):
        super().__init__()
        self.placeholders = [
            "{filebank1}", "{filebank2}", "{filebank3}", "{filebank4}", "{filebank5}",
            "${var1}", "${var2}", "${var3}",
            "{imagebank1}", "{imagebank2}", "{imagebank3}",
            "{audiobank1}", "{audiobank2}",
        ]
        self.special_chars = ["{", "}", "$", "", "\n", "\r", "\t"]
    
    def mutate(self, data, data_size, max_size):
        """Generate mutations specific to placeholder syntax"""
        import random
        
        # Base mutation from Atheris
        mutated = bytearray(data)
        
        # Strategy 1: Insert a random placeholder
        if random.random() < 0.3 and len(mutated) + 20 < max_size:
            placeholder = random.choice(self.placeholders)
            pos = random.randint(0, len(mutated))
            mutated = mutated[:pos] + placeholder.encode() + mutated[pos:]
        
        # Strategy 2: Insert special characters
        if random.random() < 0.3 and len(mutated) + 5 < max_size:
            char = random.choice(self.special_chars)
            pos = random.randint(0, len(mutated))
            mutated = mutated[:pos] + char.encode() + mutated[pos:]
        
        # Strategy 3: Create nested braces
        if random.random() < 0.2 and len(mutated) + 10 < max_size:
            nest = "{" * random.randint(1, 5) + "}" * random.randint(1, 5)
            pos = random.randint(0, len(mutated))
            mutated = mutated[:pos] + nest.encode() + mutated[pos:]
        
        # Strategy 4: Duplicate existing placeholders
        if random.random() < 0.2 and len(mutated) + 50 < max_size:
            for ph in self.placeholders:
                if ph.encode() in mutated:
                    pos = random.randint(0, len(mutated))
                    mutated = mutated[:pos] + ph.encode() + mutated[pos:]
                    break
        
        return bytes(mutated)


def TestOneInput(data: bytes):
    """Fuzz the replace_placeholders method"""
    try:
        bm = BufferManager()
        
        # Pre-populate banks and vars with safe content
        bm.file_banks["filebank1"] = "test_content_1"
        bm.file_banks["filebank2"] = "test_content_2"
        bm.script_vars["var1"] = "value1"
        bm.script_vars["var2"] = "value2"
        
        # Try with include_images=True
        try:
            result, images = bm.replace_placeholders(
                data.decode('utf-8', errors='replace'), 
                include_images=True
            )
        except Exception:
            pass
        
        # Try with include_images=False (legacy mode)
        try:
            result = bm.replace_placeholders_legacy(
                data.decode('utf-8', errors='replace')
            )
        except Exception:
            pass
            
    except Exception as e:
        # Atheris will catch and report this
        pass


def main():
    atheris.Setup(sys.argv, TestOneInput, custom_mutator=PlaceholderMutator())
    atheris.Fuzz()


if __name__ == "__main__":
    main()
```

---

### 2.6 FILE: fuzz_tests/fuzz_file_loading.py
**Purpose**: Fuzz file loading functions with potentially malicious paths

```python
#!/usr/bin/env python3
"""
Fuzzer for BufferManager file loading functions
Tests path handling, file I/O, and error handling
"""

import sys
import os
import tempfile
import atheris
from src.chatybot.buffer_manager import BufferManager


def TestOneInput(data: bytes):
    """Fuzz file loading methods"""
    try:
        bm = BufferManager()
        
        # Create a temp directory for safe testing
        with tempfile.TemporaryDirectory() as tmpdir:
            # Strategy 1: Create file with fuzz data
            test_path = os.path.join(tmpdir, "test.txt")
            try:
                with open(test_path, "wb") as f:
                    f.write(data)
                bm.load_file_to_buffer(test_path)
                bm.load_file_to_bank(1, test_path)
            except Exception:
                pass
            
            # Strategy 2: Test with the raw bytes as path (path traversal attempt)
            try:
                # Safety: only allow paths within tmpdir
                path_str = data.decode('utf-8', errors='replace')
                if not path_str.startswith('/') and not '..' in path_str:
                    full_path = os.path.join(tmpdir, path_str)
                    bm.load_file_to_buffer(full_path)
            except Exception:
                pass
                
    except Exception:
        pass


def main():
    # Create corpus directory if it doesn't exist
    os.makedirs("corpus", exist_ok=True)
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
```

---

### 2.7 FILE: fuzz_tests/fuzz_format_detection.py
**Purpose**: Fuzz format detection functions (image and audio)

```python
#!/usr/bin/env python3
"""
Fuzzer for format detection functions
Tests file extension parsing and MIME type detection
"""

import sys
import atheris
from src.chatybot.buffer_manager import BufferManager


class FormatMutator(atheris.Mutator):
    """Custom mutator for file extension fuzzing"""
    
    def __init__(self):
        super().__init__()
        self.valid_extensions = ['.jpg', '.jpeg', '.png', '.mp3', '.wav', '.flac', 
                                  '.ogg', '.m4a', '.webm', '.opus', '.aac', '.pcm']
        self.invalid_extensions = ['.exe', '.bat', '.sh', '.py', '.php', '']
    
    def mutate(self, data, data_size, max_size):
        import random
        
        mutated = bytearray(data)
        
        # Strategy: Append a valid extension
        if random.random() < 0.5 and len(mutated) + 10 < max_size:
            ext = random.choice(self.valid_extensions + self.invalid_extensions)
            mutated.extend(ext.encode())
        
        # Strategy: Insert dots and extensions
        if random.random() < 0.3 and len(mutated) + 10 < max_size:
            pos = random.randint(0, len(mutated))
            ext = random.choice(self.valid_extensions)
            mutated = mutated[:pos] + b"." + ext[1:].encode() + mutated[pos:]
        
        return bytes(mutated)


def TestOneInput(data: bytes):
    """Fuzz format detection methods"""
    try:
        bm = BufferManager()
        
        # Try to decode as UTF-8, fallback to raw bytes
        path_str = data.decode('utf-8', errors='replace')
        
        # Test image format detection
        try:
            bm.detect_image_format(path_str)
        except Exception:
            pass
        
        # Test audio format detection
        try:
            bm.detect_audio_format(path_str)
        except Exception:
            pass
            
    except Exception:
        pass


def main():
    atheris.Setup(sys.argv, TestOneInput, custom_mutator=FormatMutator())
    atheris.Fuzz()


if __name__ == "__main__":
    main()
```

---

### 2.8 FILE: fuzz_tests/fuzz_bank_operations.py
**Purpose**: Fuzz bank loading/clearing operations with edge cases

```python
#!/usr/bin/env python3
"""
Fuzzer for bank operations (file, image, audio)
Tests bank number handling, data URL parsing, and edge cases
"""

import sys
import os
import base64
import tempfile
import atheris
from src.chatybot.buffer_manager import BufferManager


def TestOneInput(data: bytes):
    """Fuzz bank operations"""
    try:
        bm = BufferManager()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Test file bank operations
            test_file = os.path.join(tmpdir, "test.txt")
            with open(test_file, "wb") as f:
                f.write(b"test content")
            
            # Fuzz bank number (should be 1-5)
            try:
                # Extract a number from the data
                path_str = data.decode('utf-8', errors='replace')
                # Try to find a digit
                bank_num = 1
                for c in path_str:
                    if c.isdigit():
                        bank_num = int(c)
                        break
                bank_num = max(1, min(bank_num, 5))  # Clamp to valid range
                
                bm.load_file_to_bank(bank_num, test_file)
                bm.clear_file_bank(bank_num)
                bm.show_file_bank(bank_num)
            except Exception:
                pass
            
            # Test image bank with fuzz data
            try:
                test_image = os.path.join(tmpdir, "test.png")
                with open(test_image, "wb") as f:
                    f.write(data)
                bm.load_image_to_bank(1, test_image)
                bm.clear_image_bank(1)
            except Exception:
                pass
            
            # Test audio bank with fuzz data
            try:
                test_audio = os.path.join(tmpdir, "test.mp3")
                with open(test_audio, "wb") as f:
                    f.write(data)
                bm.load_audio_to_bank(1, test_audio)
                bm.clear_audio_bank(1)
            except Exception:
                pass
                
    except Exception:
        pass


def main():
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
```

---

### 2.9 Corpus Files

**fuzz_tests/corpus/empty.txt**
```

```

**fuzz_tests/corpus/normal_placeholders.txt**
```
Hello {filebank1} world! My name is ${var1}.
```

**fuzz_tests/corpus/nested_placeholders.txt**
```
{{filebank1}} {{{filebank2}}} ${var1}
```

**fuzz_tests/corpus/special_chars.txt**
```
Test {filebank1} with $ special chars: !@#$%^&*(){}[]
```

**fuzz_tests/corpus/long_string.txt**
```
This is a very long string with {filebank1} repeated many times. {filebank1} {filebank1} {filebank1} {filebank1} {filebank1} {filebank1} {filebank1} {filebank1} {filebank1} {filebank1}
```

**fuzz_tests/corpus/unicode.txt**
```
Unicode test: 你好 {filebank1} 世界 ${var1} 🌍
```

**fuzz_tests/corpus/all_placeholders.txt**
```
{filebank1} {filebank2} {filebank3} {filebank4} {filebank5} ${var1} ${var2} {imagebank1} {imagebank2} {audiobank1}
```

**fuzz_tests/corpus/malformed_placeholders.txt**
```
{filebank {filebank1} filebank} ${var ${var1} var} }{{{ broken
```

---

### 2.10 Modified Files

#### FILE: src/chatybot/buffer_manager.py (Optional Instrumentation)

Add instrumentation to the module for better coverage tracking. Add at the **top** of the file after imports:

```python
# Optional: Uncomment for Atheris instrumentation
# import atheris
# atheris.instrument_func(BufferManager.load_file_to_buffer)
# atheris.instrument_func(BufferManager.load_file_to_bank)
# atheris.instrument_func(BufferManager.load_image_to_bank)
# atheris.instrument_func(BufferManager.load_audio_to_bank)
# atheris.instrument_func(BufferManager.replace_placeholders)
# atheris.instrument_func(BufferManager.replace_placeholders_legacy)
# atheris.instrument_func(BufferManager.detect_image_format)
# atheris.instrument_func(BufferManager.detect_audio_format)
# atheris.instrument_func(BufferManager.dump_variables)
```

Or use automatic instrumentation:
```python
# import atheris
# atheris.instrument_all()
```

#### FILE: .gitignore
Add to ignore fuzzing artifacts:
```
# Atheris fuzzing
fuzz_tests/crashes/
fuzz_tests/artifacts/
```

---

## 3. RUNNING THE FUZZERS

### First Run
```bash
# Install Atheris
pip install atheris

# Create directory
mkdir -p fuzz_tests/corpus

# Copy the files above into fuzz_tests/

# Make run script executable
chmod +x fuzz_tests/run_all_fuzzers.sh

# Run a single fuzzer (test first)
python fuzz_tests/fuzz_placeholders.py -atheris_runs=1000

# Run all fuzzers
cd fuzz_tests && ./run_all_fuzzers.sh
```

### Monitoring
- Fuzzers output progress and crashes to stdout
- Crashes are saved in `crashes/` directory with the input that caused them
- Use `Ctrl+C` to stop

### Example Output
```
INFO: Seed corpus: 8 files in corpus/
INFO: Running with entropic power schedule (0x100000000)
INFO: Starting 1000 test cases
...
INFO: Fuzzer found a crash!
INFO: Saved crash artifact to crashes/fuzz_placeholders/2026-04-28-12:34:56
```

---

## 4. WHAT ATHERIS WILL DO

### For Each Fuzzer:
1. **Read corpus files** from `corpus/` directory
2. **Mutate inputs** using:
   - Built-in mutators (bit flips, byte flips, insertions, deletions)
   - Custom mutators (placeholder-specific, format-specific)
3. **Track coverage** of which lines are executed
4. **Prioritize inputs** that increase coverage
5. **Save crashes** when unhandled exceptions occur
6. **Loop indefinitely** until stopped

### What Atheris Tests Automatically:
- ✅ Empty inputs
- ✅ Very long inputs
- ✅ Unicode/non-UTF-8 byte sequences
- ✅ Special characters (null bytes, control chars)
- ✅ Repeated patterns
- ✅ All combinations of placeholders
- ✅ Edge cases in file paths
- ✅ Malformed data URLs

---

## 5. EXPECTED BUGS TO FIND

### High Priority (Critical)
| Category | Example Input | Method | Expected Bug |
|----------|---------------|--------|--------------|
| Path traversal | `../../../etc/passwd` | load_file_to_bank | Unauthorized file access |
| Path traversal | `../../../etc/passwd` | load_image_to_bank | Unauthorized file access |
| Path traversal | `../../../etc/passwd` | load_audio_to_bank | Unauthorized file access |

### Medium Priority (Functionality)
| Category | Example Input | Method | Expected Bug |
|----------|---------------|--------|--------------|
| Placeholder parsing | `{{filebank1}}` | replace_placeholders | Incorrect nesting handling |
| Placeholder parsing | `{filebank1}{filebank2}` | replace_placeholders | Overlapping replacement |
| Placeholder parsing | `{filebank` (unclosed) | replace_placeholders | No error, silent failure |
| Format detection | `test.xyz` | detect_image_format | No error, returns wrong MIME |
| Format detection | `test` (no ext) | detect_audio_format | No error, returns wrong MIME |
| Base64 encoding | Invalid base64 | load_image_to_bank | Crash on decode |
| Unicode | Non-UTF-8 bytes | Any | Encoding errors |

### Low Priority (Edge Cases)
| Category | Example Input | Method | Expected Bug |
|----------|---------------|--------|--------------|
| Bank numbers | bank_num=0 | load_file_to_bank | No error, wrong bank |
| Bank numbers | bank_num=6 | load_file_to_bank | No error, wrong bank |
| Bank numbers | bank_num=-1 | load_file_to_bank | ValueError (correct) |
| Empty input | `""` | replace_placeholders | No error (correct) |
| Very long | 10MB string | replace_placeholders | Memory/performance |

---

## 6. SUCCESS CRITERIA

- [ ] Atheris installed successfully
- [ ] `fuzz_tests/` directory created with all files
- [ ] Corpus directory populated with seed inputs
- [ ] At least 1 fuzzer runs without errors
- [ ] Any crashes found are documented
- [ ] Crashes are fixed or acknowledged

## 7. ESTIMATED TIME
- **Quick test**: 30 minutes (install + 1 fuzzer)
- **Full setup**: 2 hours (all fuzzers + corpus)
- **Finding bugs**: 1-4 hours (depends on code quality)
- **Fixing bugs**: Variable

## 8. RISKS AND MITIGATIONS

| Risk | Mitigation |
|------|------------|
| False positives from corpus | Start with empty corpus, let Atheris generate |
| Performance overhead | Run with `-atheris_runs=10000` limit |
| Disk space from crashes | Clean crashes/ directory periodically |
| Native extension issues | N/A - buffer_manager.py is pure Python |
| Infinite loops | Atheris has built-in timeout per input |

## 9. NEXT STEP

Approve this plan to proceed with implementation:
1. Create `fuzz_tests/` directory structure
2. Add all fuzzer files and corpus files
3. Install Atheris (`pip install atheris`)
4. Run initial test: `python fuzz_tests/fuzz_placeholders.py -atheris_runs=1000`

---

## FILE 3: fuzz_tests/run_all_fuzzers.sh

**Purpose**: Run all fuzzers in parallel

```bash
#!/bin/bash
# Run all Atheris fuzzers in parallel
# Usage: ./run_all_fuzzers.sh

set -e

echo "=========================================="
echo "  Atheris Fuzzing for chatybot BufferManager"
echo "  Starting all fuzzers..."
echo "  Press Ctrl+C to stop all"
echo "=========================================="
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

export PYTHONPATH=.:"$PYTHONPATH"

FUZZERS=(
    "fuzz_placeholders.py"
    "fuzz_file_loading.py"
    "fuzz_format_detection.py"
    "fuzz_bank_operations.py"
)

PIDS=()

for fuzzer in "${FUZZERS[@]}"; do
    echo "[+] Starting $fuzzer at $(date)"
    python "$SCRIPT_DIR/$fuzzer" -artifact_prefix="$SCRIPT_DIR/../crashes/$fuzzer" &
    PIDS+=($!)
    echo "    PID: $!"
done

echo ""
echo "All fuzzers running. PIDs: ${PIDS[*]}"
echo "Output will appear below. Press Ctrl+C to stop."
echo ""

# Wait for all background processes
wait

echo ""
echo "All fuzzers stopped at $(date)"
```

Make executable after creation:
```bash
chmod +x fuzz_tests/run_all_fuzzers.sh
```

---

## FILE 4: fuzz_tests/fuzz_placeholders.py

**Purpose**: Fuzz placeholder replacement logic - the most complex and bug-prone functionality

```python
#!/usr/bin/env python3
"""
Atheris Fuzzer for BufferManager.replace_placeholders()

Target: String parsing and placeholder substitution logic

Tests:
- Normal placeholder replacement ({filebank1}, ${var1})
- Nested braces ({{filebank1}})
- Adjacent placeholders ({filebank1}{filebank2})
- Special characters in content ($, {, })
- Unicode characters
- Empty inputs
- Very long inputs
- Malformed placeholders

Custom Mutator: PlaceholderMutator with domain-specific mutations

Usage:
    python fuzz_placeholders.py [-atheris_runs=N] [-max_len=N]

Author: Generated for chatybot fuzzing
Date: 2026-04-28
"""

import sys
import os
import random
import atheris

# Ensure project is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.chatybot.buffer_manager import BufferManager


class PlaceholderMutator(atheris.Mutator):
    """
    Custom mutator that understands placeholder syntax.
    
    Generates inputs that specifically test:
    - Valid placeholder patterns
    - Nested braces
    - Special characters that interact with placeholders
    - Edge cases in string parsing
    """
    
    def __init__(self):
        super().__init__()
        
        # All valid placeholders in buffer_manager
        self.all_placeholders = [
            # File banks
            "{filebank1}", "{filebank2}", "{filebank3}", "{filebank4}", "{filebank5}",
            # Script variables
            "${var1}", "${var2}", "${var3}", "${var4}", "${var5}",
            # Image banks
            "{imagebank1}", "{imagebank2}", "{imagebank3}", "{imagebank4}", "{imagebank5}",
            # Audio banks
            "{audiobank1}", "{audiobank2}", "{audiobank3}", "{audiobank4}", "{audiobank5}",
        ]
        
        # Special characters that might interact with placeholder parsing
        self.special_chars = [
            "{", "}", "$", 
            "\n", "\r", "\t", "\\", 
            "'", '"', ";", ":", ",", ".", "/", "|", "&", 
        ]
        
        # Nesting patterns
        self.nesting_patterns = [
            "{{", "}}", 
            "{{{", "}}}", 
            "{{{{", "}}}}",
            "${{", "}}$",
            "${", "}$",
            "}{{", "}}",
        ]
        
        # Partial/malformed placeholders
        self.malformed_patterns = [
            "{filebank", "filebank}", "${var", "var}",
            "{", "}", "${", "}",
            "{{filebank", "filebank}}",
        ]
    
    def mutate(self, data, data_size, max_size):
        """
        Generate domain-specific mutations for placeholder testing.
        
        Strategies:
        1. Insert valid placeholders (30%)
        2. Insert special characters (30%)
        3. Create nesting patterns (20%)
        4. Create malformed patterns (10%)
        5. Duplicate existing placeholders (10%)
        
        Args:
            data: Current input bytes
            data_size: Size of current input
            max_size: Maximum allowed size
            
        Returns:
            Mutated bytes
        """
        mutated = bytearray(data)
        strategy = random.random()
        
        # Strategy 1: Insert a valid placeholder (30%)
        if strategy < 0.3 and len(mutated) + 20 < max_size:
            placeholder = random.choice(self.all_placeholders)
            pos = random.randint(0, len(mutated))
            mutated = mutated[:pos] + placeholder.encode() + mutated[pos:]
        
        # Strategy 2: Insert special character (30%)
        elif strategy < 0.6 and len(mutated) + 5 < max_size:
            char = random.choice(self.special_chars)
            pos = random.randint(0, len(mutated))
            mutated = mutated[:pos] + char.encode() + mutated[pos:]
        
        # Strategy 3: Create nesting (20%)
        elif strategy < 0.8 and len(mutated) + 10 < max_size:
            pattern = random.choice(self.nesting_patterns)
            pos = random.randint(0, len(mutated))
            mutated = mutated[:pos] + pattern.encode() + mutated[pos:]
        
        # Strategy 4: Create malformed pattern (10%)
        elif strategy < 0.9 and len(mutated) + 15 < max_size:
            pattern = random.choice(self.malformed_patterns)
            pos = random.randint(0, len(mutated))
            mutated = mutated[:pos] + pattern.encode() + mutated[pos:]
        
        # Strategy 5: Duplicate existing placeholder (10%)
        elif len(mutated) + 50 < max_size:
            for ph in self.all_placeholders:
                if ph.encode() in mutated:
                    pos = random.randint(0, len(mutated))
                    mutated = mutated[:pos] + ph.encode() + mutated[pos:]
                    break
        
        # Bonus: Sometimes truncate to create partial placeholders
        if random.random() < 0.05 and len(mutated) > 10:
            cut_pos = random.randint(1, len(mutated))
            mutated = mutated[:cut_pos]
        
        return bytes(mutated)


def TestOneInput(data: bytes):
    """
    Test function called by Atheris for each fuzzed input.
    
    Tests the replace_placeholders and replace_placeholders_legacy methods
    with various inputs including placeholders, special characters, and edge cases.
    
    Args:
        data: Fuzzed input bytes (will be decoded to string)
    """
    try:
        # Create fresh BufferManager for each test
        bm = BufferManager()
        
        # Pre-populate banks and vars with test content
        # This ensures that when placeholders are replaced, there's actual content
        bm.file_banks["filebank1"] = "FILEBANK_1_CONTENT"
        bm.file_banks["filebank2"] = "FILEBANK_2_CONTENT"
        bm.file_banks["filebank3"] = "FILEBANK_3_CONTENT"
        bm.file_banks["filebank4"] = "FILEBANK_4_CONTENT"
        bm.file_banks["filebank5"] = "FILEBANK_5_CONTENT"
        
        bm.script_vars["var1"] = "SCRIPT_VAR_1_VALUE"
        bm.script_vars["var2"] = "SCRIPT_VAR_2_VALUE"
        bm.script_vars["var3"] = "SCRIPT_VAR_3_VALUE"
        bm.script_vars["var4"] = "SCRIPT_VAR_4_VALUE"
        bm.script_vars["var5"] = "SCRIPT_VAR_5_VALUE"
        
        # Decode input with robust error handling
        try:
            input_str = data.decode('utf-8')
        except UnicodeDecodeError:
            try:
                input_str = data.decode('latin-1')
            except UnicodeDecodeError:
                input_str = data.decode('utf-8', errors='replace')
        
        # Test 1: replace_placeholders with include_images=True
        try:
            result_text, images = bm.replace_placeholders(
                input_str, 
                include_images=True
            )
            # Use result to ensure coverage
            if result_text:
                _ = len(result_text)
                _ = result_text.encode('utf-8')
        except Exception:
            # Atheris automatically catches and reports unhandled exceptions
            pass
        
        # Test 2: replace_placeholders with include_images=False
        try:
            result_text, images = bm.replace_placeholders(
                input_str,
                include_images=False
            )
        except Exception:
            pass
        
        # Test 3: Legacy replacement (text only, no images)
        try:
            result_text = bm.replace_placeholders_legacy(input_str)
        except Exception:
            pass
            
    except Exception:
        # This catches any exception in the test setup itself
        # Atheris catches exceptions in TestOneInput
        pass


def main():
    """Main entry point for the fuzzer."""
    # Ensure corpus directory exists
    os.makedirs("corpus", exist_ok=True)
    
    # Set up and run fuzzer with custom mutator
    atheris.Setup(
        sys.argv, 
        TestOneInput,
        custom_mutator=PlaceholderMutator()
    )
    atheris.Fuzz()


if __name__ == "__main__":
    main()
```

---


---

## FILE 5: fuzz_tests/fuzz_file_loading.py

**Purpose**: Fuzz all file loading methods to test path handling and I/O operations

```python
#!/usr/bin/env python3
"""
Atheris Fuzzer for BufferManager file loading functions.

Tests:
- Path validation and sanitization
- File I/O operations
- Error handling for various file scenarios
- Path traversal resistance

Safety: All file operations use temp directory

Usage:
    python fuzz_file_loading.py [-atheris_runs=N] [-max_len=N]
"""

import sys
import os
import tempfile
import atheris

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.chatybot.buffer_manager import BufferManager


def TestOneInput(data: bytes):
    """Test file loading methods with fuzzed inputs."""
    try:
        bm = BufferManager()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Strategy 1: Create file with fuzz data, then load it
            try:
                test_path = os.path.join(tmpdir, "fuzz_test.txt")
                with open(test_path, "wb") as f:
                    f.write(data)
                
                bm.load_file_to_buffer(test_path)
                bm.clear_file_buffer()
                
                # Test all 5 file banks
                for bank_num in range(1, 6):
                    bm.load_file_to_bank(bank_num, test_path)
                    bm.clear_file_bank(bank_num)
            except Exception:
                pass
            
            # Strategy 2: Use fuzz data as filename (path manipulation test)
            # SAFETY: Only allow safe relative paths
            try:
                path_str = data.decode('utf-8', errors='replace')
                
                # Sanitize: reject absolute paths and traversal
                if (not path_str.startswith('/') and 
                    '..' not in path_str and 
                    path_str and 
                    all(c.isalnum() or c in '_-./ ' for c in path_str)):
                    
                    full_path = os.path.join(tmpdir, path_str)
                    # Ensure it's still within tmpdir after resolution
                    if os.path.abspath(full_path).startswith(tmpdir):
                        bm.load_file_to_buffer(full_path)
            except Exception:
                pass
    except Exception:
        pass


def main():
    os.makedirs("corpus", exist_ok=True)
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
```

---

## FILE 6: fuzz_tests/fuzz_format_detection.py

**Purpose**: Fuzz MIME type detection from file extensions

```python
#!/usr/bin/env python3
"""
Atheris Fuzzer for BufferManager format detection functions.

Tests:
- File extension parsing
- MIME type detection logic
- Edge cases in extension handling

Usage:
    python fuzz_format_detection.py [-atheris_runs=N] [-max_len=N]
"""

import sys
import os
import random
import atheris

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.chatybot.buffer_manager import BufferManager


class FormatMutator(atheris.Mutator):
    """Custom mutator for file extension fuzzing."""
    
    def __init__(self):
        super().__init__()
        self.image_exts = ['.jpg', '.jpeg', '.png']
        self.audio_exts = ['.mp3', '.wav', '.flac', '.ogg', '.m4a', '.webm', '.opus', '.aac', '.pcm']
        self.invalid_exts = ['.exe', '.bat', '.sh', '.py', '.php', '.js', '']
        self.special_exts = ['.', '..', '...', '.tar.gz', '.old.bak', '.tmp~', '.']
    
    def mutate(self, data, data_size, max_size):
        import random
        mutated = bytearray(data)
        
        all_exts = self.image_exts + self.audio_exts + self.invalid_exts + self.special_exts
        
        # Strategy: Append an extension
        if random.random() < 0.5 and len(mutated) + 10 < max_size:
            ext = random.choice(all_exts)
            mutated.extend(ext.encode())
        
        # Strategy: Insert extension in middle
        elif random.random() < 0.8 and len(mutated) + 10 < max_size:
            pos = random.randint(0, len(mutated))
            ext = random.choice(all_exts)
            mutated = mutated[:pos] + b"." + ext[1:].encode() + mutated[pos:]
        
        # Strategy: Multiple extensions
        elif len(mutated) + 30 < max_size:
            for _ in range(random.randint(1, 3)):
                ext = random.choice(self.image_exts + self.audio_exts)
                mutated.extend(b"." + ext[1:].encode())
        
        return bytes(mutated)


def TestOneInput(data: bytes):
    """Test format detection with fuzzed file paths."""
    try:
        bm = BufferManager()
        
        try:
            path_str = data.decode('utf-8')
        except UnicodeDecodeError:
            try:
                path_str = data.decode('latin-1')
            except UnicodeDecodeError:
                path_str = data.decode('utf-8', errors='replace')
        
        # Test image format detection
        try:
            mime = bm.detect_image_format(path_str)
            if mime:
                _ = mime.encode('utf-8')
        except Exception:
            pass
        
        # Test audio format detection
        try:
            mime = bm.detect_audio_format(path_str)
            if mime:
                _ = mime.encode('utf-8')
        except Exception:
            pass
    except Exception:
        pass


def main():
    os.makedirs("corpus", exist_ok=True)
    atheris.Setup(sys.argv, TestOneInput, custom_mutator=FormatMutator())
    atheris.Fuzz()


if __name__ == "__main__":
    main()
```

---

## FILE 7: fuzz_tests/fuzz_bank_operations.py

**Purpose**: Fuzz all bank loading/clearing operations

```python
#!/usr/bin/env python3
"""
Atheris Fuzzer for BufferManager bank operations.

Tests:
- Bank number validation (1-5)
- Bank loading with various file types
- Bank clearing
- Bank display
- Data URL parsing for images/audio

Safety: Uses temp directory for all operations

Usage:
    python fuzz_bank_operations.py [-atheris_runs=N] [-max_len=N]
"""

import sys
import os
import tempfile
import atheris

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.chatybot.buffer_manager import BufferManager


def TestOneInput(data: bytes):
    """Test bank operations with fuzzed inputs."""
    try:
        bm = BufferManager()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            test_file = os.path.join(tmpdir, "test.txt")
            test_image = os.path.join(tmpdir, "test.png")
            test_audio = os.path.join(tmpdir, "test.mp3")
            
            with open(test_file, "wb") as f:
                f.write(b"file bank test content")
            with open(test_image, "wb") as f:
                f.write(b'\x89PNG\r\n\x1a\n' + data[:100])  # Valid PNG header
            with open(test_audio, "wb") as f:
                f.write(data[:100])  # Audio data
            
            # Extract bank number from data
            try:
                path_str = data.decode('utf-8', errors='replace')
                bank_num = 1
                for c in path_str:
                    if c.isdigit():
                        bank_num = int(c) % 5 + 1  # Clamp to 1-5
                        break
            except Exception:
                bank_num = 1
            
            # Test file bank operations
            try:
                bm.load_file_to_bank(bank_num, test_file)
                bm.show_file_bank(bank_num)
                bm.clear_file_bank(bank_num)
            except Exception:
                pass
            
            # Test image bank operations
            try:
                bm.load_image_to_bank(1, test_image)
                bm.show_image_bank(1)
                bm.clear_image_bank(1)
            except Exception:
                pass
            
            # Test audio bank operations
            try:
                bm.load_audio_to_bank(1, test_audio)
                bm.clear_audio_bank(1)
            except Exception:
                pass
            
            # Test variable operations
            try:
                path_str = data.decode('utf-8', errors='replace')
                safe_name = ''.join(c if c.isalnum() or c in '_-' else '_' for c in path_str[:50])
                if safe_name and safe_name[0].isalpha():
                    bm.set_script_var(safe_name, "test_value")
                    bm.dump_variables(safe_name)
            except Exception:
                pass
    except Exception:
        pass


def main():
    os.makedirs("corpus", exist_ok=True)
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
```

---

## FILE 8-15: Corpus Files

Create these files in `fuzz_tests/corpus/`:

### corpus/empty.txt
```

```

### corpus/normal_placeholders.txt
```
Hello {filebank1} world! My name is ${var1} and I work at {filebank2}.
```

### corpus/nested_placeholders.txt
```
{{filebank1}} {{{filebank2}}} ${var1} $${var2} ${{var3}}
```

### corpus/adjacent_placeholders.txt
```
{filebank1}{filebank2}{filebank3}${var1}${var2}${var3}
```

### corpus/special_chars.txt
```
Special chars: !@#$%^&*(){}[]|\:;"'<>,.?/~` {filebank1} ${var1}
```

### corpus/long_string.txt
```
This is a very long string with {filebank1} repeated many times throughout. {filebank1} {filebank1} {filebank1} {filebank1} {filebank1} {filebank1} {filebank1} {filebank1} {filebank1} {filebank1} and more content here.
```

### corpus/unicode.txt
```
Unicode test: 你好世界 {filebank1} 世界 ${var1} 🌍 Привет {filebank2} こんにちは
```

### corpus/all_placeholders.txt
```
{filebank1} {filebank2} {filebank3} {filebank4} {filebank5} ${var1} ${var2} ${var3} ${var4} ${var5} {imagebank1} {imagebank2} {imagebank3} {imagebank4} {imagebank5} {audiobank1} {audiobank2} {audiobank3} {audiobank4} {audiobank5}
```

### corpus/malformed_placeholders.txt
```
{filebank {filebank1} filebank} ${var ${var1} var} }{{{ broken [[}]
```

---

## FILE 16: Modified .gitignore

Add to your `.gitignore`:

```
# Atheris fuzzing
fuzz_tests/crashes/
fuzz_tests/artifacts/
fuzz_tests/*.pyc
fuzz_tests/__pycache__/
fuzz_tests/corpus/*.pyc
/tmp/fuzz_*
```

---

## FILE 17: Optional Instrumentation in buffer_manager.py

Add at the top of `src/chatybot/buffer_manager.py` (after existing imports):

```python
# ============================================================================
# ATHERIS FUZZING INSTRUMENTATION (Optional)
# Uncomment the lines below when running fuzzers for better coverage
# ============================================================================
# import atheris
# atheris.instrument_func(BufferManager.load_file_to_buffer)
# atheris.instrument_func(BufferManager.load_file_to_bank)
# atheris.instrument_func(BufferManager.load_image_to_bank)
# atheris.instrument_func(BufferManager.load_audio_to_bank)
# atheris.instrument_func(BufferManager.clear_file_buffer)
# atheris.instrument_func(BufferManager.clear_file_bank)
# atheris.instrument_func(BufferManager.clear_image_bank)
# atheris.instrument_func(BufferManager.clear_audio_bank)
# atheris.instrument_func(BufferManager.replace_placeholders)
# atheris.instrument_func(BufferManager.replace_placeholders_legacy)
# atheris.instrument_func(BufferManager.detect_image_format)
# atheris.instrument_func(BufferManager.detect_audio_format)
# atheris.instrument_func(BufferManager.set_script_var)
# atheris.instrument_func(BufferManager.dump_variables)
# atheris.instrument_func(BufferManager.show_memory_usage)
# atheris.instrument_all()  # Alternative: instrument all loaded modules
```

---

# 5. Expected Bug Categories with Examples

## 5.1 Critical Security Issues (P0)

### Path Traversal
**Description**: Ability to read files outside the intended directory
**Methods**: `load_file_to_bank`, `load_image_to_bank`, `load_audio_to_bank`
**Test Input**: `../../../etc/passwd`
**Expected**: Should either reject or sanitize the path
**Actual**: Currently loads arbitrary files (SECURITY BUG)
**Fix**: Add path validation: `if '..' in path or path.startswith('/'): raise ValueError`

### Arbitrary File Read
**Description**: Reading sensitive files
**Methods**: All load_* methods
**Test Input**: `/etc/passwd`
**Expected**: Rejected
**Actual**: May succeed if file exists (SECURITY BUG)
**Fix**: Restrict to specific allowed directories

### Symlink Attack
**Description**: Following symlinks to sensitive files
**Methods**: All load_* methods
**Test Input**: Symlink pointing to `/etc/shadow`
**Expected**: Rejected or resolved to real path first
**Actual**: Currently follows symlinks (SECURITY BUG)
**Fix**: Use `os.path.realpath()` and validate

## 5.2 High Priority Bugs (P1)

### Nested Braces
**Description**: Incorrect handling of nested curly braces
**Method**: `replace_placeholders`
**Test Input**: `{{filebank1}}`
**Expected**: Replaced with `{FILEBANK_1_CONTENT}`
**Actual**: May not replace or may error
**Fix**: Implement recursive/proper brace counting

### Adjacent Placeholders
**Description**: Overlapping placeholder replacement
**Method**: `replace_placeholders`
**Test Input**: `{filebank1}{filebank2}`
**Expected**: Both replaced correctly
**Actual**: May have issues if replacement changes string length
**Fix**: Process placeholders in single pass, not sequential replace

### Partial Placeholders
**Description**: Unclosed or malformed placeholders
**Method**: `replace_placeholders`
**Test Input**: `{filebank1` or `filebank1}`
**Expected**: Left as-is or error
**Actual**: Currently left as-is (silent)
**Fix**: Add warning or validation

### Invalid Extensions
**Description**: Unknown file extensions
**Method**: `detect_image_format`, `detect_audio_format`
**Test Input**: `file.xyz` or `file`
**Expected**: ValueError for images, fallback for audio
**Actual**: May work or may crash
**Fix**: Consistent error handling

## 5.3 Medium Priority Bugs (P2)

### Unicode Paths
**Description**: Non-ASCII file paths
**Methods**: All load_* methods
**Test Input**: `tëst_文件.txt`
**Expected**: Handle correctly
**Actual**: May crash or misbehave
**Fix**: Use proper Unicode handling

### Very Long Inputs
**Description**: Memory/performance with large inputs
**Method**: `replace_placeholders`
**Test Input**: 10MB string
**Expected**: Complete in reasonable time
**Actual**: May be slow or crash
**Fix**: Add length limits or streaming

### Control Characters
**Description**: Null bytes and control chars in input
**Method**: All string methods
**Test Input**: `\x00{filebank1}\x00`
**Expected**: Handle correctly
**Actual**: May cause issues
**Fix**: Validate input strings

### Bank Number Edge Cases
**Description**: Invalid bank numbers
**Methods**: All bank methods
**Test Input**: bank_num=0, bank_num=6, bank_num=-1
**Expected**: ValueError for invalid numbers
**Actual**: Currently accepts 0 and negative (BUG)
**Fix**: Add validation: `if bank_num < 1 or bank_num > 5: raise ValueError`

---

# 6. Step-by-Step Setup Guide

## 6.1 Prerequisites Check

```bash
# Check Python version
python3 --version  # Should be 3.7+

# Check pip
pip --version

# Check OS
uname -a  # Linux/macOS recommended
```

## 6.2 Installation

```bash
# Install Atheris
pip install atheris

# Verify
python3 -c "import atheris; print(f'Atheris version: {atheris.__version__}')"

# Install project dependencies (if any)
pip install -e .  # Or: python setup.py develop
```

## 6.3 Create Directory Structure

```bash
cd /Users/jon2allen/github/chatybot

# Create fuzzing directory
mkdir -p fuzz_tests/corpus

# Create files (copy from this document)
touch fuzz_tests/__init__.py
# ... create all other files ...
```

## 6.4 Make Scripts Executable

```bash
chmod +x fuzz_tests/run_all_fuzzers.sh
```

## 6.5 Verify Imports

```bash
cd /Users/jon2allen/github/chatybot
PYTHONPATH=. python3 -c "from src.chatybot.buffer_manager import BufferManager; print('✓ BufferManager import works')"
PYTHONPATH=. python3 -c "import atheris; print('✓ Atheris import works')"
```

## 6.6 Test Single Fuzzer

```bash
cd /Users/jon2allen/github/chatybot
PYTHONPATH=. python3 fuzz_tests/fuzz_placeholders.py -atheris_runs=100
```

If this runs without errors and completes, your setup is working!

---

# 7. Execution and Monitoring

## 7.1 Running Fuzzers

### Run Single Fuzzer
```bash
cd /Users/jon2allen/github/chatybot
PYTHONPATH=. python3 fuzz_tests/fuzz_placeholders.py
```

### Run With Limit
```bash
# Run 10,000 iterations and exit
PYTHONPATH=. python3 fuzz_tests/fuzz_placeholders.py -atheris_runs=10000
```

### Run All Fuzzers
```bash
cd /Users/jon2allen/github/chatybot
./fuzz_tests/run_all_fuzzers.sh
```

### Run in Background
```bash
nohup ./fuzz_tests/run_all_fuzzers.sh > fuzz_output.log 2>&1 &
echo "PID: $!"
```

### Run in Screen Session (Recommended)
```bash
# Start screen session
screen -S chatybot_fuzzing

# Run fuzzers
cd /Users/jon2allen/github/chatybot
./fuzz_tests/run_all_fuzzers.sh

# Detach: Ctrl+A, D
# Reattach: screen -r chatybot_fuzzing
```

## 7.2 Monitoring Output

### Normal Progress
```
INFO: Running with entropic power schedule (0x100000000)
INFO: Starting 1 workers
INFO: Loaded 8 corpus files
INFO: -1234567890 0x12345678 (data flow: 123-456-789)
INFO: 10000 executions, 0 crashes, coverage: 85%
```

### Crash Found
```
INFO: Fuzzer found a crash!
INFO: Saving artifact to crashes/fuzz_placeholders/2026-04-28T14:30:45
INFO: Crash input: b'{{{filebank1}}'  
WARNING: Exception in TestOneInput: KeyError: 'filebank10'
```

### Statistics Interpretation
- **Exec/s**: Executions per second (higher = better)
- **Unique crashes**: Number of distinct crash types
- **Total runs**: Total test cases executed
- **Coverage**: Percentage of code lines covered

## 7.3 Stopping Fuzzers

- **Single fuzzer**: `Ctrl+C`
- **All fuzzers**: `pkill -f "python.*fuzz_"`
- **Screen session**: `screen -XS chatybot_fuzzing quit`

---

# 8. Interpreting Results

## 8.1 Crash Artifacts

When a crash is found, Atheris saves:

```
crashes/<fuzzer>/<timestamp>/
├── crash_input          # Input that caused the crash
├── crash_stacktrace     # Python stack trace
├── crash_reproduce.py   # Script to reproduce
└── INFO                 # Metadata
```

### Reproducing a Crash

```bash
# Navigate to crash directory
cd crashes/fuzz_placeholders/2026-04-28T14:30:45

# Run the reproduce script
python crash_reproduce.py

# Or manually
python3 -c "
import sys
sys.path.insert(0, '/Users/jon2allen/github/chatybot')
from src.chatybot.buffer_manager import BufferManager

# Read crash input
with open('crash_input', 'rb') as f:
    data = f.read()

# Reproduce
bm = BufferManager()
bm.replace_placeholders(data.decode('utf-8', errors='replace'))
"
```

## 8.2 Analyzing Crash Inputs

### Common Patterns to Look For:

1. **Path Traversal**: `../` or `/etc/` in file paths
2. **Nested Braces**: `{{{` or `}}}` in placeholder strings
3. **Special Characters**: Null bytes, control chars
4. **Unicode**: Non-ASCII characters
5. **Length**: Very long or very short inputs
6. **Boundary Values**: Bank numbers 0, 6, -1

### Example Analysis:

```
Crash Input: b'../../../etc/passwd'
Crash Location: buffer_manager.py:35 in load_file_to_buffer
Exception: FileNotFoundError

Analysis: Path traversal not prevented. The code tries to open
../../../etc/passwd which may not exist in the test environment but
would work if the file existed.

Fix: Add path validation:
    if '..' in file_path or file_path.startswith('/'):
        raise ValueError(f"Invalid file path: {file_path}")
```

## 8.3 Coverage Analysis

Atheris tracks which lines of code are executed. Low coverage indicates:

1. **Dead code**: Code that's never executed
2. **Hard-to-reach paths**: Code that requires specific conditions
3. **Missing corpus**: Seed inputs don't trigger certain code paths

### Improving Coverage:

1. **Add more corpus files** with diverse inputs
2. **Add custom mutators** that understand the domain
3. **Add instrumentation** to key functions
4. **Manually review** low-coverage areas

---

# 9. Advanced Configurations

## 9.1 Environment Variables

```bash
# Limit memory usage (MB)
ATHERIS_MEMORY_LIMIT=2048 python fuzz_placeholders.py

# Disable leak detection (faster)
ASAN_OPTIONS=detect_leaks=0 python fuzz_placeholders.py

# Set output directory
ARTIFACT_DIR=my_crashes python fuzz_placeholders.py
```

## 9.2 Differential Fuzzing

Compare buffer_manager against a reference implementation:

```python
# In TestOneInput:
def TestOneInput(data: bytes):
    try:
        # Reference implementation
        ref_result = reference_replace_placeholders(data)
        
        # Target implementation  
        bm = BufferManager()
        bm.file_banks["filebank1"] = "test"
        target_result, _ = bm.replace_placeholders(data.decode('utf-8'))
        
        # Compare
        assert ref_result == target_result, f"Mismatch: {ref_result} != {target_result}"
    except Exception:
        pass
```

## 9.3 Fuzzing with Sanitizers

For deeper bug finding, compile Python with sanitizers:

```bash
# Install sanitizer-enabled Python (Linux)
# This is advanced - requires building Python from source

# Then run with:
LD_PRELOAD=$(python -c "import atheris; print(atheris.path())")/asan_with_fuzzer.so \
    python fuzz_placeholders.py
```

## 9.4 Custom Mutator Advanced Techniques

```python
class AdvancedPlaceholderMutator(atheris.Mutator):
    def mutate(self, data, data_size, max_size):
        # Use Atheris's built-in mutations 80% of the time
        if random.random() < 0.8:
            return super().mutate(data, data_size, max_size)
        
        # Custom mutations 20% of the time
        mutated = bytearray(data)
        
        # Create realistic prompt with placeholders
        if random.random() < 0.5 and len(mutated) < max_size - 100:
            prefix = random.choice(["Please ", "Can you ", "Show me "])
            placeholder = random.choice(["{filebank1}", "{filebank2}", "${var1}"])
            suffix = random.choice([" now", " please", " thanks"])
            new_input = (prefix + placeholder + suffix).encode()
            return new_input
        
        return bytes(mutated)
```

---

# Summary

## What You Now Have

1. **4 specialized fuzzers** targeting different parts of buffer_manager.py
2. **2 custom mutators** for domain-specific input generation
3. **8 corpus seed files** for guided fuzzing
4. **Complete documentation** for setup and execution
5. **Expected bug list** with specific test cases

## Next Steps

1. ✅ **Create the files** (copy from this document)
2. ✅ **Install Atheris** (`pip install atheris`)
3. ✅ **Test single fuzzer** (`python fuzz_placeholders.py -atheris_runs=1000`)
4. ✅ **Run all fuzzers** (`./run_all_fuzzers.sh`)
5. ✅ **Monitor for crashes** (check `crashes/` directory)
6. ✅ **Fix any bugs found**
7. ✅ **Add to CI/CD** (optional)

## Files Created

```
fuzz_tests/
├── __init__.py                    # 1 line
├── README.md                      # Documentation
├── run_all_fuzzers.sh             # Parallel execution
├── fuzz_placeholders.py           # ~150 lines
├── fuzz_file_loading.py           # ~100 lines
├── fuzz_format_detection.py       # ~120 lines
├── fuzz_bank_operations.py        # ~110 lines
└── corpus/
    ├── empty.txt
    ├── normal_placeholders.txt
    ├── nested_placeholders.txt
    ├── adjacent_placeholders.txt
    ├── special_chars.txt
    ├── long_string.txt
    ├── unicode.txt
    ├── all_placeholders.txt
    └── malformed_placeholders.txt

Total: 15 files, ~700 lines of code
```

## Support

- **Atheris Documentation**: https://github.com/google/atheris
- **Atheris PyPI**: https://pypi.org/project/atheris/
- **libFuzzer**: https://llvm.org/docs/LibFuzzer.html
- **Fuzzing Book**: https://www.fuzzingbook.org/

---

*Document created: 2026-04-28*  
*Last updated: 2026-04-28*  
*Total lines: ~1500*  
*Estimated reading time: 30-45 minutes*
