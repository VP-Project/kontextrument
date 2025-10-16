#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kontextrument GUI
------------------------------------
A unified graphical user interface for the Kontextrument, combining 'create'
and 'apply' functionalities into a single tabbed application.
"""

import wx
import sys
import os
import configparser
import importlib
import traceback
from collections import OrderedDict
from pubsub import pub

from wxktr_modules.wxmodmanager import ModuleManagerPanel
from wxktr_modules.wxlauncher import LauncherPanel

try:
    from ktr.__version__ import version
except ImportError:
    version = "0.0"


class DraggableNotebook(wx.Notebook):
    """
    A wx.Notebook subclass that allows reordering tabs via drag-and-drop.
    """
    def __init__(self, parent, id=wx.ID_ANY, pos=wx.DefaultPosition,
                 size=wx.DefaultSize, style=0, name="notebook"):
        super().__init__(parent, id, pos, size, style, name)

        self._dragging = False
        self._drag_source_index = -1

        self.Bind(wx.EVT_LEFT_DOWN, self.on_left_down)
        self.Bind(wx.EVT_LEFT_UP, self.on_left_up)
        self.Bind(wx.EVT_MOTION, self.on_motion)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.on_leave_window)

    def on_left_down(self, event):
        """Handles the start of a drag operation."""
        hit_test_result, flags = self.HitTest(event.GetPosition())

        if hit_test_result != wx.NOT_FOUND and (flags & wx.BK_HITTEST_ONLABEL):
            self._dragging = True
            self._drag_source_index = hit_test_result
            self.CaptureMouse()
        event.Skip()

    def on_left_up(self, event):
        """Handles the mouse left-up event to end a drag operation."""
        if self._dragging:
            self._dragging = False
            self._drag_source_index = -1
            if self.HasCapture():
                self.ReleaseMouse()
        event.Skip()

    def on_motion(self, event):
        """Handles moving a tab while dragging."""
        if not self._dragging or not event.Dragging():
            event.Skip()
            return

        hit_test_result, flags = self.HitTest(event.GetPosition())

        if hit_test_result != wx.NOT_FOUND and (flags & wx.BK_HITTEST_ONLABEL):
            if hit_test_result != self._drag_source_index:
                self.move_page(self._drag_source_index, hit_test_result)
                self._drag_source_index = hit_test_result
        event.Skip()

    def on_leave_window(self, event):
        """Handles the mouse leaving the control to cancel a drag operation."""
        if self._dragging:
            self._dragging = False
            self._drag_source_index = -1
            if self.HasCapture():
                self.ReleaseMouse()
        event.Skip()
    
    def force_release_mouse(self):
        """Forcefully releases mouse capture and resets dragging state."""
        if self.HasCapture():
            self.ReleaseMouse()
        self._dragging = False
        self._drag_source_index = -1

    def move_page(self, src_index, dest_index):
        """Moves a page from src_index to dest_index."""
        if src_index == dest_index:
            return

        page = self.GetPage(src_index)
        label = self.GetPageText(src_index)
        image_id = self.GetPageImage(src_index)

        self.Freeze()

        try:
            self.RemovePage(src_index)

            self.InsertPage(dest_index, page, label, select=True, imageId=image_id)
        finally:
            self.Thaw()


class UnifiedFrame(wx.Frame):
    """Main application frame that holds the tabbed interface."""
    def __init__(self, initial_directory=None):
        """Initializes the main application frame."""
        title = f"Kontextrument GUI v{version}"
        super().__init__(None, title=title, size=(1600, 900))
        self.SetMinSize((1200, 700))

        self.working_directory = initial_directory
        self.launcher_active = (initial_directory is None)

        self._setup_modules()

        self._load_app_icon()

        self.notebook = DraggableNotebook(self)

        if self.launcher_active:
            self._load_launcher_panel()
        else:
            self._load_main_panels()
            try:
                os.chdir(self.working_directory)
            except Exception as e:
                print(f"Warning: Could not change to directory {self.working_directory}: {e}")

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.notebook, 1, wx.EXPAND)
        self.SetSizer(sizer)

        self.CreateStatusBar(2)
        self.SetStatusWidths([-1, 200])
        self.progress_bar = wx.Gauge(self, range=100, style=wx.GA_HORIZONTAL | wx.GA_SMOOTH)
        self.progress_bar.Hide()
        self._update_status_text()

        self.Layout()
        self.Centre()

        self.Bind(wx.EVT_SIZE, self.on_size)
        self.Bind(wx.EVT_IDLE, self.on_idle)
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.on_tab_changed)

        pub.subscribe(self.on_status_update, "status.update")
        pub.subscribe(self.on_progress_pulse, "progress.pulse")
        pub.subscribe(self.on_directory_selected, "directory.selected")
    
    def _setup_modules(self):
        """
        Discovers modules, reads config, and determines which modules to load.
        """
        from wxktr_modules.settings_manager import get_settings_manager
        self.settings_manager = get_settings_manager()
        
        self.manageable_modules = OrderedDict([
            ('create', {
                'display_name': 'Create Context', 'module_name': 'wxktr_modules.create_context_panel',
                'class_name': 'CreateContextPanel', 'instance_name': 'create_panel'}),
            ('browser', {
                'display_name': 'Browser', 'module_name': 'wxktr_modules.wxbrowse',
                'class_name': 'BrowserPanel', 'instance_name': 'browser_panel'}),
            ('apply', {
                'display_name': 'Apply Context', 'module_name': 'wxktr_modules.apply_context_panel',
                'class_name': 'ApplyContextPanel', 'instance_name': 'apply_panel'}),
            ('workspace', {
                'display_name': 'Workspace', 'module_name': 'wxktr_modules.wxworkspace',
                'class_name': 'WorkspacePanel', 'instance_name': 'workspace_panel'}),
            ('Git', {
                'display_name': 'Git', 'module_name': 'wxktr_modules.wxgit',
                'class_name': 'GitPanel', 'instance_name': 'git_panel'}),
        ])
        
        for key, info in self.manageable_modules.items():
            enabled = self.settings_manager.get_module_enabled(key)
            info['enabled_in_config'] = enabled
            info['status'] = 'disabled'
            info['panel_class'] = None
            info['error_message'] = None
            info['error_traceback'] = None
            
            if enabled:
                try:
                    module = importlib.import_module(info['module_name'])
                    panel_class = getattr(module, info['class_name'])
                    info['panel_class'] = panel_class
                    info['status'] = 'loaded'
                except Exception as e:
                    error_msg = str(e)
                    error_tb = traceback.format_exc()
                    
                    print(f"Warning: Failed to load module '{key}'. It will be disabled. Error: {error_msg}", file=sys.stderr)
                    print(f"Traceback:\n{error_tb}", file=sys.stderr)
                    
                    info['status'] = 'failed'
                    info['error_message'] = error_msg
                    info['error_traceback'] = error_tb
                    
                    self.settings_manager.set_module_enabled(key, False)

    def _load_launcher_panel(self):
        """Load only the launcher panel."""
        self.launcher_panel = LauncherPanel(self.notebook)
        self.notebook.AddPage(self.launcher_panel, "Select Directory")

    def _load_main_panels(self):
        """
        Instantiates and adds the main panels to the notebook based on the module setup.
        """
        for key, info in self.manageable_modules.items():
            if info['status'] == 'loaded' and info['panel_class']:
                try:
                    panel_instance = info['panel_class'](self.notebook)
                    setattr(self, info['instance_name'], panel_instance)
                    self.notebook.AddPage(panel_instance, info['display_name'])
                except Exception as e:
                    error_msg = str(e)
                    error_tb = traceback.format_exc()
                    
                    print(f"ERROR: Could not instantiate panel for module '{key}': {error_msg}", file=sys.stderr)
                    print(f"Traceback:\n{error_tb}", file=sys.stderr)
                    
                    info['status'] = 'failed'
                    info['error_message'] = error_msg
                    info['error_traceback'] = error_tb
        
        self.module_manager_panel = ModuleManagerPanel(self.notebook, self.manageable_modules)
        self.notebook.AddPage(self.module_manager_panel, "Modules")
        
    def _load_app_icon(self):
        """
        Attempts to load the application icon.
        This method is robust for both development and PyInstaller builds.
        """
        icon_path = ""
        try:
            if getattr(sys, 'frozen', False):
                base_path = os.path.dirname(sys.executable)
            else:
                base_path = os.path.abspath(".")

            icon_path = os.path.join(base_path, "assets", "icon.png")
            
            if os.path.exists(icon_path):
                icon = wx.Icon(icon_path, wx.BITMAP_TYPE_PNG)
                self.SetIcon(icon)
            else:
                print(f"Warning: Icon file not found at {icon_path}")
                
        except Exception as e:
            print(f"Warning: Could not load application icon from {icon_path}: {e}")
    
    def on_directory_selected(self, directory_path: str):
        """PubSub handler for when a directory is selected from the launcher."""
        self.working_directory = directory_path
        self.launcher_active = False
        
        try:
            os.chdir(self.working_directory)
        except Exception as e:
            wx.MessageBox(
                f"Could not change to directory:\n{directory_path}\n\nError: {e}",
                "Error",
                wx.OK | wx.ICON_ERROR,
                self
            )
            return
        
        for i in range(self.notebook.GetPageCount()):
            if self.notebook.GetPage(i) == self.launcher_panel:
                self.notebook.DeletePage(i)
                break
        
        self._load_main_panels()
        
        self._update_status_text()
        
        if self.notebook.GetPageCount() > 0:
            self.notebook.SetSelection(0)
    
    def _update_status_text(self):
        """Update status bar with current working directory."""
        if self.working_directory:
            self.SetStatusText(f"Working Directory: {self.working_directory}", 0)
        else:
            self.SetStatusText("Ready", 0)
        
    def on_size(self, event):
        """Reposition the progress bar when the window is resized."""
        self.reposition_progress_bar()
        event.Skip()

    def on_idle(self, event):
        """Position the progress bar once the window is stable."""
        self.reposition_progress_bar()
        self.Unbind(wx.EVT_IDLE)

    def on_close(self, event):
        """Handle the window close event, allowing panels to save settings."""
        for i in range(self.notebook.GetPageCount()):
            panel = self.notebook.GetPage(i)
            if hasattr(panel, 'handle_exit_request'):
                if not panel.handle_exit_request():
                    event.Veto()
                    return
        
        from wxktr_modules.task_manager import get_task_manager
        get_task_manager().shutdown(wait=False)
        
        self.Destroy()

    def on_tab_changed(self, event):
        """Reset status bar when switching tabs."""
        if hasattr(self.notebook, 'force_release_mouse'):
            self.notebook.force_release_mouse()

        self.on_progress_pulse(False)
        self._update_status_text()
        
        if not self.launcher_active:
            selected_page = self.notebook.GetCurrentPage()
            if hasattr(self, 'browser_panel') and selected_page == self.browser_panel:
                if hasattr(self.browser_panel, 'on_panel_shown'):
                    self.browser_panel.on_panel_shown()
        
        event.Skip()

    def reposition_progress_bar(self):
        """Calculates and sets the position of the progress bar in the status bar."""
        if self.GetStatusBar() and self.GetStatusBar().GetFieldsCount() > 1:
            try:
                rect = self.GetStatusBar().GetFieldRect(1)
                self.progress_bar.SetPosition((rect.x + 2, rect.y + 2))
                self.progress_bar.SetSize((rect.width - 4, rect.height - 4))
            except wx.wxAssertionError:
                pass

    def on_status_update(self, text: str, pane: int = 0):
        """PubSub handler for updating the status bar text."""
        if self:
            self.SetStatusText(text, pane)

    def on_progress_pulse(self, pulse: bool):
        """PubSub handler for controlling the progress bar."""
        if not self: return
        if pulse:
            self.progress_bar.Show()
            self.progress_bar.Pulse()
        else:
            self.progress_bar.SetValue(0)
            self.progress_bar.Hide()

    def set_initial_tab(self, tab_name: str):
        """Sets the initially selected tab based on a given name."""
        if self.launcher_active:
            return
        
        label_map = {
            "create": "Create Context",
            "browser": "Browser",
            "apply": "Apply Context",
            "workspace": "Workspace",
            "modules": "Modules"
        }
        target_label = label_map.get(tab_name.lower())

        index_to_select = 0
        if target_label:
            for i in range(self.notebook.GetPageCount()):
                if self.notebook.GetPageText(i) == target_label:
                    index_to_select = i
                    break

        if self.notebook.GetPageCount() > index_to_select:
            self.notebook.SetSelection(index_to_select)
            fake_event = wx.BookCtrlEvent(wx.wxEVT_COMMAND_NOTEBOOK_PAGE_CHANGED, self.notebook.GetId())
            fake_event.SetSelection(index_to_select)
            self.on_tab_changed(fake_event)

class ContextToolsApp(wx.App):
    """The main wxPython App class."""
    def __init__(self, initial_tab='create', initial_directory=None):
        """Initializes the application."""
        self.initial_tab = initial_tab
        self.initial_directory = initial_directory
        super().__init__(False)

    def OnInit(self):
        """Initializes the main frame and shows it."""
        from wxktr_modules.settings_manager import SettingsManager
        self.SetAppName(SettingsManager.APP_NAME)
        self.SetVendorName(SettingsManager.VENDOR_NAME)
        frame = UnifiedFrame(initial_directory=self.initial_directory)
        frame.set_initial_tab(self.initial_tab)
        frame.Show(True)
        return True

def run(initial_tab='create', initial_directory=None):
    """Main entry point to run the unified wxPython GUI."""
    app = ContextToolsApp(initial_tab, initial_directory)
    app.MainLoop()

if __name__ == '__main__':
    run()