#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Launcher Panel
---------------------------------
A startup panel for selecting the working directory.
Displays directory selection and history of recently used directories.
"""

import wx
import os
from datetime import datetime
from pubsub import pub
from .settings_manager import get_settings_manager


class LauncherPanel(wx.Panel):
    """A wx.Panel for selecting a working directory at application startup."""

    def __init__(self, parent):
        """Initializes the Launcher panel."""
        super().__init__(parent)
        
        self.settings = get_settings_manager()
        
        mainsizer = wx.BoxSizer(wx.VERTICAL)

        mainsizer.AddSpacer(50)

        title = wx.StaticText(self, label="Select Working Directory")
        titlefont = title.GetFont()
        titlefont.PointSize += 4
        titlefont = titlefont.Bold()
        title.SetFont(titlefont)
        mainsizer.Add(title, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, 10)

        desctext = wx.StaticText(
            self, label="Choose a directory to work with or select from recent directories below."
        )
        mainsizer.Add(desctext, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, 5)
        mainsizer.AddSpacer(20)

        browsebtn = wx.Button(self, label="Browse for Directory...", size=(200, 35))
        browsebtn.Bind(wx.EVT_BUTTON, self.onbrowse)
        mainsizer.Add(browsebtn, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, 5)
        mainsizer.AddSpacer(30)

        recentlabel = wx.StaticText(self, label="Recent Directories")
        recentfont = recentlabel.GetFont()
        recentfont = recentfont.Bold()
        recentlabel.SetFont(recentfont)
        mainsizer.Add(recentlabel, 0, wx.LEFT | wx.RIGHT | wx.TOP, 20)

        self.historylist = wx.ListBox(self, style=wx.LB_SINGLE | wx.LB_NEEDED_SB)
        self.historylist.Bind(wx.EVT_LISTBOX_DCLICK, self.onhistorydoubleclick)
        mainsizer.Add(self.historylist, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 20)

        btnsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.openbtn = wx.Button(self, label="Open Selected")
        self.openbtn.Bind(wx.EVT_BUTTON, self.onopenselected)
        self.openbtn.Enable(False)
        btnsizer.Add(self.openbtn, 0, wx.ALL, 5)

        self.removebtn = wx.Button(self, label="Remove from History")
        self.removebtn.Bind(wx.EVT_BUTTON, self.onremoveselected)
        self.removebtn.Enable(False)
        btnsizer.Add(self.removebtn, 0, wx.ALL, 5)

        self.clearbtn = wx.Button(self, label="Clear History")
        self.clearbtn.Bind(wx.EVT_BUTTON, self.onclearhistory)
        btnsizer.Add(self.clearbtn, 0, wx.ALL, 5)

        mainsizer.Add(btnsizer, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, 5)

        self.SetSizer(mainsizer)

        self.populatehistorylist()

        self.historylist.Bind(wx.EVT_LISTBOX, self.onhistoryselectionchanged)

    def populatehistorylist(self):
        """Populates the history ListBox with directories."""
        self.historylist.Clear()
        
        directoryhistory = self.settings.get_directory_history()
        
        for entry in directoryhistory:
            path = entry.get("path", "")
            if os.path.isdir(path):
                self.historylist.Append(path)

        self.clearbtn.Enable(self.historylist.GetCount() > 0)

    def onbrowse(self, event):
        """Handles the browse button click."""
        dlg = wx.DirDialog(
            self,
            "Choose a working directory",
            style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST,
        )

        directoryhistory = self.settings.get_directory_history()
        if directoryhistory and os.path.isdir(directoryhistory[0]["path"]):
            dlg.SetPath(directoryhistory[0]["path"])

        if dlg.ShowModal() == wx.ID_OK:
            selectedpath = dlg.GetPath()
            self.selectdirectory(selectedpath)
        dlg.Destroy()

    def onhistorydoubleclick(self, event):
        """Handles a double-click on a history item."""
        selection = self.historylist.GetSelection()
        if selection != wx.NOT_FOUND:
            selectedpath = self.historylist.GetString(selection)
            self.selectdirectory(selectedpath)

    def onhistoryselectionchanged(self, event):
        """Handles a selection change in the history list."""
        hasselection = self.historylist.GetSelection() != wx.NOT_FOUND
        self.openbtn.Enable(hasselection)
        self.removebtn.Enable(hasselection)

    def onopenselected(self, event):
        """Handles the 'Open Selected' button click."""
        selection = self.historylist.GetSelection()
        if selection != wx.NOT_FOUND:
            selectedpath = self.historylist.GetString(selection)
            self.selectdirectory(selectedpath)

    def onremoveselected(self, event):
        """Handles the 'Remove Selected' button click."""
        selection = self.historylist.GetSelection()
        if selection != wx.NOT_FOUND:
            selectedpath = self.historylist.GetString(selection)
            self.settings.removedirectoryfromhistory(selectedpath)
            self.populatehistorylist()
            self.openbtn.Enable(False)
            self.removebtn.Enable(False)

    def onclearhistory(self, event):
        """Handles the 'Clear History' button click."""
        dlg = wx.MessageDialog(
            self,
            "Are you sure you want to clear all directory history?",
            "Clear History",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
        )
        if dlg.ShowModal() == wx.ID_YES:
            self.settings.cleardirectoryhistory()
            self.populatehistorylist()
            self.openbtn.Enable(False)
            self.removebtn.Enable(False)
        dlg.Destroy()

    def selectdirectory(self, directorypath):
        """Select a directory and trigger the callback."""
        if not os.path.isdir(directorypath):
            wx.MessageBox(
                f"The selected directory does not exist:\n{directorypath}",
                "Directory Not Found",
                wx.OK | wx.ICON_ERROR,
                self,
            )
            return

        timestamp = datetime.now().isoformat()
        self.settings.add_directory_to_history(directorypath, timestamp)

        pub.sendMessage("directory.selected", directory_path=directorypath)

    def handleexitrequest(self):
        """Part of the application's exit protocol."""
        return True