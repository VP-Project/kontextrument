#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Generates Markdown with heading levels indicating file/directory depth.
Supports configuration sections, preamble, appendix, binary file skipping,
summary control, file tree, "addself" option to include the script itself,
and "include" option to force-include specific files.

Enhanced with:
- Default .gitignore exclusion (unless explicitly included)
- Automatic processing of .gitignore rules.
- Relative path support in include/exclude lists
- FIXED: Nested subdirectories now work properly when using LIST option
'''

from __future__ import annotations
import argparse
import io
import os
import sys
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import configparser

try:
    import pathspec
except ImportError:
    pathspec = None

DEFAULT_OUTPUT_FILENAME = 'context.md'
DEFAULT_CONFIG_FILENAME = '.context'
DEFAULT_SECTION_NAME = 'DEFAULT'

class ContextGenerator:
    """Generates a markdown-based context file from a directory structure."""
    def __init__(
        self,
        working_path: str = '.',
        *,
        script_name_to_exclude: Optional[str] = None,
        verbose: bool = True,
        is_root: bool = True,
        current_depth: int = 0,
        root_path: Optional[Path] = None,
        gitignore_spec: Optional['pathspec.PathSpec'] = None
    ):
        """Initializes the ContextGenerator."""
        self.working_path = Path(working_path).resolve()
        if not self.working_path.is_dir():
            raise FileNotFoundError(f"Working path '{working_path}' is not a directory.")
        self.script_name_to_exclude = script_name_to_exclude
        self.verbose = verbose
        self.is_root = is_root
        self.current_depth = current_depth
        self.root_path = root_path if root_path else self.working_path
        self.gitignore_spec = gitignore_spec

        self.config_found = False
        self.loaded_config_filename: Optional[str] = None
        self.target_extensions: Optional[Set[str]] = None
        self.excluded_items: Set[str] = {'.gitignore', '.context', '.ktrsettings'}
        self.output_filename = DEFAULT_OUTPUT_FILENAME
        self.subdir_option = '#NONE'
        self.preamble: Optional[str] = None
        self.appendix: Optional[str] = None
        self.summary = True
        self.include_file_tree = False
        self.include_formatting_instructions = False
        self.include_items: Set[str] = set()
        self.include_preamble_in_output = True
        self.include_appendix_in_output = True

        if self.is_root:
            self._load_gitignore()

    def _load_gitignore(self):
        """Loads and parses the .gitignore file from the root path."""
        if not pathspec:
            if self.verbose:
                print("Warning: 'pathspec' library not found. Ignoring .gitignore file.")
                print("         To enable, please install it via: pip install pathspec")
            return

        gitignore_path = self.root_path / '.gitignore'
        if gitignore_path.is_file():
            try:
                with gitignore_path.open('r', encoding='utf-8') as f:
                    patterns = f.read().splitlines()
                self.gitignore_spec = pathspec.PathSpec.from_lines('gitwildmatch', patterns)
            except Exception as e:
                if self.verbose:
                    print(f"Warning: Could not read or parse .gitignore file: {e}")
                self.gitignore_spec = None
        else:
            if self.verbose:
                pass

    def _get_relative_path(self, path: Path) -> str:
        """Get relative path from root in Unix style."""
        try:
            rel_path = path.relative_to(self.root_path)
            return str(rel_path).replace('\\', '/')
        except ValueError:
            return str(path).replace('\\', '/')

    def _is_excluded(self, file_path: Path) -> bool:
        """
        Check if an item is excluded.

        The logic is as follows:
        1. If the item is explicitly in the 'include' list, it is NOT excluded.
        2. If the item is in the '.context' 'excludedfiles' list, it IS excluded.
        3. If the item matches a '.gitignore' pattern:
           a. If it's a file, it IS excluded.
           b. If it's a directory, it is ONLY excluded if no explicitly included
              files are located inside it.
        4. Otherwise, it is NOT excluded.
        """
        name = file_path.name
        rel_path = self._get_relative_path(file_path)

        if self._is_explicitly_included(file_path):
            return False

        for excluded_item in self.excluded_items:
            normalized_excluded_item = excluded_item.strip().replace('\\', '/')
            if '/' in normalized_excluded_item:
                if rel_path == normalized_excluded_item or rel_path == normalized_excluded_item.lstrip('./'):
                    return True
            else:
                if name == normalized_excluded_item:
                    return True

        if self.gitignore_spec:
            if self.gitignore_spec.match_file(rel_path):
                if file_path.is_dir():
                    dir_prefix = rel_path if rel_path != '.' else ''
                    if dir_prefix:
                        dir_prefix += '/'

                    for included_path_str in self.include_items:
                        normalized_include = included_path_str.strip().replace('\\', '/').lstrip('./')
                        if normalized_include.startswith(dir_prefix):
                            return False
                
                return True

        return False

    def _is_explicitly_included(self, file_path: Path) -> bool:
        """
        Check if a file is explicitly included based on filename or relative path.
        """
        name = file_path.name
        rel_path = self._get_relative_path(file_path)
        
        for included_item in self.include_items:
            normalized_included_item = included_item.strip().replace('\\', '/')
            if '/' in normalized_included_item:
                if rel_path == normalized_included_item or rel_path == normalized_included_item.lstrip('./'):
                    return True
            else:
                if name == normalized_included_item:
                    return True
        
        return False

    def _should_silently_exclude(self, item_path: Path) -> bool:
        """
        Check if an item should be silently excluded (not counted in excluded lists).
        These items are completely ignored during processing.
        """
        name = item_path.name
        
        if self.script_name_to_exclude and name == self.script_name_to_exclude:
            return True
        
        if self.is_root and self.config_found and self.loaded_config_filename and name == self.loaded_config_filename:
            return True
        
        if item_path.is_dir():
            if name in {'.git', '__pycache__', 'temp', '.venv', 'venv'}:
                return True
            if name.startswith('~') or (name.startswith('.') and name != '.'):
                return True
        
        return False

    def _process_content_with_file_blocks(self, content: str) -> str:
        """
        Process content string and replace {filename} blocks with file content.
        Searches for files relative to the working directory.
        """
        if not content:
            return content
        
        pattern = r'\{([^}]+)\}'
        
        def replace_file_block(match):
            filename = match.group(1).strip()
            
            file_path = None
            if Path(filename).is_absolute():
                file_path = Path(filename)
            else:
                file_path = self.working_path / filename
                if not file_path.is_file():
                    file_path = self.root_path / filename
            
            if file_path and file_path.is_file():
                try:
                    file_content = file_path.read_text(encoding='utf-8')
                    if self.verbose:
                        print(f"Replaced {{{filename}}} with content from {file_path}")
                    return file_content.rstrip()
                except Exception as e:
                    if self.verbose:
                        print(f"Error reading file {file_path} for {{{filename}}} block: {e}")
                    return f"[Error reading {filename}: {e}]"
            else:
                if self.verbose:
                    print(f"File not found for {{{filename}}} block")
                return f"[File not found: {filename}]"
        
        processed_content = re.sub(pattern, replace_file_block, content)
        return processed_content

    @staticmethod
    def is_binary_file(path: Path) -> bool:
        """Checks if a file is likely binary by reading a sample for null bytes."""
        try:
            with path.open('rb') as f:
                return b'\x00' in f.read(1024)
        except Exception:
            return False

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """
        Estimates the number of tokens in a string.
        A common heuristic is that one token is approximately 4 characters.
        """
        if not text:
            return 0
        return round(len(text) / 4)

    def load_config_from_file(
        self,
        filename: str = DEFAULT_CONFIG_FILENAME,
        section: Optional[str] = None
    ) -> None:
        """Loads and applies settings from a .context configuration file."""
        self.loaded_config_filename = filename
        path = self.working_path / filename
        if not path.is_file():
            if self.loaded_config_filename == filename:
                    self.config_found = False
            return

        parser = configparser.ConfigParser()
        try:
            parser.read(path, encoding='utf-8')
            if section and section in parser:
                sec = parser[section]
            elif parser.sections():
                sec = parser[parser.sections()[0]]
            else:
                sec = parser[DEFAULT_SECTION_NAME] if DEFAULT_SECTION_NAME in parser else {}
            
            self.config_found = True
        except Exception as e:
            if self.verbose:
                print(f"Error reading config {path}: {e}")
            self.config_found = False
            return

        if sec.get('filetypes'):
            exts = [e.strip().lstrip('.') for e in sec.get('filetypes', '').split(',') if e.strip()]
            self.target_extensions = {'.' + e for e in exts}
        
        if sec.get('excludedfiles'):
            config_excluded = {e.strip() for e in sec.get('excludedfiles', '').split(',') if e.strip()}
            self.excluded_items = {'.gitignore', '.context', '.ktrsettings'} | config_excluded
        
        if sec.get('outputfile'):
            self.output_filename = sec.get('outputfile').strip()
        if sec.get('subdirectories'):
            self.subdir_option = sec.get('subdirectories').strip()
        if sec.get('preamble'):
            self.preamble = sec.get('preamble')
        if sec.get('appendix'):
            self.appendix = sec.get('appendix')
        if sec.get('summary'):
            self.summary = sec.getboolean('summary', fallback=True)
        
        if sec.get('include'):
            includes = [e.strip() for e in sec.get('include', '').split(',') if e.strip()]
            self.include_items = set(includes)
        
        if sec.get('filetree'):
            self.include_file_tree = sec.getboolean('filetree', fallback=False)
        if sec.get('formattinginstructions'):
            self.include_formatting_instructions = sec.getboolean('formattinginstructions', fallback=False)
        if sec.get('includepreamble'):
            self.include_preamble_in_output = sec.getboolean('includepreamble', fallback=True)
        if sec.get('includeappendix'):
            self.include_appendix_in_output = sec.getboolean('includeappendix', fallback=True)

    def _subdir_selected(self, name: str, path: Path) -> bool:
        opt = (self.subdir_option or '#NONE').strip().upper()
        if opt == '#NONE':
            return False
        if opt == '#ALL':
            return True
        return name in {d.strip() for d in self.subdir_option.split(',') if d.strip()}

    def _language_hint(self, ext: str) -> str:
        mapping = {
            '.py': 'python', '.json': 'json', '.js': 'javascript',
            '.html': 'html', '.css': 'css', '.yaml': 'yaml',
            '.yml': 'yaml', '.xml': 'xml', '.md': 'markdown',
            '.sh': 'bash'
        }
        return mapping.get(ext.lower(), ext.lstrip('.'))

    def _generate_file_tree(self, path: Path = None, prefix: str = "", is_last: bool = True, depth: int = 0) -> str:
        """Generate a tree structure showing files and their status."""
        if path is None:
            path = self.working_path
        
        tree_lines = []
        
        all_items = list(path.iterdir())
        items = [item for item in all_items if not self._should_silently_exclude(item)]
        items = sorted(items, key=lambda x: (x.is_file(), x.name.lower()))
        
        for i, item in enumerate(items):
            is_last_item = i == (len(items) - 1)
            current_prefix = "└── " if is_last_item else "├── "
            
            status = ""
            if item.is_file():
                if self._should_include_file_in_content(item):
                    if self.is_binary_file(item):
                        status = " [binary]"
                    else:
                        status = " [included]"
                else:
                    if self.is_binary_file(item):
                        status = " [binary]"
                    else:
                        status = " [excluded]"
            elif item.is_dir():
                if self._subdir_selected(item.name, item):
                    status = " [included]"
                else:
                    status = " [excluded]"
            
            tree_lines.append(f"{prefix}{current_prefix}{item.name}{status}")
            
            if item.is_dir() and self._subdir_selected(item.name, item) and depth < 10:
                extension = "    " if is_last_item else "│   "
                subtree = self._generate_file_tree(item, prefix + extension, True, depth + 1)
                if subtree:
                    tree_lines.append(subtree)
        
        return "\n".join(tree_lines)

    def _should_include_file_in_content(self, file_path: Path) -> bool:
        """Check if a file should be included in content generation."""
        name = file_path.name
        
        if name == self.output_filename:
            return False
            
        if self._is_excluded(file_path):
            return False
        
        if self.target_extensions is None:
            if not self.include_items:
                return True
            elif self._is_explicitly_included(file_path):
                return True
        else:
            if file_path.suffix.lower() in self.target_extensions or self._is_explicitly_included(file_path):
                return True
        
        return False

    def get_file_lists(self) -> Dict[str, List[str]]:
        """Recursively scans the directory to categorize files as included, excluded, or skipped."""
        always_excluded_patterns = {self.output_filename}

        all_files: List[str] = []
        included_files: List[str] = []
        excluded_files: List[str] = []
        skipped_files: List[str] = []

        def process_directory_recursively(dir_path: Path, relative_base: Path = None):
            """Recursively process directories and collect file information."""
            if relative_base is None:
                relative_base = self.root_path
                
            all_items = list(dir_path.iterdir())
            items = [item for item in all_items if not self._should_silently_exclude(item)]
            items = sorted(items)
            
            for item in items:
                if item.is_file():
                    try:
                        rel_path = item.relative_to(relative_base)
                        rel_path_str = str(rel_path).replace('\\', '/')
                    except ValueError:
                        rel_path_str = str(item).replace('\\', '/')
                    
                    name = item.name
                    all_files.append(rel_path_str)

                    if name == self.output_filename:
                        continue

                    if self._is_excluded(item):
                        excluded_files.append(rel_path_str)
                        continue

                    if ContextGenerator.is_binary_file(item):
                        skipped_files.append(rel_path_str)
                        excluded_files.append(f"{rel_path_str} (binary)")
                        continue

                    should_be_included = False
                    if self.target_extensions is None:
                        if not self.include_items:
                            should_be_included = True
                        elif self._is_explicitly_included(item):
                            should_be_included = True
                    else:
                        if item.suffix.lower() in self.target_extensions or self._is_explicitly_included(item):
                            should_be_included = True
                    
                    if should_be_included:
                        included_files.append(rel_path_str)
                    else:
                        excluded_files.append(rel_path_str)
                
                elif item.is_dir():
                    if self._subdir_selected(item.name, item):
                        process_directory_recursively(item, relative_base)
        
        process_directory_recursively(self.working_path)
                                
        return {
            'all_files': all_files,
            'included_files': included_files,
            'excluded_files': excluded_files,
            'skipped_files': skipped_files
        }

    def generate_context_string(self, include_summary: bool = True) -> Dict[str, Any]:
        """Generates the complete markdown context string from files and subdirectories."""
        files_included = 0
        items_skipped_from_content = 0
        read_errors: List[str] = []
        buf = io.StringIO()

        file_lists_data = self.get_file_lists()
        included_files_for_list_section = file_lists_data['included_files']
        excluded_files_for_list_section = file_lists_data['excluded_files']

        if self.is_root and self.preamble is not None and self.include_preamble_in_output:
            processed_preamble = self._process_content_with_file_blocks(self.preamble)
            buf.write(processed_preamble.rstrip() + '\n\n')

        always_excluded_patterns_content = {self.output_filename}
        
        all_items = list(self.working_path.iterdir())
        items_to_process = [item for item in all_items if not self._should_silently_exclude(item)]
        items_to_process = sorted(items_to_process)
        
        files_for_content: List[Path] = []
        dirs_for_content: List[Path] = []

        for item in items_to_process:
            item_name = item.name
            if item_name == self.output_filename:
                continue
            
            if self._is_excluded(item):
                items_skipped_from_content += 1
                continue
            
            if item.is_file():
                files_for_content.append(item)
            elif item.is_dir():
                dirs_for_content.append(item)
            else:
                items_skipped_from_content += 1

        for item_path in files_for_content:
            name = item_path.name
            if ContextGenerator.is_binary_file(item_path):
                if self.verbose:
                    print(f"Skipping binary file for content: {name}")
                items_skipped_from_content += 1
                continue

            process_this_file_content = False
            if self.target_extensions is None:
                if not self.include_items:
                    process_this_file_content = True
                elif self._is_explicitly_included(item_path):
                        process_this_file_content = True
            else:
                if item_path.suffix.lower() in self.target_extensions or self._is_explicitly_included(item_path):
                    process_this_file_content = True
            
            if not process_this_file_content:
                items_skipped_from_content += 1
                continue

            if self.verbose:
                print(f"Including file in content: {name}")
            files_included += 1
            
            rel_path = self._get_relative_path(item_path)
            
            buf.write(f"### FILE: {rel_path}\n")
            buf.write("```\n")
            try:
                text = item_path.read_text(encoding='utf-8')
                buf.write(text.rstrip() + '\n')
            except Exception as e:
                read_errors.append(name)
                buf.write(f"--- Error reading {name}: {e} ---\n")
            buf.write("```\n\n")

        for item_path in dirs_for_content:
            name = item_path.name
            if self._subdir_selected(name, item_path):
                if self.verbose:
                    print(f"Processing subdir: {name} (Depth: {self.current_depth+1})")
                
                child = ContextGenerator(
                    str(item_path),
                    script_name_to_exclude=self.script_name_to_exclude,
                    verbose=self.verbose,
                    is_root=False,
                    current_depth=self.current_depth + 1,
                    root_path=self.root_path,
                    gitignore_spec=self.gitignore_spec
                )
                
                parent_subdir_option = self.subdir_option
                parent_target_extensions = self.target_extensions.copy() if self.target_extensions else None
                parent_excluded_items = self.excluded_items.copy()
                parent_include_items = self.include_items.copy()
                
                child.load_config_from_file(DEFAULT_CONFIG_FILENAME)
                
                child.subdir_option = parent_subdir_option
                if parent_target_extensions:
                    if child.target_extensions:
                        child.target_extensions = parent_target_extensions | child.target_extensions
                    else:
                        child.target_extensions = parent_target_extensions
                child.excluded_items = child.excluded_items | parent_excluded_items
                child.include_items = child.include_items | parent_include_items
                
                child.summary = self.summary

                sub_result = child.generate_context_string(include_summary=False)
                
                if sub_result['files_included_count'] > 0:
                    files_included += sub_result['files_included_count']
                    items_skipped_from_content += sub_result['files_skipped_count']
                    read_errors.extend(sub_result['files_errored'])
                    
                    rel_dir_path = self._get_relative_path(item_path)
                    buf.write(f"## DIRECTORYSECTION {rel_dir_path}\n\n")
                    buf.write(sub_result['markdown_content'])
                else:
                    items_skipped_from_content += sub_result['files_skipped_count']

            else:
                items_skipped_from_content += 1

        if self.is_root and self.appendix is not None and self.include_appendix_in_output:
            processed_appendix = self._process_content_with_file_blocks(self.appendix)
            buf.write(processed_appendix.rstrip() + '\n\n')

        if self.is_root and self.include_file_tree:
            buf.write('---\n\n**File Tree:**\n\n')
            buf.write("```\n")
            tree_output = self._generate_file_tree()
            buf.write(tree_output)
            buf.write('\n```\n\n')

        markdown_content_before_summary = buf.getvalue()
        estimated_tokens = self._estimate_tokens(markdown_content_before_summary)

        if self.is_root and include_summary and self.summary:
            buf.write('---\n\n**Summary:**\n')
            buf.write(f'* Files included in context content: {files_included}\n')
            buf.write(f'* Items skipped during content generation (dirs, non-matching files, binaries): {items_skipped_from_content}\n')
            buf.write(f'* Estimated token count (approx): {estimated_tokens}\n')
            if read_errors:
                buf.write(f'* Read errors ({len(read_errors)}): {", ".join(read_errors)}\n')

        if self.is_root and self.include_formatting_instructions:
            buf.write('\n---\n\n## FORMATTING INSTRUCTIONS\n')
            buf.write('Produce a plain text document with these rules:\n')
            buf.write('1. Preamble (optional):\n')
            buf.write('   Add preamble text or content from a file at the top, if needed.\n')
            buf.write('   Use {filename} blocks to include file content inline.\n')
            buf.write('2. Files:\n')
            buf.write('   For each included file, use this format:\n')
            buf.write('   "### FILE: <relative/path>"\n')
            buf.write("```\n")
            buf.write('   (file content goes here)\n')
            buf.write('   "```"\n')
            buf.write('   Use project-root-relative paths with forward slashes. The code block should immediately follow the header. The end of the file is marked by the closing of the code block.\n')
            buf.write('3. Directories:\n')
            buf.write('   For selected subdirectories, start a section with:\n')
            buf.write('   "## DIRECTORYSECTION <relative/path>"\n')
            buf.write('   Recursively include subdirectory content as above.\n')
            buf.write('4. Removals:\n')
            buf.write('   To remove items, use these formats. They should appear on their own without a following code block.\n')
            buf.write('   - "### DELETE FILE: <relative/path>": Permanently deletes the specified file.\n')
            buf.write('   - "### DELETE DIRECTORY: <relative/path>": Permanently deletes the specified directory, but only if it is empty.\n')
            buf.write('5. File Lists (optional):\n')
            buf.write('   Include lists showing:\n')
            buf.write('   * Included Files in Context\n')
            buf.write('   * Excluded/Skipped Items\n')
            buf.write('6. Appendix (optional):\n')
            buf.write('   Add appendix text or file content at the end if needed.\n')
            buf.write('   Use {filename} blocks to include file content inline.\n')
            buf.write('7. In-place replacements (optional):\n')
            buf.write('   Add literal text replacements to existing files using this format:\n')
            buf.write('   "### REPLACE IN: <relative/path>"\n')
            buf.write('   "```"\n')
            buf.write('   (text to find, matched literally)\n')
            buf.write('   "```"\n')
            buf.write('   "WITH"\n')
            buf.write('   "```"\n')
            buf.write('   (replacement text, inserted literally)\n')
            buf.write('   "```"\n')
            buf.write('   Rules and notes:\n')
            buf.write('   - Paths are project-root-relative with forward slashes, identical to file paths elsewhere.\n')
            buf.write('   - The first code block contains the exact search text; the second contains the replacement. No regex or templating; matches and replacements are literal.\n')
            buf.write('   - FILE blocks should be used for whole files, REPLACE IN blocks should be used for small changes in a small section of a large file. Avoid using REPLACE IN with large blocks of code.\n')
            buf.write('   - Indentation should be preserved exactly in REPLACE IN blocks.\n')
            buf.write('   - The separator line must be WITH on its own line; case-insensitive is allowed.\n')
            buf.write('   - The opening code fence must immediately follow the REPLACE IN header; closing fences mark the end of each block.\n')
            buf.write('   - Multiple REPLACE IN blocks may be provided and are applied in document order for the same file.\n')
            buf.write('   - Non-breaking spaces are treated as regular spaces inside code blocks.\n')
            buf.write('   - If a target file does not exist, the replacement block may be ignored or reported by downstream tools according to their settings.\n')
            buf.write('   - If overwrite protections are enabled downstream, replacements for existing files may be skipped according to those settings.\n')

        markdown_content = buf.getvalue()
        buf.close()

        final_estimated_tokens = self._estimate_tokens(markdown_content)

        return {
            'success': True,
            'markdown_content': markdown_content,
            'files_included_count': files_included,
            'files_skipped_count': items_skipped_from_content,
            'files_errored': read_errors,
            'files_included_list_overview': included_files_for_list_section,
            'files_skipped_list_overview': excluded_files_for_list_section,
            'estimated_tokens': final_estimated_tokens,
        }

    def write_context_to_file(self) -> Dict[str, Any]:
        """Generates the context string and writes it to the configured output file."""
        res = self.generate_context_string(include_summary=True)
        if self.is_root:
            out_path = self.working_path / self.output_filename
            res['output_filepath'] = str(out_path)
            try:
                out_path.write_text(res['markdown_content'], encoding='utf-8')
                if self.verbose:
                    print(f"Wrote context to {out_path}")
            except Exception as e:
                res['success'] = False
                res['message'] = f'Error writing file: {e}'
        return res

def main_cli():
    """Command-line interface entry point for the context generation script."""
    ap = argparse.ArgumentParser(
        description='Generate a combined Markdown context for an LLM.',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument('directory', nargs='?', default='.', help='Project root directory to scan.')
    ap.add_argument('-c', '--config', default=DEFAULT_CONFIG_FILENAME, help=f'Config file name (default: {DEFAULT_CONFIG_FILENAME}).')
    ap.add_argument('-s', '--section', help='Config section to use.')
    ap.add_argument('-q', '--quiet', action='store_true', help='Suppress progress messages.')
    ap.add_argument('-v', '--verbose', action='store_true', help='Print verbose actions like file processing details to console.')

    ns = ap.parse_args()

    script_verbose = ns.verbose
    
    gen = ContextGenerator(
        ns.directory,
        script_name_to_exclude=os.path.basename(sys.argv[0]),
        verbose=script_verbose,
        is_root=True,
        current_depth=0
    )
    gen.load_config_from_file(ns.config, section=ns.section)
    
    result = gen.write_context_to_file()

    if not result['success']:
        print('-'*30, file=sys.stderr)
        print(f"Directory: {gen.working_path}", file=sys.stderr)
        if result.get('output_filepath'):
            print(f"Output File: {result.get('output_filepath')}", file=sys.stderr)
        print('Status: Failed', file=sys.stderr)
        if result.get('message'):
            print(f"Message: {result.get('message')}", file=sys.stderr)
        print('-'*30, file=sys.stderr)
        sys.exit(1)
    else:
        if not ns.quiet:
            print('-'*30)
            print(f"Directory: {gen.working_path}")
            if result.get('output_filepath'):
                print(f"Output File: {result.get('output_filepath')}")
            print('Status: Success')
            print(f"Files Included in Context Content: {result.get('files_included_count')}" )
            print(f"Items Skipped from Content: {result.get('files_skipped_count')}")
            if result.get('estimated_tokens'):
                print(f"Estimated Token Count: {result.get('estimated_tokens')}")
            errors = result.get('files_errored', [])
            if errors:
                print('Read errors: ' + ', '.join(errors))
            print('-'*30)
        sys.exit(0)

if __name__ == '__main__':
    main_cli()