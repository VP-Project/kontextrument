"""
lexer_themes.py – Language detection, theming, and mixins for the CodeEditor.
"""

import re
import wx
import wx.stc as stc
import os

ML = re.MULTILINE

MD_CODE_CONTENT_STYLE = stc.STC_STYLE_LASTPREDEFINED + 1

DARK_COLORS = {
    "bg": "#2B2B2B",
    "fg": "#A9B7C6",
    "keyword": "#CC7832",
    "string": "#6A8759",
    "comment": "#808080",
    "number": "#6897BB",
    "property": "#9876AA",
    "operator": "#A9B7C6",
    "header": "#FFC66D",
    "emphasis": "#CC7832",
    "list_item": "#6A8759",
    "blockquote": "#A9B7C6",
    "code": "#FFC66D",
    "code_bg": "#3C3F41",
    "error": "#FF6B68",
    "error_bg": "#5D2D2A",
    "sel_bg": "#4E5254",
    "sel_fg": "#FFFFFF",
    "fence_bg": "#3C3F41",
}

LIGHT_COLORS = {
    "bg": "#FFFFFF",
    "fg": "#1E1E1E",
    "keyword": "#0000FF",
    "string": "#A31515",
    "comment": "#008000",
    "number": "#098658",
    "property": "#0451A5",
    "operator": "#000000",
    "header": "#0B61A4",
    "emphasis": "#B00020",
    "list_item": "#D2691E",
    "blockquote": "#608B4E",
    "code": "#7F2AFF",
    "code_bg": "#F5F5F5",
    "error": "#FF0000",
    "error_bg": "#FFE0E0",
    "sel_bg": "#C0D2E8",
    "sel_fg": "#000000",
    "fence_bg": "#F5F5F5",
}

_PY_SIGNS = [
    re.compile(r'^\s*def\s+\w+\s*\(', ML),
    re.compile(r'^\s*class\s+\w+\s*:', ML),
    re.compile(r':\s*(#.*)?$',         ML),
    re.compile(r'\blambda\b'),
    re.compile(r'\byield\b'),
    re.compile(r'^\s*import\s+\w',    ML),
]

_C_SIGNS = [
    re.compile(r'//'),
    re.compile(r'/\*'),
    re.compile(r'\{'),
    re.compile(r';\s*(//.*)?$',           ML),
    re.compile(r'#include\s*<',           ML),
    re.compile(r'\bprintf\s*\('),
]

_MD_SIGNS = [
    re.compile(r'^\s*#{1,6}\s+\w', ML),
    re.compile(r'^\s*[-*+]\s+\w',  ML),
    re.compile(r'^\s*\d+\.\s+\w',  ML),
    re.compile(r'\[.+?\]\(.+?\)'),
    re.compile(r'\*\*.+?\*\*'),
]

_CODE_FENCE_RE = re.compile(r'(^|\n)\s*(?:`{3}|~{3})', ML)


def detect_language(text: str,
                      t_py: int = 2,
                      t_c:  int = 2,
                      t_md: int = 2) -> str:
    """Guesses the language of a text snippet ('python', 'c', 'markdown', or 'unknown')."""
    if _CODE_FENCE_RE.search(text):
        return 'markdown'

    py = sum(bool(p.search(text)) for p in _PY_SIGNS)
    c  = sum(bool(p.search(text)) for p in _C_SIGNS)

    if py >= t_py and py > c:
        return 'python'
    if c >= t_c and c > py:
        return 'c'

    md = sum(bool(p.search(text)) for p in _MD_SIGNS)
    return 'markdown' if md >= t_md else 'unknown'


class AutoIndentMixin:
    """A mixin for StyledTextCtrl that provides automatic indentation."""
    _dedent_re = re.compile(r'^\s*(return|pass|break|continue|raise)\b')

    def _on_char_added_indent(self, evt):
        key = evt.GetKey()
        if chr(key) != '\n':
            evt.Skip()
            return

        cur  = self.LineFromPosition(self.GetCurrentPos())
        prev = cur - 1
        if prev < 0:
            evt.Skip()
            return

        ind = self.GetLineIndentation(prev)
        self.SetLineIndentation(cur, ind)
        self.GotoPos(self.PositionFromLine(cur) + ind)

        prev_txt = self.GetLine(prev).rstrip()
        if prev_txt.endswith(':'):
            self.CmdKeyExecute(stc.STC_CMD_TAB)
        
        current_line_text = self.GetLine(cur).strip()
        if self._dedent_re.match(current_line_text):
            self.CmdKeyExecute(stc.STC_CMD_BACKTAB)

        evt.Skip()


class SmartLexerMixin:
    """
    Applies the proper lexer & palette (Python, C-family, Markdown, YAML, JSON, INI/TOML, plain).
    """
    def is_dark_mode(self):
        """Checks if the system is in dark mode."""
        bg = wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW)
        return bg.GetLuminance() < 0.5

    def _set_line_number_style(self):
        """Sets the line number margin style, respecting dark mode."""
        if self.is_dark_mode():
            self.StyleSetSpec(stc.STC_STYLE_LINENUMBER, "back:#313335,fore:#A0A0A0")
        else:
            self.StyleSetSpec(stc.STC_STYLE_LINENUMBER, "back:#F0F0F0,fore:#606060")

    def _apply_base_style(self, colors):
        """Applies base editor styles like selection color based on theme."""
        self.SetSelBackground(True, colors["sel_bg"])
        self.SetSelForeground(True, colors["sel_fg"])
        self.SetCaretForeground(colors["fg"])

    _EXT_MAP = {
        '.py': 'python', '.pyw': 'python',
        '.c': 'c', '.h': 'c', '.cpp': 'c', '.cxx': 'c', '.hpp': 'c',
        '.js': 'c', '.java': 'c', '.hx': 'c', '.hxml': 'hxml',
        '.md': 'markdown', '.markdown': 'markdown',
        '.json': 'json',
        '.yaml': 'yaml', '.yml': 'yaml',
        '.toml': 'ini',
        '.ini': 'ini', '.cfg': 'ini', '.conf': 'ini',
        '.spec': 'python',
    }

    _PY_KW = (
        "and as assert break class continue def del elif else except False "
        "finally for from global if import in is lambda None nonlocal not or "
        "pass raise return True try while with yield"
    )

    _C_KW = (
        "auto break case catch char class const continue default do double else "
        "enum extern float for goto if int long namespace new private protected "
        "public return short signed sizeof static struct switch template this "
        "throw try typedef union unsigned virtual void volatile while "
        "boolean byte extends final finally implements import instanceof "
        "interface native package strictfp super synchronized throws transient "
        "abstract function let var const yield await "
        "abstract cast dynamic inline macro override typedef untyped using trace "
    )

    _HXML_KW = (
        "-cp -lib -main -dce -debug -js -neko -swf -cpp -java -cs -php "
        "-python -lua -hl -D -resource -xml -json -cmd --next --each --cwd -v "
        "--help --version --run --no-output --times --connect --wait"
    )

    @staticmethod
    def _md_const(*names: str) -> int | None:
        prefixes = ("STC_MARKDOWN_", "STC_MD_")
        for n in names:
            for p in prefixes:
                ident = p + n
                if hasattr(stc, ident):
                    return getattr(stc, ident)
        return None

    def _apply_theme(self, face, colors, apply_styles_func):
        """Generic theme application helper."""
        self.StyleSetSpec(stc.STC_STYLE_DEFAULT, f"face:{face},size:11,fore:{colors['fg']},back:{colors['bg']}")
        self.StyleClearAll()
        self._set_line_number_style()
        self._apply_base_style(colors)
        apply_styles_func(colors)

    def _apply_python_theme(self):
        colors = DARK_COLORS if self.is_dark_mode() else LIGHT_COLORS
        def apply_styles(c):
            self.SetKeyWords(0, self._PY_KW)
            self.StyleSetSpec(stc.STC_P_DEFAULT,       f"fore:{c['fg']}")
            self.StyleSetSpec(stc.STC_P_COMMENTLINE,  f"fore:{c['comment']},italic")
            self.StyleSetSpec(stc.STC_P_NUMBER,        f"fore:{c['number']}")
            self.StyleSetSpec(stc.STC_P_STRING,        f"fore:{c['string']}")
            self.StyleSetSpec(stc.STC_P_WORD,          f"fore:{c['keyword']},bold")
        self._apply_theme("Courier New", colors, apply_styles)
        self.Bind(stc.EVT_STC_CHARADDED, self._on_char_added_indent)

    def _apply_c_theme(self):
        colors = DARK_COLORS if self.is_dark_mode() else LIGHT_COLORS
        def apply_styles(c):
            self.SetKeyWords(0, self._C_KW)
            self.StyleSetSpec(stc.STC_C_DEFAULT,       f"fore:{c['fg']}")
            self.StyleSetSpec(stc.STC_C_COMMENT,       f"fore:{c['comment']},italic")
            self.StyleSetSpec(stc.STC_C_COMMENTLINE,  f"fore:{c['comment']},italic")
            self.StyleSetSpec(stc.STC_C_NUMBER,        f"fore:{c['number']}")
            self.StyleSetSpec(stc.STC_C_STRING,        f"fore:{c['string']}")
            self.StyleSetSpec(stc.STC_C_WORD,          f"fore:{c['keyword']},bold")
        self._apply_theme("Courier New", colors, apply_styles)
        self.Unbind(stc.EVT_STC_CHARADDED, handler=self._on_char_added_indent)

    def _apply_md_theme(self):
        colors = DARK_COLORS if self.is_dark_mode() else LIGHT_COLORS
        def apply_styles(c):
            if self.is_dark_mode():
                self.StyleSetSpec(MD_CODE_CONTENT_STYLE, f"back:{c['code_bg']},fore:{c['code']},face:Courier New,size:10")

            def sty(names, spec):
                for name in names:
                    s = self._md_const(name)
                    if s is not None:
                        self.StyleSetSpec(s, spec)

            sty(("DEFAULT",), f"fore:{c['fg']},size:11")
            sty(("HEADER1",), f"fore:{c['header']},bold,size:16")
            sty(("HEADER2",), f"fore:{c['header']},bold,size:14")
            sty(("HEADER3",), f"fore:{c['header']},bold,size:12")
            sty(("HEADER4",), f"fore:{c['header']},bold,size:11")
            sty(("HEADER5",), f"fore:{c['header']},bold,size:11")
            sty(("HEADER6",), f"fore:{c['header']},bold,size:11")
            sty(("STRONG1", "STRONG", "BOLD"), f"bold,fore:{c['emphasis']}")
            sty(("EM1", "EM", "ITALIC"),       f"italic,fore:{c['emphasis']}")
            sty(("CODE", "CODEINLINE", "CODE2"), f"back:{c['code_bg']},fore:{c['code']},face:Courier New,size:10")
            sty(("CODEBK",), f"back:{c['code_bg']}")
            sty(("LIST_ITEM",),  f"fore:{c['list_item']}")
            sty(("BLOCKQUOTE",), f"fore:{c['blockquote']},italic")
        self._apply_theme("Arial", colors, apply_styles)
        self.Unbind(stc.EVT_STC_CHARADDED, handler=self._on_char_added_indent)

    def _apply_json_theme(self):
        colors = DARK_COLORS if self.is_dark_mode() else LIGHT_COLORS
        def apply_styles(c):
            self.StyleSetSpec(stc.STC_JSON_DEFAULT,        f"fore:{c['fg']}")
            self.StyleSetSpec(stc.STC_JSON_NUMBER,         f"fore:{c['number']}")
            self.StyleSetSpec(stc.STC_JSON_STRING,         f"fore:{c['string']}")
            self.StyleSetSpec(stc.STC_JSON_PROPERTYNAME,   f"fore:{c['property']}")
            self.StyleSetSpec(stc.STC_JSON_OPERATOR,       f"fore:{c['operator']}")
            self.StyleSetSpec(stc.STC_JSON_KEYWORD,        f"fore:{c['keyword']},bold")
            self.StyleSetSpec(stc.STC_JSON_ERROR,          f"fore:{c['error']},back:{c['error_bg']}")
        self._apply_theme("Courier New", colors, apply_styles)
        self.Unbind(stc.EVT_STC_CHARADDED, handler=self._on_char_added_indent)

    def _apply_yaml_theme(self):
        colors = DARK_COLORS if self.is_dark_mode() else LIGHT_COLORS
        def apply_styles(c):
            self.StyleSetSpec(stc.STC_YAML_DEFAULT,        f"fore:{c['fg']}")
            self.StyleSetSpec(stc.STC_YAML_COMMENT,        f"fore:{c['comment']},italic")
            self.StyleSetSpec(stc.STC_YAML_IDENTIFIER,     f"fore:{c['property']},bold")
            self.StyleSetSpec(stc.STC_YAML_KEYWORD,        f"fore:{c['keyword']},bold")
            self.StyleSetSpec(stc.STC_YAML_NUMBER,         f"fore:{c['number']}")
            self.StyleSetSpec(stc.STC_YAML_TEXT,           f"fore:{c['string']}")
            self.StyleSetSpec(stc.STC_YAML_ERROR,          f"fore:{c['error']},back:{c['error_bg']}")
            self.StyleSetSpec(stc.STC_YAML_OPERATOR,       f"fore:{c['operator']},bold")
        self._apply_theme("Courier New", colors, apply_styles)
        self.Unbind(stc.EVT_STC_CHARADDED, handler=self._on_char_added_indent)

    def _apply_ini_theme(self):
        colors = DARK_COLORS if self.is_dark_mode() else LIGHT_COLORS
        def apply_styles(c):
            self.StyleSetSpec(stc.STC_PROPS_DEFAULT,          f"fore:{c['fg']}")
            self.StyleSetSpec(stc.STC_PROPS_COMMENT,          f"fore:{c['comment']},italic")
            self.StyleSetSpec(stc.STC_PROPS_SECTION,          f"fore:{c['keyword']},bold")
            self.StyleSetSpec(stc.STC_PROPS_ASSIGNMENT,       f"fore:{c['operator']},bold")
            self.StyleSetSpec(stc.STC_PROPS_DEFVAL,           f"fore:{c['string']}")
            self.StyleSetSpec(stc.STC_PROPS_KEY,              f"fore:{c['property']}")
        self._apply_theme("Courier New", colors, apply_styles)
        self.Unbind(stc.EVT_STC_CHARADDED, handler=self._on_char_added_indent)

    def _apply_gitignore_theme(self):
        colors = DARK_COLORS if self.is_dark_mode() else LIGHT_COLORS
        def apply_styles(c):
            self.StyleSetSpec(stc.STC_SH_DEFAULT,       f"fore:{c['fg']}")
            self.StyleSetSpec(stc.STC_SH_COMMENTLINE,   f"fore:{c['comment']},italic")
            self.StyleSetSpec(stc.STC_SH_WORD,          f"fore:{c['keyword']},bold")
            self.StyleSetSpec(stc.STC_SH_STRING,        f"fore:{c['string']}")
            self.StyleSetSpec(stc.STC_SH_NUMBER,        f"fore:{c['number']}")
            self.StyleSetSpec(stc.STC_SH_OPERATOR,      f"fore:{c['operator']},bold")
            self.StyleSetSpec(stc.STC_SH_IDENTIFIER,    f"fore:{c['property']}")
        self._apply_theme("Courier New", colors, apply_styles)
        self.Unbind(stc.EVT_STC_CHARADDED, handler=self._on_char_added_indent)

    def _apply_hxml_theme(self):
        colors = DARK_COLORS if self.is_dark_mode() else LIGHT_COLORS
        def apply_styles(c):
            self.SetKeyWords(0, self._HXML_KW)
            self.StyleSetSpec(stc.STC_SH_DEFAULT,       f"fore:{c['fg']}")
            self.StyleSetSpec(stc.STC_SH_COMMENTLINE,   f"fore:{c['comment']},italic")
            self.StyleSetSpec(stc.STC_SH_WORD,          f"fore:{c['keyword']},bold")
            self.StyleSetSpec(stc.STC_SH_STRING,        f"fore:{c['string']}")
            self.StyleSetSpec(stc.STC_SH_NUMBER,        f"fore:{c['number']}")
            self.StyleSetSpec(stc.STC_SH_OPERATOR,      f"fore:{c['operator']},bold")
            self.StyleSetSpec(stc.STC_SH_IDENTIFIER,    f"fore:{c['property']}")
        self._apply_theme("Courier New", colors, apply_styles)
        self.Unbind(stc.EVT_STC_CHARADDED, handler=self._on_char_added_indent)

    def _set_lexer_for_lang(self, lang: str):
        """Helper to apply lexer and theme for a language string."""
        if not hasattr(self, '_default_word_chars'):
            self._default_word_chars = self.GetWordChars()
        
        if lang == 'hxml':
            self.SetWordChars(self._default_word_chars + '-')
        else:
            if self.GetWordChars() != self._default_word_chars:
                self.SetWordChars(self._default_word_chars)

        theme_map = {
            "python": self._apply_python_theme,
            "c": self._apply_c_theme,
            "markdown": self._apply_md_theme,
            "json": self._apply_json_theme,
            "yaml": self._apply_yaml_theme,
            "ini": self._apply_ini_theme,
            "gitignore": self._apply_gitignore_theme,
            "hxml": self._apply_hxml_theme
        }
        lexer_map = {
            "python": stc.STC_LEX_PYTHON,
            "c": stc.STC_LEX_CPP,
            "markdown": stc.STC_LEX_MARKDOWN,
            "json": stc.STC_LEX_JSON,
            "yaml": stc.STC_LEX_YAML,
            "ini": stc.STC_LEX_PROPERTIES,
            "gitignore": stc.STC_LEX_BASH,
            "hxml": stc.STC_LEX_BASH
        }

        lexer = lexer_map.get(lang, stc.STC_LEX_NULL)
        self.SetLexer(lexer)
        if lang in theme_map:
            theme_map[lang]()
            if lang == "markdown":
                self.SetWrapMode(stc.STC_WRAP_WORD)
        else:
            colors = DARK_COLORS if self.is_dark_mode() else LIGHT_COLORS
            self._apply_theme("Courier New", colors, lambda c: None)
            self.Unbind(stc.EVT_STC_CHARADDED, handler=self._on_char_added_indent)

        self.Colourise(0, self.GetTextLength())

    def guess_and_set_lexer(self, filepath=None):
        """Overhauled lexer detection.
        1. Handle special filenames (e.g., .gitignore).
        2. Check file extension.
        3. If no match, fallback to content-based detection.
        """
        lang = 'unknown'
        self._lang_from_ext = False
        if filepath:
            filename = os.path.basename(filepath)
            if filename.lower() == '.gitignore':
                lang = 'gitignore'
                self._lang_from_ext = True
            else:
                _, ext = os.path.splitext(filepath)
                if ext.lower() in self._EXT_MAP:
                    lang = self._EXT_MAP[ext.lower()]
                    self._lang_from_ext = True

        if not self._lang_from_ext:
            snippet = self.GetTextRange(0, min(self.GetTextLength(), 4000))
            lang = detect_language(snippet, t_py=2, t_c=2, t_md=1)
        
        new_lexer = {
            "python": stc.STC_LEX_PYTHON, "c": stc.STC_LEX_CPP,
            "markdown": stc.STC_LEX_MARKDOWN, "json": stc.STC_LEX_JSON,
            "yaml": stc.STC_LEX_YAML, "ini": stc.STC_LEX_PROPERTIES,
            "gitignore": stc.STC_LEX_BASH, "hxml": stc.STC_LEX_BASH,
        }.get(lang, stc.STC_LEX_NULL)

        if self.GetLexer() != new_lexer:
            self._set_lexer_for_lang(lang)