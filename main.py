import tkinter as tk
import threading
import requests
import subprocess
import webbrowser
import random
import math
import json
import speech_recognition as sr
import textwrap
import os
from datetime import datetime

# --- CONFIGURATION ---
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.2" # Default, overridden by logic below

class DesktopPet:
    def __init__(self):
        # Initialize all attributes to prevent AttributeError
        self.is_recording = False
        self.is_paused = False
        self.is_frozen = False
        self.freeze_btn = None
        self.pet_x = 100
        self.pet_y = 100
        self.target_x = 300
        self.target_y = 300
        self.anim_frame = 0
        self.drag_x = 0
        self.drag_y = 0
        self.chat_drag_x = 0
        self.chat_drag_y = 0
        self.chat_history = []
        self.chat_window = None
        self.context_menu_win = None
        self.context_menu = None
        self.menu_just_opened = False
        self.mic_btn = None
        
        self.chat_entry = None
        self.chat_display = None
        self.on_send = None
        
        self.root = tk.Tk()
        # Get TRUE screen dimensions
        self.screen_w = self.root.winfo_screenwidth()
        self.screen_h = self.root.winfo_screenheight()
        
        # Pet window size
        self.pet_w = 100
        self.pet_h = 100
        
        # TRUE boundaries pet can reach
        self.max_x = self.screen_w - self.pet_w
        self.max_y = self.screen_h - self.pet_h
        self.min_x = 0
        self.min_y = 0

        print(f'Screen: {self.screen_w}x{self.screen_h}')
        print(f'Max X: {self.max_x} Max Y: {self.max_y}')
        
        # --- ROOT WINDOW TRANSPARENCY FIX ---
        self.win_w, self.win_h = 100, 100
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        # Use #010101 for transparency (Tkinter click-through fix)
        self.bg_color = '#010101'
        self.root.config(bg=self.bg_color)
        self.root.wm_attributes("-transparentcolor", self.bg_color)
        
        # Canvas (must share the same bg color)
        self.canvas = tk.Canvas(self.root, width=self.win_w, height=self.win_h, bg=self.bg_color, highlightthickness=0)
        self.canvas.pack()
        
        # State
        self.pet_x, self.pet_y = self.screen_w // 2, self.screen_h // 2
        self.target_x, self.target_y = self.pet_x, self.pet_y
        self.is_dragging = False
        self.facing_right = True
        self.frame = 0
        self.blink_timer = 0
        self.is_blinking = False
        self.context_menu = None
        self.is_listening = False
        # self.is_paused already set above
        self.resume_after_id = None
        
        self.ai_timer_count = 0
        self.ai_timer_running = False
        self.chat_messages = []
        # self.chat_window already set above
        
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.stop_listening = None

        # Calibrate microphone ONCE at startup 
        # in background thread so it is instant later
        def calibrate():
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
        threading.Thread(target=calibrate, daemon=True).start()

        self.installed_apps = {}
        threading.Thread(target=self.scan_installed_apps, daemon=True).start()
        
        # --- UI COMPONENTS ---
        self.create_widgets()
        
        # Exact Drag Variables
        self._drag_x = 0
        self._drag_y = 0
        self.shape_ids = {} # Persistent shape IDs for performance
        
        # Bind dragging to ROOT directly
        self.root.bind('<ButtonPress-1>', self.drag_start, add='+')
        self.root.bind('<B1-Motion>', self.drag_move, add='+')
        self.root.bind('<ButtonRelease-1>', self.drag_end, add='+')

        self.draw_pet()
        self.move_pet()
        self.check_ollama_startup()
        self.root.mainloop()

    def create_widgets(self):
        # Create hidden context menu once on startup for instant display
        self._create_context_menu()

    def start_process_command(self, text):
        if not text: return
        
        # Try direct command detection first (Layer 1)
        result = self.detect_command(text)
        if result:
            self.root.after(0, self.append_chat, 'Pet', result)
            return

        # No command found, ask AI (Layer 2)
        self.ai_timer_count = 0
        self.ai_timer_running = True
        self.update_thinking_timer()
        threading.Thread(target=self._ai_task, args=(text,), daemon=True).start()

    def scan_installed_apps(self):
        import glob
        import winreg
        
        apps = {}
        
        # Scan Program Files folders
        search_paths = [
            'C:/Program Files/**/*.exe',
            'C:/Program Files (x86)/**/*.exe',
            f'C:/Users/{os.getenv("USERNAME")}/AppData/Local/**/*.exe',
            f'C:/Users/{os.getenv("USERNAME")}/AppData/Roaming/**/*.exe',
        ]
        
        for pattern in search_paths:
            try:
                for exe in glob.glob(pattern, recursive=True):
                    name = os.path.basename(exe)
                    name_clean = name.replace('.exe','').lower()
                    apps[name_clean] = exe
            except:
                pass
        
        # Scan Windows Registry for installed apps
        reg_paths = [
            r'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths',
            r'SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths',
        ]
        
        for reg_path in reg_paths:
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path)
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        sub_name = winreg.EnumKey(key, i)
                        sub_key = winreg.OpenKey(key, sub_name)
                        path = winreg.QueryValue(sub_key, '')
                        clean = sub_name.replace('.exe','').lower()
                        apps[clean] = path
                    except:
                        pass
            except:
                pass
        
        # Add common app aliases manually
        aliases = {
            'chrome': 'chrome',
            'google chrome': 'chrome',
            'firefox': 'firefox',
            'mozilla': 'firefox',
            'edge': 'msedge',
            'microsoft edge': 'msedge',
            'notepad': 'notepad',
            'notepad++': 'notepad++',
            'calculator': 'calc',
            'calc': 'calc',
            'spotify': 'spotify',
            'discord': 'discord',
            'vscode': 'code',
            'visual studio code': 'code',
            'vs code': 'code',
            'word': 'winword',
            'microsoft word': 'winword',
            'excel': 'excel',
            'microsoft excel': 'excel',
            'powerpoint': 'powerpnt',
            'teams': 'teams',
            'microsoft teams': 'teams',
            'zoom': 'zoom',
            'vlc': 'vlc',
            'steam': 'steam',
            'obs': 'obs64',
            'paint': 'mspaint',
            'task manager': 'taskmgr',
            'file explorer': 'explorer',
            'explorer': 'explorer',
            'cmd': 'cmd',
            'command prompt': 'cmd',
            'powershell': 'powershell',
            'whatsapp': 'whatsapp',
            'telegram': 'telegram',
            'skype': 'skype',
            'blender': 'blender',
            'photoshop': 'photoshop',
            'premiere': 'premiere',
            'illustrator': 'illustrator',
            'postman': 'postman',
            'figma': 'figma',
            'slack': 'slack',
            'notion': 'notion',
            'cursor': 'cursor',
            'pycharm': 'pycharm64',
            'intellij': 'idea64',
            'android studio': 'studio64',
        }
        
        self.installed_apps = {**apps, **aliases}
        print(f'Scanned {len(apps)} apps!')

    def find_app(self, app_name):
        name = app_name.lower().strip()
        
        # Direct match
        if name in self.installed_apps:
            return self.installed_apps[name]
        
        # Partial match
        for key, path in self.installed_apps.items():
            if name in key or key in name:
                return path
        
        # Fallback: just try running the name directly
        return name

    def open_app(self, app_name):
        try:
            path = self.find_app(app_name)
            
            # Try full path first
            if os.path.exists(path):
                subprocess.Popen(
                    path,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                return True
            
            # Try with start command
            subprocess.Popen(
                f'start "" "{path}"',
                shell=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return True
        except:
            try:
                # Last resort - use os.startfile
                os.startfile(app_name)
                return True
            except:
                return False

    def close_app(self, app_name):
        name = app_name.lower().strip()
        
        # Build exe name variations to try
        exe_variations = [
            f'{name}.exe',
            f'{name}64.exe',
            f'{name}32.exe',
        ]
        
        # Common app to exe mappings
        close_map = {
            'chrome': 'chrome.exe',
            'google chrome': 'chrome.exe',
            'firefox': 'firefox.exe',
            'edge': 'msedge.exe',
            'microsoft edge': 'msedge.exe',
            'spotify': 'spotify.exe',
            'discord': 'discord.exe',
            'vscode': 'code.exe',
            'vs code': 'code.exe',
            'visual studio code': 'code.exe',
            'notepad': 'notepad.exe',
            'notepad++': 'notepad++.exe',
            'calculator': 'calculatorapp.exe',
            'word': 'winword.exe',
            'excel': 'excel.exe',
            'powerpoint': 'powerpnt.exe',
            'teams': 'teams.exe',
            'zoom': 'zoom.exe',
            'vlc': 'vlc.exe',
            'steam': 'steam.exe',
            'obs': 'obs64.exe',
            'paint': 'mspaint.exe',
            'explorer': 'explorer.exe',
            'whatsapp': 'whatsapp.exe',
            'telegram': 'telegram.exe',
            'slack': 'slack.exe',
            'skype': 'skype.exe',
            'pycharm': 'pycharm64.exe',
            'cursor': 'cursor.exe',
            'postman': 'postman.exe',
            'figma': 'figma.exe',
        }
        
        # Direct map match
        if name in close_map:
            exe = close_map[name]
            subprocess.run(
                f'taskkill /IM {exe} /F',
                shell=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return True
        
        # Try variations
        for exe in exe_variations:
            try:
                result = subprocess.run(
                    f'taskkill /IM {exe} /F',
                    shell=True,
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                if result.returncode == 0:
                    return True
            except:
                pass
        
        # Last resort - find process by name
        try:
            subprocess.run(
                f'taskkill /FI "WINDOWTITLE eq *{name}*" /F',
                shell=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return True
        except:
            return False

    def detect_command(self, text):
        text_lower = text.lower().strip()
        
        close_keywords = [
            'close ', 'quit ', 'exit ', 
            'kill ', 'shut ', 'stop '
        ]
        
        open_keywords = [
            'open ', 'launch ', 'start ', 
            'go to ', 'visit ', 'browse '
        ]
        
        # ✅ CHECK CLOSE FIRST always
        for keyword in close_keywords:
            if keyword in text_lower:
                app_name = text_lower.split(keyword)[-1].strip()
                
                # Check if closing a browser directly
                common_browsers = {
                    'chrome': 'chrome.exe',
                    'firefox': 'firefox.exe',
                    'edge': 'msedge.exe',
                    'opera': 'opera.exe',
                    'brave': 'brave.exe',
                }
                for browser, exe in common_browsers.items():
                    if browser in app_name:
                        subprocess.run(
                            f'taskkill /IM {exe} /F',
                            shell=True,
                            creationflags=subprocess.CREATE_NO_WINDOW
                        )
                        return f'Closed {browser}!'
                
                # Check if closing a website tab
                common_sites_close = {
                    'youtube': 'chrome.exe',
                    'google': 'chrome.exe',
                    'facebook': 'chrome.exe',
                    'instagram': 'chrome.exe',
                    'netflix': 'chrome.exe',
                    'whatsapp': 'chrome.exe',
                    'twitter': 'chrome.exe',
                    'reddit': 'chrome.exe',
                }
                for site in common_sites_close.keys():
                    if site in app_name:
                        import pyautogui
                        pyautogui.hotkey('ctrl', 'w')
                        return f'Closed {site} tab!'
                
                success = self.close_app(app_name)
                if success:
                    return f'Closed {app_name}!'
                else:
                    return f'Could not find {app_name} running!'

        # Search detection
        search_triggers = ['search ', 'google ', 'look up ', 'find ']
        for trigger in search_triggers:
            if trigger in text_lower:
                query = text_lower.split(trigger)[-1].strip()
                if query:
                    webbrowser.open(f'https://google.com/search?q={query}')
                    return f"Searching for {query}!"
        
        # ✅ THEN CHECK OPEN after close is ruled out
        for keyword in open_keywords:
            if keyword in text_lower:
                app_name = text_lower.split(keyword)[-1].strip()
                
                # Check websites first
                common_sites = {
                    'youtube': 'https://youtube.com',
                    'google': 'https://google.com',
                    'facebook': 'https://facebook.com',
                    'instagram': 'https://instagram.com',
                    'twitter': 'https://twitter.com',
                    'x': 'https://x.com',
                    'github': 'https://github.com',
                    'reddit': 'https://reddit.com',
                    'netflix': 'https://netflix.com',
                    'amazon': 'https://amazon.com',
                    'whatsapp': 'https://web.whatsapp.com',
                    'gmail': 'https://gmail.com',
                    'chatgpt': 'https://chat.openai.com',
                    'claude': 'https://claude.ai',
                    'linkedin': 'https://linkedin.com',
                    'spotify': 'https://open.spotify.com',
                    'twitch': 'https://twitch.tv',
                }
                
                for site, url in common_sites.items():
                    if site in app_name:
                        webbrowser.open(url)
                        return f'Opening {site}!'
                
                # Check if its a URL
                if any(x in app_name for x in ['.com','.org','.net','.io','www.']):
                    url = app_name
                    if not url.startswith('http'):
                        url = 'https://' + url
                    webbrowser.open(url)
                    return f'Opening {url}!'
                
                # Try opening as app
                success = self.open_app(app_name)
                if success:
                    return f'Opening {app_name}!'
                else:
                    return f'Could not find {app_name}!'
        
        # No command detected - send to AI
        return None

    # --- CHAT WINDOW ---
    def get_smart_position(self):
        pet_x = self.root.winfo_x()
        pet_y = self.root.winfo_y()
        win_w = 300
        win_h = 400
        
        # Try LEFT of pet first
        x = pet_x - win_w - 10
        y = pet_y
        
        # If goes off LEFT edge, place RIGHT of pet
        if x < 0:
            x = pet_x + 110
        
        # If goes off RIGHT edge, center on screen
        if x + win_w > self.screen_w:
            x = (self.screen_w - win_w) // 2
        
        # If goes off BOTTOM edge, move up
        if y + win_h > self.screen_h:
            y = self.screen_h - win_h - 20
        
        # If goes off TOP edge, place at top
        if y < 0:
            y = 20
        
        return x, y

    def append_chat(self, sender, text):
        self.chat_messages.append((sender, text))
        self.show_chat_window()
        if self.chat_display:
            # Remove thinking temp message if exists
            try:
                self.chat_display.delete('temp.first', 'temp.last')
            except tk.TclError:
                pass
                
            tag = 'user' if sender == 'User' else 'pet'
            self.chat_display.insert('end', f"{sender}: ", tag)
            self.chat_display.insert('end', f"{text}\n\n")
            self.chat_display.see('end')

    def show_chat_window(self):
        self.is_paused = True
        if self.resume_after_id:
            self.root.after_cancel(self.resume_after_id)
            self.resume_after_id = None
            
        if self.chat_window and self.chat_window.winfo_exists():
            self.chat_window.lift()
            self.chat_entry.focus()
            return
            
        self.chat_window = tk.Toplevel(self.root)
        self.chat_window.overrideredirect(True)
        self.chat_window.attributes('-topmost', True)
        self.chat_window.configure(bg='#0a0a0f', highlightbackground='#6c63ff', highlightthickness=1)
        
        x, y = self.get_smart_position()
        self.chat_window.geometry(f'300x400+{x}+{y}')
        
        # Header (Top)
        header = tk.Frame(self.chat_window, bg='#0a0a0f')
        header.pack(side='top', fill='x')
        title_label = tk.Label(header, text="🐾 Pet Assistant", bg='#0a0a0f', fg='#e0e0ff', font=('Segoe UI', 10, 'bold'))
        title_label.pack(side='left', padx=10, pady=5)
        tk.Button(header, text='✕', bg='#ff4757', fg='white', bd=0, command=self.close_chat_window, cursor='hand2').pack(side='right', padx=5)
        
        header.bind('<ButtonPress-1>', self.chat_drag_start)
        header.bind('<B1-Motion>', self.chat_drag_move)
        title_label.bind('<ButtonPress-1>', self.chat_drag_start)
        title_label.bind('<B1-Motion>', self.chat_drag_move)
        
        # Input area (Bottom)
        bottom_frame = tk.Frame(self.chat_window, bg='#0a0a0f', height=50)
        bottom_frame.pack_propagate(False) # Force the fixed height
        bottom_frame.pack(side='bottom', fill='x', padx=5, pady=5)
        
        entry_frame = tk.Frame(bottom_frame, bg='#6c63ff', padx=1, pady=1)
        entry_frame.pack(side='left', fill='both', expand=True, padx=(0,5))
        
        self.chat_entry = tk.Entry(entry_frame, bg='#0a0a0f', fg='#e0e0ff', font=('Segoe UI', 11), insertbackground='#e0e0ff', relief='flat')
        self.chat_entry.pack(fill='both', expand=True, ipady=5, padx=2)
        
        def _handle_send(event=None):
            if not self.chat_window: return
            text = self.chat_entry.get().strip()
            if text:
                self.chat_entry.delete(0, 'end')
                self.append_chat('User', text)
                self.start_process_command(text)
                self.chat_entry.focus() 
                
        self.chat_entry.bind('<Return>', _handle_send)
        self.on_send = _handle_send # Store for voice reference
        
        self.mic_btn = tk.Button(bottom_frame, text='🎤', bg='#555555', fg='white', bd=0, font=('Segoe UI', 12), cursor='hand2', command=self.toggle_voice)
        self.mic_btn.pack(side='left', padx=(5,2))

        send_btn = tk.Button(bottom_frame, text='➤', bg='#6c63ff', fg='white', bd=0, font=('Segoe UI', 12), cursor='hand2', command=_handle_send)
        send_btn.pack(side='left')

        # Chat display (Middle) - fills remaining space above bottom frame
        self.chat_display = tk.Text(self.chat_window, bg='#0a0a0f', fg='#e0e0ff', font=('Segoe UI', 10), wrap='word', bd=0, padx=10, pady=10)
        self.chat_display.pack(side='top', fill='both', expand=True)
        
        self.chat_display.tag_config('user', foreground='#2ed573', font=('Segoe UI', 10, 'bold'))
        self.chat_display.tag_config('pet', foreground='#c9b8ff', font=('Segoe UI', 10, 'bold'))
        self.chat_display.tag_config('temp', foreground='#aaaaaa', font=('Segoe UI', 9, 'italic'))
        
        def block_typing(event):
            if event.state & 4 and event.keysym.lower() == 'c': return None
            if event.keysym in ('Left', 'Right', 'Up', 'Down', 'Prior', 'Next', 'Home', 'End'): return None
            return 'break'
        self.chat_display.bind('<Key>', block_typing)
        
        for sender, msg in self.chat_messages:
            tag = 'user' if sender == 'User' else 'pet'
            self.chat_display.insert('end', f"{sender}: ", tag)
            self.chat_display.insert('end', f"{msg}\n\n")
        self.chat_display.see('end')

        self.chat_entry.focus()

    def close_chat_window(self):
        if self.chat_window:
            self.chat_window.destroy()
            self.chat_window = None
            self.chat_display = None
        if not self.is_dragging and not self.is_listening and not self.is_frozen:
            if self.resume_after_id: self.root.after_cancel(self.resume_after_id)
            self.resume_after_id = self.root.after(100, self.resume_movement)

    def chat_drag_start(self, event):
        self.chat_drag_x = event.x_root - self.chat_window.winfo_x()
        self.chat_drag_y = event.y_root - self.chat_window.winfo_y()

    def chat_drag_move(self, event):
        new_x = event.x_root - self.chat_drag_x
        new_y = event.y_root - self.chat_drag_y
        
        # Clamp to screen bounds
        new_x = max(0, min(new_x, self.screen_w - 300))
        new_y = max(0, min(new_y, self.screen_h - 400))
        
        self.chat_window.geometry(f'300x400+{new_x}+{new_y}')

    # --- CONTEXT MENU ---
    def toggle_freeze(self):
        self.is_frozen = not self.is_frozen
        
        if self.is_frozen:
            self.is_paused = True
            # Show pin on pet
            self.canvas.create_text(
                88, 14,
                text='📌',
                font=('Arial', 12),
                tags='pin_icon'
            )
            # Update menu label
            if self.freeze_btn:
                self.freeze_btn.config(text='📌 Unfreeze Pet')
        else:
            self.is_paused = False
            # Remove pin from pet
            self.canvas.delete('pin_icon')
            # Update menu label
            if self.freeze_btn:
                self.freeze_btn.config(text='📌 Freeze Pet')

    def _create_context_menu(self):
        self.context_menu = tk.Toplevel(self.root)
        self.context_menu.overrideredirect(True)
        self.context_menu.attributes('-topmost', True)
        self.context_menu.configure(bg='#0a0a0f', highlightbackground='#6c63ff', highlightthickness=1)
        self.context_menu.withdraw() # Hide immediately
        
        # Add bindings to close context menu when clicking outside
        self.root.bind('<ButtonPress-1>', lambda e: None if self.menu_just_opened else self.close_context_menu(), add='+')
        self.root.bind('<ButtonPress-3>', lambda e: self.show_context_menu(e), add='+')
        self.context_menu.bind('<FocusOut>', lambda e: self.close_context_menu())
        self.context_menu.bind('<Escape>', lambda e: self.close_context_menu())
        self.root.bind('<Escape>', lambda e: self.close_context_menu())
        self.canvas.bind('<ButtonPress-1>', lambda e: self.close_context_menu(), add='+')
        
        items = [
            ('📌 Freeze Pet', self.toggle_freeze),
            ('🔍 Search & Chat', self.show_chat_window),
            ('⏻   Quit', self.root.destroy)
        ]
        
        for label, command in items:
            def handler(cmd=command):
                self.close_context_menu()
                cmd()
                
            btn = tk.Button(
                self.context_menu,
                text=label,
                bg='#0a0a0f',
                fg='#e0e0ff',
                font=('Segoe UI', 11),
                relief='flat',
                anchor='w',
                padx=15,
                cursor='hand2',
                activebackground='#1a1a2e',
                activeforeground='#c9b8ff',
                bd=0,
                width=18,
                command=handler
            )
            btn.pack(fill='x', ipady=10)
            if 'Freeze' in label:
                self.freeze_btn = btn
            
            btn.bind('<Enter>', lambda e, b=btn: b.config(bg='#1a1a2e'))
            btn.bind('<Leave>', lambda e, b=btn: b.config(bg='#0a0a0f'))

    def show_context_menu(self, event):
        self.menu_just_opened = True
        # Stop pet from moving while menu is open
        self.is_paused = True
        if self.resume_after_id:
            self.root.after_cancel(self.resume_after_id)
            self.resume_after_id = None
            
        mx, my = event.x_root, event.y_root
        self.context_menu.geometry(f'190x138+{mx}+{my}')
        self.context_menu.deiconify()
        self.context_menu.lift()
        self.context_menu.focus_force()
        
        # Reset flag after 200ms
        self.root.after(200, self._reset_menu_flag)
        return "break"

    def _reset_menu_flag(self):
        self.menu_just_opened = False

    def close_context_menu(self):
        if self.menu_just_opened:
            return  # dont close if just opened
        try:
            if self.context_menu and self.context_menu.winfo_exists():
                was_open = self.context_menu.winfo_ismapped()
                self.context_menu.withdraw()
                # Resume movement when closed
                if was_open and not self.chat_window and not self.is_listening and not self.is_dragging and not self.is_frozen:
                    if self.resume_after_id: self.root.after_cancel(self.resume_after_id)
                    self.resume_after_id = self.root.after(100, self.resume_movement)
        except:
            pass

    # --- PET DESIGN & CLICK BINDING ---
    def draw_pet(self):
        cx, cy = 50, 50
        bob = math.sin(self.frame * 0.1) * 2.5
        curr_y = cy + bob
        look = 4.5 if self.facing_right else -4.5
        ear_wobble = math.sin(self.frame * 0.15) * 2 if not self.is_paused else 0
        
        # Blinking logic (blink every ~150 frames, blink lasts 5 frames)
        if random.random() < 0.01 and not self.is_blinking:
            self.is_blinking = True
            self.blink_timer = 5
        elif self.is_blinking:
            self.blink_timer -= 1
            if self.blink_timer <= 0:
                self.is_blinking = False

        # First run: Create shapes and bind events
        if not self.shape_ids:
            # 1. Shadow
            self.shape_ids['shadow'] = self.canvas.create_oval(0,0,0,0, fill="#040404", outline="", stipple="gray50")
            # 2. Body & Ears
            self.shape_ids['l_ear'] = self.canvas.create_oval(0,0,0,0, fill="#c9b8ff", outline="#6c63ff", width=1.5)
            self.shape_ids['r_ear'] = self.canvas.create_oval(0,0,0,0, fill="#c9b8ff", outline="#6c63ff", width=1.5)
            self.shape_ids['l_inner'] = self.canvas.create_oval(0,0,0,0, fill="#ffb3c6", outline="")
            self.shape_ids['r_inner'] = self.canvas.create_oval(0,0,0,0, fill="#ffb3c6", outline="")
            self.shape_ids['body'] = self.canvas.create_oval(0,0,0,0, fill="#c9b8ff", outline="#6c63ff", width=1.5)
            self.shape_ids['hint'] = self.canvas.create_oval(0,0,0,0, fill="#e6dbff", outline="")
            self.shape_ids['l_cheek'] = self.canvas.create_oval(0,0,0,0, fill="#ff9ebd", outline="", stipple="gray50")
            self.shape_ids['r_cheek'] = self.canvas.create_oval(0,0,0,0, fill="#ff9ebd", outline="", stipple="gray50")
            self.shape_ids['l_eye'] = self.canvas.create_oval(0,0,0,0, fill="#fefefe", outline="#6c63ff", width=1.5)
            self.shape_ids['r_eye'] = self.canvas.create_oval(0,0,0,0, fill="#fefefe", outline="#6c63ff", width=1.5)
            self.shape_ids['l_pupil'] = self.canvas.create_oval(0,0,0,0, fill="#2d1b69", outline="")
            self.shape_ids['r_pupil'] = self.canvas.create_oval(0,0,0,0, fill="#2d1b69", outline="")
            self.shape_ids['l_s1'] = self.canvas.create_oval(0,0,0,0, fill="#ffffff", outline="")
            self.shape_ids['l_s2'] = self.canvas.create_oval(0,0,0,0, fill="#ffffff", outline="")
            self.shape_ids['r_s1'] = self.canvas.create_oval(0,0,0,0, fill="#ffffff", outline="")
            self.shape_ids['r_s2'] = self.canvas.create_oval(0,0,0,0, fill="#ffffff", outline="")
            self.shape_ids['l_blink'] = self.canvas.create_arc(0,0,0,0, start=0, extent=180, style='arc', outline="#2d1b69", width=2)
            self.shape_ids['r_blink'] = self.canvas.create_arc(0,0,0,0, start=0, extent=180, style='arc', outline="#2d1b69", width=2)
            self.shape_ids['nose'] = self.canvas.create_oval(0,0,0,0, fill="#ff9ebd", outline="")
            self.shape_ids['mouth'] = self.canvas.create_arc(0,0,0,0, start=180, extent=180, style='arc', outline="#2d1b69", width=1.5)
            self.shape_ids['pause'] = self.canvas.create_text(0,0, text="⏸", fill="#6c63ff", font=("Arial", 10, "bold"))

            # One-time bindings for all shapes
            for sid in self.shape_ids.values():
                self.canvas.tag_bind(sid, '<ButtonPress-1>', self.drag_start)
                self.canvas.tag_bind(sid, '<B1-Motion>', self.drag_move)
                self.canvas.tag_bind(sid, '<ButtonRelease-1>', self.drag_end)
                self.canvas.tag_bind(sid, '<ButtonPress-3>', self.show_context_menu)

        # Update Shapes
        self.canvas.coords(self.shape_ids['shadow'], cx-30, cy+30, cx+30, cy+41)
        self.canvas.coords(self.shape_ids['l_ear'], cx-30+look, curr_y-30+ear_wobble, cx-10+look, curr_y-7+ear_wobble)
        self.canvas.coords(self.shape_ids['r_ear'], cx+10+look, curr_y-30-ear_wobble, cx+30+look, curr_y-7-ear_wobble)
        self.canvas.coords(self.shape_ids['l_inner'], cx-25+look, curr_y-25+ear_wobble, cx-15+look, curr_y-12+ear_wobble)
        self.canvas.coords(self.shape_ids['r_inner'], cx+15+look, curr_y-25-ear_wobble, cx+25+look, curr_y-12-ear_wobble)
        self.canvas.coords(self.shape_ids['body'], cx-37, curr_y-30, cx+37, curr_y+30)
        self.canvas.coords(self.shape_ids['hint'], cx-27, curr_y-23, cx-10, curr_y-7)
        self.canvas.coords(self.shape_ids['l_cheek'], cx-27+look, curr_y+3, cx-13+look, curr_y+10)
        self.canvas.coords(self.shape_ids['r_cheek'], cx+13+look, curr_y+3, cx+27+look, curr_y+10)
        self.canvas.coords(self.shape_ids['nose'], cx-1+look, curr_y+4, cx+1+look, curr_y+6)
        self.canvas.coords(self.shape_ids['mouth'], cx-4+look, curr_y+7, cx+4+look, curr_y+12)
        
        # Eyes/Blink logic
        eye_state = 'hidden' if self.is_blinking else 'normal'
        blink_state = 'normal' if self.is_blinking else 'hidden'
        
        self.canvas.itemconfig(self.shape_ids['l_eye'], state=eye_state)
        self.canvas.itemconfig(self.shape_ids['r_eye'], state=eye_state)
        self.canvas.itemconfig(self.shape_ids['l_pupil'], state=eye_state)
        self.canvas.itemconfig(self.shape_ids['r_pupil'], state=eye_state)
        self.canvas.itemconfig(self.shape_ids['l_s1'], state=eye_state)
        self.canvas.itemconfig(self.shape_ids['l_s2'], state=eye_state)
        self.canvas.itemconfig(self.shape_ids['r_s1'], state=eye_state)
        self.canvas.itemconfig(self.shape_ids['r_s2'], state=eye_state)
        self.canvas.itemconfig(self.shape_ids['l_blink'], state=blink_state)
        self.canvas.itemconfig(self.shape_ids['r_blink'], state=blink_state)

        if not self.is_blinking:
            self.canvas.coords(self.shape_ids['l_eye'], cx-19+look, curr_y-10, cx-3+look, curr_y+8)
            self.canvas.coords(self.shape_ids['r_eye'], cx+3+look, curr_y-10, cx+19+look, curr_y+8)
            self.canvas.coords(self.shape_ids['l_pupil'], cx-15+look, curr_y-7, cx-6+look, curr_y+5)
            self.canvas.coords(self.shape_ids['r_pupil'], cx+6+look, curr_y-7, cx+15+look, curr_y+5)
            self.canvas.coords(self.shape_ids['l_s1'], cx-15+look, curr_y-5, cx-10+look, curr_y-1)
            self.canvas.coords(self.shape_ids['l_s2'], cx-9+look, curr_y+1, cx-7+look, curr_y+3)
            self.canvas.coords(self.shape_ids['r_s1'], cx+7+look, curr_y-5, cx+11+look, curr_y-1)
            self.canvas.coords(self.shape_ids['r_s2'], cx+12+look, curr_y+1, cx+14+look, curr_y+3)
        else:
            self.canvas.coords(self.shape_ids['l_blink'], cx-17+look, curr_y-7, cx-3+look, curr_y+3)
            self.canvas.coords(self.shape_ids['r_blink'], cx+3+look, curr_y-7, cx+17+look, curr_y+3)

        pause_state = 'normal' if self.is_paused else 'hidden'
        self.canvas.itemconfig(self.shape_ids['pause'], state=pause_state)
        if self.is_paused:
            self.canvas.coords(self.shape_ids['pause'], cx+33, curr_y-23)

    def pick_new_target(self):
        self.target_x = random.randint(self.min_x, self.max_x)
        self.target_y = random.randint(self.min_y, self.max_y)

    # --- MOVEMENT LOOP ---
    def move_pet(self):
        self.frame += 1
        if not self.is_dragging and not self.is_paused and not self.is_frozen:
            # Move towards target
            dx, dy = self.target_x - self.pet_x, self.target_y - self.pet_y
            dist = (dx**2 + dy**2)**0.5
            if dist > 3:
                self.pet_x += (dx / dist) * 3
                self.pet_y += (dy / dist) * 3
                self.facing_right = dx > 0
            else:
                if self.frame % 150 == 0:
                    self.pick_new_target()

        # Apply movement
        # Ensure coordinates are within screen bounds
        self.pet_x = max(self.min_x, min(self.pet_x, self.max_x))
        self.pet_y = max(self.min_y, min(self.pet_y, self.max_y))
        
        self.root.geometry(f"{self.pet_w}x{self.pet_h}+{int(self.pet_x)}+{int(self.pet_y)}")
        self.draw_pet()

        self.root.after(40, self.move_pet)

    # --- INPUT HANDLERS ---
    # --- EXACT DRAG HANDLERS ---
    def drag_start(self, event):
        self.close_context_menu()
        self.is_paused = True
        self._drag_x = event.x_root - self.root.winfo_x()
        self._drag_y = event.y_root - self.root.winfo_y()
        
        if self.resume_after_id: self.root.after_cancel(self.resume_after_id)
        if not self.is_frozen:
            self.resume_after_id = self.root.after(5000, self.resume_movement)

    def drag_move(self, event):
        self.is_dragging = True
        self.is_paused = True
        self.pet_x = event.x_root - self._drag_x
        self.pet_y = event.y_root - self._drag_y
        
        # Clamp to screen bounds
        self.pet_x = max(self.min_x, min(self.pet_x, self.max_x))
        self.pet_y = max(self.min_y, min(self.pet_y, self.max_y))
        
        self.root.geometry(f'{self.pet_w}x{self.pet_h}+{int(self.pet_x)}+{int(self.pet_y)}')

    def drag_end(self, event):
        self.is_dragging = False
        if not self.is_frozen:
            self.is_paused = False
            if self.resume_after_id: self.root.after_cancel(self.resume_after_id)
            self.resume_after_id = self.root.after(3000, self.resume_movement)

    def resume_movement(self):
        if not self.is_frozen:
            self.is_paused = False
        self.resume_after_id = None

    # --- UI ACTIONS DELETED ---
    # show_search_input has been replaced by show_chat_window

    # --- AI & VOICE ---
    def toggle_voice(self):
        if self.is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        self.is_recording = True
        self.mic_btn.config(bg='#ff4757', text='⏹')
        self.append_chat('Pet', 'Listening...')
        
        # Use listen_in_background for continuous recording
        self.stop_listening = self.recognizer.listen_in_background(
            self.microphone,
            self.on_speech_detected,
            phrase_time_limit=5
        )

    def stop_recording(self):
        self.is_recording = False
        self.mic_btn.config(bg='#555555', text='🎤')
        
        # Stop background listener
        if self.stop_listening:
            self.stop_listening(wait_for_stop=False)
            self.stop_listening = None

    def on_speech_detected(self, recognizer, audio):
        # This runs in background thread automatically
        try:
            text = recognizer.recognize_google(audio)
            if text and self.is_recording:
                # Append to input box simultaneously
                self.root.after(0, self.append_voice_text, text)
        except sr.UnknownValueError:
            pass  # Ignore silence silently
        except sr.RequestError:
            self.root.after(0, self.append_chat, 'Pet', 'Voice service error!')

    def append_voice_text(self, text):
        # Add recognized text to input box live
        current = self.chat_entry.get()
        if current:
            self.chat_entry.insert('end', ' ' + text)
        else:
            self.chat_entry.insert(0, text)
        self.chat_entry.update()
        
        # Show in chat what user is saying live
        # Update or add live transcript line
        self.chat_display.configure(state='normal')
        self.chat_display.delete('end-2l', 'end-1l')
        self.chat_display.insert('end', f'🎤 {text}\n', 'voice_text')
        self.chat_display.tag_config('voice_text', foreground='#2ed573', font=('Segoe UI', 10, 'italic'))
        self.chat_display.configure(state='disabled')
        self.chat_display.see('end')

    def update_thinking_timer(self):
        if self.ai_timer_running:
            if self.chat_display:
                try:
                    self.chat_display.delete('temp.first', 'temp.last')
                except tk.TclError:
                    pass
                self.chat_display.insert('end', f"Thinking... ({self.ai_timer_count}s)\n", 'temp')
                self.chat_display.see('end')
            self.ai_timer_count += 1
            self.root.after(1000, self.update_thinking_timer)

    def _ai_task(self, prompt):
        try:
            system_prompt = """
You are a friendly desktop pet assistant.
You handle casual conversation ONLY.
PC commands like opening apps, searching Google,
closing apps are handled by another system.
You will only receive messages that need 
a conversational response.
Keep ALL replies under 2 sentences.
Be warm, casual and friendly like a pet.
Never say things like "I'll open that for you"
or "Let me search that" - just have normal
friendly conversation.
"""
            payload = {
                "model": MODEL,
                "messages": [{"role":"system","content":system_prompt}, {"role":"user","content":prompt}],
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "num_predict": 80,
                    "num_ctx": 512,
                    "top_k": 10,
                    "top_p": 0.9,
                    "repeat_penalty": 1.1
                }
            }
            r = requests.post(OLLAMA_URL, json=payload, timeout=15)
            self.ai_timer_running = False
            reply = r.json()['message']['content']
            self.root.after(0, self.append_chat, "Pet", reply.strip())
        except Exception as e:
            self.ai_timer_running = False
            self.root.after(0, self.append_chat, "Pet", f"AI Error: {e}")

    def handle_ai_response(self, reply, original):
        # Deprecated: AI no longer returns commands, but keeping for reference
        self.root.after(0, self.append_chat, "Pet", reply.strip())

    def check_ollama_startup(self):
        def _check():
            global MODEL
            try:
                r = requests.get("http://localhost:11434/api/tags", timeout=3)
                if r.status_code == 200:
                    installed = [m['name'] for m in r.json().get('models', [])]
                    for m in ["llama3.2", "llama3", "mistral", "phi3"]:
                        if any(m in i for i in installed):
                            MODEL = m
                            break
            except: pass
            
            try: 
                requests.get("http://localhost:11434", timeout=2)
                # Warmup probe
                requests.post(OLLAMA_URL, json={"model":MODEL, "messages":[{"role":"user","content":"ping"}], "stream":False}, timeout=2)
            except: self.root.after(0, self.append_chat, "Pet", "Start Ollama!")
        threading.Thread(target=_check, daemon=True).start()

if __name__ == "__main__":
    DesktopPet()
