"""
modules_parts package – Modular editor components.
"""


from .git_backend import GitBackend

from .diff_viewer import DiffViewer

from .file_tree import FileTreeCtrl
from .editor_core import CodeEditor
from .autocomplete import AutoCompleteMixin, PythonSymbolExtractor, CSymbolExtractor
from .lexer_themes import SmartLexerMixin, AutoIndentMixin, detect_language

__all__ = [
    'CodeEditor',
    'AutoCompleteMixin',
    'PythonSymbolExtractor',
    'CSymbolExtractor',
    'SmartLexerMixin',
    'AutoIndentMixin',
    'detect_language',

    'GitBackend',

    'DiffViewer',

    'FileTreeCtrl'
]