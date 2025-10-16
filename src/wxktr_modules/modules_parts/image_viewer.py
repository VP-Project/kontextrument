import wx
import os

class ImageViewer(wx.Panel):
    """A panel that displays images with zoom and pan capabilities."""
    
    SUPPORTED_FORMATS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.tif', '.tiff', '.webp'}
    
    def __init__(self, parent):
        """Initializes the ImageViewer panel."""
        super().__init__(parent)
        self.current_image = None
        self.image_path = None
        self.zoom_level = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.dragging = False
        self.drag_start_x = 0
        self.drag_start_y = 0
        
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_SIZE, self.on_size)
        self.Bind(wx.EVT_MOUSEWHEEL, self.on_mouse_wheel)
        self.Bind(wx.EVT_LEFT_DOWN, self.on_left_down)
        self.Bind(wx.EVT_LEFT_UP, self.on_left_up)
        self.Bind(wx.EVT_MOTION, self.on_motion)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda evt: None)
    
    @classmethod
    def is_supported_image(cls, filepath):
        """Check if the file is a supported image format."""
        if not filepath:
            return False
        ext = os.path.splitext(filepath)[1].lower()
        return ext in cls.SUPPORTED_FORMATS
    
    def load_image(self, filepath):
        """Load an image from the specified file path."""
        self.image_path = filepath
        self.zoom_level = 1.0
        self.offset_x = 0
        self.offset_y = 0
        
        try:
            self.current_image = wx.Image(filepath, wx.BITMAP_TYPE_ANY)
            if not self.current_image.IsOk():
                self.current_image = None
                wx.MessageBox(f"Failed to load image: {filepath}", "Error", wx.ICON_ERROR)
            else:
                self.fit_to_window()
        except Exception as e:
            self.current_image = None
            wx.MessageBox(f"Error loading image: {e}", "Error", wx.ICON_ERROR)
        
        self.Refresh()
    
    def clear(self):
        """Clear the current image."""
        self.current_image = None
        self.image_path = None
        self.zoom_level = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.Refresh()
    
    def fit_to_window(self):
        """Adjust zoom level to fit image to window."""
        if not self.current_image:
            return
        
        window_width, window_height = self.GetSize()
        img_width = self.current_image.GetWidth()
        img_height = self.current_image.GetHeight()
        
        if img_width == 0 or img_height == 0 or window_width == 0 or window_height == 0:
            self.zoom_level = 1.0
            return
        
        zoom_width = window_width / img_width
        zoom_height = window_height / img_height
        
        self.zoom_level = min(zoom_width, zoom_height, 1.0)
        self.offset_x = 0
        self.offset_y = 0
        self.Refresh()
    
    def on_size(self, event):
        """Handle window resize events."""
        event.Skip()
        self.Refresh()
    
    def on_paint(self, event):
        """Handle paint events to draw the image."""
        dc = wx.AutoBufferedPaintDC(self)
        dc.Clear()
        
        if not self.current_image:
            dc.SetTextForeground(wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT))
            dc.DrawLabel("No image loaded", self.GetClientRect(), wx.ALIGN_CENTER)
            return
        
        window_width, window_height = self.GetSize()
        img_width = self.current_image.GetWidth()
        img_height = self.current_image.GetHeight()
        
        scaled_width = int(img_width * self.zoom_level)
        scaled_height = int(img_height * self.zoom_level)
        
        x = (window_width - scaled_width) // 2 + self.offset_x
        y = (window_height - scaled_height) // 2 + self.offset_y
        
        if scaled_width > 0 and scaled_height > 0:
            scaled_image = self.current_image.Scale(scaled_width, scaled_height, wx.IMAGE_QUALITY_HIGH)
            bitmap = wx.Bitmap(scaled_image)
            dc.DrawBitmap(bitmap, x, y, True)
        
        info_text = f"{os.path.basename(self.image_path)} | {img_width}x{img_height} | {int(self.zoom_level * 100)}%"
        dc.SetTextForeground(wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT))
        dc.DrawText(info_text, 10, 10)
    
    def on_mouse_wheel(self, event):
        """Handle mouse wheel events for zooming."""
        if not self.current_image:
            return
        
        delta = event.GetWheelRotation()
        zoom_factor = 1.1 if delta > 0 else 0.9
        
        old_zoom = self.zoom_level
        self.zoom_level = max(0.1, min(10.0, self.zoom_level * zoom_factor))
        
        mouse_x, mouse_y = event.GetPosition()
        window_width, window_height = self.GetSize()
        
        center_x = window_width // 2
        center_y = window_height // 2
        
        dx = mouse_x - center_x
        dy = mouse_y - center_y
        
        scale_change = self.zoom_level / old_zoom
        self.offset_x = int(self.offset_x * scale_change + dx * (1 - scale_change))
        self.offset_y = int(self.offset_y * scale_change + dy * (1 - scale_change))
        
        self.Refresh()
    
    def on_left_down(self, event):
        """Handle left mouse button down for panning."""
        if not self.current_image:
            return
        
        self.dragging = True
        self.drag_start_x = event.GetX()
        self.drag_start_y = event.GetY()
        self.SetCursor(wx.Cursor(wx.CURSOR_HAND))
    
    def on_left_up(self, event):
        """Handle left mouse button up."""
        self.dragging = False
        self.SetCursor(wx.Cursor(wx.CURSOR_ARROW))
    
    def on_motion(self, event):
        """Handle mouse motion for panning."""
        if not self.dragging or not self.current_image:
            return
        
        dx = event.GetX() - self.drag_start_x
        dy = event.GetY() - self.drag_start_y
        
        self.offset_x += dx
        self.offset_y += dy
        
        self.drag_start_x = event.GetX()
        self.drag_start_y = event.GetY()
        
        self.Refresh()
    
    def reset_view(self):
        """Reset zoom and pan to default."""
        if self.current_image:
            self.fit_to_window()
            self.Refresh()
    
    def zoom_in(self):
        """Zoom in by 10%."""
        if self.current_image:
            self.zoom_level = min(10.0, self.zoom_level * 1.1)
            self.Refresh()
    
    def zoom_out(self):
        """Zoom out by 10%."""
        if self.current_image:
            self.zoom_level = max(0.1, self.zoom_level * 0.9)
            self.Refresh()
    
    def actual_size(self):
        """Show image at 100% zoom."""
        if self.current_image:
            self.zoom_level = 1.0
            self.offset_x = 0
            self.offset_y = 0
            self.Refresh()