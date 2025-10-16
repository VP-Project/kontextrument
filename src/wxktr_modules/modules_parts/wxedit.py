"""
wxedit.py – Main entry point for the editor component.
This file is now simplified to import the core editor and provide
an example usage frame.
"""

import wx
import wx.stc as stc
import sys
import os
from .editor_core import CodeEditor

class Frame(wx.Frame):
    """A simple wx.Frame to host and demonstrate the CodeEditor."""
    def __init__(self, filepath=None):
        """Initializes the main application frame."""
        title = "Smart editor – Python | C-family | Markdown | JSON | YAML | INI/TOML"
        self.filepath = filepath
        if self.filepath:
            title = f"{os.path.basename(self.filepath)} - {title}"
        
        super().__init__(None, title=title, size=(900, 600))
        self.editor = CodeEditor(self, filepath=self.filepath)
        
        self.Bind(wx.EVT_CLOSE, self.on_close)
        
        self.editor.Bind(stc.EVT_STC_MODIFIED, self.on_editor_modified)

    def on_editor_modified(self, event):
        """When the editor content changes, update the title."""
        self.update_title()
        event.Skip()

    def update_title(self):
        """Adds an asterisk to the title if the file is modified."""
        title = self.GetTitle().lstrip('* ')
        if self.editor.IsModified():
            self.SetTitle(f"* {title}")
        else:
            self.SetTitle(title)

    def save_file(self) -> bool:
        """Saves the file, handling 'Save As' logic. Returns success."""
        if not self.filepath:
            with wx.FileDialog(self, "Save file", wildcard="All files (*.*)|*.*",
                              style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dlg:
                if dlg.ShowModal() == wx.ID_CANCEL:
                    return False
                self.filepath = dlg.GetPath()
                self.editor.filepath = self.filepath
        
        try:
            with open(self.filepath, 'w', encoding='utf-8', newline='') as f:
                f.write(self.editor.GetText())
            self.editor.SetSavePoint()
            self.editor.guess_and_set_lexer(self.filepath)
            return True
        except IOError as e:
            wx.LogError(f"Error saving file '{self.filepath}': {e}")
            return False

    def on_close(self, event):
        """On closing, check for modifications and ask to save."""
        if self.editor.IsModified():
            result = wx.MessageBox("File has changed. Save before closing?",
                                  "Confirm",
                                  wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION,
                                  self)
            if result == wx.YES:
                if self.save_file():
                    self.Destroy()
                else:
                    if event.CanVeto(): event.Veto()
            elif result == wx.NO:
                self.Destroy()
            else:
                if event.CanVeto(): event.Veto()
        else:
            self.Destroy()


if __name__ == "__main__":
    app = wx.App(False)
    
    fpath = sys.argv[1] if len(sys.argv) > 1 else None
    
    frame = Frame(filepath=fpath)
    frame.Show()
    app.MainLoop()