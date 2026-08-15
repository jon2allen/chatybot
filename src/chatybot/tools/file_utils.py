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

def read_file(path: str, start_line: int = None, end_line: int = None) -> str:
    """Read contents of a file with optional line range filtering."""
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

def find_files(path: str = ".", pattern: str = "*", search_term: str = None, details: bool = False) -> List[Any]:
    """Find files and directories matching pattern, optionally containing search_term and metadata."""
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
    max_matches: int = 100,
    max_line_length: int = 1000
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
        return results

    try:
        for root, dirs, files in os.walk(path):
            # Prune unwanted/hidden system and dependency folders
            dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__', 'node_modules', '.venv', 'build', 'dist', '.eggs')]
            
            for file in files:
                if not fnmatch.fnmatch(file, pattern):
                    continue
                
                full_path = os.path.join(root, file)
                if search_file(full_path):
                    return results
    except Exception as e:
        return [{"error": f"Error during search: {e}"}]

    return results

def replace_file_content(path: str, target: str, replacement: str) -> str:
    """Replace target content with replacement content in the file at path."""
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


