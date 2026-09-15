import datetime
import fnmatch
import json
import math
import os
import re
from typing import Any


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

def list_directory(path: str = ".", details: bool = False) -> list[Any]:
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
            
            start = 1
            # Apply line range filtering if specified
            if start_line is not None or end_line is not None:
                start = 1 if start_line is None else max(1, int(start_line))
                end = len(lines) if end_line is None else min(len(lines), int(end_line))
                lines = lines[start-1:end]
            
            numbered_lines = []
            for i, line in enumerate(lines, start=start):
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


def enforce_list_payload_limits(results: list[Any], tool_name: str, max_items: int = 100) -> list[Any]:
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


def find_files(path: str = ".", pattern: str = "*", search_term: str = None, details: bool = False) -> list[Any]:
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
    import re
    import shlex
    import subprocess
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

def _get_relative_backup_target(file_path: str) -> str:
    """
    Convert an absolute or relative file path into a relative target path
    safe for directory mirroring on all platforms.
    On Windows (or Windows paths), converts drive specifications like 'C:\\' into 'C\\'.
    """
    # Check for Windows drive letter prefix (e.g. C:\ or C:/) before abspath on POSIX
    m = re.match(r"^([a-zA-Z]):[\\/](.*)", file_path)
    if m:
        drive_letter, rest = m.groups()
        clean_rest = rest.lstrip("\\/").replace("\\", os.path.sep).replace("/", os.path.sep)
        return os.path.join(drive_letter.upper(), clean_rest)

    abs_target = os.path.abspath(file_path)
    drive, rest = os.path.splitdrive(abs_target)
    if drive:
        clean_drive = drive.rstrip(":")
        clean_rest = rest.lstrip(os.path.sep)
        return os.path.join(clean_drive, clean_rest) if clean_drive else clean_rest
    return abs_target.lstrip(os.path.sep)

def _resolve_backup_context(app: Any = None) -> tuple[bool, bool, str, str | None]:
    """
    Resolve backup settings and session directory context.
    Returns:
        (backup_enabled, enable_chat_history, session_dir, active_session_id)
    """
    backup_enabled = True
    enable_chat_history = True
    session_dir = os.path.expanduser("~/.local/share/chatybot/sessions")
    active_session_id = None

    if app is not None:
        backup_enabled = getattr(app, "backup_file_on_write", True)
        enable_chat_history = getattr(app, "enable_chat_history", True)
        session_dir = getattr(app, "session_dir", session_dir)
        active_session_id = getattr(app, "active_session_id", None)
        if enable_chat_history and not active_session_id:
            if hasattr(app, "_ensure_active_session"):
                try:
                    app._ensure_active_session()
                    active_session_id = getattr(app, "active_session_id", None)
                except Exception:
                    pass
    else:
        # Check environment variables passed by parent process (chatybot_app)
        if "CHATYBOT_ENABLE_CHAT_HISTORY" in os.environ:
            enable_chat_history = os.environ.get("CHATYBOT_ENABLE_CHAT_HISTORY", "1") != "0"
        if "CHATYBOT_BACKUP_ON_WRITE" in os.environ:
            backup_enabled = os.environ.get("CHATYBOT_BACKUP_ON_WRITE", "1") != "0"
        if os.environ.get("CHATYBOT_SESSION_DIR"):
            session_dir = os.environ["CHATYBOT_SESSION_DIR"]
        if os.environ.get("CHATYBOT_ACTIVE_SESSION_ID"):
            active_session_id = os.environ["CHATYBOT_ACTIVE_SESSION_ID"]

        # Fallback check directly in tools_config.toml if not passed via env
        try:
            import tomllib
            cfg_path = os.path.expanduser("~/.config/chatybot/tools_config.toml")
            if not os.path.exists(cfg_path):
                cfg_path = os.path.join(os.path.dirname(__file__), "..", "tools_config.toml")
            if os.path.exists(cfg_path):
                with open(cfg_path, "rb") as f:
                    cfg = tomllib.load(f)
                cfg_sec = cfg.get("config", {})
                if "backup_file_on_write" in cfg_sec and "CHATYBOT_BACKUP_ON_WRITE" not in os.environ:
                    backup_enabled = cfg_sec.get("backup_file_on_write", True)
                if "session_dir" in cfg_sec and not os.environ.get("CHATYBOT_SESSION_DIR"):
                    session_dir = os.path.expanduser(str(cfg_sec.get("session_dir")))
        except Exception:
            pass

    return backup_enabled, enable_chat_history, session_dir, active_session_id

def create_file_backup(file_path: str, app: Any = None) -> str | None:
    """
    Create a backup of file_path inside the active session's backup directory:
    ~/.local/share/chatybot/sessions/<session_id>/backups/<relative_path>
    Backups are placed in the session directory even when unnamed.
    Only falls back to the global backup path (~/.local/share/chatybot/backups/<relative_path>)
    if chat history collection is turned off (/session history off).
    Returns the backup path if created, or None if skipped/failed.
    """
    try:
        backup_enabled, enable_chat_history, session_dir, active_session_id = _resolve_backup_context(app)

        if not backup_enabled or not os.path.exists(file_path) or not os.path.isfile(file_path):
            return None

        abs_target = os.path.abspath(file_path)
        rel_target = _get_relative_backup_target(file_path)

        # Behavior rule:
        # If /session history off is enabled (enable_chat_history is False), use global backups.
        # Otherwise, place backup inside session dir (even when unnamed).
        if not enable_chat_history:
            backup_base = os.path.join(os.path.dirname(session_dir), "backups")
        else:
            if not active_session_id:
                # If session_id not yet created in an unnamed session, generate a deterministic/timestamped session id
                from datetime import datetime
                active_session_id = f"default_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            backup_base = os.path.join(session_dir, active_session_id, "backups")

        backup_file_path = os.path.join(backup_base, rel_target)
        # Ensure only a single initial copy backup is kept per file
        if os.path.exists(backup_file_path):
            return backup_file_path

        os.makedirs(os.path.dirname(backup_file_path), exist_ok=True)

        import shutil
        shutil.copy2(abs_target, backup_file_path)
        return backup_file_path
    except Exception:
        return None


def write_file(path: str, content: str, append: bool = False, app: Any = None) -> str:
    """Write or append contents to a file, preserving a backup in session data before modification."""
    path = normalize_path(path)
    try:
        backup_path = None
        if os.path.exists(path):
            backup_path = create_file_backup(path, app=app)

        dir_name = os.path.dirname(path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        mode = 'a' if append else 'w'
        with open(path, mode, encoding='utf-8') as f:
            f.write(content)
        action = "Appended to" if append else "Wrote to"
        msg = f"Success: {action} file '{path}'"
        if backup_path:
            msg += f" (pre-edit backup saved: '{backup_path}')"
        return msg
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
) -> list[dict[str, Any]]:
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

def save_file_diff(file_path: str, original_content: str, modified_content: str, app: Any = None) -> str | None:
    """
    Generate and save a re-applicable unified diff patch for file modifications.
    Stored inside the active session's diff directory:
    ~/.local/share/chatybot/sessions/<session_id>/diffs/<relative_path>.<timestamp>.patch
    If chat history is off, saved under ~/.local/share/chatybot/diffs/<relative_path>.<timestamp>.patch.
    Returns the patch file path if saved, or None on failure/skip.
    """
    import difflib
    from datetime import datetime

    try:
        backup_enabled, enable_chat_history, session_dir, active_session_id = _resolve_backup_context(app)

        if not backup_enabled:
            return None

        rel_target = _get_relative_backup_target(file_path)

        if not enable_chat_history:
            diff_base = os.path.join(os.path.dirname(session_dir), "diffs")
        else:
            if not active_session_id:
                active_session_id = f"default_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            diff_base = os.path.join(session_dir, active_session_id, "diffs")

        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        patch_file_path = os.path.join(diff_base, f"{rel_target}.{timestamp_str}.patch")
        os.makedirs(os.path.dirname(patch_file_path), exist_ok=True)

        orig_lines = original_content.splitlines(keepends=True)
        mod_lines = modified_content.splitlines(keepends=True)
        diff_lines = list(difflib.unified_diff(
            orig_lines,
            mod_lines,
            fromfile=f"a/{rel_target}",
            tofile=f"b/{rel_target}",
            lineterm="\n"
        ))

        if not diff_lines:
            return None

        with open(patch_file_path, "w", encoding="utf-8") as pf:
            pf.writelines(diff_lines)

        return patch_file_path
    except Exception:
        return None


def diagnose_target_mismatch(content: str, target: str, search_start_line: int = 1) -> str:
    """
    Diagnose why a target string was not found in content, checking for indentation,
    whitespace differences, or surrounding line context mismatches.
    """
    target_lines = target.splitlines()
    if not target_lines:
        return ""

    file_lines = content.splitlines()
    target_stripped = [l.strip() for l in target_lines if l.strip()]
    if not target_stripped:
        return ""

    first_target_stripped = target_stripped[0]

    # 1. Search for matching sequence of stripped lines (accounting for intermediate blank lines)
    matches = []
    for idx, f_line in enumerate(file_lines):
        if f_line.strip() == first_target_stripped:
            f_idx = idx
            t_idx = 0
            all_matched = True
            matched_file_lines = []
            while t_idx < len(target_stripped) and f_idx < len(file_lines):
                if not file_lines[f_idx].strip():
                    f_idx += 1
                    continue
                if file_lines[f_idx].strip() == target_stripped[t_idx]:
                    matched_file_lines.append((search_start_line + f_idx, file_lines[f_idx]))
                    f_idx += 1
                    t_idx += 1
                else:
                    all_matched = False
                    break
            if all_matched and t_idx == len(target_stripped):
                matches.append((search_start_line + idx, matched_file_lines))

    if matches:
        line_num, matched_lines = matches[0]
        actual_first_line = matched_lines[0][1]
        target_first_line = [l for l in target_lines if l.strip()][0]
        target_spaces = len(target_first_line) - len(target_first_line.lstrip(" "))
        actual_spaces = len(actual_first_line) - len(actual_first_line.lstrip(" "))

        hint = (
            f"\nDiagnosis: Target text matches line {line_num} but failed due to an indentation/whitespace discrepancy.\n"
            f"  Target (line 1): {target_spaces} leading spaces: {target_first_line!r}\n"
            f"  File   (line {line_num}): {actual_spaces} leading spaces: {actual_first_line!r}"
        )
        return hint

    # 2. Check if the first line exists in the file with different surrounding context
    single_line_matches = [
        search_start_line + idx for idx, l in enumerate(file_lines) if l.strip() == first_target_stripped
    ]
    if single_line_matches:
        lines_str = ", ".join(str(ln) for ln in single_line_matches[:5])
        return (
            f"\nDiagnosis: First line {first_target_stripped!r} exists at line(s) [{lines_str}], "
            f"but surrounding lines or block indentation did not match."
        )

    return ""


def replace_file_content(
    path: str,
    target: str,
    replacement: str,
    start_line: int = None,
    end_line: int = None,
    app: Any = None,
) -> str:
    """
    Replace target content with replacement content in the file at path, saving a re-applicable diff patch.
    Optionally restrict search and replacement to lines between start_line and end_line (1-indexed).
    """
    path = normalize_path(path)
    try:
        if not os.path.exists(path):
            return f"Error: File '{path}' does not exist."

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        file_lines = content.splitlines(keepends=True)
        total_lines = len(file_lines)

        # Handle line-bounded replacement if start_line or end_line is specified
        if start_line is not None or end_line is not None:
            start_idx = 0 if start_line is None else max(0, int(start_line) - 1)
            end_idx = total_lines if end_line is None else min(total_lines, int(end_line))

            bounded_segment = "".join(file_lines[start_idx:end_idx])
            if target not in bounded_segment:
                diag = diagnose_target_mismatch(bounded_segment, target, search_start_line=start_idx + 1)
                return (
                    f"Error: Target content not found in file '{path}' within lines {start_idx + 1}-{end_idx}."
                    f"{diag}"
                )

            occurrences = bounded_segment.count(target)
            new_bounded_segment = bounded_segment.replace(target, replacement)
            new_content = "".join(file_lines[:start_idx]) + new_bounded_segment + "".join(file_lines[end_idx:])
        else:
            if target not in content:
                diag = diagnose_target_mismatch(content, target, search_start_line=1)
                return f"Error: Target content not found in file '{path}'.{diag}"

            occurrences = content.count(target)
            new_content = content.replace(target, replacement)

        diff_path = save_file_diff(path, content, new_content, app=app)

        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)

        msg = f"Success: Replaced {occurrences} occurrence(s) of target in '{path}'"
        if start_line is not None or end_line is not None:
            msg += f" (within lines {start_idx + 1}-{end_idx})"
        if diff_path:
            msg += f" (diff patch saved: '{diff_path}')"
        return msg
    except Exception as e:
        return f"Error replacing file content: {e}"


