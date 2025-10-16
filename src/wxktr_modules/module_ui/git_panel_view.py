#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Git Panel - View
--------------------------
The View for the Git panel in an MVP architecture.

This class is responsible for creating and laying out all the UI widgets.
It exposes widgets to be controlled by the Presenter.
"""

import wx
import wx.stc as stc

try:
    from ..modules_parts.diff_viewer import DiffViewer
    from ..modules_parts.file_tree import FileTreeCtrl
except ImportError:
    import sys
    import os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from modules_parts.diff_viewer import DiffViewer
    from modules_parts.file_tree import FileTreeCtrl


class GitPanelView(wx.Panel):
    """The View for the Git panel."""

    def __init__(self, parent):
        """Initializes the view, creating all widgets and sizers."""
        super().__init__(parent)
        self._create_widgets_and_sizers()

    def _create_widgets_and_sizers(self):
        """Creates and lays out all widgets for the panel."""
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        toolbar_panel = self._create_toolbar()
        main_sizer.Add(toolbar_panel, 0, wx.EXPAND | wx.ALL, 5)

        self.main_splitter = wx.SplitterWindow(self, style=wx.SP_LIVE_UPDATE)

        left_panel = wx.Panel(self.main_splitter)
        left_sizer = wx.BoxSizer(wx.VERTICAL)

        self.tree_splitter = wx.SplitterWindow(left_panel, style=wx.SP_LIVE_UPDATE)

        unstaged_panel = wx.Panel(self.tree_splitter)
        unstaged_sizer = wx.BoxSizer(wx.VERTICAL)
        unstaged_label = wx.StaticText(unstaged_panel, label="Unstaged Changes")
        unstaged_label.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        unstaged_sizer.Add(unstaged_label, 0, wx.ALL, 5)
        self.unstaged_tree = FileTreeCtrl(unstaged_panel)
        unstaged_sizer.Add(self.unstaged_tree, 1, wx.EXPAND)
        unstaged_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.stage_button = wx.Button(unstaged_panel, label="Stage Selected")
        self.discard_button = wx.Button(unstaged_panel, label="Discard Changes")
        unstaged_btn_sizer.Add(self.stage_button, 0, wx.ALL, 2)
        unstaged_btn_sizer.Add(self.discard_button, 0, wx.ALL, 2)
        unstaged_sizer.Add(unstaged_btn_sizer, 0, wx.ALL, 5)
        unstaged_panel.SetSizer(unstaged_sizer)

        staged_panel = wx.Panel(self.tree_splitter)
        staged_sizer = wx.BoxSizer(wx.VERTICAL)
        staged_label = wx.StaticText(staged_panel, label="Staged Changes")
        staged_label.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        staged_sizer.Add(staged_label, 0, wx.ALL, 5)
        self.staged_tree = FileTreeCtrl(staged_panel)
        staged_sizer.Add(self.staged_tree, 1, wx.EXPAND)
        unstaged_btn_sizer2 = wx.BoxSizer(wx.HORIZONTAL)
        self.unstage_button = wx.Button(staged_panel, label="Unstage Selected")
        unstaged_btn_sizer2.Add(self.unstage_button, 0, wx.ALL, 2)
        staged_sizer.Add(unstaged_btn_sizer2, 0, wx.ALL, 5)
        staged_panel.SetSizer(staged_sizer)

        self.tree_splitter.SplitHorizontally(unstaged_panel, staged_panel, 300)
        self.tree_splitter.SetSashGravity(0.5)
        left_sizer.Add(self.tree_splitter, 1, wx.EXPAND)
        left_panel.SetSizer(left_sizer)

        right_panel = wx.Panel(self.main_splitter)
        right_sizer = wx.BoxSizer(wx.VERTICAL)
        diff_label = wx.StaticText(right_panel, label="Diff View")
        diff_label.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        right_sizer.Add(diff_label, 0, wx.ALL, 5)
        self.diff_viewer = DiffViewer(right_panel)
        right_sizer.Add(self.diff_viewer, 1, wx.EXPAND)
        right_panel.SetSizer(right_sizer)

        self.main_splitter.SplitVertically(left_panel, right_panel, 400)
        self.main_splitter.SetSashGravity(0.4)
        main_sizer.Add(self.main_splitter, 1, wx.EXPAND)

        commit_panel = self._create_commit_panel()
        main_sizer.Add(commit_panel, 0, wx.EXPAND | wx.ALL, 5)

        log_label = wx.StaticText(self, label="Git Output Log")
        log_label.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        main_sizer.Add(log_label, 0, wx.LEFT | wx.TOP, 5)
        self.log_output = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        font = wx.Font(9, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.log_output.SetFont(font)
        self.log_output.SetBackgroundColour(wx.Colour(30, 30, 30))
        self.log_output.SetForegroundColour(wx.Colour(200, 200, 200))
        self.log_output.SetMinSize((-1, 100))
        main_sizer.Add(self.log_output, 0, wx.EXPAND | wx.ALL, 5)

        cmd_panel = self._create_custom_command_panel()
        main_sizer.Add(cmd_panel, 0, wx.EXPAND | wx.ALL, 5)

        self.SetSizer(main_sizer)

    def _create_toolbar(self) -> wx.Panel:
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.branch_label = wx.StaticText(panel, label="Branch: -")
        self.branch_label.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(self.branch_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        self.refresh_button = wx.Button(panel, label="Refresh")
        self.pull_button = wx.Button(panel, label="Pull")
        self.pull_rebase_button = wx.Button(panel, label="Pull Rebase")
        self.push_button = wx.Button(panel, label="Push")

        sizer.Add(self.refresh_button, 0, wx.RIGHT, 5)
        sizer.Add(self.pull_button, 0, wx.RIGHT, 5)
        sizer.Add(self.pull_rebase_button, 0, wx.RIGHT, 5)
        sizer.Add(self.push_button, 0, wx.RIGHT, 5)

        panel.SetSizer(sizer)
        return panel

    def _create_commit_panel(self) -> wx.Panel:
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        label = wx.StaticText(panel, label="Commit Message")
        label.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(label, 0, wx.BOTTOM, 5)

        self.commit_message = wx.TextCtrl(panel, style=wx.TE_MULTILINE)
        self.commit_message.SetMinSize((-1, 80))
        sizer.Add(self.commit_message, 1, wx.EXPAND | wx.BOTTOM, 5)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.commit_button = wx.Button(panel, label="Commit")
        self.amend_checkbox = wx.CheckBox(panel, label="Amend Last Commit")
        btn_sizer.Add(self.commit_button, 0, wx.RIGHT, 5)
        btn_sizer.Add(self.amend_checkbox, 0, wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(btn_sizer, 0)

        panel.SetSizer(sizer)
        return panel

    def _create_custom_command_panel(self) -> wx.Panel:
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.HORIZONTAL)

        label = wx.StaticText(panel, label="Custom Git Command:")
        sizer.Add(label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        self.custom_command = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        sizer.Add(self.custom_command, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        self.execute_button = wx.Button(panel, label="Execute")
        sizer.Add(self.execute_button, 0)

        panel.SetSizer(sizer)
        return panel