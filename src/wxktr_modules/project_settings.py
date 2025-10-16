#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Project Settings Manager
------------------------
Manages project-specific settings that are stored within the project directory.

This module handles:
- .ktrsettings file (INI format) containing:
  - wxterm command history
  - wxterm pre-command
  - treeview expansion state
  - Other project-specific GUI preferences

Note: .context files are managed separately by the context generator modules.
"""

import os
import configparser
from pathlib import Path
from typing import List, Optional, Set


class ProjectSettings:
    """Manages project-specific settings stored in a .ktrsettings file."""
    
    SETTINGS_FILENAME = ".ktrsettings"
    
    def __init__(self, project_path: str):
        """
        Initialize project settings for a given project directory.
        
        Args:
            project_path: Path to the project root directory
        """
        self.project_path = Path(project_path).resolve()
        self.settings_file = self.project_path / self.SETTINGS_FILENAME
        
        self.config = configparser.ConfigParser()
        
        self.load()
    
    def load(self) -> None:
        """Load settings from .ktrsettings file if it exists."""
        if self.settings_file.exists():
            try:
                self.config.read(self.settings_file, encoding='utf-8')
            except Exception as e:
                print(f"Warning: Could not load {self.SETTINGS_FILENAME}: {e}")
                self._initialize_defaults()
        else:
            self._initialize_defaults()
    
    def _initialize_defaults(self) -> None:
        """Initialize default sections and values."""
        if not self.config.has_section('Terminal'):
            self.config.add_section('Terminal')
            self.config.set('Terminal', 'history', '')
            self.config.set('Terminal', 'pre_command', '')
            self.config.set('Terminal', 'max_history', '100')
        
        if not self.config.has_section('TreeView'):
            self.config.add_section('TreeView')
            self.config.set('TreeView', 'expanded_paths', '')
    
    def save(self) -> None:
        """Save settings to .ktrsettings file."""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                self.config.write(f)
        except IOError as e:
            print(f"Error: Could not save {self.SETTINGS_FILENAME}: {e}")
    
    
    def get_terminal_history(self) -> List[str]:
        """
        Get terminal command history.
        
        Returns:
            List of command strings from history
        """
        if not self.config.has_section('Terminal'):
            return []
        
        history_str = self.config.get('Terminal', 'history', fallback='')
        if not history_str:
            return []
        
        return [cmd.strip() for cmd in history_str.split('\n') if cmd.strip()]
    
    def set_terminal_history(self, commands: List[str]) -> None:
        """
        Set terminal command history.
        
        Args:
            commands: List of command strings to save
        """
        if not self.config.has_section('Terminal'):
            self.config.add_section('Terminal')
        
        max_history = self.config.getint('Terminal', 'max_history', fallback=100)
        
        commands = commands[-max_history:]
        
        history_str = '\n'.join(commands)
        self.config.set('Terminal', 'history', history_str)
        
        self.save()
    
    def add_to_terminal_history(self, command: str) -> None:
        """
        Add a command to terminal history.
        
        Args:
            command: Command string to add
        """
        history = self.get_terminal_history()
        
        if command in history:
            history.remove(command)
        
        history.append(command)
        
        self.set_terminal_history(history)
    
    def get_terminal_pre_command(self) -> str:
        """
        Get the pre-command that should be executed when terminal starts.
        
        Returns:
            Pre-command string (empty if not set)
        """
        if not self.config.has_section('Terminal'):
            return ''
        
        return self.config.get('Terminal', 'pre_command', fallback='')
    
    def set_terminal_pre_command(self, pre_command: str) -> None:
        """
        Set the pre-command for terminal startup.
        
        Args:
            pre_command: Command to execute on terminal start
        """
        if not self.config.has_section('Terminal'):
            self.config.add_section('Terminal')
        
        self.config.set('Terminal', 'pre_command', pre_command)
        self.save()
    
    def get_terminal_max_history(self) -> int:
        """Get maximum number of history entries to keep."""
        if not self.config.has_section('Terminal'):
            return 100
        
        return self.config.getint('Terminal', 'max_history', fallback=100)
    
    def set_terminal_max_history(self, max_history: int) -> None:
        """Set maximum number of history entries to keep."""
        if not self.config.has_section('Terminal'):
            self.config.add_section('Terminal')
        
        self.config.set('Terminal', 'max_history', str(max_history))
        self.save()
    
    def get_treeview_expanded_paths(self) -> Set[str]:
        """
        Get the set of expanded directory paths in the treeview.
        
        Returns:
            Set of directory paths that were expanded
        """
        if not self.config.has_section('TreeView'):
            return set()
        
        paths_str = self.config.get('TreeView', 'expanded_paths', fallback='')
        if not paths_str:
            return set()
        
        return {p.strip() for p in paths_str.split('\n') if p.strip()}
    
    def set_treeview_expanded_paths(self, paths: Set[str]) -> None:
        """
        Save the set of expanded directory paths in the treeview.
        
        Args:
            paths: Set of directory paths that are currently expanded
        """
        if not self.config.has_section('TreeView'):
            self.config.add_section('TreeView')
        
        paths_list = sorted(paths)
        paths_str = '\n'.join(paths_list)
        
        self.config.set('TreeView', 'expanded_paths', paths_str)
        self.save()
    
    @staticmethod
    def is_settings_file(filename: str) -> bool:
        """
        Check if a filename is the project settings file.
        
        This is useful for excluding it from context generation.
        
        Args:
            filename: Filename to check
            
        Returns:
            True if filename matches .ktrsettings
        """
        return filename == ProjectSettings.SETTINGS_FILENAME


def should_exclude_from_context(filename: str) -> bool:
    """
    Check if a file should be automatically excluded from context generation.
    
    Args:
        filename: Filename to check
        
    Returns:
        True if file should be excluded (.ktrsettings or .context)
    """
    return filename in ['.ktrsettings', '.context']