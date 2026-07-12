import os
import fnmatch
from typing import List, Dict, Any
import re
import datetime

def list_directory(path: str = ".", details: bool = False) -> List[Any]:
    """List contents of a directory."""
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

def read_file(path: str) -> str:
    """Read contents of a file with line numbers."""
    try:
        if os.path.exists(path):
            with open(path, 'rb') as f:
                chunk = f.read(8192)
                if b'\x00' in chunk:
                    return "Error reading file: Binary file format is not supported."
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            numbered_lines = []
            for i, line in enumerate(lines, 1):
                numbered_lines.append(f"{i}: {line.rstrip('\r\n')}\n")
            return ''.join(numbered_lines)
    except Exception as e:
        return f"Error reading file: {e}"

def find_files(path: str = ".", pattern: str = "*", search_term: str = None, details: bool = False) -> List[Any]:
    """Find files matching pattern, optionally containing search_term and metadata."""
    results = []
    try:
        for root, dirs, files in os.walk(path):
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
    return results

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
            return f"Command exited with code {result.returncode}\nStderr: {result.stderr}\nStdout: {result.stdout}"
        return result.stdout
    except Exception as e:
        return f"Error executing command: {e}"

def write_file(path: str, content: str, append: bool = False) -> str:
    """Write or append contents to a file."""
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
    max_matches: int = 100
) -> List[Dict[str, Any]]:
    """
    Search for a literal string or regular expression in files.
    Returns a list of matches containing the filename, line number, and line content.
    """
    results = []
    flags = re.IGNORECASE if case_insensitive else 0

    try:
        if is_regex:
            regex = re.compile(query, flags)
        else:
            regex = re.compile(re.escape(query), flags)
    except Exception as e:
        return [{"error": f"Invalid regular expression: {e}"}]

    try:
        for root, _, files in os.walk(path):
            for file in files:
                if not fnmatch.fnmatch(file, pattern):
                    continue
                
                full_path = os.path.join(root, file)
                
                try:
                    with open(full_path, 'rb') as f:
                        if b'\x00' in f.read(8192):
                            continue
                except Exception:
                    continue

                try:
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        for line_num, line in enumerate(f, 1):
                            if regex.search(line):
                                results.append({
                                    "file": full_path,
                                    "line_number": line_num,
                                    "content": line.rstrip('\r\n')
                                })
                                
                                if len(results) >= max_matches:
                                    return results
                except Exception:
                    continue
    except Exception as e:
        return [{"error": f"Error during search: {e}"}]

    return results


