#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Workspace Panel - View
----------------------
The View for the Workspace panel in an MVP architecture.

This class is responsible for creating and laying out all the UI widgets.
It exposes widgets to be controlled by the Presenter.
"""

import wx
import wx.stc as stc
import os
import sys

try:
    from ..modules_parts.wxedit import CodeEditor
    from ..modules_parts.wxterm import TerminalPanel
    from ..modules_parts.image_viewer import ImageViewer
    from ..modules_parts.sound_player import SoundPlayer
except ImportError:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from modules_parts.wxedit import CodeEditor
    from modules_parts.wxterm import TerminalPanel
    from modules_parts.image_viewer import ImageViewer
    from modules_parts.sound_player import SoundPlayer


class WorkspacePanelView(wx.Panel):
    """The View for the Workspace panel."""

    def __init__(self, parent, project_settings):
        """Initializes the view, creating all widgets and sizers."""
        super().__init__(parent)
        self.project_settings = project_settings
        self._create_widgets()
        self._create_sizers()
        
    def _create_widgets(self):
        """Creates all the widgets for the panel."""
        self.main_splitter = wx.SplitterWindow(self, style=wx.SP_LIVE_UPDATE)
        
        self.left_panel = wx.Panel(self.main_splitter)
        self.newfolder_button = wx.Button(self.left_panel, label="New Folder")
        self.newfile_button = wx.Button(self.left_panel, label="New File")
        self.file_tree = wx.TreeCtrl(self.left_panel, style=wx.TR_DEFAULT_STYLE | wx.TR_HIDE_ROOT)
        
        self.right_panel = wx.Panel(self.main_splitter)
        self.right_splitter = wx.SplitterWindow(self.right_panel, style=wx.SP_LIVE_UPDATE)

        self.content_container_panel = wx.Panel(self.right_splitter)
        
        self.toolbar_panel = wx.Panel(self.content_container_panel)
        self.save_button = wx.Button(self.toolbar_panel, label="Save")
        self.revert_button = wx.Button(self.toolbar_panel, label="Revert")
        self.find_button = wx.Button(self.toolbar_panel, label="Find/Replace...")
        self.delete_button = wx.Button(self.toolbar_panel, label="Delete")
        self.zoom_in_button = wx.Button(self.toolbar_panel, label="Zoom In")
        self.zoom_out_button = wx.Button(self.toolbar_panel, label="Zoom Out")
        self.fit_button = wx.Button(self.toolbar_panel, label="Fit")
        self.actual_size_button = wx.Button(self.toolbar_panel, label="100%")
        
        self.editor = CodeEditor(self.content_container_panel, filepath=None)
        self.image_viewer = ImageViewer(self.content_container_panel)
        self.sound_player = SoundPlayer(self.content_container_panel)
        self.image_viewer.Hide()
        self.sound_player.Hide()

        self.terminal_panel = TerminalPanel(self.right_splitter, self.project_settings)

    def _create_sizers(self):
        """Lays out all the created widgets using sizers."""
        main_view_sizer = wx.BoxSizer(wx.VERTICAL)
        main_view_sizer.Add(self.main_splitter, 1, wx.EXPAND)
        self.SetSizer(main_view_sizer)
        
        left_sizer = wx.BoxSizer(wx.VERTICAL)
        file_ops_sizer = wx.BoxSizer(wx.HORIZONTAL)
        file_ops_sizer.Add(self.newfolder_button, 1, wx.EXPAND | wx.ALL, 2)
        file_ops_sizer.Add(self.newfile_button, 1, wx.EXPAND | wx.ALL, 2)
        left_sizer.Add(file_ops_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 5)
        left_sizer.Add(self.file_tree, 1, wx.EXPAND | wx.ALL, 5)
        self.left_panel.SetSizer(left_sizer)
        
        right_sizer = wx.BoxSizer(wx.VERTICAL)
        right_sizer.Add(self.right_splitter, 1, wx.EXPAND)
        self.right_panel.SetSizer(right_sizer)

        content_container_sizer = wx.BoxSizer(wx.VERTICAL)
        toolbar_sizer = wx.BoxSizer(wx.HORIZONTAL)
        toolbar_sizer.Add(self.save_button, 0, wx.RIGHT, 5)
        toolbar_sizer.Add(self.revert_button, 0, wx.RIGHT, 10)
        toolbar_sizer.Add(self.find_button, 0)
        toolbar_sizer.Add(self.delete_button, 0, wx.LEFT, 5)
        toolbar_sizer.AddStretchSpacer()
        toolbar_sizer.Add(self.zoom_in_button, 0, wx.RIGHT, 5)
        toolbar_sizer.Add(self.zoom_out_button, 0, wx.RIGHT, 5)
        toolbar_sizer.Add(self.fit_button, 0, wx.RIGHT, 5)
        toolbar_sizer.Add(self.actual_size_button, 0)
        self.toolbar_panel.SetSizer(toolbar_sizer)

        content_container_sizer.Add(self.toolbar_panel, 0, wx.EXPAND | wx.ALL, 5)
        content_container_sizer.Add(self.editor, 1, wx.EXPAND)
        content_container_sizer.Add(self.image_viewer, 1, wx.EXPAND)
        content_container_sizer.Add(self.sound_player, 1, wx.EXPAND)
        self.content_container_panel.SetSizer(content_container_sizer)

        self.right_splitter.SplitHorizontally(self.content_container_panel, self.terminal_panel, -250)
        self.right_splitter.SetSashGravity(0.75)
        self.main_splitter.SplitVertically(self.left_panel, self.right_panel, 250)
        self.main_splitter.SetSashGravity(0.25)