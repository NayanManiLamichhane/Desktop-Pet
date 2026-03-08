import subprocess
import os
import webbrowser
import pyautogui
import time
from win32com.client import Dispatch

# App Map for common Windows applications
APP_MAP = {
    'chrome': 'chrome.exe',
    'firefox': 'firefox.exe',
    'spotify': 'spotify.exe',
    'notepad': 'notepad.exe',
    'vscode': 'code.exe',
    'discord': 'discord.exe',
    'explorer': 'explorer.exe',
    'calculator': 'calc.exe',
    'word': 'winword.exe',
    'excel': 'excel.exe'
}

# Cache for file searching
_file_cache = {}

def open_app(app_name):
    """Launch an application by name."""
    try:
        app_name_lower = app_name.lower()
        exe_name = APP_MAP.get(app_name_lower, app_name)
        
        # Try finding the path if it's not a common name in PATH
        subprocess.Popen(exe_name, shell=True)
        return f"Successfully launched {app_name}"
    except Exception as e:
        try:
            # Fallback if Popen fails
            os.startfile(app_name)
            return f"Successfully opened {app_name}"
        except Exception:
            return f"Failed to open {app_name}: {str(e)}"

def close_app(app_name):
    """Terminate an application by name."""
    try:
        app_name_lower = app_name.lower()
        exe_name = APP_MAP.get(app_name_lower, app_name)
        if not exe_name.endswith('.exe'):
            exe_name += '.exe'
            
        subprocess.run(['taskkill', '/IM', exe_name, '/F'], check=True, capture_output=True)
        return f"Closed {app_name}"
    except subprocess.CalledProcessError:
        return f"Could not find a running process for {app_name}"
    except Exception as e:
        return f"Error closing {app_name}: {str(e)}"

def scan_pc():
    """Scan Desktop, Documents, and Downloads for files and cache them."""
    global _file_cache
    user_profile = os.environ['USERPROFILE']
    folders = ['Desktop', 'Documents', 'Downloads']
    
    _file_cache = {}
    for folder in folders:
        path = os.path.join(user_profile, folder)
        if os.path.exists(path):
            for root, dirs, files in os.walk(path):
                for file in files:
                    # Store filename (lowercase for search) mapping to full path
                    _file_cache[file.lower()] = os.path.join(root, file)
    return _file_cache

def open_file(filename):
    """Search for a file in common folders and open it."""
    try:
        # First scan or refresh if empty
        if not _file_cache:
            scan_pc()
            
        filename_lower = filename.lower()
        
        # Exact match check
        if filename_lower in _file_cache:
            path = _file_cache[filename_lower]
            os.startfile(path)
            return f"Opening {os.path.basename(path)}"
            
        # Partial match check
        for name, path in _file_cache.items():
            if filename_lower in name:
                os.startfile(path)
                return f"Opening {os.path.basename(path)}"
                
        # If still not found, try a fresh scan once
        scan_pc()
        for name, path in _file_cache.items():
            if filename_lower in name:
                os.startfile(path)
                return f"Opening {os.path.basename(path)}"
                
        return f"Could not find a file named '{filename}' on your Desktop, Documents, or Downloads."
    except Exception as e:
        return f"Error opening file: {str(e)}"

def google_search(query):
    """Perform a Google search in the default browser."""
    try:
        webbrowser.open(f'https://google.com/search?q={query}')
        return f"Searching Google for '{query}'"
    except Exception as e:
        return f"Error performing search: {str(e)}"

def type_text(text):
    """Type text using keyboard simulation."""
    try:
        pyautogui.typewrite(text, interval=0.05)
        return f"Typed: {text}"
    except Exception as e:
        return f"Error typing text: {str(e)}"

def press_key(keys):
    """Press a hotkey combination (e.g., 'ctrl+c')."""
    try:
        # Split by '+' and strip whitespace
        key_list = [k.strip().lower() for k in keys.split('+')]
        pyautogui.hotkey(*key_list)
        return f"Pressed keys: {keys}"
    except Exception as e:
        return f"Error pressing keys: {str(e)}"
