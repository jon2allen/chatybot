import os
import fnmatch
from typing import List, Dict, Any
import re
import datetime
import math
import json

def normalize_path(path: str) -> str:
    """
    Normalize path to handle double-escaped backslashes and literal unicode escapes.

    Architecture & Encoding Note (ensure_ascii / UTF-8):
    1. Modern LLMs emit raw UTF-8 characters when tool output is formatted with ensure_ascii=False.
    2. However, some models or legacy clients may emit literal \\uXXXX strings in JSON payloads.
    3. Normalizing both raw backslashes and unicode escape sequences ensures path resolution
       remains robust across all locales without breaking Windows path structures.
    """
    if not path or not isinstance(path, str):
        return path

    # Handle standard Windows double-backslash escaping
    path = path.replace('\\\\', '\\')

    # If the path contains literal unicode escape sequences (e.g. \u8273 or \\u8273), decode them safely
    if '\\u' in path or r'\u' in path:
        try:
            # Decode unicode-escaped representations while preserving standard path slashes
            path = path.encode('utf-8').decode('unicode-escape')
        except Exception:
            pass

    return path

def list_directory(path: str = ".", details: bool = False) -> List[Any]:
    """List contents of a directory."""
    path = normalize_path(path)
    try:
        if not details:
            return os.listdir(path)
        
        results = []
        with os.scandir(path) as entries:
            for entry in entries:
                try:
                    stat_info = entry.stat()
                    mtime = datetime.datetime.fromtimestamp(stat_info.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                    
                    if entry.is_dir(follow_symlinks=False):
                        entry_type = "directory"
                        size = 0
                    elif entry.is_file(follow_symlinks=False):
                        entry_type = "file"
                        size = stat_info.st_size
                    else:
                        entry_type = "other"
                        size = stat_info.st_size
                        
                    results.append({
                        "name": entry.name,
                        "type": entry_type,
                        "size": size,
                        "modified": mtime
                    })
                except Exception:
                    # Fallback if stat fails for a specific entry
                    results.append({
                        "name": entry.name,
                        "type": "unknown",
                        "size": 0,
                        "modified": "unknown"
                    })
        return results
    except Exception as e:
        return [f"Error listing directory: {e}"]

def read_file(path: str, start_line: int = None, end_line: int = None) -> str:
    """Read contents of a file with optional line range filtering."""
    path = normalize_path(path)
    if os.name != 'nt':
        if path and not os.path.isabs(path) and '/' not in path and '\\' not in path:
            path = f"./{path}"
    try:
        if os.path.exists(path):
            with open(path, 'rb') as f:
                chunk = f.read(8192)
                if b'\x00' in chunk:
                    return "Error reading file: Binary file format is not supported."
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            
            # Apply line range filtering if specified
            if start_line is not None or end_line is not None:
                start = 1 if start_line is None else max(1, int(start_line))
                end = len(lines) if end_line is None else min(len(lines), int(end_line))
                lines = lines[start-1:end]
            
            numbered_lines = []
            for i, line in enumerate(lines, 1):
                stripped_line = line.rstrip('\r\n')
                numbered_lines.append(f"{i}: {stripped_line}\n")
            return ''.join(numbered_lines)
    except Exception as e:
        return f"Error reading file: {e}"

SOFT_WARNING_BYTES = 30 * 1024  # 30 KB (~7,500 tokens)
HARD_TRUNCATE_BYTES = 50 * 1024  # 50 KB (~12,500 tokens)


def enforce_string_payload_limits(text: str, tool_name: str) -> str:
    """
    Enforces soft warning and hard truncation on string tool outputs.
    Preserves head and tail on hard truncation so critical error/tail info is preserved.
    """
    if not isinstance(text, str):
        return text

    encoded = text.encode("utf-8")
    byte_count = len(encoded)

    if byte_count <= SOFT_WARNING_BYTES:
        return text

    size_kb = byte_count / 1024
    est_tokens = max(1, math.ceil(byte_count / 4))

    # Hard Truncation (> 50 KB)
    if byte_count > HARD_TRUNCATE_BYTES:
        lines = text.splitlines(keepends=True)
        # Keep first 200 lines and last 60 lines
        if len(lines) > 260:
            head = "".join(lines[:200])
            tail = "".join(lines[-60:])
            omitted_count = len(lines) - 260
            warning_banner = (
                f"\n\n[WARNING: Tool '{tool_name}' output exceeded hard limit "
                f"({size_kb:.1f} KB, ~{est_tokens} tokens). "
                f"{omitted_count} middle lines truncated to conserve context budget.]\n\n"
            )
            return head + warning_banner + tail
        else:
            # Fallback byte slice if line count is small but lines are very wide
            head_bytes = encoded[: 35 * 1024].decode("utf-8", errors="ignore")
            tail_bytes = encoded[-15 * 1024 :].decode("utf-8", errors="ignore")
            warning_banner = (
                f"\n\n[WARNING: Tool '{tool_name}' output exceeded hard limit "
                f"({size_kb:.1f} KB, ~{est_tokens} tokens). "
                f"Middle content truncated to conserve context budget.]\n\n"
            )
            return head_bytes + warning_banner + tail_bytes

    # Soft Warning (30 KB - 50 KB)
    warning_notice = (
        f"\n[NOTE: Tool '{tool_name}' output is large: {size_kb:.1f} KB, "
        f"~{est_tokens} estimated tokens. Consider narrowing search/command scope.]"
    )
    return text + warning_notice


def enforce_list_payload_limits(results: List[Any], tool_name: str, max_items: int = 100) -> List[Any]:
    """
    Enforces soft warning and hard truncation on list/structured tool outputs.
    """
    if not isinstance(results, list):
        return results

    raw_json = json.dumps(results, default=str)
    byte_count = len(raw_json.encode("utf-8"))

    if byte_count <= SOFT_WARNING_BYTES and len(results) <= max_items:
        return results

    size_kb = byte_count / 1024
    est_tokens = max(1, math.ceil(byte_count / 4))

    # Hard Truncation (> 50 KB or > max_items)
    if byte_count > HARD_TRUNCATE_BYTES or len(results) > max_items:
        truncated_list = results[:max_items]
        omitted = len(results) - max_items
        truncation_note = {
            "warning": (
                f"Tool '{tool_name}' output exceeded limit ({size_kb:.1f} KB, ~{est_tokens} tokens). "
                f"Showing first {max_items} matches; {max(0, omitted)} additional results omitted. "
                "Please refine path or pattern to narrow results."
            ),
            "omitted_count": max(0, omitted),
        }
        truncated_list.append(truncation_note)
        return truncated_list

    # Soft Warning (30 KB - 50 KB)
    soft_warning_note = {
        "note": (
            f"Tool '{tool_name}' output is large: {size_kb:.1f} KB, ~{est_tokens} estimated tokens across {len(results)} items."
        )
    }
    results.append(soft_warning_note)
    return results


def find_files(path: str = ".", pattern: str = "*", search_term: str = None, details: bool = False) -> List[Any]:
    """Find files and directories matching pattern, optionally containing search_term and metadata."""
    path = normalize_path(path)
    results = []
    try:
        for root, dirs, files in os.walk(path):
            # Check matching directories (only if search_term is not specified)
            if not search_term:
                for d in dirs:
                    if fnmatch.fnmatch(d, pattern):
                        full_path = os.path.join(root, d)
                        if not details:
                            results.append(full_path)
                        else:
                            try:
                                stat_info = os.stat(full_path)
                                mtime = datetime.datetime.fromtimestamp(stat_info.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                                results.append({
                                    "name": d,
                                    "path": full_path,
                                    "type": "directory",
                                    "size": stat_info.st_size,
                                    "modified": mtime
                                })
                            except Exception:
                                results.append({
                                    "name": d,
                                    "path": full_path,
                                    "type": "unknown_dir",
                                    "size": 0,
                                    "modified": "unknown"
                                })
            
            # Check matching files
            for file in files:
                if fnmatch.fnmatch(file, pattern):
                    full_path = os.path.join(root, file)
                    if search_term:
                        try:
                            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                                if search_term not in f.read():
                                    continue
                        except Exception:
                            continue
                    
                    if not details:
                        results.append(full_path)
                    else:
                        try:
                            stat_info = os.stat(full_path)
                            mtime = datetime.datetime.fromtimestamp(stat_info.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                            results.append({
                                "name": file,
                                "path": full_path,
                                "type": "file",
                                "size": stat_info.st_size,
                                "modified": mtime
                            })
                        except Exception:
                            results.append({
                                "name": file,
                                "path": full_path,
                                "type": "unknown",
                                "size": 0,
                                "modified": "unknown"
                            })
    except Exception as e:
        return [f"Error finding files: {e}"]
    return enforce_list_payload_limits(results, "find_files", max_items=100)

def run_command(command: str, shell: bool = True) -> str:
    """Execute a safe shell command and return its output."""
    import subprocess
    import shlex
    import re
    try:
        # Prevent critical privilege escalations or system modifications
        DANGEROUS_PATTERNS = [
            (r'rm\s+-r\b', "Recursive delete"),
            (r'rm\s+-rf\b', "Recursive force delete"),
            (r'>\s*(/dev/|/etc/|/usr/|/bin/|/sbin/|/lib/|/boot/|/var/|/opt/)', "Write to critical system directory"),
            (r'chmod\s+-R\b', "Recursive chmod"),
            (r'chown\s+-R\b', "Recursive chown"),
            (r'mkfs\b', "Filesystem creation"),
            (r'dd\s+if=\s*', "dd command"),
            (r'sudo\b', "Privilege escalation"),
        ]
        for pattern, desc in DANGEROUS_PATTERNS:
            if re.search(pattern, command):
                return f"Blocked: Dangerous command pattern detected ({desc})"

        if shell:
            result = subprocess.run(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30
            )
        else:
            result = subprocess.run(
                shlex.split(command),
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30
            )
        if result.returncode != 0:
            out = f"Command exited with code {result.returncode}\nStderr: {result.stderr}\nStdout: {result.stdout}"
            return enforce_string_payload_limits(out, "run_command")
        return enforce_string_payload_limits(result.stdout, "run_command")
    except Exception as e:
        return f"Error executing command: {e}"

def write_file(path: str, content: str, append: bool = False) -> str:
    """Write or append contents to a file."""
    path = normalize_path(path)
    try:
        dir_name = os.path.dirname(path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        mode = 'a' if append else 'w'
        with open(path, mode, encoding='utf-8') as f:
            f.write(content)
        action = "Appended to" if append else "Wrote to"
        return f"Success: {action} file '{path}'"
    except Exception as e:
        return f"Error writing file: {e}"

def change_dir(path: str) -> str:
    """Change the current working directory."""
    path = normalize_path(path)
    try:
        os.chdir(path)
        return f"Success: Changed working directory to '{os.getcwd()}'"
    except Exception as e:
        return f"Error changing directory: {e}"

def grep_search(
    query: str,
    path: str = ".",
    pattern: str = "*",
    case_insensitive: bool = False,
    is_regex: bool = False,
    max_matches: int = 100,
    max_line_length: int = 1000
) -> List[Dict[str, Any]]:
    """
    Search for a literal string or regular expression in files.
    Returns a list of matches containing the filename, line number, and line content.
    """
    path = normalize_path(path)
    results = []
    flags = re.IGNORECASE if case_insensitive else 0

    try:
        if is_regex:
            regex = re.compile(query, flags)
        else:
            regex = re.compile(re.escape(query), flags)
    except Exception as e:
        return [{"error": f"Invalid regular expression: {e}"}]

    def search_file(file_path: str) -> bool:
        try:
            with open(file_path, 'rb') as f:
                if b'\x00' in f.read(8192):
                    return False
        except Exception:
            return False

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    if regex.search(line):
                        content = line.rstrip('\r\n')
                        if len(content) > max_line_length:
                            content = content[:max_line_length] + " [TRUNCATED]"
                        results.append({
                            "file": file_path,
                            "line_number": line_num,
                            "content": content
                        })
                        if len(results) >= max_matches:
                            return True
        except Exception:
            pass
        return False

    if os.path.isfile(path):
        search_file(path)
        return enforce_list_payload_limits(results, "grep_search", max_items=max_matches)

    try:
        for root, dirs, files in os.walk(path):
            # Prune unwanted/hidden system and dependency folders
            dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__', 'node_modules', '.venv', 'build', 'dist', '.eggs')]
            
            for file in files:
                if not fnmatch.fnmatch(file, pattern):
                    continue
                
                full_path = os.path.join(root, file)
                if search_file(full_path):
                    return enforce_list_payload_limits(results, "grep_search", max_items=max_matches)
    except Exception as e:
        return [{"error": f"Error during search: {e}"}]

    return enforce_list_payload_limits(results, "grep_search", max_items=max_matches)

def replace_file_content(path: str, target: str, replacement: str) -> str:
    """Replace target content with replacement content in the file at path."""
    path = normalize_path(path)
    try:
        if not os.path.exists(path):
            return f"Error: File '{path}' does not exist."
        
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        if target not in content:
            return f"Error: Target content not found in file '{path}'."
        
        occurrences = content.count(target)
        new_content = content.replace(target, replacement)
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        return f"Success: Replaced {occurrences} occurrence(s) of target in '{path}'"
    except Exception as e:
        return f"Error replacing file content: {e}"


