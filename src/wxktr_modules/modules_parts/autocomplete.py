"""
autocomplete.py – Syntax-aware autocomplete for CodeEditor.
Provides context-aware suggestions for variables, classes, methods, and fields.
"""

import re
import wx.stc as stc
from typing import List, Set, Dict, Optional

class PythonSymbolExtractor:
    """Extracts Python symbols (variables, classes, methods, fields) from code."""
    
    CLASS_RE = re.compile(r'^\s*class\s+(\w+)', re.MULTILINE)
    FUNCTION_RE = re.compile(r'^\s*def\s+(\w+)', re.MULTILINE)
    ASSIGNMENT_RE = re.compile(r'^\s*(\w+)\s*=', re.MULTILINE)
    IMPORT_RE = re.compile(r'^\s*(?:from\s+\S+\s+)?import\s+(.+)', re.MULTILINE)
    METHOD_CALL_RE = re.compile(r'\.(\w+)\s*\(')
    ATTRIBUTE_RE = re.compile(r'\.(\w+)\b(?!\s*\()')
    PARAMETER_RE = re.compile(r'def\s+\w+\s*\(([^)]*)\)', re.MULTILINE)
    
    def __init__(self, text: str):
        """Initializes the PythonSymbolExtractor."""
        self.text = text
        self._symbols_cache: Optional[Dict[str, Set[str]]] = None
    
    def extract_all_symbols(self) -> Dict[str, Set[str]]:
        """Extract all symbols categorized by type."""
        if self._symbols_cache is not None:
            return self._symbols_cache
        
        symbols = {
            'classes': set(),
            'functions': set(),
            'variables': set(),
            'methods': set(),
            'attributes': set(),
            'imports': set(),
        }
        
        for match in self.CLASS_RE.finditer(self.text):
            symbols['classes'].add(match.group(1))
        
        for match in self.FUNCTION_RE.finditer(self.text):
            symbols['functions'].add(match.group(1))
        
        for match in self.ASSIGNMENT_RE.finditer(self.text):
            var_name = match.group(1)
            if var_name not in symbols['classes'] and var_name not in symbols['functions']:
                symbols['variables'].add(var_name)
        
        for match in self.METHOD_CALL_RE.finditer(self.text):
            symbols['methods'].add(match.group(1))
        
        for match in self.ATTRIBUTE_RE.finditer(self.text):
            symbols['attributes'].add(match.group(1))
        
        for match in self.IMPORT_RE.finditer(self.text):
            import_line = match.group(1)
            for item in re.split(r'[,\s]+', import_line):
                item = item.strip()
                if ' as ' in item:
                    item = item.split(' as ')[-1].strip()
                if item and item.isidentifier():
                    symbols['imports'].add(item)
        
        for match in self.PARAMETER_RE.finditer(self.text):
            params = match.group(1)
            for param in params.split(','):
                param = param.strip().split('=')[0].strip().split(':')[0].strip()
                if param and param != 'self' and param != 'cls' and param.isidentifier():
                    symbols['variables'].add(param)
        
        self._symbols_cache = symbols
        return symbols
    
    def get_all_identifiers(self) -> Set[str]:
        """Get all unique identifiers from all categories."""
        symbols = self.extract_all_symbols()
        all_ids = set()
        for category in symbols.values():
            all_ids.update(category)
        return all_ids


class CSymbolExtractor:
    """Extracts C/C++/JavaScript symbols from code."""
    
    CLASS_STRUCT_RE = re.compile(r'(?:class|struct)\s+(\w+)', re.MULTILINE)
    FUNCTION_RE = re.compile(r'(?:^\s*|\s+)(?:void|int|float|double|char|bool|const|var|let|function|async|[\w:]+)\s+(\w+)\s*\(', re.MULTILINE)
    VARIABLE_RE = re.compile(r'(?:int|float|double|char|bool|auto|var|let|const|[\w:]+)\s+(\w+)\s*[;=]', re.MULTILINE)
    DEFINE_RE = re.compile(r'^\s*#define\s+(\w+)', re.MULTILINE)
    
    def __init__(self, text: str):
        """Initializes the PythonSymbolExtractor."""
        self.text = text
        self._symbols_cache: Optional[Set[str]] = None
    
    def get_all_identifiers(self) -> Set[str]:
        """Get all unique identifiers."""
        if self._symbols_cache is not None:
            return self._symbols_cache
        
        symbols = set()
        
        for match in self.CLASS_STRUCT_RE.finditer(self.text):
            symbols.add(match.group(1))
        
        for match in self.FUNCTION_RE.finditer(self.text):
            symbols.add(match.group(1))
        
        for match in self.VARIABLE_RE.finditer(self.text):
            symbols.add(match.group(1))
        
        for match in self.DEFINE_RE.finditer(self.text):
            symbols.add(match.group(1))
        
        self._symbols_cache = symbols
        return symbols


class JSONSymbolExtractor:
    """Extracts JSON keys from code."""
    
    KEY_RE = re.compile(r'"(\w+)"\s*:', re.MULTILINE)
    
    def __init__(self, text: str):
        """Initializes the PythonSymbolExtractor."""
        self.text = text
        self._symbols_cache: Optional[Set[str]] = None
    
    def get_all_identifiers(self) -> Set[str]:
        """Get all unique JSON keys."""
        if self._symbols_cache is not None:
            return self._symbols_cache
        
        symbols = set()
        for match in self.KEY_RE.finditer(self.text):
            symbols.add(match.group(1))
        
        self._symbols_cache = symbols
        return symbols


class YAMLSymbolExtractor:
    """Extracts YAML keys from code."""
    
    KEY_RE = re.compile(r'^(\s*)(\w+):', re.MULTILINE)
    
    def __init__(self, text: str):
        """Initializes the PythonSymbolExtractor."""
        self.text = text
        self._symbols_cache: Optional[Set[str]] = None
    
    def get_all_identifiers(self) -> Set[str]:
        """Get all unique YAML keys."""
        if self._symbols_cache is not None:
            return self._symbols_cache
        
        symbols = set()
        for match in self.KEY_RE.finditer(self.text):
            symbols.add(match.group(2))
        
        self._symbols_cache = symbols
        return symbols


class INISymbolExtractor:
    """Extracts INI/TOML sections and keys from code."""
    
    SECTION_RE = re.compile(r'^\[(\w+)\]', re.MULTILINE)
    KEY_RE = re.compile(r'^(\w+)\s*=', re.MULTILINE)
    
    def __init__(self, text: str):
        """Initializes the PythonSymbolExtractor."""
        self.text = text
        self._symbols_cache: Optional[Set[str]] = None
    
    def get_all_identifiers(self) -> Set[str]:
        """Get all unique sections and keys."""
        if self._symbols_cache is not None:
            return self._symbols_cache
        
        symbols = set()
        
        for match in self.SECTION_RE.finditer(self.text):
            symbols.add(match.group(1))
        
        for match in self.KEY_RE.finditer(self.text):
            symbols.add(match.group(1))
        
        self._symbols_cache = symbols
        return symbols


class AutoCompleteMixin:
    """
    Mixin class that adds intelligent autocomplete to CodeEditor.
    Provides context-aware suggestions for variables, classes, methods, and fields.
    """
    
    PYTHON_BUILTINS = {
        'abs', 'all', 'any', 'ascii', 'bin', 'bool', 'breakpoint', 'bytearray',
        'bytes', 'callable', 'chr', 'classmethod', 'compile', 'complex',
        'delattr', 'dict', 'dir', 'divmod', 'enumerate', 'eval', 'exec',
        'filter', 'float', 'format', 'frozenset', 'getattr', 'globals',
        'hasattr', 'hash', 'help', 'hex', 'id', 'input', 'int', 'isinstance',
        'issubclass', 'iter', 'len', 'list', 'locals', 'map', 'max',
        'memoryview', 'min', 'next', 'object', 'oct', 'open', 'ord', 'pow',
        'print', 'property', 'range', 'repr', 'reversed', 'round', 'set',
        'setattr', 'slice', 'sorted', 'staticmethod', 'str', 'sum', 'super',
        'tuple', 'type', 'vars', 'zip', '__import__',
        'Exception', 'ValueError', 'TypeError', 'KeyError', 'IndexError',
        'AttributeError', 'RuntimeError', 'NotImplementedError', 'IOError',
        'FileNotFoundError', 'PermissionError', 'OSError',
        'True', 'False', 'None',
    }
    
    JAVASCRIPT_BUILTINS = {
        'eval', 'parseInt', 'parseFloat', 'isNaN', 'isFinite', 'encodeURI',
        'encodeURIComponent', 'decodeURI', 'decodeURIComponent', 'escape', 'unescape',
        'console', 'alert', 'prompt', 'confirm',
        'Object', 'Array', 'String', 'Number', 'Boolean', 'Date', 'Math',
        'RegExp', 'Error', 'Function', 'Promise', 'Map', 'Set', 'WeakMap',
        'WeakSet', 'Symbol', 'Proxy', 'Reflect', 'JSON',
        'push', 'pop', 'shift', 'unshift', 'concat', 'slice', 'splice',
        'indexOf', 'lastIndexOf', 'filter', 'map', 'reduce', 'reduceRight',
        'forEach', 'find', 'findIndex', 'includes', 'some', 'every', 'sort',
        'reverse', 'join', 'toString', 'flat', 'flatMap', 'fill', 'copyWithin',
        'charAt', 'charCodeAt', 'substring', 'substr', 'split', 'replace',
        'match', 'search', 'toLowerCase', 'toUpperCase', 'trim', 'trimStart',
        'trimEnd', 'padStart', 'padEnd', 'repeat', 'startsWith', 'endsWith',
        'keys', 'values', 'entries', 'assign', 'create', 'defineProperty',
        'freeze', 'seal', 'getPrototypeOf', 'setPrototypeOf',
        'PI', 'E', 'abs', 'ceil', 'floor', 'round', 'sqrt', 'pow', 'min', 'max',
        'random', 'sin', 'cos', 'tan', 'asin', 'acos', 'atan', 'atan2',
        'document', 'window', 'navigator', 'location', 'history',
        'getElementById', 'getElementsByClassName', 'getElementsByTagName',
        'querySelector', 'querySelectorAll', 'createElement', 'appendChild',
        'removeChild', 'addEventListener', 'removeEventListener',
        'setTimeout', 'setInterval', 'clearTimeout', 'clearInterval',
        'undefined', 'null', 'true', 'false', 'this', 'new', 'delete',
        'typeof', 'instanceof', 'void',
    }
    
    JAVA_BUILTINS = {
        'String', 'StringBuilder', 'StringBuffer', 'Integer', 'Double', 'Float',
        'Long', 'Short', 'Byte', 'Character', 'Boolean', 'Math', 'System',
        'Object', 'Class', 'Thread', 'Runnable', 'Exception', 'Error',
        'ArrayList', 'LinkedList', 'HashMap', 'HashSet', 'TreeMap', 'TreeSet',
        'Vector', 'Stack', 'Queue', 'Deque', 'List', 'Set', 'Map', 'Collection',
        'Iterator', 'Enumeration',
        'File', 'FileReader', 'FileWriter', 'BufferedReader', 'BufferedWriter',
        'InputStream', 'OutputStream', 'PrintStream', 'Scanner',
        'println', 'print', 'printf', 'length', 'size', 'get', 'set', 'add',
        'remove', 'contains', 'isEmpty', 'clear', 'toString', 'equals',
        'hashCode', 'compareTo', 'clone',
        'public', 'private', 'protected', 'static', 'final', 'abstract',
        'synchronized', 'volatile', 'transient', 'native', 'strictfp',
        'true', 'false', 'null', 'this', 'super', 'new', 'instanceof',
    }
    
    YAML_KEYWORDS = {
        'true', 'True', 'TRUE', 'false', 'False', 'FALSE',
        'yes', 'Yes', 'YES', 'no', 'No', 'NO',
        'on', 'On', 'ON', 'off', 'Off', 'OFF',
        'null', 'Null', 'NULL', '~',
        'stages', 'stage', 'script', 'before_script', 'after_script',
        'variables', 'image', 'services', 'only', 'except', 'tags',
        'when', 'artifacts', 'cache', 'dependencies', 'needs',
        'extends', 'include', 'pages', 'trigger', 'workflow',
        'version', 'services', 'networks', 'volumes', 'build', 'image',
        'ports', 'environment', 'depends_on', 'command', 'entrypoint',
        'volumes', 'restart', 'container_name', 'hostname',
        'apiVersion', 'kind', 'metadata', 'name', 'namespace', 'labels',
        'annotations', 'spec', 'replicas', 'selector', 'template',
        'containers', 'ports', 'env', 'resources', 'limits', 'requests',
    }
    
    JSON_KEYWORDS = {
        'true', 'false', 'null',
    }
    
    INI_KEYWORDS = {
        'general', 'settings', 'config', 'database', 'server', 'client',
        'options', 'defaults', 'main', 'core', 'app', 'logging',
        'name', 'value', 'enabled', 'disabled', 'host', 'port', 'user',
        'password', 'path', 'file', 'directory', 'timeout', 'debug',
        'verbose', 'level', 'format', 'output', 'input',
        'true', 'false', 'yes', 'no', 'on', 'off', '1', '0',
    }
    
    def _init_autocomplete(self):
        """Initialize autocomplete settings. Call from __init__."""
        self._autocomplete_enabled = True
        self._min_chars_for_autocomplete = 2
        self._symbol_extractor = None
        self._last_text_length = 0
        
        self.AutoCompSetIgnoreCase(False)
        self.AutoCompSetAutoHide(True)
        self.AutoCompSetDropRestOfWord(False)
        self.AutoCompSetMaxHeight(10)
        
        self.Bind(stc.EVT_STC_CHARADDED, self._on_char_added_autocomplete)
    
    def _invalidate_symbol_cache(self):
        """Invalidate the symbol cache when text changes significantly."""
        self._symbol_extractor = None
    
    def _get_symbol_extractor(self):
        """Get or create a symbol extractor for the current document."""
        current_len = self.GetTextLength()
        
        if self._symbol_extractor and self._last_text_length > 0:
            if abs(current_len - self._last_text_length) / self._last_text_length > 0.05:
                self._invalidate_symbol_cache()
        
        if self._symbol_extractor is None:
            text = self.GetText()
            lexer = self.GetLexer()
            
            if lexer == stc.STC_LEX_PYTHON:
                self._symbol_extractor = PythonSymbolExtractor(text)
            elif lexer == stc.STC_LEX_CPP:
                self._symbol_extractor = CSymbolExtractor(text)
            elif lexer == stc.STC_LEX_JSON:
                self._symbol_extractor = JSONSymbolExtractor(text)
            elif lexer == stc.STC_LEX_YAML:
                self._symbol_extractor = YAMLSymbolExtractor(text)
            elif lexer == stc.STC_LEX_PROPERTIES:
                self._symbol_extractor = INISymbolExtractor(text)
            else:
                self._symbol_extractor = None
            
            self._last_text_length = current_len
        
        return self._symbol_extractor
    
    def _get_word_before_caret(self) -> tuple[int, str]:
        """Get the partial word before the caret. Returns (start_pos, word)."""
        current_pos = self.GetCurrentPos()
        word_start_pos = self.WordStartPosition(current_pos, True)
        word = self.GetTextRange(word_start_pos, current_pos)
        return word_start_pos, word
    
    def _get_completions_for_context(self, partial_word: str) -> List[str]:
        """Get completion suggestions based on current context."""
        completions = set()
        lexer = self.GetLexer()
        
        if lexer == stc.STC_LEX_PYTHON:
            if hasattr(self, '_PY_KW'):
                for kw in self._PY_KW.split():
                    if kw.startswith(partial_word):
                        completions.add(kw)
            
            for builtin in self.PYTHON_BUILTINS:
                if builtin.startswith(partial_word):
                    completions.add(builtin)
            
            extractor = self._get_symbol_extractor()
            if extractor:
                symbols = extractor.get_all_identifiers()
                for symbol in symbols:
                    if symbol.startswith(partial_word):
                        completions.add(symbol)
        
        elif lexer == stc.STC_LEX_CPP:
            if hasattr(self, '_C_KW'):
                for kw in self._C_KW.split():
                    if kw.startswith(partial_word):
                        completions.add(kw)
            
            for builtin in self.JAVASCRIPT_BUILTINS:
                if builtin.startswith(partial_word):
                    completions.add(builtin)
            
            for builtin in self.JAVA_BUILTINS:
                if builtin.startswith(partial_word):
                    completions.add(builtin)
            
            extractor = self._get_symbol_extractor()
            if extractor:
                symbols = extractor.get_all_identifiers()
                for symbol in symbols:
                    if symbol.startswith(partial_word):
                        completions.add(symbol)
        
        elif lexer == stc.STC_LEX_JSON:
            for kw in self.JSON_KEYWORDS:
                if kw.startswith(partial_word):
                    completions.add(kw)
            
            extractor = self._get_symbol_extractor()
            if extractor:
                symbols = extractor.get_all_identifiers()
                for symbol in symbols:
                    if symbol.startswith(partial_word):
                        completions.add(symbol)
        
        elif lexer == stc.STC_LEX_YAML:
            for kw in self.YAML_KEYWORDS:
                if kw.startswith(partial_word):
                    completions.add(kw)
            
            extractor = self._get_symbol_extractor()
            if extractor:
                symbols = extractor.get_all_identifiers()
                for symbol in symbols:
                    if symbol.startswith(partial_word):
                        completions.add(symbol)
        
        elif lexer == stc.STC_LEX_PROPERTIES:
            for kw in self.INI_KEYWORDS:
                if kw.startswith(partial_word):
                    completions.add(kw)
            
            extractor = self._get_symbol_extractor()
            if extractor:
                symbols = extractor.get_all_identifiers()
                for symbol in symbols:
                    if symbol.startswith(partial_word):
                        completions.add(symbol)
        
        elif lexer == stc.STC_LEX_MARKDOWN:
            text = self.GetText()
            words = re.findall(r'\b[a-zA-Z_]\w*\b', text)
            for word in set(words):
                if word.startswith(partial_word) and word != partial_word and len(word) >= 3:
                    completions.add(word)
        
        else:
            text = self.GetText()
            words = re.findall(r'\b[a-zA-Z_]\w*\b', text)
            for word in set(words):
                if word.startswith(partial_word) and word != partial_word:
                    completions.add(word)
        
        return sorted(list(completions))
    
    def _should_show_autocomplete(self, char: str, partial_word: str) -> bool:
        """Determine if autocomplete should be shown."""
        if not self._autocomplete_enabled:
            return False
        
        if self.AutoCompActive():
            return False
        
        if len(partial_word) >= self._min_chars_for_autocomplete:
            return True
        
        if char == '.':
            return True
        
        return False
    
    def _on_char_added_autocomplete(self, evt):
        """Handle character addition for autocomplete triggering."""
        char = chr(evt.GetKey())
        
        word_start_pos, partial_word = self._get_word_before_caret()
        
        if self._should_show_autocomplete(char, partial_word):
            completions = self._get_completions_for_context(partial_word)
            
            if completions:
                completion_list = ' '.join(completions)
                
                len_entered = len(partial_word)
                self.AutoCompShow(len_entered, completion_list)
        
        evt.Skip()
    
    def enable_autocomplete(self, enabled: bool = True):
        """Enable or disable autocomplete."""
        self._autocomplete_enabled = enabled
    
    def set_min_autocomplete_chars(self, min_chars: int):
        """Set minimum characters required before showing autocomplete."""
        self._min_chars_for_autocomplete = max(1, min_chars)