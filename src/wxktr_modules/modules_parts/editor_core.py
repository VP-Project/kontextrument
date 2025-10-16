"""
editor_core.py – The core CodeEditor widget component.
"""

import wx
import wx.stc as stc
import os
import re
from .lexer_themes import SmartLexerMixin, AutoIndentMixin, MD_CODE_CONTENT_STYLE
from .autocomplete import AutoCompleteMixin

ATTR_INDIC = 0
_FENCE_LINE_RE = re.compile(r'^\s*(?:`{3}|~{3})')

class CodeEditor(AutoCompleteMixin, AutoIndentMixin, SmartLexerMixin, stc.StyledTextCtrl):
    """A wx.stc.StyledTextCtrl with syntax highlighting, auto-indent, and autocomplete."""
    def __init__(self, parent, filepath=None):
        """Initializes the CodeEditor."""
        super().__init__(parent)
        self.filepath = filepath
        self._lang_from_ext = False
        
        self._default_word_chars = self.GetWordChars()

        self.IndicatorSetStyle(ATTR_INDIC, stc.STC_INDIC_ROUNDBOX)
        self.IndicatorSetForeground(ATTR_INDIC, wx.Colour("#FF0080"))
        self.IndicatorSetAlpha(ATTR_INDIC, 80)

        self.SetMarginType(0, stc.STC_MARGIN_NUMBER)
        self._digits = 1
        self._resize_margin()
        self.Bind(stc.EVT_STC_UPDATEUI, self._on_update_ui)

        self.SetTabWidth(4)
        self.SetUseTabs(False)
        self.SetIndent(4)
        self.SetTabIndents(True)
        self.SetBackSpaceUnIndents(True)
        
        self._init_autocomplete()
        
        self.guess_and_set_lexer(self.filepath)
        
        if self.filepath:
            self.load_file()
        
        self.EmptyUndoBuffer()
        self.SetSavePoint()

        self.Bind(stc.EVT_STC_MODIFIED, self._on_modified)

    def load_file(self):
        """Load text from self.filepath into the editor."""
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                self.SetText(f.read())
        except IOError as e:
            wx.LogError(f"Error opening file '{self.filepath}': {e}")
            self.filepath = None
        except UnicodeDecodeError as e:
            wx.LogError(f"Unicode error in file '{self.filepath}': {e}")
            self.filepath = None

    def _on_modified(self, event):
        """
        Handle text modifications internal to the widget.
        """
        if not self._lang_from_ext:
            self.guess_and_set_lexer(self.filepath)
        
        if hasattr(self, '_invalidate_symbol_cache'):
            self._invalidate_symbol_cache()

        event.Skip()

    def _clear_overlay(self, indic):
        self.SetIndicatorCurrent(indic)
        self.IndicatorClearRange(0, self.GetTextLength())

    def _paint_at_overlay(self):
        if self.GetLexer() != stc.STC_LEX_CPP:
            return
        self.SetIndicatorCurrent(ATTR_INDIC)
        for ln in range(self.GetLineCount()):
            if self.GetLine(ln).lstrip().startswith("@"):
                start = self.PositionFromLine(ln)
                end   = start + len(self.GetLine(ln))
                self.IndicatorFillRange(start, end - start)

    def _paint_code_overlay(self):
        """Applies a custom style to text within Markdown fences for dark mode."""
        if self.GetLexer() != stc.STC_LEX_MARKDOWN or not self.is_dark_mode():
            return

        inside = False
        block_start_pos = 0

        for ln in range(self.GetLineCount()):
            line_text = self.GetLine(ln)
            line_start_pos = self.PositionFromLine(ln)

            if _FENCE_LINE_RE.match(line_text):
                if not inside:
                    inside = True
                    block_start_pos = line_start_pos + len(line_text)
                else:
                    inside = False
                    if block_start_pos < line_start_pos:
                        self.StartStyling(block_start_pos, 0x1f)
                        self.SetStyling(line_start_pos - block_start_pos, MD_CODE_CONTENT_STYLE)
                    block_start_pos = 0
            elif inside and block_start_pos == 0:
                 block_start_pos = line_start_pos

        if inside and block_start_pos > 0:
            end_pos = self.GetTextLength()
            self.StartStyling(block_start_pos, 0x1f)
            self.SetStyling(end_pos - block_start_pos, MD_CODE_CONTENT_STYLE)

    def _resize_margin(self):
        need = len(str(max(1, self.GetLineCount())))
        if need != self._digits:
            self._digits = need
            w = self.TextWidth(stc.STC_STYLE_LINENUMBER, "9"*need + " ")
            self.SetMarginWidth(0, w)

    def _on_update_ui(self, evt):
        self._resize_margin()
        self._clear_overlay(ATTR_INDIC)
        self._paint_at_overlay()
        
        self._paint_code_overlay()

        evt.Skip()