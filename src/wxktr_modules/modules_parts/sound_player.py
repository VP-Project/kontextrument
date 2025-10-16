import wx
import wx.media
import os

class SoundPlayer(wx.Panel):
    """A panel that plays audio files with playback controls."""
    
    SUPPORTED_FORMATS = {
        '.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac', 
        '.wma', '.opus', '.aiff', '.ape', '.mpc'
    }
    
    def __init__(self, parent):
        """Initializes the SoundPlayer panel."""
        super().__init__(parent)
        self.current_file = None
        self.pending_file = None
        self.is_loaded = False
        self.is_playing = False
        self.is_paused = False
        self.loop_mode = False
        self.is_restarting = False
        self.user_volume = 0.75
        self.is_ready = False
        
        self.media_ctrl_id = wx.NewIdRef()
        self.media_ctrl = wx.media.MediaCtrl(
            self, 
            id=self.media_ctrl_id,
            style=wx.SIMPLE_BORDER
        )
        
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        info_panel = wx.Panel(self)
        info_sizer = wx.BoxSizer(wx.VERTICAL)
        
        self.file_label = wx.StaticText(info_panel, label="No audio file loaded")
        self.file_label.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        info_sizer.Add(self.file_label, 0, wx.ALL | wx.EXPAND, 5)
        
        self.info_label = wx.StaticText(info_panel, label="")
        info_sizer.Add(self.info_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 5)
        
        info_panel.SetSizer(info_sizer)
        main_sizer.Add(info_panel, 0, wx.EXPAND | wx.ALL, 10)
        
        self.progress_slider = wx.Slider(
            self, 
            value=0, 
            minValue=0, 
            maxValue=100,
            style=wx.SL_HORIZONTAL | wx.SL_LABELS
        )
        self.progress_slider.Enable(False)
        main_sizer.Add(self.progress_slider, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        
        time_panel = wx.Panel(self)
        time_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.current_time_label = wx.StaticText(time_panel, label="0:00")
        self.total_time_label = wx.StaticText(time_panel, label="0:00")
        
        time_sizer.Add(self.current_time_label, 0, wx.LEFT, 5)
        time_sizer.AddStretchSpacer()
        time_sizer.Add(self.total_time_label, 0, wx.RIGHT, 5)
        
        time_panel.SetSizer(time_sizer)
        main_sizer.Add(time_panel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        
        control_panel = wx.Panel(self)
        control_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.play_button = wx.Button(control_panel, label="▶ Play")
        self.play_loop_button = wx.Button(control_panel, label="🔁 Play in Loop")
        self.pause_button = wx.Button(control_panel, label="⏸ Pause")
        self.stop_button = wx.Button(control_panel, label="⏹ Stop")
        
        self.play_button.Enable(False)
        self.play_loop_button.Enable(False)
        self.pause_button.Enable(False)
        self.stop_button.Enable(False)
        
        control_sizer.AddStretchSpacer()
        control_sizer.Add(self.play_button, 0, wx.ALL, 5)
        control_sizer.Add(self.play_loop_button, 0, wx.ALL, 5)
        control_sizer.Add(self.pause_button, 0, wx.ALL, 5)
        control_sizer.Add(self.stop_button, 0, wx.ALL, 5)
        control_sizer.AddStretchSpacer()
        
        control_panel.SetSizer(control_sizer)
        main_sizer.Add(control_panel, 0, wx.EXPAND | wx.ALL, 10)
        
        volume_panel = wx.Panel(self)
        volume_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        volume_label = wx.StaticText(volume_panel, label="🔊 Volume:")
        self.volume_slider = wx.Slider(
            volume_panel,
            value=75,
            minValue=0,
            maxValue=100,
            style=wx.SL_HORIZONTAL
        )
        self.volume_value_label = wx.StaticText(volume_panel, label="75%")
        
        volume_sizer.Add(volume_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
        volume_sizer.Add(self.volume_slider, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        volume_sizer.Add(self.volume_value_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        
        volume_panel.SetSizer(volume_sizer)
        main_sizer.Add(volume_panel, 0, wx.EXPAND | wx.ALL, 10)
        
        main_sizer.AddStretchSpacer()
        
        self.SetSizer(main_sizer)
        
        self.play_button.Bind(wx.EVT_BUTTON, self.on_play)
        self.play_loop_button.Bind(wx.EVT_BUTTON, self.on_play_loop)
        self.pause_button.Bind(wx.EVT_BUTTON, self.on_pause)
        self.stop_button.Bind(wx.EVT_BUTTON, self.on_stop)
        self.volume_slider.Bind(wx.EVT_SLIDER, self.on_volume_change)
        self.progress_slider.Bind(wx.EVT_SLIDER, self.on_seek)
        
        self.Bind(wx.media.EVT_MEDIA_LOADED, self.on_media_loaded, id=self.media_ctrl_id)
        self.Bind(wx.media.EVT_MEDIA_FINISHED, self.on_media_finished, id=self.media_ctrl_id)
        self.Bind(wx.media.EVT_MEDIA_STOP, self.on_media_stop, id=self.media_ctrl_id)
        
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_timer)
        
        self.media_ctrl.SetVolume(self.user_volume)
    
    @classmethod
    def is_supported_audio(cls, filepath):
        """Check if the file is a supported audio format."""
        if not filepath:
            return False
        ext = os.path.splitext(filepath)[1].lower()
        return ext in cls.SUPPORTED_FORMATS
    
    def load_audio(self, filepath):
        """
        Prepare an audio file for playback.
        Loads immediately with volume at 0 to "warm up" audio hardware.
        """
        self.pending_file = filepath
        self.current_file = None
        self.is_loaded = False
        self.is_ready = False
        
        if self.is_playing or self.is_paused:
            self.media_ctrl.Stop()
        
        self.is_playing = False
        self.is_paused = False
        self.loop_mode = False
        self.is_restarting = False
        self.timer.Stop()
        
        filename = os.path.basename(filepath)
        self.file_label.SetLabel(filename)
        
        try:
            file_size = os.path.getsize(filepath)
            size_str = self._format_file_size(file_size)
            self.info_label.SetLabel(f"Loading... | Size: {size_str}")
        except:
            self.info_label.SetLabel("Loading...")
        
        self.play_button.Enable(False)
        self.play_loop_button.Enable(False)
        self.pause_button.Enable(False)
        self.stop_button.Enable(False)
        
        self.progress_slider.Enable(False)
        self.progress_slider.SetValue(0)
        self.progress_slider.SetMax(100)
        self.current_time_label.SetLabel("0:00")
        self.total_time_label.SetLabel("0:00")
        
        wx.CallAfter(self._preload_silent, filepath)
        
        return True
    
    def _preload_silent(self, filepath):
        """
        Pre-load the file with volume muted to initialize audio hardware.
        This prevents the click sound when the user presses play.
        """
        try:
            self.media_ctrl.SetVolume(0.0)
            
            if self.media_ctrl.Load(filepath):
                self.current_file = filepath
                self.is_loaded = True
                
                wx.CallLater(100, self._initialize_audio_hardware)
            else:
                self.media_ctrl.SetVolume(self.user_volume)
                self.info_label.SetLabel("Failed to load")
                
        except Exception as e:
            print(f"Preload error: {e}")
            self.media_ctrl.SetVolume(self.user_volume)
            self.info_label.SetLabel("Error loading file")
    
    def _initialize_audio_hardware(self):
        """
        Initialize the audio hardware by briefly playing and stopping.
        This must happen after the media is fully loaded.
        """
        try:
            self.media_ctrl.Seek(0)
            
            self.media_ctrl.Play()
            
            wx.CallLater(100, self._finalize_preload)
            
        except Exception as e:
            print(f"Initialize hardware error: {e}")
            self._finalize_preload()
    
    def _finalize_preload(self):
        """Stop the preload playback and make the file ready for actual playback."""
        try:
            self.media_ctrl.Stop()
            self.media_ctrl.Seek(0)
            
            self.media_ctrl.SetVolume(self.user_volume)
            
            self.is_ready = True
            
            self.info_label.SetLabel("Ready to play")
            self.play_button.Enable(True)
            self.play_loop_button.Enable(True)
            
            print(f"Preload complete. Volume restored to: {self.user_volume}, Ready: {self.is_ready}")
            
        except Exception as e:
            print(f"Finalize preload error: {e}")
            self.media_ctrl.SetVolume(self.user_volume)
            self.is_ready = True
            self.play_button.Enable(True)
            self.play_loop_button.Enable(True)
    
    def on_media_loaded(self, event):
        """Handle media loaded event."""
        length = self.media_ctrl.Length()
        if length > 0:
            self.progress_slider.SetMax(length)
            self.progress_slider.Enable(True)
            self.total_time_label.SetLabel(self._format_time(length))
            
            if self.is_ready and self.current_file:
                try:
                    file_size = os.path.getsize(self.current_file)
                    size_str = self._format_file_size(file_size)
                    duration_str = self._format_time(length)
                    self.info_label.SetLabel(f"Duration: {duration_str} | Size: {size_str}")
                except:
                    self.info_label.SetLabel(f"Duration: {self._format_time(length)}")
        
        self.Layout()
    
    def on_play(self, event):
        """Handle play button click."""
        self.loop_mode = False
        self._start_playback()
    
    def on_play_loop(self, event):
        """Handle play in loop button click."""
        self.loop_mode = True
        self._start_playback()
    
    def _start_playback(self):
        """Internal method to start playback."""
        if not self.is_loaded or not self.is_ready:
            wx.MessageBox("Audio file not ready. Please wait a moment.", "Not Ready", wx.ICON_INFORMATION)
            return
        
        self.media_ctrl.SetVolume(self.user_volume)
        print(f"Starting playback with volume: {self.user_volume}")
        
        if self.is_paused:
            self.media_ctrl.Play()
            self.is_paused = False
        else:
            self.media_ctrl.Seek(0)
            self.media_ctrl.Play()
        
        self.is_playing = True
        self.pause_button.Enable(True)
        self.stop_button.Enable(True)
        self.timer.Start(100)
    
    def on_pause(self, event):
        """Handle pause button click."""
        if self.is_playing:
            self.media_ctrl.Pause()
            self.is_paused = True
            self.is_playing = False
            self.timer.Stop()
    
    def on_stop(self, event):
        """Handle stop button click."""
        self.loop_mode = False
        self.stop()
    
    def stop(self):
        """Stop playback and reset position."""
        self.is_restarting = False
        if self.is_loaded:
            self.media_ctrl.Stop()
            self.media_ctrl.Seek(0)
        self.is_playing = False
        self.is_paused = False
        self.loop_mode = False
        self.timer.Stop()
        self.pause_button.Enable(False)
        self.progress_slider.SetValue(0)
        self.current_time_label.SetLabel("0:00")
    
    def on_volume_change(self, event):
        """Handle volume slider change."""
        volume = self.volume_slider.GetValue()
        self.user_volume = volume / 100.0
        self.media_ctrl.SetVolume(self.user_volume)
        self.volume_value_label.SetLabel(f"{volume}%")
        print(f"Volume changed to: {self.user_volume}")
    
    def on_seek(self, event):
        """Handle seek slider change."""
        if self.is_loaded and self.media_ctrl.Length() > 0:
            position = self.progress_slider.GetValue()
            self.media_ctrl.Seek(position)
            self.current_time_label.SetLabel(self._format_time(position))
    
    def on_timer(self, event):
        """Update progress slider and time label."""
        if self.is_playing and not self.is_restarting and self.is_loaded:
            position = self.media_ctrl.Tell()
            self.progress_slider.SetValue(position)
            self.current_time_label.SetLabel(self._format_time(position))
    
    def on_media_stop(self, event):
        """Handle media stop event."""
        if self.is_restarting:
            return
        
        if self.loop_mode and not self.is_paused:
            wx.CallAfter(self._restart_for_loop)
        else:
            self.is_playing = False
            self.is_paused = False
            self.timer.Stop()
            self.pause_button.Enable(False)
    
    def on_media_finished(self, event):
        """Handle media finished event."""
        if self.is_restarting:
            return
        
        if self.loop_mode:
            wx.CallAfter(self._restart_for_loop)
        else:
            wx.CallAfter(self._final_stop)
    
    def _final_stop(self):
        """Final cleanup when playback ends normally."""
        self.is_playing = False
        self.is_paused = False
        self.timer.Stop()
        self.pause_button.Enable(False)
        self.progress_slider.SetValue(0)
        self.current_time_label.SetLabel("0:00")
    
    def _restart_for_loop(self):
        """Helper method to restart playback for looping."""
        if self.is_restarting:
            return
        
        if not self.loop_mode or not self.current_file:
            return
        
        self.is_restarting = True
        
        try:
            self.media_ctrl.SetVolume(self.user_volume)
            
            seek_result = self.media_ctrl.Seek(0)
            wx.CallLater(50, self._complete_loop_restart)
                
        except Exception as e:
            self.is_restarting = False
            self._cleanup_after_failed_loop()
    
    def _complete_loop_restart(self):
        """Complete the loop restart after seek."""
        try:
            play_result = self.media_ctrl.Play()
            
            if play_result:
                self.is_playing = True
                self.is_paused = False
                self.pause_button.Enable(True)
                if not self.timer.IsRunning():
                    self.timer.Start(100)
            else:
                self.media_ctrl.Stop()
                wx.CallLater(100, self._reload_and_play)
                return
                
            self.is_restarting = False
                
        except Exception as e:
            self.is_restarting = False
            self._cleanup_after_failed_loop()
    
    def _reload_and_play(self):
        """Alternative restart method: reload the file."""
        try:
            self.media_ctrl.SetVolume(0.0)
            
            if self.media_ctrl.Load(self.current_file):
                self.media_ctrl.SetVolume(self.user_volume)
                wx.CallLater(100, self._play_after_reload)
            else:
                self.media_ctrl.SetVolume(self.user_volume)
                self.is_restarting = False
                self._cleanup_after_failed_loop()
                
        except Exception as e:
            self.media_ctrl.SetVolume(self.user_volume)
            self.is_restarting = False
            self._cleanup_after_failed_loop()
    
    def _play_after_reload(self):
        """Play after reloading the file."""
        try:
            self.media_ctrl.Seek(0)
            
            play_result = self.media_ctrl.Play()
            
            if play_result:
                self.is_playing = True
                self.is_paused = False
                self.pause_button.Enable(True)
                if not self.timer.IsRunning():
                    self.timer.Start(100)
            else:
                self._cleanup_after_failed_loop()
            
            self.is_restarting = False
            
        except Exception as e:
            self.is_restarting = False
            self._cleanup_after_failed_loop()
    
    def _cleanup_after_failed_loop(self):
        """Clean up state after a failed loop attempt."""
        self.loop_mode = False
        self.is_playing = False
        self.is_paused = False
        self.timer.Stop()
        self.pause_button.Enable(False)
    
    def clear(self):
        """Clear the current audio file."""
        self.stop()
        self.current_file = None
        self.pending_file = None
        self.is_loaded = False
        self.is_ready = False
        self.file_label.SetLabel("No audio file loaded")
        self.info_label.SetLabel("")
        self.play_button.Enable(False)
        self.play_loop_button.Enable(False)
        self.pause_button.Enable(False)
        self.stop_button.Enable(False)
        self.loop_mode = False
        self.is_restarting = False
        self.progress_slider.Enable(False)
        self.progress_slider.SetValue(0)
        self.progress_slider.SetMax(100)
        self.current_time_label.SetLabel("0:00")
        self.total_time_label.SetLabel("0:00")
    
    @staticmethod
    def _format_time(milliseconds):
        """Format milliseconds to MM:SS format."""
        seconds = milliseconds // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes}:{seconds:02d}"
    
    @staticmethod
    def _format_file_size(size_bytes):
        """Format file size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"