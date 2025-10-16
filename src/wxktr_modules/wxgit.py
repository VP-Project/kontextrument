from __future__ import annotations

import os
import time
from typing import Dict, List, Optional, Tuple

import wx
import wx.stc as stc
from pubsub import pub

from .module_ui.git_panel_view import GitPanelView

try:
    from .modules_parts.git_backend import GitBackend
except Exception:
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from modules_parts.git_backend import GitBackend


class GitPanel(wx.Panel):
    """A wx.Panel providing a graphical interface for common Git operations."""

    def __init__(self, parent):
        """Initializes the Git panel Presenter."""
        super().__init__(parent)

        self.git = GitBackend()
        self.selected_file: Optional[str] = None

        self.refresh_timer: Optional[wx.Timer] = None
        self.fs_watcher_enabled: bool = True
        self.refresh_pending: bool = False
        self.last_fs_event: float = 0.0
        self.fs_min_interval: float = 2.0

        self.unstaged_status_map: Dict[str, str] = {}

        self.is_git_repo = self.git.is_git_repo()
        
        self.view = GitPanelView(self)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.view, 1, wx.EXPAND)
        self.SetSizer(sizer)

        self._bind_events()

        if self.is_git_repo:
            self.refresh_status()
            wx.CallAfter(self._init_fs_watcher)
        else:
            self._show_limited_mode_message()

    def _bind_events(self):
        """Binds events from the View's widgets to the Presenter's handlers."""
        self.view.unstaged_tree.Bind(wx.EVT_TREE_SEL_CHANGED, self._on_unstaged_select)
        self.view.staged_tree.Bind(wx.EVT_TREE_SEL_CHANGED, self._on_staged_select)
        self.view.stage_button.Bind(wx.EVT_BUTTON, self._on_stage_files)
        self.view.unstage_button.Bind(wx.EVT_BUTTON, self._on_unstage_files)
        self.view.discard_button.Bind(wx.EVT_BUTTON, self._on_discard_changes)

        self.view.refresh_button.Bind(wx.EVT_BUTTON, self._on_refresh)
        self.view.pull_button.Bind(wx.EVT_BUTTON, self._on_pull)
        self.view.pull_rebase_button.Bind(wx.EVT_BUTTON, self._on_pull_rebase)
        self.view.push_button.Bind(wx.EVT_BUTTON, self._on_push)

        self.view.commit_button.Bind(wx.EVT_BUTTON, self._on_commit)
        
        self.view.execute_button.Bind(wx.EVT_BUTTON, self._on_execute_custom)
        self.view.custom_command.Bind(wx.EVT_TEXT_ENTER, self._on_execute_custom)

    def _show_limited_mode_message(self) -> None:
        """Show a message that we're in limited mode (no git repo)."""
        msg = (
            "Not a Git repository.\n\n"
            "You can use the custom command panel below to run git commands:\n"
            "  • git init - to initialize a new repository\n"
            "  • git clone <url> - to clone an existing repository\n\n"
            "Other git features are disabled until the repository is initialized."
        )
        self._log_message(msg, is_info=True)
        
        self.view.refresh_button.Enable(False)
        self.view.pull_button.Enable(False)
        self.view.pull_rebase_button.Enable(False)
        self.view.push_button.Enable(False)
        self.view.stage_button.Enable(False)
        self.view.unstage_button.Enable(False)
        self.view.discard_button.Enable(False)
        self.view.commit_button.Enable(False)
        self.view.commit_message.Enable(False)
        self.view.amend_checkbox.Enable(False)
        self.view.unstaged_tree.Enable(False)
        self.view.staged_tree.Enable(False)
        self.view.diff_viewer.Enable(False)

    def _check_unsaved_changes(self) -> bool:
        """
        Query the WorkspacePanel for unsaved changes before performing a destructive operation.
        
        Returns:
            True if the operation should proceed, False if it should be cancelled.
        """
        query_data = {'has_unsaved': False, 'files': []}
        
        pub.sendMessage('query.state.unsaved_changes', query_data=query_data)
        
        if query_data['has_unsaved']:
            files_list = "\n".join(f"  • {f}" for f in query_data['files'])
            message = (
                f"The following files have unsaved changes:\n\n{files_list}\n\n"
                "These changes may be overwritten by this Git operation.\n\n"
                "Do you want to continue anyway?"
            )
            
            result = wx.MessageBox(
                message,
                "Unsaved Changes Warning",
                wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
                self
            )
            
            return result == wx.YES
        
        return True

    def _init_fs_watcher(self) -> None:
        """
        Initialize a throttled filesystem watcher.
        On Windows, only watch directories (ReadDirectoryChangesW) and filter paths.
        """
        try:
            self.fs_watcher = wx.FileSystemWatcher()
            self.fs_watcher.SetOwner(self)

            git_dir = os.path.join(self.git.repo_path, ".git")
            if os.path.isdir(git_dir):
                self.fs_watcher.AddTree(git_dir)

            self.Bind(wx.EVT_FSWATCHER, self._on_fs_change)

            self.refresh_timer = wx.Timer(self)
            self.Bind(wx.EVT_TIMER, self._on_refresh_timer, self.refresh_timer)
        except Exception as e:
            self._log_message(f"Could not initialize filesystem watcher: {e}", is_error=True)

    def _is_relevant_git_path(self, fullpath: str) -> bool:
        """
        Filter noisy .git events down to relevant ones.
        """
        p = fullpath.replace("\\", "/").lower()
        if "/.git/" not in p and not p.endswith("/.git"):
            return False

        if p.endswith("/.git/index") or p.endswith("/.git/HEAD") or p.endswith("/.git/packed-refs"):
            return True
        if "/.git/refs/heads/" in p or "/.git/refs/remotes/" in p:
            return True

        if "/.git/objects/" in p or "/.git/lfs/" in p:
            return False

        return False

    def _on_fs_change(self, event: wx.FileSystemWatcherEvent) -> None:
        if not self.fs_watcher_enabled:
            return

        paths: List[str] = []
        try:
            if event.GetPath():
                paths.append(event.GetPath().GetFullPath())
        except Exception:
            pass
        try:
            if event.GetNewPath():
                paths.append(event.GetNewPath().GetFullPath())
        except Exception:
            pass

        if not any(self._is_relevant_git_path(p) for p in paths):
            return

        now = time.monotonic()
        if (now - self.last_fs_event) < self.fs_min_interval:
            return

        self.last_fs_event = now
        if not self.refresh_pending:
            self.refresh_pending = True
            assert self.refresh_timer is not None
            self.refresh_timer.StartOnce(400)

    def _on_refresh_timer(self, _evt: wx.TimerEvent) -> None:
        self.refresh_pending = False
        self.refresh_status()

    def _disable_watcher_temporarily(self, seconds: float = 2.5) -> None:
        self.fs_watcher_enabled = False
        wx.CallLater(int(seconds * 1000), lambda: setattr(self, "fs_watcher_enabled", True))

    def refresh_status(self) -> None:
        """Refreshes the git status and updates the UI."""
        if not self.is_git_repo:
            if self.git.is_git_repo():
                self.is_git_repo = True
                self._enable_git_controls()
                wx.CallAfter(self._init_fs_watcher)
                self._log_message("Git repository detected! Full git features enabled.", is_info=True)
            else:
                return

        branch, ahead, behind = self.git.get_branch_info()
        if branch:
            status_text = f"Branch: {branch}"
            if ahead > 0 or behind > 0:
                status_text += f"    ↑{ahead} ↓{behind}"
            self.view.branch_label.SetLabel(status_text)

        modified_map, staged_map, untracked_list = self.git.get_status()

        unstaged_files: List[str] = []
        self.unstaged_status_map = {}
        for path, y in modified_map.items():
            unstaged_files.append(path)
            self.unstaged_status_map[path] = y
        for path in untracked_list:
            unstaged_files.append(path)
            self.unstaged_status_map[path] = "U"

        self.view.unstaged_tree.populate(unstaged_files, self.unstaged_status_map)

        staged_files: List[str] = []
        staged_status_map: Dict[str, str] = {}
        for path, x in staged_map.items():
            staged_files.append(path)
            staged_status_map[path] = x

        self.view.staged_tree.populate(staged_files, staged_status_map)

        self._log_message("Status refreshed")

    def _enable_git_controls(self) -> None:
        """Enable all git controls after a repository is initialized."""
        self.view.refresh_button.Enable(True)
        self.view.pull_button.Enable(True)
        self.view.pull_rebase_button.Enable(True)
        self.view.push_button.Enable(True)
        self.view.stage_button.Enable(True)
        self.view.unstage_button.Enable(True)
        self.view.discard_button.Enable(True)
        self.view.commit_button.Enable(True)
        self.view.commit_message.Enable(True)
        self.view.amend_checkbox.Enable(True)
        self.view.unstaged_tree.Enable(True)
        self.view.staged_tree.Enable(True)
        self.view.diff_viewer.Enable(True)

    def _on_unstaged_select(self, event: wx.TreeEvent) -> None:
        item = event.GetItem()
        if item.IsOk():
            filepath = self.view.unstaged_tree.GetItemData(item)
            if filepath:
                is_untracked = self.unstaged_status_map.get(filepath) == "U"
                self._show_diff(filepath, staged=False, is_untracked=is_untracked)

    def _on_staged_select(self, event: wx.TreeEvent) -> None:
        item = event.GetItem()
        if item.IsOk():
            filepath = self.view.staged_tree.GetItemData(item)
            if filepath:
                self._show_diff(filepath, staged=True, is_untracked=False)

    def _show_diff(self, filepath: str, staged: bool = False, is_untracked: bool = False) -> None:
        diff_text = self.git.get_diff(filepath, staged=staged, is_untracked=is_untracked)
        self.view.diff_viewer.show_diff(diff_text)
        self.selected_file = filepath

    def _on_stage_files(self, _evt: wx.CommandEvent) -> None:
        files = self.view.unstaged_tree.get_checked_files()
        if not files:
            wx.MessageBox("No files selected for staging.", "Info", wx.OK | wx.ICON_INFORMATION, self)
            return
        self._disable_watcher_temporarily(3.0)
        code, _out, err = self.git.stage_files(files)
        if code == 0:
            self._log_message(f"Staged {len(files)} files")
            wx.CallLater(120, self.refresh_status)
        else:
            self._log_message(f"Error staging files: {err}", is_error=True)

    def _on_unstage_files(self, _evt: wx.CommandEvent) -> None:
        files = self.view.staged_tree.get_checked_files()
        if not files:
            wx.MessageBox("No files selected for unstaging.", "Info", wx.OK | wx.ICON_INFORMATION, self)
            return
        self._disable_watcher_temporarily(3.0)
        code, _out, err = self.git.unstage_files(files)
        if code == 0:
            self._log_message(f"Unstaged {len(files)} files")
            wx.CallLater(120, self.refresh_status)
        else:
            self._log_message(f"Error unstaging files: {err}", is_error=True)

    def _on_discard_changes(self, _evt: wx.CommandEvent) -> None:
        """
        Handles discarding changes for selected files.
        Checks for unsaved changes before proceeding.
        """
        files = self.view.unstaged_tree.get_checked_files()
        if not files:
            wx.MessageBox("No files selected for discarding.", "Info", wx.OK | wx.ICON_INFORMATION, self)
            return

        if not self._check_unsaved_changes():
            return

        untracked_to_delete = []
        modified_to_discard = []
        for f in files:
            if self.unstaged_status_map.get(f) == "U":
                untracked_to_delete.append(f)
            else:
                modified_to_discard.append(f)

        message_parts = []
        if modified_to_discard:
            message_parts.append(f"discard changes in {len(modified_to_discard)} file(s)")
        if untracked_to_delete:
            message_parts.append(f"permanently delete {len(untracked_to_delete)} untracked file(s)")

        if not message_parts:
            return

        confirm_message = f"Are you sure you want to {' and '.join(message_parts)}? This cannot be undone!"

        result = wx.MessageBox(
            confirm_message,
            "Confirm Discard",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
            self,
        )

        if result == wx.YES:
            self._disable_watcher_temporarily(3.0)
            success_count = 0
            error_messages = []

            if modified_to_discard:
                code, _out, err = self.git.execute_command("checkout", "--", *modified_to_discard)
                if code == 0:
                    success_count += len(modified_to_discard)
                else:
                    error_messages.append(f"Error discarding changes: {err}")

            if untracked_to_delete:
                for f in untracked_to_delete:
                    try:
                        os.remove(os.path.join(self.git.repo_path, f))
                        success_count += 1
                    except Exception as e:
                        error_messages.append(f"Error deleting {f}: {e}")

            if success_count > 0:
                self._log_message(f"Discarded/deleted {success_count} file(s)")

            if error_messages:
                for msg in error_messages:
                    self._log_message(msg, is_error=True)

            wx.CallLater(120, self.refresh_status)

    def _on_commit(self, _evt: wx.CommandEvent) -> None:
        message = self.view.commit_message.GetValue().strip()
        if not message:
            wx.MessageBox("Please enter a commit message.", "Error", wx.OK | wx.ICON_ERROR, self)
            return
        amend = self.view.amend_checkbox.GetValue()
        self._disable_watcher_temporarily(4.0)
        code, out, err = self.git.commit(message, amend=amend)
        if code == 0:
            self._log_message(f"Commit successful\n{out.strip()}")
            self.view.commit_message.Clear()
            self.view.amend_checkbox.SetValue(False)
            wx.CallLater(150, self.refresh_status)
        else:
            self._log_message(f"Commit failed: {err}", is_error=True)

    def _on_refresh(self, _evt: wx.CommandEvent) -> None:
        self._disable_watcher_temporarily(2.5)
        self.refresh_status()

    def _on_pull(self, _evt: wx.CommandEvent) -> None:
        """
        Handles the Pull button click.
        Checks for unsaved changes before proceeding.
        """
        if not self._check_unsaved_changes():
            return

        self._log_message("Pulling from remote...")
        self._disable_watcher_temporarily(5.0)
        self._run_git_command(["pull"], "Pull completed", "Pull failed")

    def _on_pull_rebase(self, _evt: wx.CommandEvent) -> None:
        """
        Handles the Pull Rebase button click.
        Checks for unsaved changes before proceeding.
        """
        if not self._check_unsaved_changes():
            return

        self._log_message("Pulling with rebase from remote...")
        self._disable_watcher_temporarily(5.0)
        self._run_git_command(["pull", "--rebase"], "Pull rebase completed", "Pull rebase failed")

    def _on_push(self, _evt: wx.CommandEvent) -> None:
        self._log_message("Pushing to remote...")
        self._disable_watcher_temporarily(3.0)
        self._run_git_command(["push"], "Push completed", "Push failed")

    def _on_execute_custom(self, _evt: wx.CommandEvent) -> None:
        """
        Handles custom git command execution.
        Checks for unsaved changes if the command is potentially destructive.
        """
        command = self.view.custom_command.GetValue().strip()
        if not command:
            return

        destructive_commands = [
            'checkout', 'reset', 'pull', 'merge', 'rebase', 'clean', 
            'switch', 'restore', 'revert'
        ]

        is_destructive = any(cmd in command.split() for cmd in destructive_commands)

        if is_destructive:
            if not self._check_unsaved_changes():
                return

        self._log_message(f"Executing git command: {command}")
        self._disable_watcher_temporarily(5.0)
        args = command.split()
        self._run_git_command(args, "Command completed", "Command failed")

    def _run_git_command(self, args: List[str], success_msg: str, error_msg: str) -> None:
        import threading

        def worker():
            code, out, err = self.git.execute_command(*args)
            wx.CallAfter(self._handle_command_result, code, out, err, success_msg, error_msg)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def _handle_command_result(self, code: int, out: str, err: str, success_msg: str, error_msg: str) -> None:
        if code == 0:
            self._log_message(success_msg)
            if out:
                self._log_message(out.rstrip("\n"))
            wx.CallLater(200, self.refresh_status)
        else:
            self._log_message(f"{error_msg}: {err}", is_error=True)

    def _log_message(self, message: str, is_error: bool = False, is_info: bool = False) -> None:
        if is_error:
            self.view.log_output.SetDefaultStyle(wx.TextAttr(wx.RED))
            prefix = "ERROR: "
        elif is_info:
            self.view.log_output.SetDefaultStyle(wx.TextAttr(wx.Colour(100, 200, 255)))
            prefix = "INFO: "
        else:
            self.view.log_output.SetDefaultStyle(wx.TextAttr(wx.Colour(200, 200, 200)))
            prefix = "INFO: "
        self.view.log_output.AppendText(f"{prefix}{message}\n")
        self.view.log_output.SetInsertionPointEnd()

    def handle_exit_request(self) -> bool:
        """Handles the application exit request by cleaning up resources."""
        try:
            if hasattr(self, "fs_watcher") and self.fs_watcher:
                try:
                    self.fs_watcher.RemoveAll()
                except Exception:
                    pass
        except Exception:
            pass
        try:
            if hasattr(self, "refresh_timer") and self.refresh_timer:
                try:
                    self.refresh_timer.Stop()
                except Exception:
                    pass
        except Exception:
            pass
        return True


if __name__ == "__main__":
    app = wx.App(False)
    frame = wx.Frame(None, title="Git", size=(1200, 800))
    panel = GitPanel(frame)
    frame.Show()
    app.MainLoop()