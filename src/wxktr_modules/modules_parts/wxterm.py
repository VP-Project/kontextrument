import wx
import threading
import re
import sys
import os
import select
import glob
import time
from collections import deque

if sys.platform == 'win32':
    try:
        import winpty.ptyprocess
    except ImportError:
        winpty = None
    import subprocess
    import signal
else:
    try:
        import ptyprocess
    except ImportError:
        ptyprocess = None


class TerminalBackend:
    """Abstract base class for platform-specific terminal backends."""
    def __init__(self):
        """Initializes the TerminalBackend."""
        self.proc = None

    def spawn(self, command):
        """Spawns the terminal process."""
        raise NotImplementedError("Spawn must be implemented by subclasses.")

    def isalive(self):
        """Checks if the terminal process is running."""
        return self.proc and self.proc.isalive()

    def read(self):
        """Reads data from the terminal's stdout."""
        return self.proc.read() if self.isalive() else ''

    def write(self, data):
        """Writes data to the terminal's stdin."""
        if self.isalive():
            self.proc.write(data)

    def close(self, force=True):
        """Closes the terminal connection."""
        if self.isalive():
            self.proc.close(force=force)

    def fileno(self):
        """Returns the file descriptor of the pty."""
        if self.proc and hasattr(self.proc, 'fd'):
            return self.proc.fd
        return None

    def kill(self):
        """Forcibly terminates the terminal process."""
        if self.proc:
            try:
                self.proc.close(force=True)
            except Exception:
                pass
            try:
                if hasattr(self.proc, 'fd'):
                    os.close(self.proc.fd)
            except Exception:
                pass

class CmdBackend(TerminalBackend):
    """Windows-specific terminal backend using winpty to spawn cmd.exe."""
    def spawn(self, command):
        """Spawns a cmd.exe process."""
        if not winpty:
            raise RuntimeError("winpty library not found. Please run 'pip install winpty'.")
        self.proc = winpty.ptyprocess.PtyProcess.spawn(['cmd.exe', '/c', command], dimensions=(24, 500))
        try:
            self._raw_pid = self.proc.pid
        except Exception:
            self._raw_pid = None

    def kill(self):
        """Forcibly terminates the cmd.exe process."""
        try:
            if self._raw_pid:
                import ctypes
                PROCESS_TERMINATE = 0x0001
                handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, self._raw_pid)
                if handle:
                    ctypes.windll.kernel32.TerminateProcess(handle, -1)
                    ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            pass
        super().kill()

class BashBackend(TerminalBackend):
    """Unix-like terminal backend using ptyprocess to spawn a bash/sh shell."""
    def spawn(self, command):
        """Spawns a bash or sh shell process."""
        if not ptyprocess:
            raise RuntimeError("ptyprocess library not found. Please run 'pip install ptyprocess'.")
        shell = '/bin/bash' if os.path.exists('/bin/bash') else '/bin/sh'
        self.proc = ptyprocess.PtyProcess.spawn([shell, '-c', command], dimensions=(24, 500))
        try:
            self._raw_pid = self.proc.pid
        except Exception:
            self._raw_pid = None

    def kill(self):
        """Forcibly terminates the shell process."""
        try:
            if self._raw_pid:
                try:
                    os.kill(self._raw_pid, signal.SIGTERM)
                except Exception:
                    try:
                        os.kill(self._raw_pid, signal.SIGKILL)
                    except Exception:
                        pass
        except Exception:
            pass
        super().kill()


class FilePathCompleter(wx.TextCompleterSimple):
    """Custom autocompleter for file and directory paths."""
    
    def __init__(self):
        """Initializes the FilePathCompleter."""
        super().__init__()
        
    def GetCompletions(self, prefix):
        """Return list of file/directory completions for the given prefix."""
        completions = []
        
        if not prefix:
            prefix = "./"
        
        parts = prefix.split()
        if len(parts) == 0:
            path_prefix = ""
        else:
            path_prefix = parts[-1]
        
        if os.path.isdir(path_prefix):
            search_dir = path_prefix
            if not search_dir.endswith(os.sep):
                search_pattern = os.path.join(search_dir, "*")
            else:
                search_pattern = os.path.join(search_dir, "*")
            base_prefix = path_prefix
        else:
            search_dir = os.path.dirname(path_prefix) or "."
            filename_start = os.path.basename(path_prefix)
            search_pattern = os.path.join(search_dir, filename_start + "*")
            base_prefix = os.path.dirname(path_prefix)
        
        try:
            matches = glob.glob(search_pattern)
            
            matches.sort(key=lambda x: (not os.path.isdir(x), x.lower()))
            
            for match in matches[:50]:
                if os.path.isdir(match):
                    display_path = match + os.sep
                else:
                    display_path = match
                
                if len(parts) > 1:
                    completion = " ".join(parts[:-1]) + " " + display_path
                else:
                    completion = display_path
                
                completions.append(completion)
                
        except (OSError, PermissionError):
            pass
        
        return completions


class PreCommandDialog(wx.Dialog):
    """Dialog for configuring the pre-command setting."""
    
    def __init__(self, parent, current_precommand=""):
        """Initializes the PreCommandDialog."""
        super().__init__(parent, title="Pre-Command Settings", 
                        style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
                        size=(550, 300))
        
        self.raw_precommand = current_precommand.strip()
        for sep in ["&&", ";", "|"]:
            if self.raw_precommand.endswith(sep):
                self.raw_precommand = self.raw_precommand[:-len(sep)].strip()
                break
        
        self.InitUI()
        self.Centre()
        
    def InitUI(self):
        """Initialize the dialog UI."""
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        description = wx.StaticText(panel, 
            label="Set a command that will be automatically prepended to every command you execute.\n"
                  "The command separator (e.g., && or ;) will be added automatically if needed.\n"
                  "Leave empty to disable.")
        vbox.Add(description, 0, wx.ALL | wx.EXPAND, 10)
        
        examples_label = wx.StaticText(panel, label="Examples:")
        examples_label.SetFont(examples_label.GetFont().Bold())
        vbox.Add(examples_label, 0, wx.LEFT | wx.RIGHT, 10)
        
        if sys.platform == 'win32':
            examples_text = wx.StaticText(panel, 
                label="  • cd C:\\MyProject\n"
                      "  • venv\\Scripts\\activate\n"
                      "  • conda activate myenv")
        else:
            examples_text = wx.StaticText(panel, 
                label="  • cd /home/user/project\n"
                      "  • source venv/bin/activate\n"
                      "  • conda activate myenv")
        vbox.Add(examples_text, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
        
        hbox1 = wx.BoxSizer(wx.HORIZONTAL)
        label = wx.StaticText(panel, label="Pre-Command:")
        hbox1.Add(label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        
        placeholder = "cd C:\\MyProject" if sys.platform == 'win32' else "source venv/bin/activate"
        self.precommand_input = wx.TextCtrl(panel, value=self.raw_precommand, 
                                            style=wx.TE_PROCESS_ENTER)
        self.precommand_input.SetHint(placeholder)
        hbox1.Add(self.precommand_input, 1, wx.EXPAND)
        vbox.Add(hbox1, 0, wx.ALL | wx.EXPAND, 10)
        
        hbox2 = wx.BoxSizer(wx.HORIZONTAL)
        sep_label = wx.StaticText(panel, label="Command Separator:")
        hbox2.Add(sep_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        
        separators = ["&& (recommended)", "; (alternative)", "| (pipe)"]
        self.separator_choice = wx.Choice(panel, choices=separators)
        self.separator_choice.SetSelection(0)
        hbox2.Add(self.separator_choice, 0, wx.EXPAND)
        
        info_label = wx.StaticText(panel, label="  (added automatically)")
        info_label.SetFont(info_label.GetFont().Italic())
        hbox2.Add(info_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
        vbox.Add(hbox2, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
        
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        clear_btn = wx.Button(panel, label="Clear")
        clear_btn.Bind(wx.EVT_BUTTON, self.OnClear)
        btn_sizer.Add(clear_btn, 0, wx.RIGHT, 5)
        
        btn_sizer.AddStretchSpacer()
        
        ok_btn = wx.Button(panel, wx.ID_OK, label="OK")
        ok_btn.Bind(wx.EVT_BUTTON, self.OnOK)
        btn_sizer.Add(ok_btn, 0, wx.RIGHT, 5)
        
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, label="Cancel")
        btn_sizer.Add(cancel_btn, 0)
        
        vbox.Add(btn_sizer, 0, wx.ALL | wx.EXPAND, 10)
        
        panel.SetSizer(vbox)
        
        self.precommand_input.SetFocus()
        
    def OnClear(self, event):
        """Handles the 'Clear' button event."""
        self.precommand_input.SetValue("")
        
    def OnOK(self, event):
        """Handles the 'OK' button event."""
        self.EndModal(wx.ID_OK)
        
    def GetPreCommand(self):
        """Returns the configured pre-command with the proper separator."""
        precommand = self.precommand_input.GetValue().strip()
        if not precommand:
            return ""
        
        separator_map = {0: "&&", 1: ";", 2: "|"}
        separator = separator_map.get(self.separator_choice.GetSelection(), "&&")
        
        for sep in ["&&", ";", "|", "&"]:
            if precommand.rstrip().endswith(sep):
                return precommand.strip()
        
        return f"{precommand} {separator}"
    
    def GetRawPreCommand(self):
        """Returns the configured pre-command without the separator."""
        return self.precommand_input.GetValue().strip()


class InputPanel(wx.Panel):
    """A panel containing the command input field and run/stop buttons."""
    def __init__(self, parent):
        """Initializes the InputPanel."""
        super().__init__(parent)
        
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        self.precommand_indicator = wx.StaticText(self, label="")
        self.precommand_indicator.SetForegroundColour(wx.Colour(200, 150, 0))
        self.precommand_indicator.SetFont(self.precommand_indicator.GetFont().Italic())
        self.precommand_indicator.Hide()
        main_sizer.Add(self.precommand_indicator, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 3)
        
        input_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.label = wx.StaticText(self, label="Command:")
        self.command_input = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        
        self.command_input.AutoComplete(FilePathCompleter())
        
        self.run_button = wx.Button(self, label="Run")
        self.stop_button = wx.Button(self, label="Stop")
        self.stop_button.Enable(False)
        
        self.settings_button = wx.Button(self, label="⚙", size=(30, -1))
        self.settings_button.SetToolTip("Configure Pre-Command Settings")

        input_sizer.Add(self.label, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, 5)
        input_sizer.Add(self.command_input, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        input_sizer.Add(self.run_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        input_sizer.Add(self.stop_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        input_sizer.Add(self.settings_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        
        main_sizer.Add(input_sizer, 0, wx.EXPAND)
        self.SetSizer(main_sizer)

        self.run_button.Bind(wx.EVT_BUTTON, self.on_run)
        self.stop_button.Bind(wx.EVT_BUTTON, self.on_stop)
        self.settings_button.Bind(wx.EVT_BUTTON, self.on_settings)
        self.command_input.Bind(wx.EVT_TEXT_ENTER, self.on_run)

    def on_run(self, event):
        """Handles the 'Run' button click or Enter key press."""
        self.GetParent().on_execute_command()

    def on_stop(self, event):
        """Handles the 'Stop' button click."""
        self.GetParent().on_stop_command()
    
    def on_settings(self, event):
        """Handles the settings button click."""
        self.GetParent().on_show_settings()

    def get_command(self):
        """Gets the command from the input field."""
        return self.command_input.GetValue()

    def set_command(self, command):
        """Sets the text in the command input field."""
        self.command_input.SetValue(command)

    def clear(self):
        """Clears the command input field."""
        self.command_input.Clear()
    
    def update_precommand_indicator(self, precommand):
        """Update the pre-command indicator display."""
        if precommand:
            self.precommand_indicator.SetLabel(f"Pre-command active: {precommand}")
            self.precommand_indicator.Show()
        else:
            self.precommand_indicator.Hide()
        self.Layout()

    def set_controls_enabled(self, enabled):
        """Enables or disables the input controls based on command execution state."""
        self.command_input.Enable(enabled)
        self.run_button.Enable(enabled)
        self.stop_button.Enable(not enabled)
        self.settings_button.Enable(enabled)
        if enabled:
            self.command_input.SetFocus()

class HistoryPanel(wx.Panel):
    """A panel displaying the command history in a listbox."""
    def __init__(self, parent, controller, project_settings):
        """Initializes the HistoryPanel."""
        super().__init__(parent)
        self.controller = controller
        self.project_settings = project_settings
        
        self.label = wx.StaticText(self, label="Command History:")
        self.history_list = wx.ListBox(self, style=wx.LB_SINGLE)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.label, 0, wx.ALL, 5)
        sizer.Add(self.history_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        self.SetSizer(sizer)

        self.history_list.Bind(wx.EVT_LISTBOX, self.on_select)
        self.history_list.Bind(wx.EVT_LISTBOX_DCLICK, self.on_dclick)
        self.history_list.Bind(wx.EVT_RIGHT_UP, self.on_show_context_menu)
        self.load_history()

    def on_show_context_menu(self, event):
        """Show context menu to delete a history item."""
        item_index = self.history_list.HitTest(event.GetPosition())
        
        if item_index != wx.NOT_FOUND:
            self.history_list.SetSelection(item_index)
            
            menu = wx.Menu()
            delete_item = menu.Append(wx.ID_ANY, "Delete")
            self.Bind(wx.EVT_MENU, self.on_delete_history, delete_item)
            
            self.PopupMenu(menu)
            menu.Destroy()

    def on_delete_history(self, event):
        """Delete the selected history item."""
        selection_index = self.history_list.GetSelection()
        if selection_index != wx.NOT_FOUND:
            command_to_delete = self.history_list.GetString(selection_index)
            
            current_history = self.project_settings.get_terminal_history()
            new_history = [cmd for cmd in current_history if cmd != command_to_delete]
            
            self.project_settings.set_terminal_history(new_history)
            
            self.load_history()

    def on_select(self, event):
        """Handles single-click selection in the history list."""
        command = self.history_list.GetStringSelection()
        self.controller.on_history_select(command)

    def on_dclick(self, event):
        """Handles double-click execution from the history list."""
        command = self.history_list.GetStringSelection()
        self.controller.on_execute_command(command_override=command)

    def add_to_history(self, command):
        """Adds a command to the history list."""
        self.project_settings.add_to_terminal_history(command)
        self.load_history()

    def update_ui(self):
        """Updates the listbox with the current history."""
        history = self.project_settings.get_terminal_history()
        self.history_list.SetItems(history[::-1])

    def load_history(self):
        """Loads and displays the command history."""
        self.update_ui()

    def save_history(self):
        """Saves the command history (handled by project_settings)."""
        pass

    def set_controls_enabled(self, enabled):
        """Enables or disables the history list."""
        self.history_list.Enable(enabled)

class OutputPanel(wx.Panel):
    """A panel that displays the terminal output with ANSI color support."""
    def __init__(self, parent):
        """Initializes the OutputPanel."""
        super().__init__(parent)
        self.ANSI_MAP = {
            '30': wx.Colour('BLACK'), '31': wx.Colour('RED'), '32': wx.Colour('GREEN'),
            '33': wx.Colour('YELLOW'), '34': wx.Colour('BLUE'), '35': wx.Colour('MAGENTA'),
            '36': wx.Colour('CYAN'), '37': wx.Colour('LIGHT GREY'), '90': wx.Colour(128, 128, 128),
            '91': wx.Colour(255, 128, 128), '92': wx.Colour(128, 255, 128), '93': wx.Colour(255, 255, 128),
            '94': wx.Colour(128, 128, 255), '95': wx.Colour(255, 128, 255), '96': wx.Colour(128, 255, 255),
            '97': wx.Colour('WHITE'),
        }
        self.output_ctrl = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_RICH2 | wx.TE_PROCESS_ENTER)
        self.copy_button = wx.Button(self, label="Copy Output")

        font = wx.Font(10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.output_ctrl.SetFont(font)
        self.output_ctrl.SetBackgroundColour(wx.Colour(0, 0, 0))
        self.default_style = wx.TextAttr(wx.Colour(200, 200, 200), wx.Colour(0, 0, 0), font)
        self.current_style = wx.TextAttr(self.default_style)
        self.output_ctrl.SetDefaultStyle(self.default_style)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.output_ctrl, 1, wx.EXPAND)
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.AddStretchSpacer()
        btn_sizer.Add(self.copy_button, 0, wx.ALL, 5)
        sizer.Add(btn_sizer, 0, wx.EXPAND)
        self.SetSizer(sizer)

        self.input_start_pos = 0
        self.command_header_end_pos = 0
        self.backend = None
        self.is_running = False
        self.stop_requested = False

        self.output_ctrl.Bind(wx.EVT_KEY_DOWN, self.on_key_press)
        self.output_ctrl.Bind(wx.EVT_TEXT_ENTER, self.on_text_enter)
        self.copy_button.Bind(wx.EVT_BUTTON, self.on_copy)

    def reader_thread_loop(self, controller):
        """Reads output from the backend process in a separate thread."""
        try:
            if sys.platform == 'win32':
                buffer = ''
                while self.backend and self.backend.isalive():
                    if self.stop_requested:
                        try: self.backend.kill()
                        except Exception: pass
                        break
                    
                    try:
                        chunk = self.backend.read()
                        if chunk:
                            buffer += chunk
                        else:
                            time.sleep(0.02)

                        if buffer and ('\n' in buffer or '\r' in buffer or not chunk):
                            wx.CallAfter(self.process_incoming_text, buffer)
                            buffer = ''
                    except (OSError, EOFError):
                        break
                if buffer:
                    wx.CallAfter(self.process_incoming_text, buffer)
            
            else:
                fd = self.backend.fileno() if self.backend and hasattr(self.backend, 'fileno') else None
                while self.backend and self.backend.isalive():
                    if self.stop_requested:
                        try: self.backend.kill()
                        except Exception: pass
                        break
                    try:
                        if fd and select.select([fd], [], [], 0.1)[0]:
                            output = self.backend.read()
                            if output:
                                wx.CallAfter(self.process_incoming_text, output)
                        else:
                            output = self.backend.read()
                            if output:
                                wx.CallAfter(self.process_incoming_text, output)

                    except (OSError, EOFError):
                        break

        except Exception as e:
            wx.CallAfter(self.process_incoming_text, f"\nError in reader thread: {e}\n")
        finally:
            self.is_running = False
            if self.backend:
                try:
                    self.backend.close(force=False)
                except Exception:
                    pass
                self.backend = None
            wx.CallAfter(controller.set_controls_enabled, True)
            status_msg = "\n--- Process Stopped ---\n" if self.stop_requested else "\n--- Process Finished ---\n"
            wx.CallAfter(self.process_incoming_text, status_msg)
            self.stop_requested = False

    def process_incoming_text(self, text):
        """Processes and displays incoming text, handling ANSI escape codes."""
        if not text: return
        
        if isinstance(text, bytes):
            text = text.decode(sys.stdout.encoding or 'utf-8', errors='replace')
        
        text = re.sub(r'\r\n?', '\n', text)
        
        text = re.sub(r'\x1b\]0;.*?\x07', '', text)
        
        csi_pattern = re.compile(r'\x1b\[([\d;?]*)(\w)')
        parts = csi_pattern.split(text)
        self.output_ctrl.SetInsertionPointEnd()
        
        for i in range(0, len(parts), 3):
            normal_text = parts[i]
            if normal_text:
                self.output_ctrl.SetDefaultStyle(self.current_style)
                self.output_ctrl.AppendText(normal_text)
            
            if i + 2 < len(parts):
                params, command = parts[i+1], parts[i+2]
                if command == 'J' and params == '2':
                    current_pos = self.output_ctrl.GetLastPosition()
                    if current_pos > self.command_header_end_pos:
                        self.output_ctrl.Remove(self.command_header_end_pos, current_pos)
                        self.output_ctrl.SetInsertionPoint(self.command_header_end_pos)
                elif command == 'm':
                    codes = params.split(';')
                    if not params or '0' in codes:
                        self.current_style = wx.TextAttr(self.default_style)
                    for code in codes:
                        if code in self.ANSI_MAP:
                            self.current_style.SetTextColour(self.ANSI_MAP[code])
                        elif code == '1':
                            self.current_style.SetFontWeight(wx.FONTWEIGHT_BOLD)
                elif command in ('B', 'E'):
                    count = 1
                    if params.isdigit() and int(params) > 0:
                        count = int(params)
                    self.output_ctrl.AppendText('\n' * count)
                            
        self.input_start_pos = self.output_ctrl.GetLastPosition()
        self.output_ctrl.SetInsertionPoint(self.input_start_pos)
        self.output_ctrl.ShowPosition(self.input_start_pos)

    def execute_command(self, command, controller, precommand=""):
        """Executes a command in a new terminal process."""
        if self.is_running:
            wx.MessageBox("A command is already running.", "Busy", wx.OK | wx.ICON_INFORMATION)
            return
        self.is_running = True
        self.stop_requested = False
        controller.set_controls_enabled(False)
        self.output_ctrl.Clear()
        self.input_start_pos = 0
        self.command_header_end_pos = 0
        
        full_command = f"{precommand} {command}" if precommand else command
        
        prompt_char = '>' if sys.platform == 'win32' else '$'
        
        command_header = f"{prompt_char} {command}\n"
        header_style = wx.TextAttr(wx.Colour(128, 255, 255), wx.Colour(0, 0, 0), self.output_ctrl.GetFont())
        self.output_ctrl.SetDefaultStyle(header_style)
        self.output_ctrl.AppendText(command_header)
        
        self.command_header_end_pos = self.output_ctrl.GetLastPosition()
        
        self.output_ctrl.SetDefaultStyle(self.default_style)
        self.current_style = wx.TextAttr(self.default_style)
        self.input_start_pos = self.command_header_end_pos
        
        try:
            self.backend = CmdBackend() if sys.platform == 'win32' else BashBackend()
            self.backend.spawn(full_command)
            thread = threading.Thread(target=self.reader_thread_loop, args=(controller,))
            thread.daemon = True
            thread.start()
        except Exception as e:
            self.output_ctrl.AppendText(f"\nError starting process: {e}")
            self.is_running = False
            controller.set_controls_enabled(True)

    def stop_command(self):
        """Stops the currently running command."""
        if self.is_running and self.backend:
            self.stop_requested = True
            try:
                self.backend.kill()
            except Exception:
                try:
                    self.backend.close(force=True)
                except Exception:
                    pass
            self.is_running = False
            self.backend = None
            wx.CallAfter(self.process_incoming_text, "\n--- Stopped by user (manual) ---\n")
            parent = self.GetParent()
            while parent and not hasattr(parent, "set_controls_enabled"):
                parent = parent.GetParent()
            if parent and hasattr(parent, "set_controls_enabled"):
                wx.CallAfter(parent.set_controls_enabled, True)

    def on_text_enter(self, event):
        """Handles Enter key press to send input to the running process."""
        if not (self.is_running and self.backend and self.backend.isalive()): return
        command = self.output_ctrl.GetValue()[self.input_start_pos:].strip()
        self.output_ctrl.AppendText('\n')
        self.input_start_pos = self.output_ctrl.GetLastPosition()
        self.backend.write(command + '\r\n')

    def on_key_press(self, event):
        """Handles key presses to manage input area protection."""
        if not self.is_running: event.Skip(); return
        pos, key = self.output_ctrl.GetInsertionPoint(), event.GetKeyCode()
        if pos < self.input_start_pos or (key == wx.WXK_BACK and pos <= self.input_start_pos):
                 if key not in [wx.WXK_LEFT, wx.WXK_RIGHT, wx.WXK_UP, wx.WXK_DOWN, wx.WXK_HOME, wx.WXK_END]:
                     return
        event.Skip()

    def on_copy(self, event):
        """Handles the 'Copy Output' button click."""
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(self.output_ctrl.GetValue()))
            wx.TheClipboard.Close()

    def shutdown(self):
        if self.backend and self.backend.isalive():
            self.backend.close()

class TerminalPanel(wx.Panel):
    """The main terminal widget, combining input, output, and history panels."""
    def __init__(self, parent, project_settings):
        """Initializes the TerminalPanel."""
        super().__init__(parent)
        self.project_settings = project_settings
        self.precommand = ""
        self.load_precommand()
        
        self.input_panel = InputPanel(self)
        splitter = wx.SplitterWindow(self, style=wx.SP_LIVE_UPDATE)
        self.history_panel = HistoryPanel(splitter, controller=self, project_settings=self.project_settings)
        self.output_panel = OutputPanel(splitter)
        splitter.SplitVertically(self.history_panel, self.output_panel, 250)
        splitter.SetSashGravity(0.25)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.input_panel, 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(splitter, 1, wx.EXPAND)
        self.SetSizer(sizer)
        
        self.input_panel.update_precommand_indicator(self.precommand)


    def on_execute_command(self, command_override=None):
        """Callback to execute a command from the input or history."""
        command = command_override or self.input_panel.get_command()
        command = command.strip()
        if command:
            self.history_panel.add_to_history(command)
            self.output_panel.execute_command(command, self, self.precommand)
            self.input_panel.clear()

    def on_stop_command(self):
        """Callback to stop the currently running command."""
        self.output_panel.stop_command()

    def on_history_select(self, command):
        """Callback when a command is selected from history."""
        if command:
            self.input_panel.set_command(command)

    def set_controls_enabled(self, enabled):
        """Enables or disables UI controls based on execution state."""
        self.input_panel.set_controls_enabled(enabled)
        self.history_panel.set_controls_enabled(enabled)
    
    def on_show_settings(self):
        """Show the pre-command settings dialog."""
        dialog = PreCommandDialog(self, self.precommand)
        if dialog.ShowModal() == wx.ID_OK:
            new_precommand_with_sep = dialog.GetPreCommand()
            new_raw_precommand = dialog.GetRawPreCommand()
            
            if new_raw_precommand != self.project_settings.get_terminal_pre_command():
                self.precommand = new_precommand_with_sep
                self.save_precommand(new_raw_precommand)
                self.input_panel.update_precommand_indicator(self.precommand)
                
                if self.precommand:
                    wx.MessageBox(f"Pre-command set to:\n{new_raw_precommand}\n\n"
                                "This will be prepended to all commands.",
                                "Pre-Command Updated", wx.OK | wx.ICON_INFORMATION)
                else:
                    wx.MessageBox("Pre-command cleared.",
                                "Pre-Command Updated", wx.OK | wx.ICON_INFORMATION)
        dialog.Destroy()
    
    def load_precommand(self):
        """Loads the raw pre-command and prepares it for execution."""
        raw_precommand = self.project_settings.get_terminal_pre_command()
        if raw_precommand:
            self.precommand = f"{raw_precommand} &&"
        else:
            self.precommand = ""
    
    def save_precommand(self, raw_precommand):
        """Saves the raw pre-command to project settings."""
        self.project_settings.set_terminal_pre_command(raw_precommand)
        
    def shutdown(self):
        """Shuts down the terminal backend process."""
        self.output_panel.shutdown()

class TerminalFrame(wx.Frame):
    """A simple wx.Frame to host and demonstrate the TerminalPanel."""
    def __init__(self):
        """Initializes the TerminalFrame."""
        super().__init__(None, title="Pymini wxPython Terminal", size=(900, 600))
        
        try:
            from .project_settings import ProjectSettings
        except ImportError:
            from project_settings import ProjectSettings
        
        project_settings = ProjectSettings(os.getcwd())
        self.panel = TerminalPanel(self, project_settings)
        
        self.Bind(wx.EVT_CLOSE, self.on_close)
        
        self.Show()
    
    def on_close(self, event):
        """Handle window close event."""
        self.panel.shutdown()
        self.Destroy()

if __name__ == '__main__':
    app = wx.App(False)
    frame = TerminalFrame()
    app.MainLoop()