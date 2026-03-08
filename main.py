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
from datetime import datetime

# --- CONFIGURATION ---
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.2" # Default, overridden by logic below

class DesktopPet:
    def __init__(self):
        self.root = tk.Tk()
        self.screen_w = self.root.winfo_screenwidth()
        self.screen_h = self.root.winfo_screenheight()
        
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
        self.pos_x, self.pos_y = self.screen_w // 2, self.screen_h // 2
        self.target_x, self.target_y = self.pos_x, self.pos_y
        self.is_dragging = False
        self.facing_right = True
        self.frame = 0
        self.blink_timer = 0
        self.is_blinking = False
        self.context_menu = None
        self.is_listening = False
        self.is_paused = False
        self.resume_after_id = None
        
        self.ai_timer_count = 0
        self.ai_timer_running = False
        self.chat_messages = []
        self.chat_window = None
        self.chat_display = None
        
        self.recognizer = sr.Recognizer()
        
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
        self.ai_timer_count = 0
        self.ai_timer_running = True
        self.update_thinking_timer()
        threading.Thread(target=self._ai_task, args=(text,), daemon=True).start()

    # --- CHAT WINDOW ---
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
        
        px, py = self.root.winfo_x(), self.root.winfo_y()
        self.chat_window.geometry(f'300x400+{px+160}+{py-100}')
        
        # Header (Top)
        header = tk.Frame(self.chat_window, bg='#0a0a0f')
        header.pack(side='top', fill='x')
        tk.Label(header, text="🐾 Pet Assistant", bg='#0a0a0f', fg='#e0e0ff', font=('Segoe UI', 10, 'bold')).pack(side='left', padx=10, pady=5)
        tk.Button(header, text='✕', bg='#ff4757', fg='white', bd=0, command=self.close_chat_window, cursor='hand2').pack(side='right', padx=5)
        
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
                self.chat_entry.focus() # Maintain focus
                
        self.chat_entry.bind('<Return>', _handle_send)
        
        send_btn = tk.Button(bottom_frame, text='➤', bg='#6c63ff', fg='white', bd=0, font=('Segoe UI', 12), cursor='hand2', command=_handle_send)
        send_btn.pack(side='left')
        
        # Keep mic button for functionality since it was requested in polish step
        mic_btn = tk.Button(bottom_frame, text='🎤', bg='#6c63ff', fg='white', bd=0, font=('Segoe UI', 12), cursor='hand2', command=self.toggle_voice)
        mic_btn.pack(side='left', padx=(5,0))

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
        if not self.is_dragging and not self.is_listening:
            if self.resume_after_id: self.root.after_cancel(self.resume_after_id)
            self.resume_after_id = self.root.after(100, self.resume_movement)

    # --- CONTEXT MENU ---
    def _create_context_menu(self):
        self.context_menu = tk.Toplevel(self.root)
        self.context_menu.overrideredirect(True)
        self.context_menu.attributes('-topmost', True)
        self.context_menu.configure(bg='#0a0a0f', highlightbackground='#6c63ff', highlightthickness=1)
        self.context_menu.withdraw() # Hide immediately
        
        items = [
            ('🎤  Voice Input', self.toggle_voice),
            ('🔍  Search & Chat', self.show_chat_window),
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
                padx=12,
                cursor='hand2',
                activebackground='#1a1a2e',
                activeforeground='white',
                command=handler
            )
            btn.pack(fill='x', ipady=6)
            
            btn.bind('<Enter>', lambda e, b=btn: b.config(bg='#1a1a2e'))
            btn.bind('<Leave>', lambda e, b=btn: b.config(bg='#0a0a0f'))

    def show_context_menu(self, event):
        # Stop pet from moving while menu is open
        self.is_paused = True
        if self.resume_after_id:
            self.root.after_cancel(self.resume_after_id)
            self.resume_after_id = None
            
        mx, my = event.x_root, event.y_root
        self.context_menu.geometry(f'160x108+{mx}+{my}')
        self.context_menu.deiconify()
        self.context_menu.lift()

    def close_context_menu(self):
        if self.context_menu and self.context_menu.winfo_ismapped():
            self.context_menu.withdraw()
            # Resume movement when closed
            if not self.chat_window and not self.is_listening and not self.is_dragging:
                if self.resume_after_id: self.root.after_cancel(self.resume_after_id)
                self.resume_after_id = self.root.after(100, self.resume_movement)

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

    # --- MOVEMENT LOOP ---
    def move_pet(self):
        self.frame += 1
        if not self.is_dragging and not self.is_paused:
            dx, dy = self.target_x - self.pos_x, self.target_y - self.pos_y
            dist = (dx**2 + dy**2)**0.5
            if dist > 3:
                self.pos_x += (dx / dist) * 3
                self.pos_y += (dy / dist) * 3
                self.facing_right = dx > 0
            else:
                if self.frame % 150 == 0:
                    self.target_x = random.randint(50, self.screen_w - 100)
                    self.target_y = random.randint(50, self.screen_h - 100)

        # Apply movement
        self.root.geometry(f"100x100+{int(self.pos_x)}+{int(self.pos_y)}")
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
        self.resume_after_id = self.root.after(5000, self.resume_movement)

    def drag_move(self, event):
        self.is_dragging = True
        self.is_paused = True
        self.pos_x = event.x_root - self._drag_x
        self.pos_y = event.y_root - self._drag_y
        
        # Clamp to screen bounds
        self.pos_x = max(0, min(self.pos_x, self.screen_w - 100))
        self.pos_y = max(0, min(self.pos_y, self.screen_h - 100))
        
        self.root.geometry(f'100x100+{int(self.pos_x)}+{int(self.pos_y)}')

    def drag_end(self, event):
        self.is_dragging = False
        self.is_paused = False
        if self.resume_after_id: self.root.after_cancel(self.resume_after_id)
        self.resume_after_id = self.root.after(3000, self.resume_movement)

    def resume_movement(self):
        self.is_paused, self.resume_after_id = False, None

    # --- UI ACTIONS DELETED ---
    # show_search_input has been replaced by show_chat_window

    # --- AI & VOICE ---
    def toggle_voice(self):
        if self.is_listening: self.is_listening = False
        else: self.start_voice_thread()

    def start_voice_thread(self):
        self.is_listening = True
        self.is_paused = True
        if self.resume_after_id:
            self.root.after_cancel(self.resume_after_id)
            self.resume_after_id = None
        self.show_chat_window()
        if self.chat_display:
            try:
                self.chat_display.delete('temp.first', 'temp.last')
            except tk.TclError:
                pass
            self.chat_display.insert('end', "Listening... 🎤\n", 'temp')
            self.chat_display.see('end')
        threading.Thread(target=self._voice_task, daemon=True).start()

    def _voice_task(self):
        try:
            with sr.Microphone() as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
                text = self.recognizer.recognize_google(audio)
                self.root.after(0, self.update_transcript, text)
        except Exception:
            pass
        finally:
            self.is_listening = False
            self.root.after(0, self.clear_listening_ui)

    def clear_listening_ui(self):
        if self.chat_display:
            try:
                self.chat_display.delete('temp.first', 'temp.last')
            except tk.TclError:
                pass
        if not self.chat_window and not self.is_dragging:
            if self.resume_after_id: self.root.after_cancel(self.resume_after_id)
            self.resume_after_id = self.root.after(100, self.resume_movement)

    def update_transcript(self, text):
        self.show_chat_window()
        if hasattr(self, 'chat_entry'):
            self.chat_entry.delete(0, 'end')
            self.chat_entry.insert(0, text)

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
You are a friendly desktop assistant pet.
Keep ALL replies under 2 sentences maximum.
Be warm, casual and natural like a friend.

ONLY return JSON for these specific commands:
- User wants to open an application
- User wants to close an application  
- User wants to search something on Google

JSON format ONLY these three:
{"action":"openApp","target":"appname"}
{"action":"closeApp","target":"appname"}
{"action":"search","query":"search term"}

For EVERYTHING else including:
- Greetings (hi, hello, hey)
- Questions (what is, how does, why)
- Conversations (how are you, tell me)
- Any other request
Reply in plain friendly English ONLY.
Never return JSON for these.
Never explain yourself.
Never use bullet points.
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
            self.root.after(0, self.handle_ai_response, reply, prompt)
        except Exception as e:
            self.ai_timer_running = False
            self.root.after(0, self.append_chat, "Pet", f"AI Error: {e}")

    def handle_ai_response(self, reply, original):
        reply = reply.strip().replace('```json','').replace('```','').strip()
        try:
            # Check if it looks like JSON
            if '{' in reply and '}' in reply:
                start, end = reply.find('{'), reply.rfind('}')+1
                cmd = json.loads(reply[start:end])
                action = cmd.get('action')
                
                if action == 'openApp':
                    t = cmd.get('target', 'notepad')
                    subprocess.Popen(f'start {t}', shell=True)
                    self.root.after(0, self.append_chat, "Pet", f"✅ Opening {t}...")
                elif action == 'closeApp':
                    t = cmd.get('target', 'notepad')
                    subprocess.Popen(f'taskkill /F /IM {t}.exe /T', shell=True)
                    self.root.after(0, self.append_chat, "Pet", f"🛡️ Closing {t}...")
                elif action == 'search':
                    q = cmd.get('query', 'google')
                    webbrowser.open(f'https://google.com/search?q={q}')
                    self.root.after(0, self.append_chat, "Pet", f"🔍 Searching: {q}")
                else: 
                    # If it's another action or missing action, show response if available
                    msg = cmd.get('response', reply)
                    self.root.after(0, self.append_chat, "Pet", msg)
            else:
                # Plain English reply
                self.root.after(0, self.append_chat, "Pet", reply)
        except Exception:
            # Fallback for any parsing errors
            self.root.after(0, self.append_chat, "Pet", reply)

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
