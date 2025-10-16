#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Apply Context Panel (Presenter)
--------------------------------------
Contains the logic for the 'Apply Context' tab of the unified GUI.
This panel acts as the Presenter in an MVP architecture.
"""

import wx
import wx.dataview
import sys
import io
import os
import configparser
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from contextlib import redirect_stdout
from pubsub import pub

from ktr.apply_context import ContextParser
from .task_manager import get_task_manager
from .module_ui.apply_context_panel_view import ApplyContextPanelView


def _run_parser_task(markdown_content: str, output_dir: str, overwrite: bool,
                    quiet: bool, dry_run: bool, tabs_to_spaces: Optional[int]
                    ) -> Tuple[ContextParser, List[Path], List[Path], str]:
    """
    Runs the initial parsing and file creation/modification simulation.
    This function is executed in a background thread.
    """
    if not markdown_content:
        raise ValueError("Input text is required.")

    log_capture = io.StringIO()
    with redirect_stdout(log_capture):
        parser = ContextParser(
            output_dir=Path(output_dir),
            overwrite=overwrite,
            verbose=not quiet,
            dry_run=dry_run,
            tabs_to_spaces=tabs_to_spaces
        )
        parser.parse_and_create(markdown_content)
        pending_files, pending_dirs = parser.get_pending_removals()

        if dry_run and (pending_files or pending_dirs):
            parser.execute_pending_removals()

    log_output = log_capture.getvalue()
    return parser, pending_files, pending_dirs, log_output


def _run_removals_task(parser: ContextParser) -> Tuple[ContextParser, str]:
    """
    Executes the pending file/directory removals.
    This function is executed in a background thread after user confirmation.
    """
    log_capture = io.StringIO()
    with redirect_stdout(log_capture):
        parser.execute_pending_removals()
    log_output = log_capture.getvalue()
    return parser, log_output


class RemovalConfirmationDialog(wx.Dialog):
    """A dialog to confirm file and directory deletions."""
    def __init__(self, parent, files_to_remove: List[str], dirs_to_remove: List[str]):
        super().__init__(parent, title="Confirm Deletion", size=(600, 400))
        self.SetMinSize((400, 300))

        main_sizer = wx.BoxSizer(wx.VERTICAL)

        info_text = wx.StaticText(self, label="The following files and/or directories are marked for permanent deletion. This action cannot be undone.")
        info_text.Wrap(580)
        main_sizer.Add(info_text, 0, wx.ALL | wx.EXPAND, 10)

        list_panel = wx.Panel(self)
        list_sizer = wx.BoxSizer(wx.VERTICAL)
        
        has_content = False
        if files_to_remove:
            files_label = wx.StaticText(list_panel, label="Files to be removed:")
            self.files_listbox = wx.ListBox(list_panel, choices=files_to_remove, style=wx.LB_EXTENDED)
            list_sizer.Add(files_label, 0, wx.BOTTOM, 5)
            list_sizer.Add(self.files_listbox, 1, wx.EXPAND)
            has_content = True

        if dirs_to_remove:
            if has_content:
                list_sizer.AddSpacer(10)
            dirs_label = wx.StaticText(list_panel, label="Directories to be removed (must be empty):")
            self.dirs_listbox = wx.ListBox(list_panel, choices=dirs_to_remove, style=wx.LB_EXTENDED)
            list_sizer.Add(dirs_label, 0, wx.BOTTOM, 5)
            list_sizer.Add(self.dirs_listbox, 1, wx.EXPAND)

        list_panel.SetSizer(list_sizer)
        main_sizer.Add(list_panel, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        btn_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        ok_btn = self.FindWindowById(wx.ID_OK)
        if ok_btn:
            ok_btn.SetLabel("Confirm Deletion")
        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.SetSizer(main_sizer)
        self.Layout()
        self.Centre()

class ApplyContextPanel(wx.Panel):
    """Presenter for applying context files. Manages the UI (View) and logic."""

    def __init__(self, parent):
        """Initializes the Apply Context panel."""
        super().__init__(parent)

        self.parser_results: Optional[ContextParser] = None
        self.is_running = False

        self.view = ApplyContextPanelView(self)
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.view, 1, wx.EXPAND)
        self.SetSizer(sizer)
        
        self._bind_events()
        
        wx.CallAfter(self.load_settings)
        
    def _bind_events(self):
        """Bind events from the View's widgets to the Presenter's handlers."""
        self.view.output_browse_btn.Bind(wx.EVT_BUTTON, self.on_browse_output_dir)
        self.view.dry_run_btn.Bind(wx.EVT_BUTTON, self.on_start_dry_run)
        self.view.parse_btn.Bind(wx.EVT_BUTTON, self.on_start_parsing)
        self.view.save_btn.Bind(wx.EVT_BUTTON, self.on_save_report)
        self.view.clear_btn.Bind(wx.EVT_BUTTON, self.on_clear_all)
        self.view.cb_tabs_to_spaces.Bind(wx.EVT_CHECKBOX, self.on_toggle_tabs_to_spaces)

    def on_toggle_tabs_to_spaces(self, event):
        """Enable/disable the spin control based on the checkbox state."""
        self.view.spin_tabs_to_spaces.Enable(self.view.cb_tabs_to_spaces.IsChecked())

    def on_browse_output_dir(self, event):
        """Handles the 'Browse' button click to select an output directory."""
        with wx.DirDialog(self.GetTopLevelParent(), "Select Output Directory", defaultPath=self.view.output_dir_ctrl.GetValue(),
                          style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as dialog:
            if dialog.ShowModal() == wx.ID_CANCEL:
                return
            self.view.output_dir_ctrl.SetValue(dialog.GetPath())

    def on_start_dry_run(self, event):
        """Handle the 'Dry Run' button click."""
        self.start_parsing_process(dry_run=True)

    def on_start_parsing(self, event):
        """Handle the 'Parse && Create' button click."""
        self.start_parsing_process(dry_run=False)

    def start_parsing_process(self, dry_run: bool):
        """Core logic to start the parsing process, either as a dry run or for real."""
        if self.is_running:
            return

        if not self.validate_inputs():
            return

        self.clear_log()
        self.parser_results = None
        self.is_running = True

        self.view.dry_run_btn.Disable()
        self.view.parse_btn.Disable()
        self.view.save_btn.Disable()

        for i in range(1, self.view.notebook.GetPageCount()):
            self.view.notebook.GetPage(i).Enable(False)
        self.view.notebook.SetSelection(0)

        markdown_content = self.view.input_text_ctrl.GetValue()
        tabs_to_spaces_val = self.view.spin_tabs_to_spaces.GetValue() if self.view.cb_tabs_to_spaces.GetValue() else None

        status_message = "Running Dry Run..." if dry_run else "Running Parse & Create..."
        pub.sendMessage("status.update", text=status_message, pane=0)
        pub.sendMessage("progress.pulse", pulse=True)

        task_manager = get_task_manager()
        task_manager.submit_job(
            target_function=_run_parser_task,
            on_complete=self.on_parse_complete,
            on_error=self.on_parsing_error,
            markdown_content=markdown_content,
            output_dir=self.view.output_dir_ctrl.GetValue(),
            overwrite=self.view.cb_overwrite.GetValue(),
            quiet=self.view.cb_quiet.GetValue(),
            dry_run=dry_run,
            tabs_to_spaces=tabs_to_spaces_val
        )

    def on_parse_complete(self, result: Tuple[ContextParser, List, List, str]):
        """Callback for when the initial parsing task is complete."""
        parser, pending_files, pending_dirs, log_output = result
        self.parser_results = parser

        if log_output:
            for line in log_output.strip().split('\n'):
                self.append_to_log(line.strip())

        if (pending_files or pending_dirs) and not parser.dry_run:
            pending_file_strs = [str(p.relative_to(parser.output_base_dir)) for p in pending_files]
            pending_dir_strs = [str(p.relative_to(parser.output_base_dir)) for p in pending_dirs]

            dialog = RemovalConfirmationDialog(self.GetTopLevelParent(), pending_file_strs, pending_dir_strs)
            user_choice = dialog.ShowModal()
            dialog.Destroy()

            if user_choice == wx.ID_OK:
                task_manager = get_task_manager()
                task_manager.submit_job(
                    target_function=_run_removals_task,
                    on_complete=self.on_final_complete,
                    on_error=self.on_parsing_error,
                    parser=self.parser_results
                )
            else:
                self.on_final_complete((self.parser_results, "Deletion cancelled by user.\n"))
        else:
            self.on_final_complete((self.parser_results, ""))

    def on_final_complete(self, result: Tuple[ContextParser, str]):
        """Handles final completion after all tasks, including optional removals."""
        parser, removal_log_output = result
        self.parser_results = parser
        self.is_running = False

        if removal_log_output:
            for line in removal_log_output.strip().split('\n'):
                self.append_to_log(line.strip())

        pub.sendMessage("progress.pulse", pulse=False)
        pub.sendMessage("status.update", text="Success" if not parser.errors else "Completed with errors", pane=0)

        self.populate_results()
        
        self.view.dry_run_btn.Enable()
        self.view.parse_btn.Enable()
        self.view.save_btn.Enable()

        for i in range(1, self.view.notebook.GetPageCount()):
            self.view.notebook.GetPage(i).Enable(True)
        
        if self.parser_results.errors:
            self.view.notebook.SetSelection(8)
        elif self.parser_results.diffs:
            self.view.notebook.SetSelection(1)
        else:
            self.view.notebook.SetSelection(0)

    def on_parsing_error(self, error: Exception):
        """Callback for when a background task raises an exception."""
        self.is_running = False
        pub.sendMessage("progress.pulse", pulse=False)
        pub.sendMessage("status.update", text="Completed with errors", pane=0)
        
        self.view.dry_run_btn.Enable()
        self.view.parse_btn.Enable()
        
        error_msg = f"An unexpected error occurred: {error}"
        self.append_to_log(error_msg)
        wx.MessageBox(error_msg, "Error", wx.OK | wx.ICON_ERROR, parent=self.GetTopLevelParent())
        self.view.notebook.SetSelection(9)

    def on_save_report(self, event):
        """Handles the 'Save Report' button click."""
        if not self.parser_results:
            wx.MessageBox("No parsing results to save.", "No Results", wx.OK | wx.ICON_WARNING, parent=self.GetTopLevelParent())
            return

        with wx.FileDialog(self.GetTopLevelParent(), "Save Report", wildcard="Markdown files (*.md)|*.md|Text files (*.txt)|*.txt",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dialog:
            if dialog.ShowModal() == wx.ID_CANCEL:
                return
            filepath = dialog.GetPath()
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(self.generate_report())
                wx.MessageBox(f"Report saved to {filepath}", "Success", wx.OK | wx.ICON_INFORMATION, parent=self.GetTopLevelParent())
            except Exception as e:
                wx.MessageBox(f"Failed to save report: {e}", "Error", wx.OK | wx.ICON_ERROR, parent=self.GetTopLevelParent())

    def on_clear_all(self, event):
        """Handles the 'Clear' button click, resetting the UI."""
        self.clear_log()
        self.parser_results = None
        self.view.save_btn.Disable()
        self.view.input_text_ctrl.Clear()
        self.view.changes_text_ctrl.Clear()

        for label in self.view.summary_labels.values():
            label.SetLabel("N/A")

        for list_ctrl in [self.view.files_created_list, self.view.files_overwritten_list, 
                          self.view.files_removed_list, self.view.dirs_removed_list,
                          self.view.files_skipped_list, self.view.dirs_skipped_list,
                          self.view.errors_list]:
            list_ctrl.DeleteAllItems()
            
        for i in range(1, self.view.notebook.GetPageCount()):
            self.view.notebook.GetPage(i).Enable(False)
        
        pub.sendMessage("status.update", text="Ready", pane=0)

    def handle_exit_request(self):
        """Handles the application exit request, saving settings if possible."""
        if self.is_running:
            if wx.MessageBox("A parsing operation is in progress. Exit anyway?", "Confirm Exit",
                             wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION, parent=self.GetTopLevelParent()) == wx.NO:
                return False
        self.save_settings()
        return True

    def validate_inputs(self) -> bool:
        """Validates the required input fields."""
        if not self.view.input_text_ctrl.GetValue():
           wx.MessageBox("Input text is required.", "Validation Error", wx.OK | wx.ICON_ERROR, parent=self.GetTopLevelParent())
           return False

        if not self.view.output_dir_ctrl.GetValue():
            wx.MessageBox("Output directory is required.", "Validation Error", wx.OK | wx.ICON_ERROR, parent=self.GetTopLevelParent())
            return False
            
        return True

    def clear_log(self):
        """Clears the log output text control."""
        self.view.log_text_ctrl.Clear()

    def append_to_log(self, text: str):
        """Appends a message to the log with appropriate coloring."""
        text_lower = text.lower()
        attr = self.view.log_attr_normal
        if "error" in text_lower:
            attr = self.view.log_attr_error
        elif any(word in text_lower for word in ["created", "overwritten", "success", "removed"]):
            attr = self.view.log_attr_success
        
        self.view.log_text_ctrl.SetDefaultStyle(attr)
        self.view.log_text_ctrl.AppendText(text + "\n")
        self.view.log_text_ctrl.SetDefaultStyle(self.view.log_attr_normal)

    def populate_results(self):
        """Populates the results tabs with data from the ContextParser."""
        if not self.parser_results:
            return

        p = self.parser_results

        self.view.summary_labels["output_dir"].SetLabel(str(p.output_base_dir))
        self.view.summary_labels["dirs_created"].SetLabel(str(len(p.dirs_created)))
        self.view.summary_labels["files_created"].SetLabel(str(len(p.files_created)))
        self.view.summary_labels["files_overwritten"].SetLabel(str(len(p.files_overwritten)))
        self.view.summary_labels["files_removed"].SetLabel(str(len(p.files_removed)))
        self.view.summary_labels["dirs_removed"].SetLabel(str(len(p.dirs_removed)))
        self.view.summary_labels["files_skipped"].SetLabel(str(len(p.files_skipped)))
        self.view.summary_labels["dirs_skipped_removal"].SetLabel(str(len(p.dirs_skipped_removal)))
        self.view.summary_labels["errors"].SetLabel(str(len(p.errors)))
        self.view.summary_labels["status"].SetLabel("Success" if not p.errors else "Completed with errors")

        self.populate_list_ctrl(self.view.files_created_list, p.files_created)
        self.populate_list_ctrl(self.view.files_overwritten_list, p.files_overwritten)
        self.populate_list_ctrl(self.view.files_removed_list, p.files_removed)
        self.populate_list_ctrl(self.view.dirs_removed_list, p.dirs_removed)
        self.populate_list_ctrl(self.view.files_skipped_list, p.files_skipped)
        self.populate_list_ctrl(self.view.dirs_skipped_list, p.dirs_skipped_removal)
        self.populate_list_ctrl(self.view.errors_list, p.errors, has_index=False)

        self.populate_changes_tab()

    def populate_changes_tab(self):
        self.view.changes_text_ctrl.Clear()

        if not self.parser_results or not hasattr(self.parser_results, 'diffs') or not self.parser_results.diffs:
            self.view.changes_text_ctrl.SetValue("No changes to display.")
            return

        sorted_files = sorted(self.parser_results.diffs.keys())

        for filename in sorted_files:
            diff_text = self.parser_results.diffs[filename]
            if not diff_text:
                continue

            for line in diff_text.splitlines(True):
                attr = self.view.diff_attr_normal
                stripped_line = line.strip()

                if not stripped_line:
                    self.view.changes_text_ctrl.SetDefaultStyle(attr)
                    self.view.changes_text_ctrl.AppendText(line)
                    continue

                if line.startswith("---") or line.startswith("+++") or line.startswith("@@"):
                    attr = self.view.diff_attr_header
                elif line.startswith("+"):
                    attr = self.view.diff_attr_add
                elif line.startswith("-"):
                    attr = self.view.diff_attr_remove

                self.view.changes_text_ctrl.SetDefaultStyle(attr)
                self.view.changes_text_ctrl.AppendText(line)

        self.view.changes_text_ctrl.SetDefaultStyle(self.view.diff_attr_normal)
        self.view.changes_text_ctrl.SetInsertionPoint(0)

    def populate_list_ctrl(self, list_ctrl: wx.ListCtrl, items: list, has_index: bool = True):
        list_ctrl.DeleteAllItems()

        for i, item in enumerate(items):
            if has_index:
                index = list_ctrl.InsertItem(i, str(i + 1))
                list_ctrl.SetItem(index, 1, str(item))
            else:
                list_ctrl.InsertItem(i, str(item))


    def generate_report(self) -> str:
        """Generates a markdown report of the last parsing operation."""
        if not self.parser_results:
            return "No results available."

        p = self.parser_results
        report = ["# apply_context GUI - Parsing Report\n"]
        report.append(f"**Output Directory:** `{p.output_base_dir}`")
        report.append(f"**Directories Created:** {len(p.dirs_created)}")
        report.append(f"**Files Created:** {len(p.files_created)}")
        report.append(f"**Files Overwritten:** {len(p.files_overwritten)}")
        report.append(f"**Files Removed:** {len(p.files_removed)}")
        report.append(f"**Directories Removed:** {len(p.dirs_removed)}")
        report.append(f"**Files Skipped:** {len(p.files_skipped)}")
        report.append(f"**Directories Skipped (not empty):** {len(p.dirs_skipped_removal)}")
        report.append(f"**Errors:** {len(p.errors)}\n")

        for name, items in [("Directories Created", p.dirs_created), ("Files Created", p.files_created),
                            ("Files Overwritten", p.files_overwritten), ("Files Removed", p.files_removed),
                            ("Directories Removed", p.dirs_removed), ("Files Skipped", p.files_skipped),
                            ("Directories Skipped (not empty)", p.dirs_skipped_removal),
                            ("Errors", p.errors)]:
            if items:
                report.append(f"\n## {name}")
                report.extend([f"- {item}" for item in items])

        report.append("\n## Log Output\n")
        report.append(self.view.log_text_ctrl.GetValue().strip())
        report.append("")

        return "\n".join(report)

    def get_config_path(self) -> Path:
        """Gets the path to the panel's configuration file."""
        return Path.home() / ".apply_context_gui.ini"

    def load_settings(self):
        """Loads panel settings from the configuration file."""
        config_path = self.get_config_path()
        if not config_path.exists():
            return

        config = configparser.ConfigParser()
        config.read(config_path)

        if "Settings" in config:
            settings = config["Settings"]
            self.view.output_dir_ctrl.SetValue(settings.get("output_dir", "."))
            self.view.cb_overwrite.SetValue(settings.getboolean("overwrite", False))
            self.view.cb_quiet.SetValue(settings.getboolean("quiet", False))
            self.view.cb_tabs_to_spaces.SetValue(settings.getboolean("tabs_to_spaces_enabled", False))
            self.view.spin_tabs_to_spaces.SetValue(settings.getint("tabs_to_spaces_count", 4))

        self.on_toggle_tabs_to_spaces(None)

    def save_settings(self):
        """Saves current panel settings to the configuration file."""
        config_path = self.get_config_path()

        config = configparser.ConfigParser()
        config["Settings"] = {
            "output_dir": self.view.output_dir_ctrl.GetValue(),
            "overwrite": str(self.view.cb_overwrite.GetValue()),
            "quiet": str(self.view.cb_quiet.GetValue()),
            "tabs_to_spaces_enabled": str(self.view.cb_tabs_to_spaces.GetValue()),
            "tabs_to_spaces_count": str(self.view.spin_tabs_to_spaces.GetValue())
        }

        with open(config_path, 'w') as f:
            config.write(f)