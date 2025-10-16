#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Create Context Panel (Presenter)
---------------------------------------
Contains the logic for the 'Create Context' tab of the unified GUI.
This panel acts as the Presenter in an MVP architecture.
"""

import wx
import threading
import sys
import io
import os
import configparser
from pathlib import Path
from typing import Dict, Any, List, Optional

from ktr.create_context import ContextGenerator
from pubsub import pub
from .module_ui.create_context_panel_view import CreateContextPanelView


class FileDropTarget(wx.TextDropTarget):
    """Drop target for handling file drops on list controls."""
    def __init__(self, parent_panel, target_listbox):
        super().__init__()
        self.parent_panel = parent_panel
        self.target_listbox = target_listbox

    def OnDropText(self, x, y, data):
        """Handle text drop event."""
        self.parent_panel.handle_drop(self.target_listbox, data)
        return True


class CreateContextPanel(wx.Panel):
    """Presenter for creating context files. Manages the UI (View) and logic."""

    def __init__(self, parent):
        """Initializes the Create Context panel."""
        super().__init__(parent)

        self.current_config_file: Optional[str] = None
        self.config_parser: Optional[configparser.ConfigParser] = None
        self.selected_section: str = ""
        self.is_populating_fields: bool = False
        self.last_generated_result: Optional[Dict[str, Any]] = None
        self.generator_instance: Optional[ContextGenerator] = None
        self.worker_thread: Optional[threading.Thread] = None
        self.is_running: bool = False
        self.scroll_ratio_before_update: float = 0.0

        self.refresh_timer = wx.Timer(self)

        self.dnd_source_list: Optional[wx.ListBox] = None
        self.dnd_start_pos: Optional[wx.Point] = None
        self.dnd_dragging: bool = False

        self.view = CreateContextPanelView(self)
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.view, 1, wx.EXPAND)
        self.SetSizer(sizer)

        self._create_file_list_context_menus()
        self._bind_events()

        self.view.included_files_ctrl.SetDropTarget(FileDropTarget(self, self.view.included_files_ctrl))
        self.view.skipped_files_ctrl.SetDropTarget(FileDropTarget(self, self.view.skipped_files_ctrl))

        self.Layout()
        self._update_ui_states()
        wx.CallAfter(self._auto_load_initial_config)

    def _bind_events(self):
        self.view.load_config_btn.Bind(wx.EVT_BUTTON, self.on_browse_config)
        self.view.sections_list_box.Bind(wx.EVT_LISTBOX, self.on_section_select)
        self.view.add_section_btn.Bind(wx.EVT_BUTTON, self.on_add_section)
        self.view.copy_section_btn.Bind(wx.EVT_BUTTON, self.on_copy_section)
        self.view.delete_section_btn.Bind(wx.EVT_BUTTON, self.on_delete_section)
        self.view.save_config_btn.Bind(wx.EVT_BUTTON, self.on_save_config)

        self.view.setting_controls['subdirectories_mode'].Bind(wx.EVT_COMBOBOX, self._on_subdir_mode_change)

        for key, control in self.view.setting_controls.items():
            if key == 'subdirectories_mode': continue
            if isinstance(control, wx.TextCtrl): control.Bind(wx.EVT_TEXT, self.on_setting_change)
            elif isinstance(control, wx.CheckBox): control.Bind(wx.EVT_CHECKBOX, self.on_setting_change)
        
        self.view.preamble_ctrl.Bind(wx.EVT_TEXT, self.on_setting_change)
        self.view.appendix_ctrl.Bind(wx.EVT_TEXT, self.on_setting_change)
        
        self.view.copy_btn.Bind(wx.EVT_BUTTON, self.on_copy_to_clipboard)
        self.view.save_btn.Bind(wx.EVT_BUTTON, self.on_save)
        self.view.save_as_btn.Bind(wx.EVT_BUTTON, self.on_save_as)
        
        self.view.preamble_ctrl_copy_btn.Bind(wx.EVT_BUTTON, self.on_copy_text_field_content)
        self.view.appendix_ctrl_copy_btn.Bind(wx.EVT_BUTTON, self.on_copy_text_field_content)
        
        self.Bind(wx.EVT_TIMER, self.on_refresh_timer, self.refresh_timer)

        self.view.included_files_ctrl.Bind(wx.EVT_CONTEXT_MENU, self.on_file_list_context_menu)
        self.view.skipped_files_ctrl.Bind(wx.EVT_CONTEXT_MENU, self.on_file_list_context_menu)
        
        self.view.included_files_ctrl.Bind(wx.EVT_LEFT_DOWN, self.on_dnd_left_down)
        self.view.skipped_files_ctrl.Bind(wx.EVT_LEFT_DOWN, self.on_dnd_left_down)
        self.view.included_files_ctrl.Bind(wx.EVT_MOTION, self.on_dnd_motion)
        self.view.skipped_files_ctrl.Bind(wx.EVT_MOTION, self.on_dnd_motion)
        self.view.included_files_ctrl.Bind(wx.EVT_LEFT_UP, self.on_dnd_left_up)
        self.view.skipped_files_ctrl.Bind(wx.EVT_LEFT_UP, self.on_dnd_left_up)

    def _on_subdir_mode_change(self, event=None):
        mode = self.view.setting_controls['subdirectories_mode'].GetValue()
        is_list_mode = (mode == 'LIST')
        
        self.view.subdirs_list_label.Show(is_list_mode)
        self.view.setting_controls['subdirs_list'].Show(is_list_mode)
        
        self.view.scrolled_settings_panel.GetSizer().Layout()
        self.view.scrolled_settings_panel.SetupScrolling(scroll_x=False)

        if event:
            self.on_setting_change(event)

    def _auto_load_initial_config(self):
        try:
            initial_path = os.path.join(os.getcwd(), '.context')
            if os.path.exists(initial_path):
                self.load_config_file(initial_path)
            else:
                self.current_config_file = initial_path
                self.view.config_path_ctrl.SetValue(initial_path)
                self.config_parser = configparser.ConfigParser()
                self.view.sections_list_box.Clear()
                
                default_section_name = "main"
                self.config_parser.add_section(default_section_name)
                self.view.sections_list_box.Append(default_section_name)
                self.view.sections_list_box.SetSelection(0)
                
                self.on_section_select(None)
                
                self._update_ui_states()
                self.view.log_ctrl.SetValue("No '.context' file found. A new configuration has been created in memory.\n"
                                       "Use 'Save Config File' to save it to disk.")
        except Exception as e:
            wx.MessageBox(f"Failed to auto-load or create '.context' file.\n\nError: {e}", 
                          "Initialization Failed", wx.ICON_WARNING, parent=self.GetTopLevelParent())

    def load_config_file(self, filepath):
        """Loads a configuration file and updates the UI."""
        self.current_config_file = filepath
        self.view.config_path_ctrl.SetValue(filepath)
        self.config_parser = configparser.ConfigParser()
        self.config_parser.read(filepath)
        
        self.view.sections_list_box.Clear()
        for section in self.config_parser.sections():
            self.view.sections_list_box.Append(section)
        
        if self.view.sections_list_box.GetCount() > 0:
            self.view.sections_list_box.SetSelection(0)
            self.on_section_select(None)
        self._update_ui_states()

    def on_browse_config(self, event):
        """Handles the 'Browse' button click to select a config file."""
        with wx.FileDialog(self.GetTopLevelParent(), "Open .context file", wildcard="Config files (*.context)|*.context|All files (*.*)|*.*",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dialog:
            if dialog.ShowModal() == wx.ID_CANCEL: return
            self.load_config_file(dialog.GetPath())

    def on_section_select(self, event):
        """Handles selection of a new section in the list box."""
        self.is_populating_fields = True
        try:
            sel = self.view.sections_list_box.GetSelection()
            if sel == wx.NOT_FOUND:
                self.selected_section = ""
                for control in list(self.view.setting_controls.values()) + [self.view.preamble_ctrl, self.view.appendix_ctrl]:
                    if isinstance(control, wx.TextCtrl): control.SetValue("")
                    elif isinstance(control, wx.CheckBox): control.SetValue(False)
                return

            self.selected_section = self.view.sections_list_box.GetString(sel)
            section_data = self.config_parser[self.selected_section]

            for key, control in self.view.setting_controls.items():
                if key in ['subdirectories_mode', 'subdirs_list']: continue
                value = section_data.get(key, "")
                if key in ['excludedfiles', 'include'] and isinstance(control, wx.TextCtrl):
                    control.SetValue(value.replace(',', '\n'))
                elif isinstance(control, wx.TextCtrl):
                    control.SetValue(value)
                elif isinstance(control, wx.CheckBox):
                    if key in ['includepreamble', 'includeappendix', 'summary']:
                        control.SetValue(section_data.getboolean(key, True))
                    else:
                        control.SetValue(section_data.getboolean(key, False))

            sub_config_value = section_data.get('subdirectories', '#NONE')
            sub_keywords = ['#NONE', '#ALL']
            if sub_config_value.upper() in sub_keywords:
                self.view.setting_controls['subdirectories_mode'].SetValue(sub_config_value.upper())
                self.view.setting_controls['subdirs_list'].SetValue('')
            else:
                self.view.setting_controls['subdirectories_mode'].SetValue('LIST')
                self.view.setting_controls['subdirs_list'].SetValue(sub_config_value.replace(',', '\n'))
                
            self.view.preamble_ctrl.SetValue(section_data.get("preamble", ""))
            self.view.appendix_ctrl.SetValue(section_data.get("appendix", ""))
        finally:
            self.is_populating_fields = False
        
        self._on_subdir_mode_change()
        self.trigger_context_generation()
        self._update_ui_states()

    def on_add_section(self, event):
        """Handles the 'Add Section' button click."""
        dlg = wx.TextEntryDialog(self.GetTopLevelParent(), 'Enter new section name:', 'Add Section')
        if dlg.ShowModal() == wx.ID_OK:
            name = dlg.GetValue()
            if name and not self.config_parser.has_section(name):
                self.config_parser.add_section(name)
                self.view.sections_list_box.Append(name)
                self.view.sections_list_box.SetStringSelection(name)
                self.on_section_select(None)
        dlg.Destroy()

    def on_copy_section(self, event):
        """Handles the 'Copy Section' button click."""
        if not self.selected_section:
            return

        original_name = self.selected_section
        default_new_name = f"{original_name}_copy"
        
        dlg = wx.TextEntryDialog(self.GetTopLevelParent(), 'Enter name for the new copied section:', 'Copy Section', default_new_name)
        if dlg.ShowModal() == wx.ID_OK:
            new_name = dlg.GetValue()
            if not new_name:
                wx.MessageBox("Section name cannot be empty.", "Error", wx.ICON_ERROR, parent=self.GetTopLevelParent())
                return
            if self.config_parser.has_section(new_name):
                wx.MessageBox(f"Section '{new_name}' already exists.", "Error", wx.ICON_ERROR, parent=self.GetTopLevelParent())
                return
            
            self.config_parser.add_section(new_name)
            for key, value in self.config_parser.items(original_name):
                self.config_parser.set(new_name, key, value)
                
            self.view.sections_list_box.Append(new_name)
            self.view.sections_list_box.SetStringSelection(new_name)
            self.on_section_select(None)
        dlg.Destroy()
    
    def on_delete_section(self, event):
        """Handles the 'Delete Section' button click."""
        if not self.selected_section: return
        if wx.MessageBox(f"Are you sure you want to delete section '{self.selected_section}'?", "Confirm", wx.YES_NO | wx.ICON_QUESTION, parent=self.GetTopLevelParent()) == wx.YES:
            self.config_parser.remove_section(self.selected_section)
            self.view.sections_list_box.Delete(self.view.sections_list_box.GetSelection())
            if self.view.sections_list_box.GetCount() > 0: self.view.sections_list_box.SetSelection(0)
            self.on_section_select(None)

    def on_setting_change(self, event):
        """Handles changes in any of the setting controls."""
        if self.is_populating_fields or not self.selected_section:
            return
        
        section_data = self.config_parser[self.selected_section]

        for key, control in self.view.setting_controls.items():
            if key in ['subdirectories_mode', 'subdirs_list']: continue
            if isinstance(control, wx.TextCtrl):
                value = control.GetValue().replace('\n', ',') if key in ['excludedfiles', 'include'] else control.GetValue()
                section_data[key] = value
            elif isinstance(control, wx.CheckBox):
                section_data[key] = str(control.GetValue()).lower()

        mode = self.view.setting_controls['subdirectories_mode'].GetValue()
        if mode == 'LIST':
            subdirs_value = self.view.setting_controls['subdirs_list'].GetValue().replace('\n', ',')
        else:
            subdirs_value = mode
        section_data['subdirectories'] = subdirs_value
        
        section_data["preamble"] = self.view.preamble_ctrl.GetValue()
        section_data["appendix"] = self.view.appendix_ctrl.GetValue()
        
        self.refresh_timer.StartOnce(500)

    def on_save_config(self, event):
        """Handles the 'Save Config' button click."""
        if not self.current_config_file:
            wx.MessageBox("No config file loaded.", "Error", wx.ICON_ERROR, parent=self.GetTopLevelParent())
            return
        self.on_setting_change(None)
        if self.refresh_timer.IsRunning():
            self.refresh_timer.Stop()
            
        with open(self.current_config_file, 'w') as f:
            self.config_parser.write(f)
        wx.MessageBox(f"Saved config to {self.current_config_file}", "Success", parent=self.GetTopLevelParent())

    def on_refresh_timer(self, event):
        """Event handler for the refresh timer to generate context."""
        self.trigger_context_generation()

    def trigger_context_generation(self):
        """Triggers the generation of the context preview in a separate thread."""
        if not self.selected_section or self.is_running:
            return
            
        if not self.current_config_file:
            self.view.log_ctrl.SetValue("Error: No config file loaded or specified. Please browse for a .context file.")
            return

        scroll_range = self.view.preview_ctrl.GetScrollRange(wx.VERTICAL)
        thumb_pos = self.view.preview_ctrl.GetScrollPos(wx.VERTICAL)
        self.scroll_ratio_before_update = thumb_pos / scroll_range if scroll_range > 0 else 0.0

        self.is_running = True
        self._update_ui_states()
        self.view.log_ctrl.SetValue(f"Generating preview for section '{self.selected_section}' using current settings...\n")

        pub.sendMessage("status.update", text=f"Generating preview for '{self.selected_section}'...", pane=0)
        pub.sendMessage("progress.pulse", pulse=True)

        self.worker_thread = threading.Thread(target=self._run_generator_thread, daemon=True)
        self.worker_thread.start()

    def _run_generator_thread(self):
        base_path = str(Path(self.current_config_file).parent)
        gen = ContextGenerator(base_path, verbose=True)

        filetypes_str = self.view.setting_controls['filetypes'].GetValue()
        if filetypes_str:
            exts = [e.strip().lstrip('.') for e in filetypes_str.split(',') if e.strip()]
            gen.target_extensions = {'.' + e for e in exts}
        else:
            gen.target_extensions = None

        excluded_str = self.view.setting_controls['excludedfiles'].GetValue().replace('\n', ',')
        config_excluded = {e.strip() for e in excluded_str.split(',') if e.strip()}
        gen.excluded_items = {'.gitignore', '.context', '.ktrsettings'} | config_excluded

        include_str = self.view.setting_controls['include'].GetValue().replace('\n', ',')
        gen.include_items = {e.strip() for e in include_str.split(',') if e.strip()}

        gen.output_filename = self.view.setting_controls['outputfile'].GetValue() or 'context.md'
        
        sub_mode = self.view.setting_controls['subdirectories_mode'].GetValue()
        if sub_mode == 'LIST':
            gen.subdir_option = self.view.setting_controls['subdirs_list'].GetValue().replace('\n', ',')
        else:
            gen.subdir_option = sub_mode

        gen.include_preamble_in_output = self.view.setting_controls['includepreamble'].GetValue()
        gen.include_appendix_in_output = self.view.setting_controls['includeappendix'].GetValue()
        gen.summary = self.view.setting_controls['summary'].GetValue()
        gen.include_file_tree = self.view.setting_controls['filetree'].GetValue()
        gen.include_formatting_instructions = self.view.setting_controls['formattinginstructions'].GetValue()
        gen.preamble = self.view.preamble_ctrl.GetValue() or None
        gen.appendix = self.view.appendix_ctrl.GetValue() or None
        self.generator_instance = gen

        log_stream = io.StringIO()
        original_stdout = sys.stdout
        sys.stdout = log_stream
        
        result: Dict[str, Any] = {}
        try:
            result = self.generator_instance.generate_context_string()
            result['log_output'] = log_stream.getvalue()
        except Exception as e:
            result = {
                'markdown_content': f"An error occurred during generation:\n\n{e}", 
                'log_output': log_stream.getvalue(),
                'files_included_list_overview': [],
                'files_skipped_list_overview': []
            }
        finally:
            sys.stdout = original_stdout
        
        wx.CallAfter(self.on_generation_complete, result)

    def on_generation_complete(self, result):
        """Handles completion of the context generation process."""
        self.last_generated_result = result
        self.view.preview_ctrl.SetValue(result.get('markdown_content', ''))
        wx.CallAfter(self._restore_scroll_position)

        self.view.log_ctrl.SetValue(result.get('log_output', 'Generation completed.'))

        estimated_tokens = result.get('estimated_tokens', 0)
        self.view.token_count_label.SetLabel(f"Estimated Tokens: {estimated_tokens:,}")

        self.view.included_files_ctrl.Clear()
        for file in result.get('files_included_list_overview', []):
            self.view.included_files_ctrl.Append(file)

        self.view.skipped_files_ctrl.Clear()
        for file in result.get('files_skipped_list_overview', []):
            self.view.skipped_files_ctrl.Append(file)

        self.is_running = False
        self._update_ui_states()

        pub.sendMessage("status.update", text="Generation complete.", pane=0)
        pub.sendMessage("progress.pulse", pulse=False)

    def _restore_scroll_position(self):
        """Restores the scroll position after the preview is updated."""
        scroll_range = self.view.preview_ctrl.GetScrollRange(wx.VERTICAL)
        if scroll_range > 0:
            new_pos = int(scroll_range * self.scroll_ratio_before_update)
            self.view.preview_ctrl.SetScrollPos(wx.VERTICAL, new_pos)

    def on_copy_to_clipboard(self, event):
        """Copies the context preview to the clipboard."""
        content = self.get_content_to_save()
        if content is None:
            return

        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(content))
            wx.TheClipboard.Close()
            wx.MessageBox("Context copied to clipboard.", "Success", wx.ICON_INFORMATION, parent=self.GetTopLevelParent())
        else:
            wx.MessageBox("Unable to open clipboard.", "Error", wx.ICON_ERROR, parent=self.GetTopLevelParent())

    def on_copy_text_field_content(self, event):
        """Copies the content of preamble or appendix field to clipboard."""
        btn = event.GetEventObject()
        if btn == self.view.preamble_ctrl_copy_btn:
            content = self.view.preamble_ctrl.GetValue()
            field_name = "Preamble"
        elif btn == self.view.appendix_ctrl_copy_btn:
            content = self.view.appendix_ctrl.GetValue()
            field_name = "Appendix"
        else:
            return

        if not content:
            wx.MessageBox(f"{field_name} is empty.", "Info", wx.ICON_INFORMATION, parent=self.GetTopLevelParent())
            return

        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(content))
            wx.TheClipboard.Close()
            wx.MessageBox(f"{field_name} copied to clipboard.", "Success", wx.ICON_INFORMATION, parent=self.GetTopLevelParent())
        else:
            wx.MessageBox("Unable to open clipboard.", "Error", wx.ICON_ERROR, parent=self.GetTopLevelParent())

    def get_content_to_save(self) -> Optional[str]:
        """Returns the content to save, or None if there's an error."""
        if not self.last_generated_result:
            wx.MessageBox("No context has been generated yet.", "Error", wx.ICON_ERROR, parent=self.GetTopLevelParent())
            return None
        return self.last_generated_result.get('markdown_content', '')

    def on_save(self, event):
        """Handles the 'Save Context' button click."""
        content_to_save = self.get_content_to_save()
        if content_to_save is None:
            return

        output_path_str = self.config_parser.get(self.selected_section, 'outputfile', fallback='context.md')
        full_path = Path(self.current_config_file).parent / output_path_str

        try:
            full_path.write_text(content_to_save, encoding='utf-8')
            wx.MessageBox(f"Context saved to{full_path}", "Save Successful", wx.ICON_INFORMATION, parent=self.GetTopLevelParent())
        except Exception as e:
            wx.MessageBox(f"Error saving file: {e}", "Error", wx.ICON_ERROR, parent=self.GetTopLevelParent())

    def on_save_as(self, event):
        """Handles the 'Save Context As' button click."""
        content_to_save = self.get_content_to_save()
        if content_to_save is None:
            return

        output_path_str = self.config_parser.get(self.selected_section, 'outputfile', fallback='context.md')
        full_path = Path(self.current_config_file).parent / output_path_str

        with wx.FileDialog(self.GetTopLevelParent(), "Save Context File As...", style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
                           defaultFile=str(full_path.name), defaultDir=str(full_path.parent)) as dialog:
            if dialog.ShowModal() == wx.ID_CANCEL:
                return

            filepath = dialog.GetPath()
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content_to_save)
                wx.MessageBox(f"Context saved to{filepath}", "Save Successful", wx.ICON_INFORMATION, parent=self.GetTopLevelParent())
            except Exception as e:
                wx.MessageBox(f"Error saving file: {e}", "Error", wx.ICON_ERROR, parent=self.GetTopLevelParent())

    def _update_ui_states(self):
        has_config = bool(self.current_config_file)
        has_section = has_config and bool(self.selected_section)
        has_content = bool(self.last_generated_result) and bool(self.last_generated_result.get('markdown_content'))

        self.view.sections_list_box.Enable(has_config)
        self.view.add_section_btn.Enable(has_config)
        self.view.copy_section_btn.Enable(has_section)
        self.view.delete_section_btn.Enable(has_section)
        self.view.save_config_btn.Enable(has_config)

        for control in self.view.setting_controls.values():
            control.Enable(has_section)

        self.view.copy_btn.Enable(has_content)
        self.view.save_btn.Enable(has_content)
        self.view.save_as_btn.Enable(has_content)

        self.view.preamble_ctrl.Enable(has_section)
        self.view.appendix_ctrl.Enable(has_section)

    def _create_file_list_context_menus(self):
        self.included_files_context_menu = wx.Menu()
        self.mi_enforce_inclusion = self.included_files_context_menu.Append(wx.ID_ANY, "Enforce Inclusion (add to Included files)")
        self.mi_remove_from_included = self.included_files_context_menu.Append(wx.ID_ANY, "Remove from Included files list")
        self.included_files_context_menu.AppendSeparator()
        self.included_files_context_menu.Append(wx.ID_ANY, "Add to Excluded files")
        self.included_files_context_menu.AppendSeparator()
        self.included_files_context_menu.Append(wx.ID_ANY, "Add Types to File types")
        self.included_files_context_menu.Append(wx.ID_ANY, "Remove Types from File types")
        self.included_files_context_menu.AppendSeparator()
        self.included_files_context_menu.Append(wx.ID_ANY, "Load Content to Preamble Field")
        self.included_files_context_menu.Append(wx.ID_ANY, "Load Content to Appendix Field")
        self.included_files_context_menu.Bind(wx.EVT_MENU, self.on_menu_action_included)

        self.excluded_files_context_menu = wx.Menu()
        self.excluded_files_context_menu.Append(wx.ID_ANY, "Add to Include items (override exclusion)")
        self.excluded_files_context_menu.AppendSeparator()
        self.mi_enforce_exclusion = self.excluded_files_context_menu.Append(wx.ID_ANY, "Enforce Exclusion (add to Excluded files)")
        self.mi_remove_from_excluded = self.excluded_files_context_menu.Append(wx.ID_ANY, "Remove from Excluded files list")
        self.excluded_files_context_menu.AppendSeparator()
        self.excluded_files_context_menu.Append(wx.ID_ANY, "Load Content to Preamble Field")
        self.excluded_files_context_menu.Append(wx.ID_ANY, "Load Content to Appendix Field")
        self.excluded_files_context_menu.Bind(wx.EVT_MENU, self.on_menu_action_excluded)

    def on_file_list_context_menu(self, event):
        """Shows the context menu for the file list boxes."""
        listbox = event.GetEventObject()
        pos = self.ScreenToClient(event.GetPosition())

        selected_files = self.get_selected_filenames(listbox)
        if not selected_files:
            return

        include_ctrl = self.view.setting_controls['include']
        exclude_ctrl = self.view.setting_controls['excludedfiles']
        explicitly_included = [f.strip() for f in include_ctrl.GetValue().replace('\n', ',').split(',') if f.strip()]
        explicitly_excluded = [f.strip() for f in exclude_ctrl.GetValue().replace('\n', ',').split(',') if f.strip()]

        if listbox == self.view.included_files_ctrl:
            all_are_explicit = all(f in explicitly_included for f in selected_files)
            self.mi_enforce_inclusion.Enable(not all_are_explicit)
            self.mi_remove_from_included.Enable(all_are_explicit)
            self.PopupMenu(self.included_files_context_menu, pos)
        elif listbox == self.view.skipped_files_ctrl:
            all_are_explicit = all(f in explicitly_excluded for f in selected_files)
            self.mi_enforce_exclusion.Enable(not all_are_explicit)
            self.mi_remove_from_excluded.Enable(all_are_explicit)
            self.PopupMenu(self.excluded_files_context_menu, pos)

    def on_menu_action_included(self, event):
        """Handles context menu actions for the included files list."""
        self.handle_menu_action(self.view.included_files_ctrl, self.included_files_context_menu, event.GetId())

    def on_menu_action_excluded(self, event):
        """Handles context menu actions for the excluded files list."""
        self.handle_menu_action(self.view.skipped_files_ctrl, self.excluded_files_context_menu, event.GetId())

    def handle_menu_action(self, listbox, menu, menu_id):
        menu_item = menu.FindItemById(menu_id)
        if not menu_item:
            return

        label = menu_item.GetItemLabelText()

        if "Enforce Inclusion" in label or "Add to Include items" in label:
            self.perform_inclusion_change_from_list(listbox, "include")
        elif "Enforce Exclusion" in label or "Add to Excluded files" in label:
            self.perform_inclusion_change_from_list(listbox, "exclude")
        elif "Remove from Included files list" in label:
            self.perform_inclusion_change_from_list(listbox, "remove_from_include")
        elif "Remove from Excluded files list" in label:
            self.perform_inclusion_change_from_list(listbox, "remove_from_exclude")
        elif "Add Types" in label:
            self.modify_file_types(listbox, "add")
        elif "Remove Types" in label:
            self.modify_file_types(listbox, "remove")
        elif "Preamble" in label:
            self.load_content_to_field(listbox, self.view.preamble_ctrl)
        elif "Appendix" in label:
            self.load_content_to_field(listbox, self.view.appendix_ctrl)

    def get_selected_filenames(self, listbox):
        selections = listbox.GetSelections()
        if not selections:
            return []
        return [listbox.GetString(i).split(' [')[0].split(' (')[0].strip() for i in selections]

    def modify_file_types(self, listbox, action):
        filenames = self.get_selected_filenames(listbox)
        if not filenames:
            return

        types_ctrl = self.view.setting_controls['filetypes']
        current_types_str = types_ctrl.GetValue()
        types_list = [t.strip() for t in current_types_str.split(',') if t.strip()]

        changed_types = []
        for filename in filenames:
            file_ext = Path(filename).suffix
            if file_ext:
                ext_without_dot = file_ext.lstrip('.')
                if action == "add" and ext_without_dot not in types_list:
                    types_list.append(ext_without_dot)
                    changed_types.append(ext_without_dot)
                elif action == "remove" and ext_without_dot in types_list:
                    types_list.remove(ext_without_dot)
                    changed_types.append(ext_without_dot)

        if changed_types:
            types_ctrl.SetValue(','.join(types_list))
            self.on_setting_change(None)

    def load_content_to_field(self, listbox, target_ctrl):
        filenames = self.get_selected_filenames(listbox)
        if not filenames:
            return

        if not self.current_config_file:
            wx.MessageBox("No config file loaded.", "Error", wx.ICON_ERROR, parent=self.GetTopLevelParent())
            return

        base_path = Path(self.current_config_file).parent
        all_content = []

        for filename in filenames:
            file_path = base_path / filename
            if file_path.is_file():
                try:
                    content = file_path.read_text(encoding='utf-8')
                    all_content.append(f"# Content from {filename}\n{content}")
                except Exception as e:
                    all_content.append(f"# Error reading {filename}: {e}")

        if all_content:
            target_ctrl.SetValue('\n\n'.join(all_content))
            self.on_setting_change(None)

    def on_dnd_left_down(self, event):
        """Handles left mouse button down for drag-and-drop."""
        listbox = event.GetEventObject()
        self.dnd_source_list = listbox
        self.dnd_start_pos = event.GetPosition()
        self.dnd_dragging = False
        event.Skip()

    def on_dnd_motion(self, event):
        """Handles mouse motion for drag-and-drop."""
        if event.Dragging() and event.LeftIsDown() and self.dnd_source_list and self.dnd_start_pos:
            if not self.dnd_dragging:
                dx = abs(event.GetPosition().x - self.dnd_start_pos.x)
                dy = abs(event.GetPosition().y - self.dnd_start_pos.y)
                if dx > 3 or dy > 3:
                    self.dnd_dragging = True
                    self.start_drag_operation()
        event.Skip()

    def on_dnd_left_up(self, event):
        """Handles left mouse button up for drag-and-drop."""
        self.dnd_source_list = None
        self.dnd_start_pos = None
        self.dnd_dragging = False
        event.Skip()

    def start_drag_operation(self):
        """Starts the drag-and-drop operation."""
        listbox = self.dnd_source_list
        if not listbox:
            return

        filenames = self.get_selected_filenames(listbox)
        if not filenames:
            return

        data = '\n'.join(filenames)
        data_obj = wx.TextDataObject(data)
        drop_source = wx.DropSource(listbox)
        drop_source.SetData(data_obj)
        result = drop_source.DoDragDrop(wx.Drag_CopyOnly)

    def handle_drop(self, target_listbox, data):
        """Handles a drop event on one of the file lists."""
        filenames = data.strip().split('\n')
        if not filenames:
            return

        action = "include" if target_listbox == self.view.included_files_ctrl else "exclude"
        self.perform_inclusion_change(filenames, action)

    def perform_inclusion_change_from_list(self, listbox, action):
        filenames = self.get_selected_filenames(listbox)
        if not filenames:
            return
        self.perform_inclusion_change(filenames, action)

    def perform_inclusion_change(self, filenames, action):
        include_ctrl = self.view.setting_controls['include']
        exclude_ctrl = self.view.setting_controls['excludedfiles']

        include_list = [f.strip() for f in include_ctrl.GetValue().replace('\n', ',').split(',') if f.strip()]
        exclude_list = [f.strip() for f in exclude_ctrl.GetValue().replace('\n', ',').split(',') if f.strip()]

        for filename in filenames:
            if action == "include":
                if filename not in include_list:
                    include_list.append(filename)
                if filename in exclude_list:
                    exclude_list.remove(filename)
            elif action == "exclude":
                if filename not in exclude_list:
                    exclude_list.append(filename)
                if filename in include_list:
                    include_list.remove(filename)
            elif action == "remove_from_include":
                if filename in include_list:
                    include_list.remove(filename)
            elif action == "remove_from_exclude":
                if filename in exclude_list:
                    exclude_list.remove(filename)

        include_ctrl.SetValue(','.join(include_list).replace(',', '\n'))
        exclude_ctrl.SetValue(','.join(exclude_list).replace(',', '\n'))

        self.on_setting_change(None)