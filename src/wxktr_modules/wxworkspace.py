#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Workspace Panel (Presenter)
----------------------------------
Provides a workspace tab with a file tree, code editor, terminal, image viewer, and sound player.
This panel acts as the Presenter in an MVP architecture.
"""

import wx
import wx.stc as stc
import os
from pathlib import Path
import sys
import re
import shutil
from pubsub import pub

from .module_ui.workspace_panel_view import WorkspacePanelView

try:
    from .modules_parts.image_viewer import ImageViewer
    from .modules_parts.sound_player import SoundPlayer
    from .project_settings import ProjectSettings
except ImportError:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))
    from modules_parts.image_viewer import ImageViewer
    from modules_parts.sound_player import SoundPlayer
    from project_settings import ProjectSettings


class WorkspacePanel(wx.Panel):
    """A Presenter that combines a file tree, code editor, image viewer, sound player, and terminal."""
    def __init__(self, parent):
        """Initializes the Workspace panel Presenter."""
        super().__init__(parent)
        self.cwd = os.getcwd()

        self.unsaved_changes = {}
        self.current_file_path = None
        self.is_loading_file = False
        self.current_view_mode = 'editor'
        
        self.find_dialog = None
        self.fs_watcher = None
        self._refresh_timer = None
        
        self.project_settings = ProjectSettings(self.cwd)

        self.view = WorkspacePanelView(self, self.project_settings)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.view, 1, wx.EXPAND)
        self.SetSizer(sizer)

        pub.subscribe(self.on_query_unsaved_changes, 'query.state.unsaved_changes')

        self.root = self.view.file_tree.AddRoot("Root")
        self.populate_file_tree(self.root, self.cwd)

        self._bind_events()

        accel_tbl = wx.AcceleratorTable([
            (wx.ACCEL_CTRL, ord('S'), wx.ID_SAVE),
        ])
        self.SetAcceleratorTable(accel_tbl)
        self.Bind(wx.EVT_MENU, self.on_save_hotkey, id=wx.ID_SAVE)

        wx.CallAfter(self._init_fs_watcher)
        wx.CallAfter(self.restore_treeview_state)

    def _bind_events(self):
        """Binds events from the View's widgets to the Presenter's handlers."""
        self.view.save_button.Bind(wx.EVT_BUTTON, self.on_save_button_click)
        self.view.revert_button.Bind(wx.EVT_BUTTON, self.on_revert_button_click)
        self.view.find_button.Bind(wx.EVT_BUTTON, self.on_find_button_click)
        self.view.delete_button.Bind(wx.EVT_BUTTON, self.on_delete_item)
        
        self.view.zoom_in_button.Bind(wx.EVT_BUTTON, self.on_zoom_in)
        self.view.zoom_out_button.Bind(wx.EVT_BUTTON, self.on_zoom_out)
        self.view.fit_button.Bind(wx.EVT_BUTTON, self.on_fit)
        self.view.actual_size_button.Bind(wx.EVT_BUTTON, self.on_actual_size)
        
        self.view.newfile_button.Bind(wx.EVT_BUTTON, self.on_create_file)
        self.view.newfolder_button.Bind(wx.EVT_BUTTON, self.on_create_folder)

        self.view.file_tree.Bind(wx.EVT_TREE_SEL_CHANGED, self.on_file_select)
        self.view.editor.Bind(stc.EVT_STC_MODIFIED, self.on_editor_modified)

    def on_query_unsaved_changes(self, query_data):
        """
        PubSub handler for 'query.state.unsaved_changes'.
        
        This method is called synchronously by other modules (e.g., GitPanel)
        to check if there are unsaved changes before performing destructive operations.
        
        Args:
            query_data: A mutable dictionary passed by the querier. We modify it
                        to report our state.
        """
        if self.unsaved_changes:
            query_data['has_unsaved'] = True
            query_data['files'] = list(self.unsaved_changes.keys())

    def switch_to_editor_view(self):
        """Switch to editor view."""
        if self.current_view_mode != 'editor':
            self.view.image_viewer.Hide()
            self.view.sound_player.Hide()
            self.view.editor.Show()
            self.current_view_mode = 'editor'
            self.view.content_container_panel.Layout()

    def switch_to_image_view(self):
        """Switch to image viewer."""
        if self.current_view_mode != 'image':
            self.view.editor.Hide()
            self.view.sound_player.Hide()
            self.view.image_viewer.Show()
            self.current_view_mode = 'image'
            self.view.content_container_panel.Layout()

    def switch_to_sound_view(self):
        """Switch to sound player."""
        if self.current_view_mode != 'sound':
            self.view.editor.Hide()
            self.view.image_viewer.Hide()
            self.view.sound_player.Show()
            self.current_view_mode = 'sound'
            self.view.content_container_panel.Layout()

    def on_zoom_in(self, event):
        """Handles zoom in for image viewer."""
        if self.current_view_mode == 'image':
            self.view.image_viewer.zoom_in()

    def on_zoom_out(self, event):
        """Handles zoom out for image viewer."""
        if self.current_view_mode == 'image':
            self.view.image_viewer.zoom_out()

    def on_fit(self, event):
        """Handles fit to window for image viewer."""
        if self.current_view_mode == 'image':
            self.view.image_viewer.fit_to_window()

    def on_actual_size(self, event):
        """Handles actual size (100%) for image viewer."""
        if self.current_view_mode == 'image':
            self.view.image_viewer.actual_size()

    def on_find_button_click(self, event):
        """Handles the Find/Replace button click."""
        if self.find_dialog:
            self.find_dialog.Raise()
        else:
            self.find_dialog = wx.FindReplaceDialog(
                self, 
                wx.FindReplaceData(wx.FR_DOWN), 
                "Find/Replace",
                wx.FR_REPLACEDIALOG
            )
            self.find_dialog.Bind(wx.EVT_FIND, self.on_find)
            self.find_dialog.Bind(wx.EVT_FIND_NEXT, self.on_find)
            self.find_dialog.Bind(wx.EVT_FIND_REPLACE, self.on_replace)
            self.find_dialog.Bind(wx.EVT_FIND_REPLACE_ALL, self.on_replace_all)
            self.find_dialog.Bind(wx.EVT_FIND_CLOSE, self.on_find_close)
            self.find_dialog.Show()

    def on_find(self, event):
        """Handles find operations in the editor."""
        find_string = event.GetFindString()
        flags = event.GetFlags()
        
        down = bool(flags & wx.FR_DOWN)
        whole_word = bool(flags & wx.FR_WHOLEWORD)
        match_case = bool(flags & wx.FR_MATCHCASE)
        
        search_flags = 0
        if whole_word:
            search_flags |= stc.STC_FIND_WHOLEWORD
        if match_case:
            search_flags |= stc.STC_FIND_MATCHCASE
        
        if down:
            start_pos = self.view.editor.GetCurrentPos()
            end_pos = self.view.editor.GetLength()
        else:
            start_pos = self.view.editor.GetCurrentPos()
            end_pos = 0
        
        self.view.editor.SetTargetStart(start_pos)
        self.view.editor.SetTargetEnd(end_pos)
        self.view.editor.SetSearchFlags(search_flags)
        
        pos = self.view.editor.SearchInTarget(find_string)
        
        if pos != -1:
            self.view.editor.SetSelection(pos, pos + len(find_string))
            self.view.editor.EnsureCaretVisible()
        else:
            wx.MessageBox(f"'{find_string}' not found.", "Find", wx.OK | wx.ICON_INFORMATION)

    def on_replace(self, event):
        """Handles single replace operation."""
        find_string = event.GetFindString()
        replace_string = event.GetReplaceString()
        
        start, end = self.view.editor.GetSelection()
        selected_text = self.view.editor.GetTextRange(start, end)
        
        if selected_text == find_string:
            self.view.editor.ReplaceSelection(replace_string)
            self.on_find(event)
        else:
            self.on_find(event)

    def on_replace_all(self, event):
        """Handles replace all operation."""
        find_string = event.GetFindString()
        replace_string = event.GetReplaceString()
        flags = event.GetFlags()
        
        whole_word = bool(flags & wx.FR_WHOLEWORD)
        match_case = bool(flags & wx.FR_MATCHCASE)
        
        search_flags = 0
        if whole_word:
            search_flags |= stc.STC_FIND_WHOLEWORD
        if match_case:
            search_flags |= stc.STC_FIND_MATCHCASE
        
        count = 0
        self.view.editor.BeginUndoAction()
        
        self.view.editor.SetTargetStart(0)
        self.view.editor.SetTargetEnd(self.view.editor.GetLength())
        self.view.editor.SetSearchFlags(search_flags)
        
        while True:
            pos = self.view.editor.SearchInTarget(find_string)
            if pos == -1:
                break
            
            self.view.editor.ReplaceTarget(replace_string)
            count += 1
            
            new_pos = pos + len(replace_string)
            self.view.editor.SetTargetStart(new_pos)
            self.view.editor.SetTargetEnd(self.view.editor.GetLength())
        
        self.view.editor.EndUndoAction()
        
        wx.MessageBox(f"Replaced {count} occurrence(s).", "Replace All", wx.OK | wx.ICON_INFORMATION)

    def on_find_close(self, event):
        """Handles the find dialog close event."""
        if self.find_dialog:
            self.find_dialog.Destroy()
            self.find_dialog = None

    def on_save_hotkey(self, event):
        """Handles Ctrl+S hotkey for saving."""
        if self.current_file_path:
            self.save_file(self.current_file_path)

    def _init_fs_watcher(self):
        """Initialize filesystem watcher for automatic tree refresh."""
        try:
            self.fs_watcher = wx.FileSystemWatcher()
            self.fs_watcher.SetOwner(self)
            
            self.fs_watcher.AddTree(self.cwd)
            
            self.Bind(wx.EVT_FSWATCHER, self._on_fs_change)
            
            self._refresh_timer = wx.Timer(self)
            self.Bind(wx.EVT_TIMER, self._on_refresh_timer, self._refresh_timer)
            
        except Exception as e:
            print(f"Warning: Could not initialize filesystem watcher: {e}")

    def _on_fs_change(self, event):
        """Handle filesystem change events with throttling."""
        if not self._refresh_timer.IsRunning():
            self._refresh_timer.StartOnce(500)

    def _on_refresh_timer(self, event):
        """Refresh the file tree after filesystem changes."""
        self.refresh_file_tree()

    def restore_treeview_state(self):
        """Restore expanded paths from project settings."""
        expanded_paths = self.project_settings.get_treeview_expanded_paths()
        if expanded_paths:
            self.restore_expanded_state(self.root, expanded_paths)

    def save_treeview_state(self):
        """Save expanded paths to project settings."""
        expanded_paths = self.get_expanded_paths(self.root)
        self.project_settings.set_treeview_expanded_paths(expanded_paths)

    def get_expanded_paths(self, item):
        """Recursively collect all expanded directory paths."""
        expanded = set()
        
        if item == self.root:
            child, cookie = self.view.file_tree.GetFirstChild(item)
            while child.IsOk():
                expanded.update(self.get_expanded_paths(child))
                child, cookie = self.view.file_tree.GetNextChild(item, cookie)
            return expanded
        
        if item.IsOk() and self.view.file_tree.IsExpanded(item):
            item_path = self.view.file_tree.GetItemData(item)
            if item_path and os.path.isdir(item_path):
                expanded.add(item_path)
        
        child, cookie = self.view.file_tree.GetFirstChild(item)
        while child.IsOk():
            expanded.update(self.get_expanded_paths(child))
            child, cookie = self.view.file_tree.GetNextChild(item, cookie)
        
        return expanded

    def restore_expanded_state(self, item, expanded_paths):
        """Recursively restore expanded state from saved paths."""
        if not item.IsOk():
            return
        
        if item == self.root:
            child, cookie = self.view.file_tree.GetFirstChild(item)
            while child.IsOk():
                self.restore_expanded_state(child, expanded_paths)
                child, cookie = self.view.file_tree.GetNextChild(item, cookie)
            return
        
        item_path = self.view.file_tree.GetItemData(item)
        if item_path and item_path in expanded_paths:
            self.view.file_tree.Expand(item)
        
        child, cookie = self.view.file_tree.GetFirstChild(item)
        while child.IsOk():
            self.restore_expanded_state(child, expanded_paths)
            child, cookie = self.view.file_tree.GetNextChild(item, cookie)

    def populate_file_tree(self, parent_item, path):
        """Recursively populates the file tree with files and directories."""
        try:
            items = sorted(os.listdir(path), key=lambda x: (not os.path.isdir(os.path.join(path, x)), x.lower()))
        except OSError:
            return

        for item_name in items:
            if item_name.startswith('.') and item_name != '.gitignore':
                continue
            if item_name in ('__pycache__', 'build', 'dist', '.git', '.venv', 'venv'):
                continue

            item_path = os.path.join(path, item_name)

            if os.path.isdir(item_path):
                child_item = self.view.file_tree.AppendItem(parent_item, item_name)
                self.view.file_tree.SetItemData(child_item, item_path)
                self.populate_file_tree(child_item, item_path)
            elif os.path.isfile(item_path):
                file_item = self.view.file_tree.AppendItem(parent_item, item_name)
                self.view.file_tree.SetItemData(file_item, item_path)

    def refresh_file_tree(self):
        """Saves the current tree state (selection, expansion), re-populates the tree from the filesystem, and restores the state."""
        if self.is_loading_file:
            return

        selected_path = None
        selected_item = self.view.file_tree.GetSelection()
        if selected_item.IsOk():
            selected_path = self.view.file_tree.GetItemData(selected_item)

        expanded_paths = self.get_expanded_paths(self.root)

        self.view.file_tree.Freeze()
        try:
            self.view.file_tree.DeleteAllItems()
            self.root = self.view.file_tree.AddRoot("Root")
            self.populate_file_tree(self.root, self.cwd)
            
            self.restore_expanded_state(self.root, expanded_paths)

            if selected_path:
                item_to_reselect = self.find_item_by_path(selected_path)
                if item_to_reselect and item_to_reselect.IsOk():
                    self.view.file_tree.Unbind(wx.EVT_TREE_SEL_CHANGED)
                    self.view.file_tree.SelectItem(item_to_reselect)
                    self.view.file_tree.EnsureVisible(item_to_reselect)
                    self.view.file_tree.Bind(wx.EVT_TREE_SEL_CHANGED, self.on_file_select)
        finally:
            self.view.file_tree.Thaw()

    def find_item_by_path(self, target_path):
        """Recursively searches for a tree item by its file path."""
        def search_recursive(parent_item):
            child, cookie = self.view.file_tree.GetFirstChild(parent_item)
            while child.IsOk():
                child_path = self.view.file_tree.GetItemData(child)
                if child_path == target_path:
                    return child
                
                found = search_recursive(child)
                if found:
                    return found
                
                child, cookie = self.view.file_tree.GetNextChild(parent_item, cookie)
            return None

        return search_recursive(self.root)

    def finalize_selection_update(self, content, itempath, is_readonly=False, guess_lexer=True, is_dirty=False):
        """Finalizes updating the editor after loading a file."""
        self.view.editor.SetReadOnly(False)
        self.view.editor.SetText(content)
        if guess_lexer:
            self.view.editor.guess_and_set_lexer(itempath)
        self.view.editor.SetReadOnly(is_readonly)
        
        if not is_dirty:
            self.view.editor.SetSavePoint()
        
        self.is_loading_file = False
        self.update_button_states()

    def on_file_select(self, event):
        """Handles a new selection in the file tree."""
        if not self:
            return
        
        if self.is_loading_file:
            return

        item = event.GetItem()
        if not item or not item.IsOk():
            self.update_button_states()
            return

        item_path = self.view.file_tree.GetItemData(item)
        self.is_loading_file = True

        if os.path.isfile(item_path):
            self.current_file_path = item_path
            self.view.editor.filepath = item_path

            if ImageViewer.is_supported_image(item_path):
                self.switch_to_image_view()
                self.view.image_viewer.load_image(item_path)
                self.is_loading_file = False
                self.update_button_states()

            elif SoundPlayer.is_supported_audio(item_path):
                self.switch_to_sound_view()
                self.view.sound_player.load_audio(item_path)
                self.is_loading_file = False
                self.update_button_states()

            elif self.is_binary_file(item_path):
                self.switch_to_editor_view()
                content = f"Cannot display binary file: {os.path.basename(item_path)}"
                wx.CallAfter(self.finalize_selection_update, content, item_path, is_readonly=True, guess_lexer=False)

            else:
                self.switch_to_editor_view()
                content = self.unsaved_changes.get(item_path)
                is_dirty = content is not None

                if not is_dirty:
                    try:
                        with open(item_path, 'r', encoding='utf-8', newline='') as f:
                            content = f.read()
                    except Exception as e:
                        content = f"Error reading file: {e}"

                wx.CallAfter(self.finalize_selection_update, content, item_path, is_readonly=False, guess_lexer=True, is_dirty=is_dirty)

        else:
            self.switch_to_editor_view()
            self.current_file_path = None
            self.view.editor.filepath = None
            content = f"Selected directory: {os.path.basename(item_path)}"
            wx.CallAfter(self.finalize_selection_update, content, item_path, is_readonly=True, guess_lexer=False)

        self.update_button_states()

    def on_editor_modified(self, event):
        """Tracks user modifications, marking files as dirty or clean based on the editor's state relative to its last save point."""
        event.Skip()

        if self.is_loading_file or self.view.editor.GetReadOnly() or not self.current_file_path:
            return

        filepath = self.current_file_path
        item = self.find_item_by_path(filepath)

        if self.view.editor.IsModified():
            self.unsaved_changes[filepath] = self.view.editor.GetText()
            if item and item.IsOk():
                current_text = self.view.file_tree.GetItemText(item)
                if not current_text.endswith(' *'):
                    self.view.file_tree.SetItemText(item, current_text + ' *')
                    self.view.file_tree.SetItemBold(item, True)
        else:
            if filepath in self.unsaved_changes:
                del self.unsaved_changes[filepath]
                if item and item.IsOk():
                    current_text = self.view.file_tree.GetItemText(item)
                    if current_text.endswith(' *'):
                        self.view.file_tree.SetItemText(item, current_text[:-2])
                        self.view.file_tree.SetItemBold(item, False)

        self.update_button_states()

    def on_save_button_click(self, event):
        """Handles the Save Changes button click."""
        if self.current_file_path:
            self.save_file(self.current_file_path)

    def on_revert_button_click(self, event):
        """Handles the Revert Changes button click."""
        if not self.current_file_path or self.current_file_path not in self.unsaved_changes:
            return

        file_path_to_revert = self.current_file_path
        del self.unsaved_changes[file_path_to_revert]

        self.is_loading_file = True
        try:
            with open(file_path_to_revert, 'r', encoding='utf-8', newline='') as f:
                content = f.read()
            
            self.view.editor.SetText(content)
            self.view.editor.SetSavePoint()

            item = self.find_item_by_path(file_path_to_revert)
            if item and item.IsOk():
                current_text = self.view.file_tree.GetItemText(item)
                if current_text.endswith(' *'):
                    self.view.file_tree.SetItemText(item, current_text[:-2])
                    self.view.file_tree.SetItemBold(item, False)

            self.update_button_states()
        finally:
            self.is_loading_file = False

    def save_file(self, filepath):
        """Saves the specified file's modified content to disk."""
        if filepath not in self.unsaved_changes:
            return

        content = self.unsaved_changes[filepath]

        try:
            with open(filepath, 'w', encoding='utf-8', newline='') as f:
                f.write(content)

            del self.unsaved_changes[filepath]

            if self.current_file_path == filepath:
                self.view.editor.SetSavePoint()

            item = self.find_item_by_path(filepath)
            if item and item.IsOk():
                current_text = self.view.file_tree.GetItemText(item)
                if current_text.endswith(' *'):
                    self.view.file_tree.SetItemText(item, current_text[:-2])
                    self.view.file_tree.SetItemBold(item, False)

        except Exception as e:
            wx.LogError(f"Error saving file {filepath}: {e}")

    def is_binary_file(self, path: str) -> bool:
        """Checks if a file is likely binary by looking for null bytes."""
        try:
            with open(path, 'rb') as f:
                return b'\x00' in f.read(1024)
        except IOError:
            return True

    def update_button_states(self):
        """Enables or disables toolbar buttons based on editor state."""
        is_modified = bool(self.current_file_path and self.current_file_path in self.unsaved_changes)
        self.view.save_button.Enable(is_modified)
        self.view.revert_button.Enable(is_modified)

        is_text_file = self.current_file_path is not None and not self.view.editor.GetReadOnly() and self.current_view_mode == 'editor'
        self.view.find_button.Enable(is_text_file)

        is_item_selected = self.view.file_tree.GetSelection().IsOk()
        self.view.delete_button.Enable(is_item_selected)

        is_image_view = self.current_view_mode == 'image' and self.current_file_path is not None
        self.view.zoom_in_button.Enable(is_image_view)
        self.view.zoom_out_button.Enable(is_image_view)
        self.view.fit_button.Enable(is_image_view)
        self.view.actual_size_button.Enable(is_image_view)

    def get_target_directory(self):
        """Determines the target directory for new files/folders based on selection."""
        selected_item = self.view.file_tree.GetSelection()
        if not selected_item or not selected_item.IsOk():
            return self.cwd

        item_path = self.view.file_tree.GetItemData(selected_item)
        if os.path.isdir(item_path):
            return item_path
        else:
            return os.path.dirname(item_path)

    def on_create_folder(self, event):
        """Handles the New Folder button click."""
        target_dir = self.get_target_directory()

        dlg = wx.TextEntryDialog(self, "Enter the new folder's name:", "Create Folder")
        if dlg.ShowModal() == wx.ID_OK:
            folder_name = dlg.GetValue().strip()
            if folder_name:
                new_path = os.path.join(target_dir, folder_name)
                if os.path.exists(new_path):
                    wx.MessageBox(f"'{folder_name}' already exists.", "Error", wx.ICON_ERROR)
                else:
                    try:
                        os.makedirs(new_path)
                    except OSError as e:
                        wx.MessageBox(f"Error creating folder: {e}", "Error", wx.ICON_ERROR)
        dlg.Destroy()

    def on_create_file(self, event):
        """Handles the New File button click."""
        target_dir = self.get_target_directory()

        dlg = wx.TextEntryDialog(self, "Enter the new file's name:", "Create File")
        if dlg.ShowModal() == wx.ID_OK:
            filename = dlg.GetValue().strip()
            if filename:
                new_path = os.path.join(target_dir, filename)
                if os.path.exists(new_path):
                    wx.MessageBox(f"'{filename}' already exists.", "Error", wx.ICON_ERROR)
                else:
                    try:
                        with open(new_path, 'w') as f:
                            pass
                    except IOError as e:
                        wx.MessageBox(f"Error creating file: {e}", "Error", wx.ICON_ERROR)
        dlg.Destroy()

    def on_delete_item(self, event):
        """Handles deleting the selected file or folder."""
        selected_item = self.view.file_tree.GetSelection()
        if not selected_item or not selected_item.IsOk():
            return

        item_path = self.view.file_tree.GetItemData(selected_item)
        item_name = os.path.basename(item_path)
        is_dir = os.path.isdir(item_path)

        message = f"Are you sure you want to permanently delete '{item_name}'?"
        if is_dir:
            message += " This will delete all its contents."

        result = wx.MessageBox(message, "Confirm Delete", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING, self)

        if result == wx.YES:
            try:
                if is_dir:
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)

                if item_path in self.unsaved_changes:
                    del self.unsaved_changes[item_path]

                if self.current_file_path == item_path:
                    self.current_file_path = None
                    self.view.editor.filepath = None
                    self.view.editor.ClearAll()

            except Exception as e:
                wx.MessageBox(f"Error deleting '{item_name}': {e}", "Error", wx.ICON_ERROR)

    def handle_exit_request(self):
        """Called when the application is closing. Checks for unsaved changes and prompts user to save."""
        if self.unsaved_changes:
            files_list = "\n".join(self.unsaved_changes.keys())
            message = f"The following files have unsaved changes:\n\n{files_list}\n\nDo you want to save them before exiting?"
            
            result = wx.MessageBox(message, "Unsaved Changes", wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION, self)
            
            if result == wx.YES:
                for filepath in list(self.unsaved_changes.keys()):
                    self.save_file(filepath)
                return True
            elif result == wx.NO:
                return True
            else:
                return False

        self.save_treeview_state()
        return True


class Frame(wx.Frame):
    """Standalone frame for testing the WorkspacePanel."""
    def __init__(self, filepath=None):
        """Initializes the frame."""
        super().__init__(None, title="Workspace", size=(1200, 800))
        
        self.panel = WorkspacePanel(self)
        
        if filepath and os.path.isfile(filepath):
            item = self.panel.find_item_by_path(filepath)
            if item and item.IsOk():
                self.panel.view.file_tree.SelectItem(item)
        
        self.Bind(wx.EVT_CLOSE, self.on_close)

    def on_close(self, event):
        """Handles the frame close event."""
        if self.panel.handle_exit_request():
            self.Destroy()
        else:
            event.Veto()


if __name__ == "__main__":
    app = wx.App(False)
    
    fpath = sys.argv[1] if len(sys.argv) > 1 else None
    
    frame = Frame(filepath=fpath)
    frame.Show()
    app.MainLoop()