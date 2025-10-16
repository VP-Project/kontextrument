#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Apply Context Panel - View
--------------------------
The View for the Apply Context panel in an MVP architecture.

This class is responsible for creating and laying out all the UI widgets.
It exposes widgets to be controlled by the Presenter.
"""

import wx
import wx.dataview
from typing import Dict, List

class ApplyContextPanelView(wx.Panel):
    """The View for the Apply Context panel."""
    
    def __init__(self, parent):
        super().__init__(parent)

        self.splitter = wx.SplitterWindow(self, style=wx.SP_LIVE_UPDATE)
        self.splitter.SetSashGravity(0.4)

        self.top_splitter_panel = wx.Panel(self.splitter)
        self.bottom_splitter_panel = wx.Panel(self.splitter)

        self._create_widgets()
        self._create_sizers()
        
        self.splitter.SplitHorizontally(self.top_splitter_panel, self.bottom_splitter_panel, -350)
        
        panel_sizer = wx.BoxSizer(wx.VERTICAL)
        panel_sizer.Add(self.splitter, 1, wx.EXPAND)
        self.SetSizer(panel_sizer)

    def _create_widgets(self):
        """Create all the widgets for the application."""
        self.text_input_panel = self._create_text_input_panel()

        self.output_dir_label = wx.StaticText(self.bottom_splitter_panel, label="Output Folder:")
        self.output_dir_ctrl = wx.TextCtrl(self.bottom_splitter_panel)
        self.output_browse_btn = wx.Button(self.bottom_splitter_panel, label="Browse...")
        
        self.cb_overwrite = wx.CheckBox(self.bottom_splitter_panel, label="Overwrite existing files")
        self.cb_quiet = wx.CheckBox(self.bottom_splitter_panel, label="Quiet / suppress verbose output")
        self.cb_tabs_to_spaces = wx.CheckBox(self.bottom_splitter_panel, label="Replace tabs with spaces:")
        self.spin_tabs_to_spaces = wx.SpinCtrl(self.bottom_splitter_panel, min=1, max=16, initial=4)
        self.spin_tabs_to_spaces.Disable()

        self._create_results_notebook()

        self.dry_run_btn = wx.Button(self.bottom_splitter_panel, label="Dry Run")
        self.parse_btn = wx.Button(self.bottom_splitter_panel, label="Parse && Create")
        self.save_btn = wx.Button(self.bottom_splitter_panel, label="Save Report...")
        self.clear_btn = wx.Button(self.bottom_splitter_panel, label="Clear")
        self.save_btn.Disable()

    def _create_text_input_panel(self) -> wx.Panel:
        panel = wx.Panel(self.top_splitter_panel)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        self.input_text_label = wx.StaticText(panel, label="Paste your markdown content below:")
        self.input_text_ctrl = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_RICH2)
        self.input_text_ctrl.SetFont(wx.Font(10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        self.input_text_ctrl.SetHint("Paste your markdown content here...")

        sizer.Add(self.input_text_label, 0, wx.BOTTOM | wx.EXPAND, 5)
        sizer.Add(self.input_text_ctrl, 1, wx.EXPAND)
        
        panel.SetSizer(sizer)
        return panel

    def _create_results_notebook(self):
        self.notebook = wx.Notebook(self.bottom_splitter_panel)
        
        summary_panel, self.summary_labels = self._create_summary_tab_panel()
        changes_panel, self.changes_text_ctrl = self._create_changes_tab_panel()
        created_panel, self.files_created_list = self._create_list_tab_panel("Files Created", ["#", "Path"])
        overwritten_panel, self.files_overwritten_list = self._create_list_tab_panel("Files Overwritten", ["#", "Path"])
        removed_files_panel, self.files_removed_list = self._create_list_tab_panel("Files Removed", ["#", "Path"])
        removed_dirs_panel, self.dirs_removed_list = self._create_list_tab_panel("Dirs Removed", ["#", "Path"])
        skipped_panel, self.files_skipped_list = self._create_list_tab_panel("Files Skipped", ["#", "Path"])
        skipped_removals_panel, self.dirs_skipped_list = self._create_list_tab_panel("Skipped Removals", ["#", "Path"])
        errors_panel, self.errors_list = self._create_list_tab_panel("Errors", ["Error Message"])
        log_panel, self.log_text_ctrl = self._create_log_tab_panel()

        self.notebook.AddPage(summary_panel, "Summary")
        self.notebook.AddPage(changes_panel, "Changes")
        self.notebook.AddPage(created_panel, "Files Created")
        self.notebook.AddPage(overwritten_panel, "Files Overwritten")
        self.notebook.AddPage(removed_files_panel, "Files Removed")
        self.notebook.AddPage(removed_dirs_panel, "Dirs Removed")
        self.notebook.AddPage(skipped_panel, "Files Skipped")
        self.notebook.AddPage(skipped_removals_panel, "Skipped Removals")
        self.notebook.AddPage(errors_panel, "Errors")
        self.notebook.AddPage(log_panel, "Log Output")

        for i in range(1, self.notebook.GetPageCount()):
            self.notebook.GetPage(i).Enable(False)

    def _create_log_tab_panel(self) -> (wx.Panel, wx.TextCtrl):
        panel = wx.Panel(self.notebook)
        sizer = wx.BoxSizer(wx.VERTICAL)
        log_ctrl = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        log_ctrl.SetFont(wx.Font(10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        
        fg_color = wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT)
        
        self.log_attr_error = wx.TextAttr(wx.RED)
        self.log_attr_success = wx.TextAttr(wx.Colour(0, 128, 0))
        self.log_attr_normal = wx.TextAttr(fg_color)

        sizer.Add(log_ctrl, 1, wx.EXPAND)
        panel.SetSizer(sizer)
        return panel, log_ctrl

    def _create_summary_tab_panel(self) -> (wx.Panel, Dict[str, wx.StaticText]):
        panel = wx.Panel(self.notebook)
        sizer = wx.FlexGridSizer(2, 10, 10)
        sizer.AddGrowableCol(1)
        
        labels_map = {}
        label_defs = [
            ("Output Directory:", "output_dir"), ("Directories Created:", "dirs_created"),
            ("Files Created:", "files_created"), ("Files Overwritten:", "files_overwritten"),
            ("Files Removed:", "files_removed"), ("Directories Removed:", "dirs_removed"),
            ("Files Skipped:", "files_skipped"), ("Directories Skipped (not empty):", "dirs_skipped_removal"),
            ("Errors:", "errors"), ("Status:", "status")
        ]
        
        for text, key in label_defs:
            label = wx.StaticText(panel, label=text)
            value_label = wx.StaticText(panel, label="N/A")
            value_label.SetFont(wx.Font(wx.FontInfo().Bold()))
            sizer.Add(label, 0, wx.ALIGN_CENTER_VERTICAL)
            sizer.Add(value_label, 1, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
            labels_map[key] = value_label

        panel.SetSizer(sizer)
        return panel, labels_map

    def _create_list_tab_panel(self, title: str, headers: List[str]) -> (wx.Panel, wx.ListCtrl):
        panel = wx.Panel(self.notebook)
        sizer = wx.BoxSizer(wx.VERTICAL)
        list_ctrl = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_VRULES)
        
        for i, header in enumerate(headers):
            list_ctrl.InsertColumn(i, header)

        if len(headers) > 1:
            list_ctrl.SetColumnWidth(0, 60)
            list_ctrl.SetColumnWidth(1, 800)
        else:
            list_ctrl.SetColumnWidth(0, 800)

        sizer.Add(list_ctrl, 1, wx.EXPAND)
        panel.SetSizer(sizer)
        return panel, list_ctrl

    def _create_changes_tab_panel(self) -> (wx.Panel, wx.TextCtrl):
        panel = wx.Panel(self.notebook)
        sizer = wx.BoxSizer(wx.VERTICAL)
        changes_ctrl = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        changes_ctrl.SetFont(wx.Font(10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))

        fg_color = wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT)
        
        self.diff_attr_add = wx.TextAttr(wx.Colour(0, 128, 0))
        self.diff_attr_remove = wx.TextAttr(wx.RED)
        self.diff_attr_header = wx.TextAttr(fg_color, font=wx.Font(wx.FontInfo().Bold()))
        self.diff_attr_normal = wx.TextAttr(fg_color)
        
        sizer.Add(changes_ctrl, 1, wx.EXPAND)
        panel.SetSizer(sizer)
        return panel, changes_ctrl

    def _create_sizers(self):
        top_sizer = wx.BoxSizer(wx.VERTICAL)
        
        input_box = wx.StaticBox(self.top_splitter_panel, label="Input")
        self.input_box_sizer = wx.StaticBoxSizer(input_box, wx.VERTICAL)
        self.input_box_sizer.Add(self.text_input_panel, 1, wx.EXPAND | wx.ALL, 5)
        
        top_sizer.Add(self.input_box_sizer, 1, wx.EXPAND | wx.ALL, 5)
        self.top_splitter_panel.SetSizer(top_sizer)

        bottom_sizer = wx.BoxSizer(wx.VERTICAL)
        
        output_box = wx.StaticBox(self.bottom_splitter_panel, label="Output")
        output_box_sizer = wx.StaticBoxSizer(output_box, wx.HORIZONTAL)
        output_box_sizer.Add(self.output_dir_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        output_box_sizer.Add(self.output_dir_ctrl, 1, wx.EXPAND)
        output_box_sizer.Add(self.output_browse_btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)

        options_box = wx.StaticBox(self.bottom_splitter_panel, label="Options")
        options_box_sizer = wx.StaticBoxSizer(options_box, wx.HORIZONTAL)
        options_box_sizer.Add(self.cb_overwrite, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        options_box_sizer.Add(self.cb_quiet, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15)
        options_box_sizer.Add(self.cb_tabs_to_spaces, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        options_box_sizer.Add(self.spin_tabs_to_spaces, 0, wx.ALIGN_CENTER_VERTICAL)

        results_box = wx.StaticBox(self.bottom_splitter_panel, label="Results")
        results_box_sizer = wx.StaticBoxSizer(results_box, wx.VERTICAL)
        results_box_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 5)

        action_sizer = wx.BoxSizer(wx.HORIZONTAL)
        action_sizer.Add(self.dry_run_btn)
        action_sizer.Add(self.parse_btn, 0, wx.LEFT, 5)
        action_sizer.Add(self.save_btn, 0, wx.LEFT, 5)
        action_sizer.Add(self.clear_btn, 0, wx.LEFT, 5)
        action_sizer.AddStretchSpacer()

        bottom_sizer.Add(output_box_sizer, 0, wx.EXPAND | wx.ALL, 5)
        bottom_sizer.Add(options_box_sizer, 0, wx.EXPAND | wx.ALL, 5)
        bottom_sizer.Add(results_box_sizer, 1, wx.EXPAND | wx.ALL, 5)
        bottom_sizer.Add(action_sizer, 0, wx.EXPAND | wx.ALL, 5)

        self.bottom_splitter_panel.SetSizer(bottom_sizer)