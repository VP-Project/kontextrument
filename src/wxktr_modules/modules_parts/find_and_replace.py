import wx
import wx.stc as stc
import os
import re

class FindReplaceDialog(wx.Dialog):
    """A dialog for find and replace operations in the code editor."""
    def __init__(self, parent, editor):
        """Initializes the Find and Replace dialog."""
        super().__init__(parent, title="Find and Replace", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.editor = editor

        main_sizer = wx.BoxSizer(wx.VERTICAL)

        grid_sizer = wx.FlexGridSizer(2, 2, 5, 5)

        find_label = wx.StaticText(self, label="Find:")
        self.find_text = wx.TextCtrl(self, style=wx.TE_MULTILINE)
        grid_sizer.Add(find_label, 0, wx.ALIGN_TOP | wx.TOP, 4)
        grid_sizer.Add(self.find_text, 1, wx.EXPAND)

        replace_label = wx.StaticText(self, label="Replace with:")
        self.replace_text = wx.TextCtrl(self, style=wx.TE_MULTILINE)
        grid_sizer.Add(replace_label, 0, wx.ALIGN_TOP | wx.TOP, 4)
        grid_sizer.Add(self.replace_text, 1, wx.EXPAND)

        grid_sizer.AddGrowableCol(1)
        main_sizer.Add(grid_sizer, 1, wx.EXPAND | wx.ALL, 10)

        options_box = wx.StaticBox(self, label="Options")
        options_sizer = wx.StaticBoxSizer(options_box, wx.VERTICAL)

        self.case_sensitive = wx.CheckBox(self, label="Case sensitive")
        self.whole_word = wx.CheckBox(self, label="Whole word")
        self.use_regex = wx.CheckBox(self, label="Use regular expressions")

        options_sizer.Add(self.case_sensitive, 0, wx.ALL, 2)
        options_sizer.Add(self.whole_word, 0, wx.ALL, 2)
        options_sizer.Add(self.use_regex, 0, wx.ALL, 2)

        main_sizer.Add(options_sizer, 0, wx.EXPAND | wx.ALL, 10)

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.find_btn = wx.Button(self, label="Find Next")
        self.replace_btn = wx.Button(self, label="Replace")
        self.replace_all_btn = wx.Button(self, label="Replace All")
        close_btn = wx.Button(self, wx.ID_CLOSE, label="Close")

        button_sizer.Add(self.find_btn, 0, wx.ALL, 5)
        button_sizer.Add(self.replace_btn, 0, wx.ALL, 5)
        button_sizer.Add(self.replace_all_btn, 0, wx.ALL, 5)
        button_sizer.AddStretchSpacer()
        button_sizer.Add(close_btn, 0, wx.ALL, 5)

        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 5)

        self.SetSizer(main_sizer)
        self.SetSize((500, 300))

        self.find_btn.Bind(wx.EVT_BUTTON, self.on_find_next)
        self.replace_btn.Bind(wx.EVT_BUTTON, self.on_replace)
        self.replace_all_btn.Bind(wx.EVT_BUTTON, self.on_replace_all)
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.Hide())
        self.Bind(wx.EVT_CLOSE, lambda e: self.Hide())

    def on_find_next(self, event):
        """Find the next occurrence of the search text."""
        search_text = self.find_text.GetValue()
        if not search_text:
            return

        flags = 0
        if self.case_sensitive.GetValue():
            flags |= stc.STC_FIND_MATCHCASE
        if self.whole_word.GetValue():
            flags |= stc.STC_FIND_WHOLEWORD
        if self.use_regex.GetValue():
            flags |= stc.STC_FIND_REGEXP

        current_pos = self.editor.GetCurrentPos()
        self.editor.SetTargetStart(current_pos)
        self.editor.SetTargetEnd(self.editor.GetTextLength())
        self.editor.SetSearchFlags(flags)

        pos = self.editor.SearchInTarget(search_text)

        if pos == -1:
            self.editor.SetTargetStart(0)
            self.editor.SetTargetEnd(self.editor.GetTextLength())
            pos = self.editor.SearchInTarget(search_text)

        if pos != -1:
            self.editor.SetSelection(self.editor.GetTargetStart(), self.editor.GetTargetEnd())
            self.editor.EnsureCaretVisible()
        else:
            wx.MessageBox("Text not found.", "Find", wx.OK | wx.ICON_INFORMATION, self)

    def on_replace(self, event):
        """Replace the currently selected occurrence."""
        search_text = self.find_text.GetValue()
        replace_text = self.replace_text.GetValue()
        
        if not search_text:
            return

        sel_start = self.editor.GetSelectionStart()
        sel_end = self.editor.GetSelectionEnd()
        selected_text = self.editor.GetTextRange(sel_start, sel_end)

        flags = 0
        if self.case_sensitive.GetValue():
            flags |= stc.STC_FIND_MATCHCASE
        if self.use_regex.GetValue():
            flags |= stc.STC_FIND_REGEXP

        matches = False
        if self.use_regex.GetValue():
            import re
            pattern_flags = 0 if self.case_sensitive.GetValue() else re.IGNORECASE
            matches = re.match(search_text, selected_text, pattern_flags) is not None
        else:
            if self.case_sensitive.GetValue():
                matches = selected_text == search_text
            else:
                matches = selected_text.lower() == search_text.lower()

        if matches:
            if self.use_regex.GetValue():
                import re
                pattern_flags = 0 if self.case_sensitive.GetValue() else re.IGNORECASE
                replaced = re.sub(search_text, replace_text, selected_text, flags=pattern_flags)
                self.editor.ReplaceSelection(replaced)
            else:
                self.editor.ReplaceSelection(replace_text)
        
        self.on_find_next(event)

    def on_replace_all(self, event):
        """Replace all occurrences."""
        search_text = self.find_text.GetValue()
        replace_text = self.replace_text.GetValue()
        
        if not search_text:
            return

        count = 0
        self.editor.BeginUndoAction()

        flags = 0
        if self.case_sensitive.GetValue():
            flags |= stc.STC_FIND_MATCHCASE
        if self.whole_word.GetValue():
            flags |= stc.STC_FIND_WHOLEWORD
        if self.use_regex.GetValue():
            flags |= stc.STC_FIND_REGEXP

        self.editor.SetTargetStart(0)
        self.editor.SetTargetEnd(self.editor.GetTextLength())
        self.editor.SetSearchFlags(flags)

        while True:
            pos = self.editor.SearchInTarget(search_text)
            if pos == -1:
                break

            matched_text = self.editor.GetTextRange(self.editor.GetTargetStart(), self.editor.GetTargetEnd())
            
            if self.use_regex.GetValue():
                import re
                pattern_flags = 0 if self.case_sensitive.GetValue() else re.IGNORECASE
                replaced = re.sub(search_text, replace_text, matched_text, flags=pattern_flags)
                self.editor.ReplaceTarget(replaced)
                new_pos = self.editor.GetTargetStart() + len(replaced)
            else:
                self.editor.ReplaceTarget(replace_text)
                new_pos = self.editor.GetTargetStart() + len(replace_text)

            count += 1
            
            self.editor.SetTargetStart(new_pos)
            self.editor.SetTargetEnd(self.editor.GetTextLength())

        self.editor.EndUndoAction()
        wx.MessageBox(f"Replaced {count} occurrence(s).", "Replace All", wx.OK | wx.ICON_INFORMATION, self)