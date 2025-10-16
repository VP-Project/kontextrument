#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Settings Manager for Kontextrument
----------------------------------
Centralized settings management for all GUI-related application settings.
This manager handles global application preferences that persist across sessions.

Project-specific settings (like .context files) are NOT managed here.
"""

import os
import sys
import json
import configparser
from pathlib import Path
from typing import Any, Dict, Optional


class SettingsManager:
    """Manages global, persistent application settings."""
    
    APP_NAME = "Kontextrument"
    VENDOR_NAME = "VpProject"
    
    SETTINGS_VERSION = "1.0"
    
    def __init__(self):
        """Initialize the settings manager and determine storage location."""
        self.app_data_path = self._determine_app_data_path()
        self._ensure_directory_exists()
        
        self.settings_file = os.path.join(self.app_data_path, "kontextrument_settings.json")
        
        self.legacy_browser_config = os.path.join(self.app_data_path, "BrowserProfile", "browser.ini")
        self.legacy_history_json = os.path.join(self.app_data_path, "directoryhistory.json")
        
        self.settings: Dict[str, Any] = self._get_default_settings()
        
        self.load()
        
        self._migrate_legacy_settings()
    
    def _determine_app_data_path(self) -> str:
        """
        Determine the appropriate application data directory.
        
        Uses a consistent method to return a platform-appropriate path for storing all application data.
        """
        app_name = self.APP_NAME

        if sys.platform == "win32":
            base_path = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
            return os.path.join(base_path, app_name)

        try:
            import wx
            if wx.GetApp():
                return wx.StandardPaths.Get().GetUserLocalDataDir()
        except (ImportError, RuntimeError):
            pass
        
        if sys.platform == "darwin":
            base_path = os.path.expanduser('~/Library/Application Support')
            return os.path.join(base_path, app_name)
        else:
            base_path = os.environ.get('XDG_DATA_HOME', os.path.expanduser('~/.local/share'))
            return os.path.join(base_path, app_name)
    
    def _ensure_directory_exists(self) -> None:
        """Ensure the application data directory exists."""
        if not os.path.exists(self.app_data_path):
            os.makedirs(self.app_data_path)
    
    def _get_default_settings(self) -> Dict[str, Any]:
        """
        Return the default settings structure.
        
        This defines the schema for all settings managed by this class.
        """
        return {
            "version": self.SETTINGS_VERSION,
            
            "modules": {
                "create": True,
                "browser": True,
                "apply": True,
                "workspace": True,
                "git": True
            },
            
            "browser": {
                "last_url": "about:home",
                "bookmarks": {
                    "ChatGPT": "https://chat.openai.com",
                    "Perplexity": "https://www.perplexity.ai",
                    "Claude": "https://claude.ai",
                    "Gemini": "https://gemini.google.com",
                    "Deepseek": "https://chat.deepseek.com"
                }
            },
            
            "directory_history": {
                "max_entries": 20,
                "directories": []
            },
            
            "window": {
                "width": 1600,
                "height": 900,
                "maximized": False,
                "splitter_positions": {}
            },
            
            "ui": {
                "theme": "default",
                "font_size": 10
            }
        }
    
    def load(self) -> None:
        """Load settings from the settings file."""
        if not os.path.exists(self.settings_file):
            return
        
        try:
            with open(self.settings_file, 'r', encoding='utf-8') as f:
                loaded_settings = json.load(f)
            
            self._merge_settings(self.settings, loaded_settings)
            
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load settings from {self.settings_file}: {e}")
            print("Using default settings.")
    
    def _merge_settings(self, defaults: Dict, loaded: Dict) -> None:
        """
        Recursively merge loaded settings into defaults.
        
        This ensures that new keys in defaults are preserved even if they
        don't exist in the loaded settings (forward compatibility).
        """
        for key, value in loaded.items():
            if key in defaults:
                if isinstance(defaults[key], dict) and isinstance(value, dict):
                    self._merge_settings(defaults[key], value)
                else:
                    defaults[key] = value
            else:
                defaults[key] = value
    
    def save(self) -> None:
        """Save current settings to the settings file."""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
        except IOError as e:
            print(f"Error: Could not save settings to {self.settings_file}: {e}")
    
    def _migrate_legacy_settings(self) -> None:
        """
        Migrate settings from legacy configuration files.
        
        This method checks for old-style configuration files and migrates
        them to the new unified settings format. Only migrates if legacy
        files exist and the new settings haven't been initialized yet.
        """
        migrated = False
        
        if os.path.exists(self.legacy_browser_config):
            migrated |= self._migrate_browser_config()
        
        if os.path.exists(self.legacy_history_json):
            migrated |= self._migrate_directory_history()
        
        if migrated:
            print("Migrated legacy settings to new format.")
            self.save()
    
    def _migrate_browser_config(self) -> bool:
        """Migrate browser settings from legacy browser.ini file."""
        try:
            config = configparser.ConfigParser()
            config.read(self.legacy_browser_config)
            if config.has_section('Session') and config.has_option('Session', 'url'):
                self.settings['browser']['last_url'] = config.get('Session', 'url')
            
            if config.has_section('Bookmarks'):
                self.settings['browser']['bookmarks'] = dict(config.items('Bookmarks'))
            
            return True
        except Exception as e:
            print(f"Warning: Could not migrate browser config: {e}")
        
        return False
    
    def _migrate_directory_history(self) -> bool:
        """Migrate directory history from legacy JSON file."""
        try:
            with open(self.legacy_history_json, 'r', encoding='utf-8') as f:
                history = json.load(f)
            
            if isinstance(history, list):
                valid_entries = []
                for entry in history:
                    if isinstance(entry, dict) and 'path' in entry:
                        if os.path.isdir(entry['path']):
                            valid_entries.append(entry)
                
                self.settings['directory_history']['directories'] = valid_entries
                return True
        except Exception as e:
            print(f"Warning: Could not migrate directory history: {e}")
        
        return False
    
    
    def get_module_enabled(self, module_key: str) -> bool:
        """Check if a module is enabled."""
        return self.settings['modules'].get(module_key, True)
    
    def set_module_enabled(self, module_key: str, enabled: bool) -> None:
        """Set module enabled state."""
        self.settings['modules'][module_key] = enabled
        self.save()
    
    def get_browser_bookmarks(self) -> Dict[str, str]:
        """Get all browser bookmarks."""
        return self.settings['browser']['bookmarks'].copy()
    
    def add_browser_bookmark(self, name: str, url: str) -> None:
        """Add a browser bookmark."""
        self.settings['browser']['bookmarks'][name] = url
        self.save()
    
    def remove_browser_bookmark(self, name: str) -> None:
        """Remove a browser bookmark."""
        if name in self.settings['browser']['bookmarks']:
            del self.settings['browser']['bookmarks'][name]
            self.save()
    
    def get_last_browser_url(self) -> str:
        """Get the last visited browser URL."""
        return self.settings['browser']['last_url']
    
    def set_last_browser_url(self, url: str) -> None:
        """Set the last visited browser URL."""
        self.settings['browser']['last_url'] = url
        self.save()
    
    def get_directory_history(self) -> list:
        """Get directory history list."""
        return self.settings['directory_history']['directories'].copy()
    
    def add_directory_to_history(self, directory_path: str, timestamp: str) -> None:
        """
        Add a directory to history.
        
        Removes duplicate entries and maintains max_entries limit.
        """
        history = self.settings['directory_history']['directories']
        history = [e for e in history if e.get('path') != directory_path]
        
        new_entry = {'path': directory_path, 'timestamp': timestamp}
        history.insert(0, new_entry)
        
        max_entries = self.settings['directory_history']['max_entries']
        self.settings['directory_history']['directories'] = history[:max_entries]
        
        self.save()
    
    def remove_directory_from_history(self, directory_path: str) -> None:
        """Remove a directory from history."""
        history = self.settings['directory_history']['directories']
        self.settings['directory_history']['directories'] = [
            e for e in history if e.get('path') != directory_path
        ]
        self.save()
    
    def clear_directory_history(self) -> None:
        """Clear all directory history."""
        self.settings['directory_history']['directories'] = []
        self.save()
    
    def get_window_geometry(self) -> Dict[str, Any]:
        """Get window geometry settings."""
        return self.settings['window'].copy()
    
    def set_window_geometry(self, width: int, height: int, maximized: bool) -> None:
        """Set window geometry settings."""
        self.settings['window']['width'] = width
        self.settings['window']['height'] = height
        self.settings['window']['maximized'] = maximized
        self.save()
    
    def get_splitter_position(self, panel_name: str, splitter_name: str) -> Optional[int]:
        """Get saved splitter position for a specific panel."""
        key = f"{panel_name}.{splitter_name}"
        return self.settings['window']['splitter_positions'].get(key)
    
    def set_splitter_position(self, panel_name: str, splitter_name: str, position: int) -> None:
        """Save splitter position for a specific panel."""
        key = f"{panel_name}.{splitter_name}"
        self.settings['window']['splitter_positions'][key] = position
        self.save()


_settings_manager: Optional[SettingsManager] = None


def get_settings_manager() -> SettingsManager:
    """
    Get the global settings manager instance.
    
    Returns the singleton settings_manager instance, creating it if necessary.
    """
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager()
    return _settings_manager