
from __future__ import annotations

import os
import subprocess
import threading
from pathlib import Path
from typing import Dict, List, Tuple, Optional


class GitBackend:
    """
    Handles all git command execution and parsing for status/diffs/branch info.
    """

    def __init__(self, repo_path: Optional[str] = None) -> None:
        """Initializes the GitBackend, setting the repository path."""
        self.repo_path = repo_path or os.getcwd()
        self.current_branch: Optional[str] = None
        self.ahead_behind: Tuple[int, int] = (0, 0)
        self.lock = threading.Lock()

    def _run(
        self,
        args: List[str],
        capture_output: bool = True,
        timeout: int = 60,
        check: bool = False,
    ) -> subprocess.CompletedProcess:
        cmd = ["git"] + args
        
        kwargs = {
            'cwd': self.repo_path,
            'timeout': timeout,
            'check': check,
        }
        
        if capture_output:
            kwargs.update({
                'capture_output': True,
                'text': True,
                'encoding': 'utf-8',
                'errors': 'replace',
            })
        
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            kwargs['startupinfo'] = startupinfo
            
            if hasattr(subprocess, 'CREATE_NO_WINDOW'):
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
        
        return subprocess.run(cmd, **kwargs)

    def execute_command(
        self, *args: str, capture_output: bool = True
    ) -> Tuple[int, str, str]:
        """
        Execute a git command and return (code, stdout, stderr).
        """
        try:
            with self.lock:
                result = self._run(list(args), capture_output=capture_output)
            stdout = result.stdout if hasattr(result, "stdout") and result.stdout else ""
            stderr = result.stderr if hasattr(result, "stderr") and result.stderr else ""
            return result.returncode, stdout, stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out"
        except Exception as e:
            return -1, "", str(e)

    def is_git_repo(self) -> bool:
        """
        Check if current directory is a git repository.
        """
        code, _, _ = self.execute_command("rev-parse", "--git-dir")
        return code == 0


    def _parse_status_porcelain_z(
        self, data: str
    ) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]], List[str]]:
        """
        Parse output of: git status --porcelain=v1 -z

        Returns:
            modified: list of (path, y_status)
            staged: list of (path, x_status)
            untracked: list of paths
        Notes:
            - Records are NUL-separated.
            - Renames/Copies provide two paths; we display the second when present.
        """
        records = data.split("\0")
        if records and records[-1] == "":
            records.pop()

        modified: List[Tuple[str, str]] = []
        staged: List[Tuple[str, str]] = []
        untracked: List[str] = []

        i = 0
        while i < len(records):
            entry = records[i]
            i += 1
            if not entry or len(entry) < 3:
                continue

            x = entry[0]
            y = entry[1]

            path1 = entry[3:] if len(entry) >= 3 else ""
            path2: Optional[str] = None

            if x in ("R", "C"):
                if i < len(records):
                    path2 = records[i]
                    i += 1

            display_path = path2 or path1

            if x == "?" and y == "?":
                untracked.append(display_path)
                continue

            if x != " " and x != "?":
                staged.append((display_path, x))
            if y != " " and y != "?":
                modified.append((display_path, y))

        return modified, staged, untracked

    def get_status(
        self,
    ) -> Tuple[
        Dict[str, str], Dict[str, str], List[str]
    ]:
        """
        Robust status using NUL-delimited porcelain for correct path parsing.
        Returns:
            - modified_map: {filepath: y_status}
            - staged_map: {filepath: x_status}
            - untracked_list: [filepath, ...]
        """
        code, stdout, _ = self.execute_command("status", "--porcelain=v1", "-z")
        if code != 0 or not stdout:
            return {}, {}, []
        modified, staged, untracked = self._parse_status_porcelain_z(stdout)
        return (
            {p: s for p, s in modified},
            {p: s for p, s in staged},
            list(untracked),
        )


    def _is_binary_by_numstat(self, filepath: str, staged: bool) -> Tuple[bool, int, str]:
        args = ["diff", "--numstat"]
        if staged:
            args.append("--cached")
        args.extend(["--", filepath])
        code, stdout, stderr = self.execute_command(*args)
        if code == 0 and stdout.strip().startswith("-"):
            return True, code, stderr
        return False, code, stderr

    def get_untracked_file_diff(self, filepath: str) -> str:
        """
        Generate a pseudo-diff for an untracked file showing all content as added.
        """
        fullpath = os.path.join(self.repo_path, filepath)
        if not os.path.exists(fullpath):
            return f"File not found: {filepath}"

        try:
            with open(fullpath, "rb") as f:
                chunk = f.read(8192)
                if b"\x00" in chunk:
                    return f"Binary file (new): {filepath}\nBinary files cannot be displayed as text diffs"
        except Exception as e:
            return f"Error reading file: {e}"

        try:
            with open(fullpath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            return f"Error reading file: {e}"

        lines = content.splitlines()
        diff_output: List[str] = []
        diff_output.append(f"diff --git a/{filepath} b/{filepath}")
        diff_output.append(f"new file mode 100644")
        diff_output.append(f"--- /dev/null")
        diff_output.append(f"+++ b/{filepath}")
        diff_output.append(f"@@ -0,0 +1,{len(lines)} @@")
        for line in lines:
            diff_output.append(f"+{line}")
        return "\n".join(diff_output)

    def get_diff(self, filepath: str, staged: bool = False, is_untracked: bool = False) -> str:
        """
        Returns diff output for a file, handling binary and untracked gracefully.
        """
        if is_untracked:
            return self.get_untracked_file_diff(filepath)

        is_bin, _, _ = self._is_binary_by_numstat(filepath, staged=staged)
        if is_bin:
            return f"Binary file: {filepath}\nBinary files cannot be displayed as text diffs"

        args = ["diff"]
        if staged:
            args.append("--cached")
        args.extend(["--", filepath])
        code, stdout, stderr = self.execute_command(*args)
        if code != 0:
            return f"Error getting diff: {stderr}"
        return stdout if stdout else "No changes"


    def stage_files(self, filepaths: List[str]) -> Tuple[int, str, str]:
        """Stages a list of files."""
        if not filepaths:
            return 0, "", ""
        args = ["add", "--"] + list(filepaths)
        return self.execute_command(*args)

    def unstage_files(self, filepaths: List[str]) -> Tuple[int, str, str]:
        """Unstages a list of files."""
        if not filepaths:
            return 0, "", ""
        args = ["restore", "--staged", "--"] + list(filepaths)
        return self.execute_command(*args)

    def commit(self, message: str, amend: bool = False) -> Tuple[int, str, str]:
        """Commits staged changes with a given message."""
        args = ["commit", "-m", message]
        if amend:
            args.insert(1, "--amend")
        return self.execute_command(*args)

    def pull(self, rebase: bool = False) -> Tuple[int, str, str]:
        """Pulls changes from the remote, optionally with rebase."""
        args = ["pull"]
        if rebase:
            args.append("--rebase")
        return self.execute_command(*args)

    def push(self, force: bool = False) -> Tuple[int, str, str]:
        """Pushes committed changes to the remote."""
        args = ["push"]
        if force:
            args.append("--force")
        return self.execute_command(*args)

    def get_branch_info(self) -> Tuple[Optional[str], int, int]:
        """Gets the current branch name and its ahead/behind status."""
        code, stdout, _ = self.execute_command("rev-parse", "--abbrev-ref", "HEAD")
        if code != 0:
            return None, 0, 0
        branch = stdout.strip()

        code2, stdout2, _ = self.execute_command(
            "rev-list", "--left-right", "--count", f"{branch}...@{{u}}"
        )
        ahead, behind = 0, 0
        if code2 == 0 and stdout2.strip():
            parts = stdout2.strip().split()
            if len(parts) == 2:
                ahead, behind = int(parts[0]), int(parts[1])
        return branch, ahead, behind