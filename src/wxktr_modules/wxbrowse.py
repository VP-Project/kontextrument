#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import wx
import wx.html2
import os
import sys
from urllib.parse import urlparse, parse_qs, quote, unquote

from .settings_manager import get_settings_manager

HOME_URL = "about:home"
REMOVE_SCHEME = "app-remove-bookmark"

class BrowserPanel(wx.Panel):
    """A wx.Panel that provides a simple web browser using wx.html2.WebView."""
    def __init__(self, parent, *args, **kwargs):
        """Initializes the browser panel."""
        super(BrowserPanel, self).__init__(parent, *args, **kwargs)

        self.settings = get_settings_manager()
        
        self._initialize_ui()
        self._bind_events()
        self.first_load_done = False

    def _generate_homepage_html(self):
        """Generates the HTML for the homepage with bookmarks and remove buttons."""
        bookmarks = self.settings.get_browser_bookmarks()
        
        bookmarks_html = ""
        for name, url in bookmarks.items():
            encoded_name = quote(name)
            remove_link = f'{REMOVE_SCHEME}://remove?name={encoded_name}'
            bookmarks_html += f"""
            <div class='bookmark-item'>
                <a href='{url}' class='bookmark-link'>{name}</a>
                <a href='{remove_link}' class='remove-btn'>Remove</a>
            </div>
            """

        html_content = f"""
        <html>
        <head>
            <title>Home</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; margin: 40px; background-color: #f0f2f5; color: #333; }}
                h1 {{ color: #1c1e21; }}
                .bookmarks-list {{ list-style: none; padding: 0; max-width: 600px; margin: 20px auto; }}
                .bookmark-item {{ 
                    display: flex; 
                    align-items: stretch; 
                    justify-content: space-between; 
                    margin: 10px 0; 
                    background-color: #fff; 
                    border-radius: 8px; 
                    box-shadow: 0 1px 3px rgba(0,0,0,0.12);
                    overflow: hidden;
                }}
                .bookmark-link {{ 
                    text-decoration: none; 
                    color: #007bff; 
                    font-size: 1.1em;
                    padding: 15px;
                    display: flex;
                    align-items: center;
                    flex-grow: 1;
                    flex-shrink: 1;
                    min-width: 0;
                    transition: background-color 0.2s;
                }}
                .bookmark-link:hover {{ background-color: #f8f9fa; }}
                .remove-btn {{
                    text-decoration: none;
                    color: #dc3545;
                    font-size: 0.9em;
                    padding: 15px;
                    display: flex;
                    align-items: center;
                    flex-shrink: 0;
                    white-space: nowrap;
                    border-left: 1px solid #eee;
                    transition: background-color 0.2s;
                }}
                .remove-btn:hover {{ background-color: #f1f1f1; }}
            </style>
        </head>
        <body>
            <h1>Bookmarks</h1>
            <div class='bookmarks-list'>
                {bookmarks_html}
            </div>
        </body>
        </html>
        """
        return html_content

    def _initialize_ui(self):
        nav_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.back_btn = wx.Button(self, label="<")
        self.forward_btn = wx.Button(self, label=">")
        self.refresh_btn = wx.Button(self, label="⟳")
        self.home_btn = wx.Button(self, label="🏠")
        self.add_bookmark_btn = wx.Button(self, label="+🔖")
        self.url_bar = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        self.go_btn = wx.Button(self, label="Go")

        self.add_bookmark_btn.SetToolTip("Add current URL to bookmarks")

        nav_sizer.Add(self.back_btn, 0, wx.ALL, 2)
        nav_sizer.Add(self.forward_btn, 0, wx.ALL, 2)
        nav_sizer.Add(self.refresh_btn, 0, wx.ALL, 2)
        nav_sizer.Add(self.home_btn, 0, wx.ALL, 2)
        nav_sizer.Add(self.url_bar, 1, wx.ALL | wx.EXPAND, 2)
        nav_sizer.Add(self.add_bookmark_btn, 0, wx.ALL, 2)
        nav_sizer.Add(self.go_btn, 0, wx.ALL, 2)

        
        if wx.html2.WebView.IsBackendAvailable(wx.html2.WebViewBackendEdge):
            self.browser = wx.html2.WebView.New(self, backend=wx.html2.WebViewBackendEdge)
        else:
            self.browser = wx.html2.WebView.New(self)

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.Add(nav_sizer, 0, wx.EXPAND)
        main_sizer.Add(self.browser, 1, wx.EXPAND)
        self.SetSizer(main_sizer)

    def _bind_events(self):
        self.go_btn.Bind(wx.EVT_BUTTON, self.on_go)
        self.url_bar.Bind(wx.EVT_TEXT_ENTER, self.on_go)
        self.back_btn.Bind(wx.EVT_BUTTON, lambda evt: self.browser.GoBack())
        self.forward_btn.Bind(wx.EVT_BUTTON, lambda evt: self.browser.GoForward())
        self.refresh_btn.Bind(wx.EVT_BUTTON, self.on_refresh)
        self.home_btn.Bind(wx.EVT_BUTTON, self.on_home)
        self.add_bookmark_btn.Bind(wx.EVT_BUTTON, self.on_add_bookmark)
        
        self.browser.Bind(wx.html2.EVT_WEBVIEW_NAVIGATING, self.on_navigating)
        self.browser.Bind(wx.html2.EVT_WEBVIEW_NAVIGATED, self.on_navigated)
        self.browser.Bind(wx.html2.EVT_WEBVIEW_ERROR, self.on_error)

    def on_go(self, event):
        """Handles the 'Go' button click to load a URL."""
        url = self.url_bar.GetValue()
        self.load_url(url)
        
    def on_refresh(self, event):
        """Handles the 'Refresh' button click."""
        if self.url_bar.GetValue() == HOME_URL:
            self.load_url(HOME_URL)
        else:
            self.browser.Reload()

    def on_home(self, event):
        """Handles the 'Home' button click."""
        self.load_url(HOME_URL)

    def on_add_bookmark(self, event):
        """Adds the current URL to the bookmarks."""
        current_url = self.url_bar.GetValue()
        if not current_url or current_url == HOME_URL:
            wx.MessageBox("Cannot bookmark the homepage or an empty URL.", "Info", wx.OK | wx.ICON_INFORMATION)
            return

        dlg = wx.TextEntryDialog(self, "Enter a name for this bookmark:", "Add Bookmark", os.path.basename(current_url.strip('/')))
        if dlg.ShowModal() == wx.ID_OK:
            name = dlg.GetValue()
            if name:
                self._save_bookmark(name, current_url)
        dlg.Destroy()

    def _save_bookmark(self, name, url):
        """Saves a single bookmark using the settings manager."""
        self.settings.add_browser_bookmark(name, url)
        
        if self.url_bar.GetValue() == HOME_URL:
            self.load_url(HOME_URL)

    def on_navigating(self, event):
        """Event handler that fires before a URL is loaded."""
        url = event.GetURL()
        if url.startswith(f'{REMOVE_SCHEME}://'):
            event.Veto()
            parsed_url = urlparse(url)
            query = parse_qs(parsed_url.query)
            bookmark_name_encoded = query.get('name', [None])[0]
            if bookmark_name_encoded:
                bookmark_name = unquote(bookmark_name_encoded)
                self._remove_bookmark(bookmark_name)
        else:
            event.Skip()

    def _remove_bookmark(self, name):
        """Removes a bookmark and refreshes the homepage."""
        self.settings.remove_browser_bookmark(name)
        self.load_url(HOME_URL)

    def on_navigated(self, event):
        """Event handler that fires after a URL has been loaded."""
        current_url = event.GetURL()
        if not current_url.startswith(f'{REMOVE_SCHEME}://'):
             self.url_bar.SetValue(current_url)

    def on_error(self, event):
        """Event handler for WebView errors."""
        url = event.GetURL()
        if not url.startswith(f'{REMOVE_SCHEME}://'):
            wx.LogError(f"WebView Error: URL '{url}' could not be loaded.")

    def load_url(self, url):
        """Loads a given URL or the homepage."""
        if url == HOME_URL:
            html = self._generate_homepage_html()
            self.browser.SetPage(html, "")
            self.url_bar.SetValue(HOME_URL)
        else:
            if "://" not in url:
                url = f"https://{url}"
            self.browser.LoadURL(url)
            self.url_bar.SetValue(url)

    def load_last_session(self):
        """Loads the last URL from the settings manager."""
        url = self.settings.get_last_browser_url()
        self.load_url(url)

    def save_session(self):
        """Saves the current URL using the settings manager."""
        current_url = self.url_bar.GetValue()
        if not current_url:
            current_url = HOME_URL
        
        self.settings.set_last_browser_url(current_url)

    def handle_exit_request(self):
        """Called when the application is closing."""
        self.save_session()
        return True

    def on_panel_shown(self):
        """Load the last session when the panel is shown for the first time."""
        if not self.first_load_done:
            self.load_last_session()
            self.first_load_done = True

class BrowserFrame(wx.Frame):
    """A wx.Frame to host the BrowserPanel for standalone testing or use."""
    def __init__(self, *args, **kwargs):
        """Initializes the browser frame."""
        super(BrowserFrame, self).__init__(*args, **kwargs)

        self.SetTitle("AWPEB - A WxPython Embeddable Browser")
        self.SetSize((1000, 700))

        self.panel = BrowserPanel(self)
        self.Bind(wx.EVT_CLOSE, self.on_close)

    def on_close(self, event):
        """Handles the frame close event."""
        self.panel.save_session()
        self.Destroy()

    def load_initial_url(self, url=None):
        """Loads the initial URL for the browser."""
        if url:
            self.panel.load_url(url)
        else:
            self.panel.load_last_session()

class BrowserApp(wx.App):
    """A wx.App for running the BrowserFrame as a standalone application."""
    def __init__(self, url=None):
        """Initializes the browser app."""
        self.url = url
        super(BrowserApp, self).__init__()

    def OnInit(self):
        """Initializes the application and shows the frame."""
        from .settings_manager import SettingsManager
        self.SetAppName(SettingsManager.APP_NAME)
        self.SetVendorName(SettingsManager.VENDOR_NAME)

        frame = BrowserFrame(None)
        frame.load_initial_url(self.url)
        frame.Show()
        frame.panel.on_panel_shown()
        return True

if __name__ == "__main__":
    cli_url = sys.argv[1] if len(sys.argv) > 1 else None
    
    app = BrowserApp(url=cli_url)
    app.MainLoop()