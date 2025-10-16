
import wx
import wx.stc as stc


class DiffViewer(stc.StyledTextCtrl):
    """
    Custom diff viewer with simple syntax highlighting and read-only mode.
    Supports both light and dark themes by detecting system colors.
    """

    def __init__(self, parent):
        """Initializes the DiffViewer."""
        super().__init__(parent)
        self._setup_styles()
        self.SetReadOnly(True)
        self.SetMarginType(0, stc.STC_MARGIN_NUMBER)
        self.SetMarginWidth(0, 40)

    def _is_dark_theme(self) -> bool:
        """
        Detects if the system is using a dark theme by checking the background color.
        Returns True if dark theme is detected, False otherwise.
        """
        sys_bg = wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW)
        
        luminance = (0.299 * sys_bg.Red() + 0.587 * sys_bg.Green() + 0.114 * sys_bg.Blue()) / 255.0
        
        return luminance < 0.5

    def _setup_styles(self) -> None:
        """Sets up the styling for the diff viewer based on the current theme."""
        is_dark = self._is_dark_theme()
        
        if is_dark:
            default_bg = wx.Colour(30, 30, 30)
            default_fg = wx.Colour(220, 220, 220)
            comment_fg = wx.Colour(128, 128, 128)
            command_fg = wx.Colour(100, 150, 255)
            header_fg = wx.Colour(200, 120, 220)
            position_fg = wx.Colour(100, 180, 255)
            added_fg = wx.Colour(100, 220, 100)
            added_bg = wx.Colour(20, 60, 20)
            deleted_fg = wx.Colour(255, 120, 120)
            deleted_bg = wx.Colour(60, 20, 20)
        else:
            default_bg = wx.Colour(255, 255, 255)
            default_fg = wx.Colour(30, 30, 30)
            comment_fg = wx.Colour(128, 128, 128)
            command_fg = wx.Colour(0, 0, 255)
            header_fg = wx.Colour(128, 0, 128)
            position_fg = wx.Colour(0, 128, 255)
            added_fg = wx.Colour(0, 128, 0)
            added_bg = wx.Colour(224, 255, 224)
            deleted_fg = wx.Colour(128, 0, 0)
            deleted_bg = wx.Colour(255, 224, 224)
        
        self.StyleSetSpec(
            stc.STC_STYLE_DEFAULT, 
            f"face:Courier New,size:10,fore:#{default_fg.GetAsString(wx.C2S_HTML_SYNTAX)[1:]},back:#{default_bg.GetAsString(wx.C2S_HTML_SYNTAX)[1:]}"
        )
        self.StyleClearAll()
        self.SetLexer(stc.STC_LEX_DIFF)

        self.SetBackgroundColour(default_bg)
        self.SetForegroundColour(default_fg)
        
        self.StyleSetBackground(stc.STC_STYLE_LINENUMBER, default_bg)
        self.StyleSetForeground(stc.STC_STYLE_LINENUMBER, comment_fg)

        self.StyleSetSpec(stc.STC_DIFF_DEFAULT, f"fore:#{default_fg.GetAsString(wx.C2S_HTML_SYNTAX)[1:]}")
        self.StyleSetSpec(stc.STC_DIFF_COMMENT, f"fore:#{comment_fg.GetAsString(wx.C2S_HTML_SYNTAX)[1:]},italic")
        self.StyleSetSpec(stc.STC_DIFF_COMMAND, f"fore:#{command_fg.GetAsString(wx.C2S_HTML_SYNTAX)[1:]},bold")
        self.StyleSetSpec(stc.STC_DIFF_HEADER, f"fore:#{header_fg.GetAsString(wx.C2S_HTML_SYNTAX)[1:]},bold")
        self.StyleSetSpec(stc.STC_DIFF_POSITION, f"fore:#{position_fg.GetAsString(wx.C2S_HTML_SYNTAX)[1:]},bold")
        self.StyleSetSpec(
            stc.STC_DIFF_ADDED, 
            f"fore:#{added_fg.GetAsString(wx.C2S_HTML_SYNTAX)[1:]},back:#{added_bg.GetAsString(wx.C2S_HTML_SYNTAX)[1:]}"
        )
        self.StyleSetSpec(
            stc.STC_DIFF_DELETED, 
            f"fore:#{deleted_fg.GetAsString(wx.C2S_HTML_SYNTAX)[1:]},back:#{deleted_bg.GetAsString(wx.C2S_HTML_SYNTAX)[1:]}"
        )

    def show_diff(self, diff_text: str) -> None:
        """Displays the provided diff text in the viewer."""
        was_ro = self.GetReadOnly()
        if was_ro:
            self.SetReadOnly(False)
        self.SetText(diff_text or "")
        self.EmptyUndoBuffer()
        self.GotoPos(0)
        if was_ro:
            self.SetReadOnly(True)
    
    def refresh_theme(self) -> None:
        """
        Refreshes the theme styling. Call this method if the system theme changes
        while the application is running.
        """
        current_text = self.GetText()
        was_ro = self.GetReadOnly()
        
        if was_ro:
            self.SetReadOnly(False)
        
        self._setup_styles()
        self.SetText(current_text)
        self.EmptyUndoBuffer()
        self.GotoPos(0)
        
        if was_ro:
            self.SetReadOnly(True)