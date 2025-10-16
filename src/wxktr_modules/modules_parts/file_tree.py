import wx


class FileTreeCtrl(wx.TreeCtrl):
    """
    Tree control with checkboxes and status icons for file staging selection.
    """

    def __init__(self, parent):
        """Initializes the FileTreeCtrl."""
        super().__init__(parent, style=wx.TR_DEFAULT_STYLE | wx.TR_HIDE_ROOT)

        il = wx.ImageList(16, 16)
        self.checkbox_unchecked = il.Add(self._create_checkbox_bitmap(False))
        self.checkbox_checked = il.Add(self._create_checkbox_bitmap(True))
        self.icon_modified = il.Add(self._create_status_bitmap("M", wx.BLUE))
        self.icon_added = il.Add(self._create_status_bitmap("A", wx.Colour(0, 150, 0)))
        self.icon_deleted = il.Add(self._create_status_bitmap("D", wx.RED))
        self.icon_untracked = il.Add(self._create_status_bitmap("?", wx.Colour(128, 128, 128)))
        self.icon_conflict = il.Add(self._create_status_bitmap("!", wx.Colour(255, 128, 0)))
        self.AssignImageList(il)

        self.root = self.AddRoot("Root")
        self.checked_items = set()

        self.Bind(wx.EVT_LEFT_DOWN, self._on_left_down)

    def _create_checkbox_bitmap(self, checked: bool) -> wx.Bitmap:
        bmp = wx.Bitmap(16, 16)
        dc = wx.MemoryDC(bmp)
        dc.SetBackground(wx.Brush(wx.WHITE))
        dc.Clear()
        dc.SetPen(wx.Pen(wx.BLACK, 1))
        dc.SetBrush(wx.Brush(wx.WHITE))
        dc.DrawRectangle(2, 2, 12, 12)
        if checked:
            dc.SetPen(wx.Pen(wx.BLACK, 2))
            dc.DrawLine(4, 8, 7, 11)
            dc.DrawLine(7, 11, 12, 4)
        dc.SelectObject(wx.NullBitmap)
        return bmp

    def _create_status_bitmap(self, letter: str, color: wx.Colour) -> wx.Bitmap:
        bmp = wx.Bitmap(16, 16)
        dc = wx.MemoryDC(bmp)
        dc.SetBackground(wx.Brush(wx.WHITE))
        dc.Clear()
        dc.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        dc.SetTextForeground(color)
        dc.DrawText(letter, 3, 0)
        dc.SelectObject(wx.NullBitmap)
        return bmp

    def _on_left_down(self, event: wx.MouseEvent):
        item, flags = self.HitTest(event.GetPosition())
        if item.IsOk() and flags & wx.TREE_HITTEST_ONITEMICON:
            self._toggle_check(item)
        else:
            event.Skip()

    def _toggle_check(self, item: wx.TreeItemId):
        if item in self.checked_items:
            self.checked_items.remove(item)
            self.SetItemImage(item, self.checkbox_unchecked)
        else:
            self.checked_items.add(item)
            self.SetItemImage(item, self.checkbox_checked)

    def is_checked(self, item: wx.TreeItemId) -> bool:
        """Checks if a specific tree item is checked."""
        return item in self.checked_items

    def get_checked_files(self) -> list[str]:
        """Returns a list of file paths for all checked items."""
        files: list[str] = []
        for item in self.checked_items:
            path = self.GetItemData(item)
            if path:
                files.append(path)
        return files

    def clear_all_checks(self) -> None:
        """Unchecks all items in the tree."""
        for item in list(self.checked_items):
            self.SetItemImage(item, self.checkbox_unchecked)
        self.checked_items.clear()

    def populate(self, files: list[str], status_map: dict[str, str]) -> None:
        """Clears and repopulates the tree with a list of files and their statuses."""
        self.DeleteAllItems()
        self.root = self.AddRoot("Root")
        self.checked_items.clear()

        for filepath in sorted(files):
            status = status_map.get(filepath, "?")
            item = self.AppendItem(self.root, f"{filepath}  [{status}]")
            self.SetItemData(item, filepath)
            self.SetItemImage(item, self.checkbox_unchecked)

        self.ExpandAll()