import os
import fnmatch
from typing import List, Dict, Any

def list_directory(path: str = ".") -> List[str]:
    """List contents of a directory."""
    try:
        return os.listdir(path)
    except Exception as e:
        return [f"Error listing directory: {e}"]

def read_file(path: str) -> str:
    """Read contents of a file."""
    try:
        if os.path.exists(path):
            with open(path, 'rb') as f:
                chunk = f.read(8192)
                if b'\x00' in chunk:
                    return "Error reading file: Binary file format is not supported."
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"

def find_files(path: str = ".", pattern: str = "*", search_term: str = None) -> List[str]:
    """Find files matching pattern, optionally containing search_term."""
    results = []
    try:
        for root, dirs, files in os.walk(path):
            for file in files:
                if fnmatch.fnmatch(file, pattern):
                    full_path = os.path.join(root, file)
                    if search_term:
                        try:
                            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                                if search_term in f.read():
                                    results.append(full_path)
                        except Exception:
                            pass
                    else:
                        results.append(full_path)
    except Exception as e:
        return [f"Error finding files: {e}"]
    return results

def run_command(command: str) -> str:
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

