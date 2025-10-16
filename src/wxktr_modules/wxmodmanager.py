#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Module Manager Panel
---------------------------------------
Provides a GUI for enabling/disabling modules in the unified application.
"""

import wx
import wx.lib.scrolledpanel
import configparser


class ModuleManagerPanel(wx.Panel):
    """A wx.Panel for enabling and disabling different application modules."""

    def __init__(self, parent, manageable_modules):
        """Initializes the Module Manager panel."""
        super().__init__(parent)
        
        self.manageable_modules = manageable_modules
        
        from .settings_manager import get_settings_manager
        self.settings_manager = get_settings_manager()

        main_sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(self, label="Module Manager")
        title_font = title.GetFont()
        title_font.PointSize += 2
        title_font = title_font.Bold()
        title.SetFont(title_font)
        main_sizer.Add(title, 0, wx.ALL, 10)

        desc = wx.StaticText(
            self,
            label="Enable or disable modules. Changes take effect after restarting the application."
        )
        main_sizer.Add(desc, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        scroll_panel = wx.lib.scrolledpanel.ScrolledPanel(self)
        scroll_panel.SetupScrolling(scroll_x=False, scroll_y=True)
        scroll_sizer = wx.BoxSizer(wx.VERTICAL)

        self.checkboxes = {}
        for key, info in self.manageable_modules.items():
            cb = wx.CheckBox(scroll_panel, label=info['display_name'])
            cb.SetValue(info['enabled_in_config'])
            
            cb.Bind(wx.EVT_CHECKBOX, lambda evt, k=key: self.on_checkbox_changed(k, evt))
            
            scroll_sizer.Add(cb, 0, wx.ALL, 5)
            
            self.checkboxes[key] = cb
            
            if info['status'] == 'failed':
                error_text = wx.StaticText(
                    scroll_panel,
                    label=f"  ⚠ Error: {info.get('error_message', 'Unknown error')}"
                )
                error_text.SetForegroundColour(wx.RED)
                scroll_sizer.Add(error_text, 0, wx.LEFT | wx.BOTTOM, 20)
                
                details_btn = wx.Button(scroll_panel, label="Show Details", size=(100, -1))
                details_btn.Bind(
                    wx.EVT_BUTTON, 
                    lambda evt, k=key: self.on_show_error_details(k)
                )
                scroll_sizer.Add(details_btn, 0, wx.LEFT | wx.BOTTOM, 20)

        scroll_panel.SetSizer(scroll_sizer)
        main_sizer.Add(scroll_panel, 1, wx.EXPAND | wx.ALL, 10)

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        save_btn = wx.Button(self, label="Save Changes")
        save_btn.Bind(wx.EVT_BUTTON, self.on_save)
        
        reset_btn = wx.Button(self, label="Reset to Defaults")
        reset_btn.Bind(wx.EVT_BUTTON, self.on_reset)
        
        button_sizer.Add(save_btn, 0, wx.RIGHT, 5)
        button_sizer.Add(reset_btn, 0)
        
        main_sizer.Add(button_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        self.SetSizer(main_sizer)

    def on_checkbox_changed(self, key, event):
        """Update the module's enabled status when checkbox changes."""
        self.manageable_modules[key]['enabled_in_config'] = event.IsChecked()

    def on_save(self, event):
        """Save the current module configuration."""
        for key, info in self.manageable_modules.items():
            self.settings_manager.set_module_enabled(key, info['enabled_in_config'])
        
        wx.MessageBox(
            "Module configuration saved. Please restart the application for changes to take effect.",
            "Configuration Saved",
            wx.OK | wx.ICON_INFORMATION,
            self
        )

    def on_reset(self, event):
        """Reset all modules to enabled (default state)."""
        result = wx.MessageBox(
            "Are you sure you want to enable all modules?",
            "Confirm Reset",
            wx.YES_NO | wx.ICON_QUESTION,
            self
        )
        
        if result == wx.YES:
            for key, info in self.manageable_modules.items():
                info['enabled_in_config'] = True
                self.checkboxes[key].SetValue(True)

    def on_show_error_details(self, key):
        """Show detailed error information for a failed module."""
        info = self.manageable_modules[key]
        error_msg = info.get('error_message', 'Unknown error')
        error_tb = info.get('error_traceback', 'No traceback available')
        
        dialog = wx.Dialog(self, title=f"Error Details: {info['display_name']}", size=(600, 400))
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        msg_label = wx.StaticText(dialog, label="Error Message:")
        sizer.Add(msg_label, 0, wx.ALL, 10)
        
        msg_text = wx.TextCtrl(dialog, value=error_msg, style=wx.TE_MULTILINE | wx.TE_READONLY)
        sizer.Add(msg_text, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        
        tb_label = wx.StaticText(dialog, label="Traceback:")
        sizer.Add(tb_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        
        tb_text = wx.TextCtrl(dialog, value=error_tb, style=wx.TE_MULTILINE | wx.TE_READONLY)
        sizer.Add(tb_text, 1, wx.EXPAND | wx.ALL, 10)
        
        close_btn = wx.Button(dialog, wx.ID_CLOSE, "Close")
        close_btn.Bind(wx.EVT_BUTTON, lambda e: dialog.Close())
        sizer.Add(close_btn, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        dialog.SetSizer(sizer)
        dialog.ShowModal()
        dialog.Destroy()