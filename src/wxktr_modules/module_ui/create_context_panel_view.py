#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Create Context Panel - View
---------------------------
The View for the Create Context panel in an MVP architecture.

This class is responsible for creating and laying out all the UI widgets.
It exposes widgets to be controlled by the Presenter.
"""

import wx
import wx.lib.scrolledpanel as scrolled
from typing import Dict

class CreateContextPanelView(wx.Panel):
    """The View for the Create Context panel."""
    
    def __init__(self, parent):
        super().__init__(parent)

        self.setting_controls: Dict[str, wx.Control] = {}
        self._create_widgets()

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.Add(self.main_splitter, 1, wx.EXPAND)
        self.SetSizer(main_sizer)
        
    def _create_widgets(self):
        """Creates all the widgets for the panel."""
        self.main_splitter = wx.SplitterWindow(self, style=wx.SP_LIVE_UPDATE | wx.SP_3D)
        self.main_splitter.SetSashGravity(0.33)

        left_panel = self._create_left_panel(self.main_splitter)
        right_panel = self._create_right_panel(self.main_splitter)

        self.main_splitter.SplitVertically(left_panel, right_panel, 500)
        self.main_splitter.SetSashGravity(0.33)
        
    def _create_left_panel(self, parent):
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        config_sizer = wx.StaticBoxSizer(wx.VERTICAL, panel, "Config File")
        config_grid = wx.FlexGridSizer(cols=2, vgap=5, hgap=5)
        config_grid.AddGrowableCol(1)

        self.config_path_ctrl = wx.TextCtrl(panel)
        config_grid.Add(wx.StaticText(panel, label="Config File:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        config_grid.Add(self.config_path_ctrl, 1, wx.EXPAND)

        self.load_config_btn = wx.Button(panel, label="Browse...")
        config_grid.AddSpacer(0)
        config_grid.Add(self.load_config_btn, 0, wx.TOP | wx.ALIGN_RIGHT, 5)

        config_sizer.Add(config_grid, 1, wx.EXPAND | wx.ALL, 5)
        sizer.Add(config_sizer, 0, wx.EXPAND | wx.ALL, 5)

        sections_sizer = wx.StaticBoxSizer(wx.VERTICAL, panel, "Sections")
        self.sections_list_box = wx.ListBox(panel)
        sections_sizer.Add(self.sections_list_box, 1, wx.EXPAND | wx.ALL, 5)

        section_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.add_section_btn = wx.Button(panel, label="Add")
        self.copy_section_btn = wx.Button(panel, label="Copy")
        self.delete_section_btn = wx.Button(panel, label="Delete")
        section_btn_sizer.Add(self.add_section_btn)
        section_btn_sizer.Add(self.copy_section_btn, 0, wx.LEFT, 5)
        section_btn_sizer.Add(self.delete_section_btn, 0, wx.LEFT, 5)

        sections_sizer.Add(section_btn_sizer, 0, wx.ALL, 5)
        sizer.Add(sections_sizer, 1, wx.EXPAND | wx.ALL, 5)

        settings_box = wx.StaticBox(panel, label="Settings")
        settings_box_sizer = wx.StaticBoxSizer(settings_box, wx.VERTICAL)

        self.scrolled_settings_panel = scrolled.ScrolledPanel(panel, style=wx.TAB_TRAVERSAL)
        self.scrolled_settings_panel.SetupScrolling(scroll_x=False)

        self.settings_grid_sizer = wx.FlexGridSizer(cols=2, vgap=5, hgap=10)
        self.settings_grid_sizer.AddGrowableCol(1)

        self._create_setting_controls(self.scrolled_settings_panel)

        self.scrolled_settings_panel.SetSizer(self.settings_grid_sizer)
        settings_box_sizer.Add(self.scrolled_settings_panel, 1, wx.EXPAND | wx.ALL, 5)

        self.save_config_btn = wx.Button(panel, label="Save Config File")
        settings_box_sizer.Add(self.save_config_btn, 0, wx.EXPAND | wx.ALL, 5)

        sizer.Add(settings_box_sizer, 2, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(sizer)
        return panel

    def _create_setting_controls(self, parent):
        def add_setting(key, label, control):
            self.settings_grid_sizer.Add(wx.StaticText(parent, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            self.settings_grid_sizer.Add(control, 1, wx.EXPAND)
            self.setting_controls[key] = control

        def add_multiline_setting(key, label, control):
            label_widget = wx.StaticText(parent, label=label)
            self.settings_grid_sizer.Add(label_widget, 0, wx.ALIGN_TOP | wx.TOP, 5)
            self.settings_grid_sizer.Add(control, 1, wx.EXPAND)
            self.setting_controls[key] = control
        
        add_setting('filetypes', "File Types (csv):", wx.TextCtrl(parent))
        
        excluded_ctrl = wx.TextCtrl(parent, style=wx.TE_MULTILINE)
        excluded_ctrl.SetMinSize((-1, 60))
        add_multiline_setting('excludedfiles', "Excluded Files (csv):", excluded_ctrl)
        
        include_ctrl = wx.TextCtrl(parent, style=wx.TE_MULTILINE)
        include_ctrl.SetMinSize((-1, 60))
        add_multiline_setting('include', "Included Files (csv):", include_ctrl)
        
        add_setting('outputfile', "Output file (for context):", wx.TextCtrl(parent))

        subdirs_mode_ctrl = wx.ComboBox(parent, choices=['#NONE', '#ALL', 'LIST'], style=wx.CB_READONLY)
        add_setting('subdirectories_mode', "Subdirectories Mode:", subdirs_mode_ctrl)

        self.subdirs_list_label = wx.StaticText(parent, label="Directory List (if LIST):")
        subdirs_list_ctrl = wx.TextCtrl(parent, style=wx.TE_MULTILINE)
        subdirs_list_ctrl.SetMinSize((-1, 60))
        self.settings_grid_sizer.Add(self.subdirs_list_label, 0, wx.ALIGN_TOP | wx.TOP, 5)
        self.settings_grid_sizer.Add(subdirs_list_ctrl, 1, wx.EXPAND)
        self.setting_controls['subdirs_list'] = subdirs_list_ctrl
        self.subdirs_list_label.Hide()
        subdirs_list_ctrl.Hide()
        
        checkboxes = {
            'includepreamble': "Include Preamble",
            'includeappendix': "Include Appendix",
            'summary': "Summary section in context",
            'filetree': "Include File Tree",
            'formattinginstructions': "Include Formatting Instructions",
        }
        for key, label in checkboxes.items():
            self.setting_controls[key] = wx.CheckBox(parent, label=label)
            self.settings_grid_sizer.AddSpacer(0)
            self.settings_grid_sizer.Add(self.setting_controls[key])

    def _create_right_panel(self, parent):
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        vertical_splitter = wx.SplitterWindow(panel, style=wx.SP_LIVE_UPDATE | wx.SP_3D)
        vertical_splitter.SetSashGravity(0.65)

        top_panel = wx.Panel(vertical_splitter)
        top_sizer = wx.BoxSizer(wx.HORIZONTAL)

        context_pa_splitter = wx.SplitterWindow(top_panel, style=wx.SP_LIVE_UPDATE | wx.SP_3D)
        context_pa_splitter.SetSashGravity(0.7)

        self.context_panel = wx.Panel(context_pa_splitter)
        context_panel_main_sizer = wx.BoxSizer(wx.VERTICAL)

        context_box_sizer = wx.StaticBoxSizer(wx.VERTICAL, self.context_panel, "Context Preview")
        self.preview_ctrl = self._create_text_panel(self.context_panel, editable=False)
        context_box_sizer.Add(self.preview_ctrl, 1, wx.EXPAND | wx.ALL, 5)
        context_panel_main_sizer.Add(context_box_sizer, 1, wx.EXPAND | wx.ALL, 5)

        bottom_controls_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.copy_btn = wx.Button(self.context_panel, label="Copy to Clipboard")
        self.save_btn = wx.Button(self.context_panel, label="Save Context")
        self.save_as_btn = wx.Button(self.context_panel, label="Save Context As...")
        bottom_controls_sizer.Add(self.copy_btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        bottom_controls_sizer.Add(self.save_btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        bottom_controls_sizer.Add(self.save_as_btn, 0, wx.ALIGN_CENTER_VERTICAL)

        bottom_controls_sizer.AddStretchSpacer()

        self.token_count_label = wx.StaticText(self.context_panel, label="Estimated Tokens: N/A")
        token_font = self.token_count_label.GetFont()
        token_font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.token_count_label.SetFont(token_font)
        bottom_controls_sizer.Add(self.token_count_label, 0, wx.ALIGN_CENTER_VERTICAL)

        context_panel_main_sizer.Add(bottom_controls_sizer, 0, wx.EXPAND | wx.ALL, 5)
        self.context_panel.SetSizer(context_panel_main_sizer)

        pa_panel = self._create_text_fields_panel(context_pa_splitter)
        context_pa_splitter.SplitVertically(self.context_panel, pa_panel)
        top_sizer.Add(context_pa_splitter, 1, wx.EXPAND)
        top_panel.SetSizer(top_sizer)

        file_lists_panel = self._create_file_lists_panel(vertical_splitter)
        vertical_splitter.SplitHorizontally(top_panel, file_lists_panel)
        sizer.Add(vertical_splitter, 1, wx.EXPAND)

        log_box = wx.StaticBox(panel, label="Generation Log")
        log_box_sizer = wx.StaticBoxSizer(log_box, wx.VERTICAL)
        self.log_ctrl = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        self.log_ctrl.SetFont(wx.Font(9, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        log_box_sizer.Add(self.log_ctrl, 1, wx.EXPAND | wx.ALL, 5)
        sizer.Add(log_box_sizer, 0, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(sizer)
        return panel

    def _create_text_panel(self, parent, editable=True):
        if editable:
            ctrl = wx.TextCtrl(parent, style=wx.TE_MULTILINE | wx.TE_RICH2 | wx.TE_WORDWRAP)
        else:
            ctrl = wx.TextCtrl(parent, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2 | wx.TE_WORDWRAP)
        ctrl.SetFont(wx.Font(10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        return ctrl

    def _create_text_fields_panel(self, parent):
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        preamble_box = wx.StaticBox(panel, label="Preamble")
        preamble_box_sizer = wx.StaticBoxSizer(preamble_box, wx.VERTICAL)
        self.preamble_ctrl = self._create_text_panel(panel, editable=True)
        self.preamble_ctrl.SetHint("Enter preamble text or use {filename} to include file content...")
        preamble_box_sizer.Add(self.preamble_ctrl, 1, wx.EXPAND | wx.ALL, 5)

        self.preamble_ctrl_copy_btn = wx.Button(panel, label="Copy Preamble")
        preamble_box_sizer.Add(self.preamble_ctrl_copy_btn, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
        sizer.Add(preamble_box_sizer, 1, wx.EXPAND | wx.ALL, 5)

        appendix_box = wx.StaticBox(panel, label="Appendix")
        appendix_box_sizer = wx.StaticBoxSizer(appendix_box, wx.VERTICAL)
        self.appendix_ctrl = self._create_text_panel(panel, editable=True)
        self.appendix_ctrl.SetHint("Enter appendix text or use {filename} to include file content...")
        appendix_box_sizer.Add(self.appendix_ctrl, 1, wx.EXPAND | wx.ALL, 5)

        self.appendix_ctrl_copy_btn = wx.Button(panel, label="Copy Appendix")
        appendix_box_sizer.Add(self.appendix_ctrl_copy_btn, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
        sizer.Add(appendix_box_sizer, 1, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(sizer)
        return panel

    def _create_file_lists_panel(self, parent):
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.HORIZONTAL)

        included_box = wx.StaticBox(panel, label="Included Files")
        included_box_sizer = wx.StaticBoxSizer(included_box, wx.VERTICAL)
        self.included_files_ctrl = wx.ListBox(panel, style=wx.LB_EXTENDED)
        included_box_sizer.Add(self.included_files_ctrl, 1, wx.EXPAND | wx.ALL, 5)
        sizer.Add(included_box_sizer, 1, wx.EXPAND | wx.ALL, 5)

        skipped_box = wx.StaticBox(panel, label="Excluded/Skipped Files")
        skipped_box_sizer = wx.StaticBoxSizer(skipped_box, wx.VERTICAL)
        self.skipped_files_ctrl = wx.ListBox(panel, style=wx.LB_EXTENDED)
        skipped_box_sizer.Add(self.skipped_files_ctrl, 1, wx.EXPAND | wx.ALL, 5)
        sizer.Add(skipped_box_sizer, 1, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(sizer)
        return panel