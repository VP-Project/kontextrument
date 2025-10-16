#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ContextParser (header-driven)
Parses markdown exported by the companion tool to create files or apply replacements.
Comments avoid markdown-like syntax to prevent tooling issues.
"""

import argparse
import os
import re
import sys
import difflib
from pathlib import Path
from typing import List, Dict, Tuple, Optional


class ContextParser:
    """Reconstructs files from a context markdown and applies replacements."""

    def __init__(self, output_dir: Path, overwrite: bool, verbose: bool = True, dry_run: bool = False, tabs_to_spaces: Optional[int] = None):
        """Initializes the ContextParser."""
        self.output_base_dir = output_dir.resolve()
        self.overwrite = overwrite
        self.verbose = verbose
        self.dry_run = dry_run
        self.tabs_to_spaces = tabs_to_spaces

        self.files_created: List[str] = []
        self.files_overwritten: List[str] = []
        self.files_skipped: List[str] = []
        self.dirs_created: List[str] = []
        self.files_removed: List[str] = []
        self.dirs_removed: List[str] = []
        self.dirs_skipped_removal: List[str] = []
        self.errors: List[str] = []
        self.virtual_fs: Dict[str, str] = {}
        self.original_content_cache: Dict[str, str] = {}
        self.pending_file_removals: List[Path] = []
        self.pending_dir_removals: List[Path] = []
        self.diffs: Dict[str, str] = {}

        self.FENCE3 = "`" * 3
        self.FENCE4 = "`" * 4

    def _normalize_content(self, content: str, is_code_block: bool = False) -> str:
        """
        Single source of truth for all character replacements and normalizations.
        
        This method handles both obligatory and optional character conversions:
        - NBSP (U+00A0) to regular space: ALWAYS applied (obligatory)
        - Tab to spaces: ONLY applied if tabs_to_spaces option is set (optional)
        
        Args:
            content: The text content to normalize
            is_code_block: Whether this content is from a code block (affects NBSP handling)
        
        Returns:
            Normalized content with all applicable replacements applied
        """
        normalized = content.replace('\u00a0', ' ')
        
        if self.tabs_to_spaces is not None and self.tabs_to_spaces > 0:
            spaces = ' ' * self.tabs_to_spaces
            normalized = normalized.replace('\t', spaces)
        
        return normalized
    
    def _normalize_for_search(self, content: str) -> str:
        """
        Normalize content specifically for search/replacement operations.
        
        When searching for text in replacement operations, we need to normalize
        both the search pattern and the content being searched. This ensures that
        NBSPs in the markdown context match regular spaces in the actual files.
        
        Args:
            content: The content to normalize for search
        
        Returns:
            Normalized content suitable for search operations
        """
        return self._normalize_content(content.replace('\u00a0', ' '))

    def _ensure_dir_exists(self, dir_path: Path) -> None:
        created_this_time = False
        if not dir_path.exists():
            created_this_time = True
        try:
            if not self.dry_run:
                dir_path.mkdir(parents=True, exist_ok=True)
            if created_this_time:
                try:
                    rel_dir_path_str = str(dir_path.relative_to(self.output_base_dir))
                    if rel_dir_path_str != "." and rel_dir_path_str not in self.dirs_created:
                        self.dirs_created.append(rel_dir_path_str)
                except ValueError:
                    if str(dir_path) not in self.dirs_created:
                        self.dirs_created.append(str(dir_path))
                if self.verbose:
                    print(f"{'[Dry Run] ' if self.dry_run else ''}Created directory: {dir_path}")
        except Exception as e:
            self.errors.append(f"Error creating directory '{dir_path}': {e}")

    def _rel_path_str(self, file_path: Path) -> str:
        try:
            if file_path.is_absolute() and self.output_base_dir.is_absolute():
                return str(file_path.relative_to(self.output_base_dir))
        except ValueError:
            pass
        return str(file_path)

    def _resolve_output_path(self, file_path_str: str) -> Path:
        file_path_parts = file_path_str.split('/')
        file_path = self.output_base_dir
        for part in file_path_parts:
            file_path = file_path / part
        return file_path

    def _create_file(self, file_path: Path, content: str, is_code_block: bool = False) -> None:
        self._ensure_dir_exists(file_path.parent)
        try:
            rel_file_path_str = self._rel_path_str(file_path)
        except Exception:
            rel_file_path_str = str(file_path)

        processed_content = self._normalize_content(content, is_code_block)

        if file_path.exists():
            if self.overwrite:
                try:
                    original_content = file_path.read_text(encoding="utf-8")
                    diff = difflib.unified_diff(
                        original_content.splitlines(keepends=True),
                        processed_content.splitlines(keepends=True),
                        fromfile=f"a/{rel_file_path_str}",
                        tofile=f"b/{rel_file_path_str}",
                    )
                    diff_text = "".join(diff)
                    if diff_text:
                        self.diffs[rel_file_path_str] = diff_text

                    if not self.dry_run:
                        file_path.write_text(processed_content, encoding="utf-8")
                    else:
                        self.virtual_fs[rel_file_path_str] = processed_content

                    if rel_file_path_str not in self.files_overwritten:
                        self.files_overwritten.append(rel_file_path_str)
                    if self.verbose:
                        print(f"{'[Dry Run] ' if self.dry_run else ''}Overwritten file: {file_path}")
                except Exception as e:
                    self.errors.append(f"Error overwriting file '{file_path}': {e}")
            else:
                if rel_file_path_str not in self.files_skipped:
                    self.files_skipped.append(rel_file_path_str)
                if self.verbose:
                    print(f"{'[Dry Run] ' if self.dry_run else ''}Skipped existing file: {file_path}")
        else:
            try:
                diff = difflib.unified_diff(
                    [],
                    processed_content.splitlines(keepends=True),
                    fromfile=f"a/{rel_file_path_str}",
                    tofile=f"b/{rel_file_path_str}",
                )
                diff_text = "".join(diff)
                if diff_text:
                    self.diffs[rel_file_path_str] = diff_text

                if not self.dry_run:
                    file_path.write_text(processed_content, encoding="utf-8")
                else:
                    self.virtual_fs[rel_file_path_str] = processed_content

                if rel_file_path_str not in self.files_created:
                    self.files_created.append(rel_file_path_str)
                if self.verbose:
                    print(f"{'[Dry Run] ' if self.dry_run else ''}Created file: {file_path}")
            except Exception as e:
                self.errors.append(f"Error creating file '{file_path}': {e}")

    def _read_current_content(self, file_path: Path) -> Tuple[str, str, bool]:
        rel = self._rel_path_str(file_path)
        if self.dry_run and rel in self.virtual_fs:
            return self.virtual_fs[rel], rel, file_path.exists()
        if file_path.exists():
            try:
                return file_path.read_text(encoding="utf-8"), rel, True
            except Exception as e:
                self.errors.append(f"Error reading file '{file_path}': {e}")
                return "", rel, True
        return "", rel, False

    def _write_replacement_result(self, file_path: Path, rel: str, original_for_diff: str, new_content: str, existed_on_disk: bool) -> None:
        if existed_on_disk and not self.overwrite:
            if rel not in self.files_skipped:
                self.files_skipped.append(rel)
            if self.verbose:
                print(f"{'[Dry Run] ' if self.dry_run else ''}Skipped replacement (overwrite disabled): {file_path}")
            return

        self._ensure_dir_exists(file_path.parent)

        diff = difflib.unified_diff(
            original_for_diff.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{rel}",
            tofile=f"b/{rel}",
        )
        diff_text = "".join(diff)
        if diff_text:
            self.diffs[rel] = diff_text

        try:
            if not self.dry_run:
                file_path.write_text(new_content, encoding="utf-8")
            else:
                self.virtual_fs[rel] = new_content
        except Exception as e:
            self.errors.append(f"Error writing replacement to '{file_path}': {e}")
            return

        if existed_on_disk:
            if rel not in self.files_overwritten:
                self.files_overwritten.append(rel)
            if self.verbose:
                print(f"{'[Dry Run] ' if self.dry_run else ''}Applied replacement (overwrite): {file_path}")
        else:
            if rel not in self.files_created:
                self.files_created.append(rel)
            if self.verbose:
                print(f"{'[Dry Run] ' if self.dry_run else ''}Applied replacement (create): {file_path}")

    def _apply_replacement(self, file_path: Path, search_text: str, replacement_text: str) -> None:
        processed_search = self._normalize_content(search_text, is_code_block=True)
        processed_replacement = self._normalize_content(replacement_text, is_code_block=True)

        current_content, rel, existed_on_disk = self._read_current_content(file_path)

        if rel not in self.original_content_cache:
            self.original_content_cache[rel] = current_content

        if not current_content and not existed_on_disk:
            self.errors.append(f"Replacement target not found: '{rel}'")
            if self.verbose:
                print(f"{'[Dry Run] ' if self.dry_run else ''}ERROR: Replacement target not found: {file_path}")
            return

        processed_current_for_search = self._normalize_for_search(current_content)

        new_content = processed_current_for_search.replace(processed_search, processed_replacement)

        if new_content == processed_current_for_search:
            if rel not in self.files_skipped:
                self.files_skipped.append(rel)
            if self.verbose:
                print(f"{'[Dry Run] ' if self.dry_run else ''}No occurrences to replace in: {file_path}")
            return

        original_for_diff = self.original_content_cache[rel]
        self._write_replacement_result(file_path, rel, original_for_diff, new_content, existed_on_disk)

    def _remove_file(self, file_path: Path) -> None:
        rel_file_path_str = self._rel_path_str(file_path)

        if not file_path.exists():
            if self.verbose:
                print(f"{'[Dry Run] ' if self.dry_run else ''}Skipped removing non-existent file: {file_path}")
            return

        try:
            if not self.dry_run:
                os.remove(file_path)
            
            if rel_file_path_str not in self.files_removed:
                self.files_removed.append(rel_file_path_str)
            
            if self.verbose:
                print(f"{'[Dry Run] ' if self.dry_run else ''}Removed file: {file_path}")

        except Exception as e:
            self.errors.append(f"Error removing file '{file_path}': {e}")

    def _remove_directory(self, dir_path: Path) -> None:
        rel_dir_path_str = self._rel_path_str(dir_path)

        if not dir_path.exists():
            if self.verbose:
                print(f"{'[Dry Run] ' if self.dry_run else ''}Skipped removing non-existent directory: {dir_path}")
            return
        
        if not dir_path.is_dir():
            self.errors.append(f"Cannot remove '{dir_path}': It is not a directory.")
            return

        try:
            if any(dir_path.iterdir()):
                if rel_dir_path_str not in self.dirs_skipped_removal:
                    self.dirs_skipped_removal.append(rel_dir_path_str)
                if self.verbose:
                    print(f"{'[Dry Run] ' if self.dry_run else ''}Skipped removing non-empty directory: {dir_path}")
                return

            if not self.dry_run:
                os.rmdir(dir_path)

            if rel_dir_path_str not in self.dirs_removed:
                self.dirs_removed.append(rel_dir_path_str)

            if self.verbose:
                print(f"{'[Dry Run] ' if self.dry_run else ''}Removed empty directory: {dir_path}")

        except Exception as e:
            self.errors.append(f"Error removing directory '{dir_path}': {e}")

    def parse_and_create(self, markdown_content: str) -> None:
        """
        Parses the markdown content to create/modify files and directories.
        Removal operations are collected but not executed until explicitly called.
        """
        self.files_created = []
        self.files_overwritten = []
        self.files_skipped = []
        self.dirs_created = []
        self.files_removed = []
        self.dirs_removed = []
        self.dirs_skipped_removal = []
        self.pending_file_removals = []
        self.pending_dir_removals = []
        self.errors = []
        self.virtual_fs = {}
        self.original_content_cache = {}
        self.diffs = {}

        summary_start_marker = "\n---\n\n**Summary:**"
        summary_pos = markdown_content.rfind(summary_start_marker)
        content_body = markdown_content[:summary_pos] if summary_pos != -1 else markdown_content

        file_header_pattern = re.compile(r'^(?:#+)\s+FILE:\s*(.+)')
        replace_header_pattern = re.compile(r'^(?:#+)\s+REPLACE IN:\s*(.+)')
        remove_file_header_pattern = re.compile(r'^(?:#+)\s+DELETE FILE:\s*(.+)')
        remove_dir_header_pattern = re.compile(r'^(?:#+)\s+DELETE DIRECTORY:\s*(.+)')

        lines = content_body.splitlines()
        idx = 0

        while idx < len(lines):
            line = lines[idx]
            cleaned_line = line.replace('*', '')
            stripped = cleaned_line.strip()

            match_file = file_header_pattern.match(stripped)
            if match_file:
                file_path_str = match_file.group(1).strip()
                if len(file_path_str) > 1 and file_path_str[0] == file_path_str[-1] and file_path_str[0] in ('"', "'", '`'):
                    file_path_str = file_path_str[1:-1]
                file_path_str = file_path_str.replace('\\', '')
                if self.verbose:
                    print(f"Found file marker: {file_path_str}")

                idx += 1
                while idx < len(lines) and not lines[idx].strip().startswith(self.FENCE3):
                    idx += 1

                if idx >= len(lines):
                    self.errors.append(f"Expected code block start fence for file '{file_path_str}', but reached end of file.")
                    continue

                code_fence_line = lines[idx].strip()
                language = code_fence_line[len(self.FENCE3):].strip()
                is_code_block = bool(language)

                idx += 1

                file_content_lines: List[str] = []
                while idx < len(lines) and not lines[idx].strip() in (self.FENCE3, self.FENCE4):
                    file_content_lines.append(lines[idx])
                    idx += 1

                file_content = "\n".join(file_content_lines)

                if idx >= len(lines):
                    self.errors.append(f"Missing closing code block fence for file '{file_path_str}'.")

                try:
                    file_path = self._resolve_output_path(file_path_str)
                    self._create_file(file_path, file_content, is_code_block)
                except Exception as e:
                    self.errors.append(f"Error processing file path '{file_path_str}': {e}")

                if idx < len(lines):
                    idx += 1
                continue

            match_repl = replace_header_pattern.match(stripped)
            if match_repl:
                file_path_str = match_repl.group(1).strip()
                if len(file_path_str) > 1 and file_path_str[0] == file_path_str[-1] and file_path_str[0] in ('"', "'", '`'):
                    file_path_str = file_path_str[1:-1]
                file_path_str = file_path_str.replace('\\', '')
                if self.verbose:
                    print(f"Found replace marker: {file_path_str}")

                idx += 1

                while idx < len(lines) and not lines[idx].strip().startswith(self.FENCE3):
                    if lines[idx].strip() and lines[idx].strip().upper() == "WITH":
                        self.errors.append(f"Unexpected 'WITH' before search text code block for '{file_path_str}'.")
                    idx += 1

                if idx >= len(lines):
                    self.errors.append(f"Expected code block start fence for replacement search text in '{file_path_str}', but reached end of file.")
                    continue

                idx += 1

                search_lines: List[str] = []
                while idx < len(lines) and not lines[idx].strip() in (self.FENCE3, self.FENCE4):
                    search_lines.append(lines[idx])
                    idx += 1

                if idx >= len(lines):
                    self.errors.append(f"Missing closing code block fence for replacement search text in '{file_path_str}'.")
                    continue

                search_text = "\n".join(search_lines)

                idx += 1

                while idx < len(lines) and not lines[idx].strip():
                    idx += 1

                if idx >= len(lines) or lines[idx].strip().upper() != "WITH":
                    self.errors.append(f"Expected 'WITH' separator for replacement in '{file_path_str}'.")
                    continue

                idx += 1

                while idx < len(lines) and not lines[idx].strip().startswith(self.FENCE3):
                    if lines[idx].strip():
                        self.errors.append(f"Expected code block start fence for replacement text in '{file_path_str}', found unexpected content.")
                    idx += 1

                if idx >= len(lines):
                    self.errors.append(f"Expected code block start fence for replacement text in '{file_path_str}', but reached end of file.")
                    continue

                idx += 1

                replacement_lines: List[str] = []
                while idx < len(lines) and not lines[idx].strip() in (self.FENCE3, self.FENCE4):
                    replacement_lines.append(lines[idx])
                    idx += 1

                if idx >= len(lines):
                    self.errors.append(f"Missing closing code block fence for replacement text in '{file_path_str}'.")
                    continue

                replacement_text = "\n".join(replacement_lines)

                idx += 1

                try:
                    file_path = self._resolve_output_path(file_path_str)
                    self._apply_replacement(file_path, search_text, replacement_text)
                except Exception as e:
                    self.errors.append(f"Error processing replacement for '{file_path_str}': {e}")

                continue

            match_rem_file = remove_file_header_pattern.match(stripped)
            if match_rem_file:
                file_path_str = match_rem_file.group(1).strip()
                if len(file_path_str) > 1 and file_path_str[0] == file_path_str[-1] and file_path_str[0] in ('"', "'", '`'):
                    file_path_str = file_path_str[1:-1]
                file_path_str = file_path_str.replace('\\', '')
                if self.verbose:
                    print(f"Found remove file marker: {file_path_str}")
                
                try:
                    file_path = self._resolve_output_path(file_path_str)
                    self.pending_file_removals.append(file_path)
                except Exception as e:
                    self.errors.append(f"Error processing remove file path '{file_path_str}': {e}")
                
                idx += 1
                continue

            match_rem_dir = remove_dir_header_pattern.match(stripped)
            if match_rem_dir:
                dir_path_str = match_rem_dir.group(1).strip()
                if len(dir_path_str) > 1 and dir_path_str[0] == dir_path_str[-1] and dir_path_str[0] in ('"', "'", '`'):
                    dir_path_str = dir_path_str[1:-1]
                dir_path_str = dir_path_str.replace('\\', '')
                if self.verbose:
                    print(f"Found remove directory marker: {dir_path_str}")

                try:
                    dir_path = self._resolve_output_path(dir_path_str)
                    self.pending_dir_removals.append(dir_path)
                except Exception as e:
                    self.errors.append(f"Error processing remove directory path '{dir_path_str}': {e}")
                
                idx += 1
                continue

            idx += 1

        for lst_attr in ['files_created', 'files_overwritten', 'files_skipped', 'dirs_created', 'files_removed', 'dirs_removed', 'dirs_skipped_removal']:
            setattr(self, lst_attr, sorted(set(getattr(self, lst_attr))))

    def get_pending_removals(self) -> Tuple[List[Path], List[Path]]:
        """Returns lists of files and directories pending removal."""
        return self.pending_file_removals, self.pending_dir_removals

    def execute_pending_removals(self) -> None:
        """Executes the pending file and directory removal operations."""
        for file_path in self.pending_file_removals:
            self._remove_file(file_path)
        for dir_path in self.pending_dir_removals:
            self._remove_directory(dir_path)

    def report(self) -> None:
        """Prints a summary report of the parsing and file operations."""
        print("-" * 30)
        if self.dry_run:
            print("****DRY RUN****")
        print(f"Context Parsing Report")
        print(f"Output Base Directory: {self.output_base_dir}")
        if self.dirs_created: print(f"Directories Created: {len(self.dirs_created)}")
        if self.files_created: print(f"Files Created: {len(self.files_created)}")
        if self.files_overwritten: print(f"Files Overwritten: {len(self.files_overwritten)}")
        if self.files_removed: print(f"Files Removed: {len(self.files_removed)}")
        if self.dirs_removed: print(f"Directories Removed: {len(self.dirs_removed)}")
        if self.files_skipped: print(f"Files Skipped (already exist): {len(self.files_skipped)}")
        if self.dirs_skipped_removal: print(f"Directories Skipped (not empty): {len(self.dirs_skipped_removal)}")

        if self.errors:
            print(f"Errors ({len(self.errors)}):")
            for error in self.errors:
                print(f"  - {error}")

        total_actions = len(self.dirs_created) + len(self.files_created) + len(self.files_overwritten) + len(self.files_removed) + len(self.dirs_removed)
        if not self.errors and total_actions == 0 and not self.files_skipped:
            print("Status: No actions performed (input might have been empty or only contained skipped items).")
        elif not self.errors:
            print("Status: Success")
        else:
            print("Status: Completed with errors")

        if self.dry_run:
            print("****")
        print("-" * 30)


def main_cli() -> None:
    """Command-line interface entry point for the context application script."""
    parser = argparse.ArgumentParser(
        description="Reconstructs a directory structure from a context markdown file and applies replacements."
    )
    parser.add_argument(
        "input_file",
        type=Path,
        help="Path to the markdown context file."
    )
    parser.add_argument(
        "-o", "--output-dir",
        type=Path,
        default=".",
        help="Directory to reconstruct files in (default: current directory)."
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing files. If not set, existing files are skipped or replacements are skipped."
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress verbose output (show summary report only)."
    )
    parser.add_argument(
        "--dry-run", "--dry",
        action="store_true",
        help="Perform a dry run without creating any files or directories on disk."
    )
    parser.add_argument(
        "--tabs-to-spaces",
        type=int,
        metavar="N",
        default=None,
        help="Replace tabs with N spaces (e.g., 4)."
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Automatically confirm all prompts (e.g., deletions)."
    )

    args = parser.parse_args()

    if not args.input_file.is_file():
        print(f"Error: Input file '{args.input_file}' not found or is not a file.", file=sys.stderr)
        sys.exit(1)

    try:
        markdown_content = args.input_file.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Error reading input file '{args.input_file}': {e}", file=sys.stderr)
        sys.exit(1)

    context_parser = ContextParser(
        output_dir=args.output_dir,
        overwrite=args.overwrite,
        verbose=not args.quiet,
        dry_run=args.dry_run,
        tabs_to_spaces=args.tabs_to_spaces
    )

    context_parser.parse_and_create(markdown_content)
    
    pending_files, pending_dirs = context_parser.get_pending_removals()
    if (pending_files or pending_dirs) and not context_parser.dry_run:
        print("\nThe following items are marked for DELETION:")
        if pending_files:
            print("Files:")
            for f in pending_files: print(f"  - {f}")
        if pending_dirs:
            print("Directories:")
            for d in pending_dirs: print(f"  - {d}")
        
        if not args.yes:
            try:
                confirm = input("Proceed with deletions? [y/N]: ").lower().strip()
            except (EOFError, KeyboardInterrupt):
                print("\nDeletion cancelled by user.")
                sys.exit(1)

            if confirm != 'y':
                print("Deletion cancelled by user.")
                context_parser.report()
                sys.exit(0)

    context_parser.execute_pending_removals()
    context_parser.report()

    if context_parser.errors:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main_cli()