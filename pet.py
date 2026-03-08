import tkinter as tk
from tkinter import simpledialog
import math
import random
import winsound
import tkinter.font as tkFont
import threading

class Dashboard:
    def __init__(self, parent_root, toggle_mic_cb, send_cmd_cb, toggle_mute_cb, toggle_pet_cb, change_name_cb):
        self.root = tk.Toplevel(parent_root)
        self.root.title("Pet Dashboard")
        self.root.geometry("280x350-20+40")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.92)
        self.root.configure(bg="#1a1a2e")

        self.toggle_mic_cb = toggle_mic_cb
        self.send_cmd_cb = send_cmd_cb
        self.toggle_mute_cb = toggle_mute_cb
        self.toggle_pet_cb = toggle_pet_cb
        self.change_name_cb = change_name_cb
        self.is_visible = True

        self.setup_ui()

    def setup_ui(self):
        self.canvas = tk.Canvas(self.root, width=280, height=350, bg="#1a1a2e", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.name_text = self.canvas.create_text(140, 30, text="Pixel", fill="white", font=("Arial", 16, "bold"))
        self.canvas.tag_bind(self.name_text, "<Button-1>", self.on_name_click)

        self.canvas.create_text(20, 30, text="AI:", fill="#888888", font=("Arial", 8))
        self.ai_status_dot = self.canvas.create_oval(35, 25, 45, 35, fill="red", outline="")

        self.status_label_id = self.canvas.create_text(140, 60, text="Status: IDLE", fill="#00CCFF", font=("Arial", 10))

        self.canvas.create_text(140, 90, text="--- History ---", fill="#555555", font=("Arial", 8))
        self.history_labels = []
        for i in range(3):
            label_id = self.canvas.create_text(140, 110 + (i * 20), text="", fill="#aaaaaa", font=("Arial", 9), width=240)
            self.history_labels.append(label_id)

        btn_frame = tk.Frame(self.root, bg="#1a1a2e")
        self.canvas.create_window(140, 220, window=btn_frame)

        self.mic_btn = tk.Button(btn_frame, text="🎤 Mic On/Off", bg="#2a2a40", fg="white", relief="flat", command=self.toggle_mic_cb, width=15)
        self.mic_btn.pack(pady=2)

        self.mute_btn = tk.Button(btn_frame, text="🔊 Mute/Unmute", bg="#2a2a40", fg="white", relief="flat", command=self.toggle_mute_cb, width=15)
        self.mute_btn.pack(pady=2)

        self.pet_btn = tk.Button(btn_frame, text="🐾 Show/Hide Pet", bg="#2a2a40", fg="white", relief="flat", command=self.toggle_pet_cb, width=15)
        self.pet_btn.pack(pady=2)

        input_frame = tk.Frame(self.root, bg="#1a1a2e")
        self.canvas.create_window(140, 310, window=input_frame)

        self.entry = tk.Entry(input_frame, bg="#2a2a40", fg="white", insertbackground="white", borderwidth=0, width=18)
        self.entry.pack(side="left", padx=5)
        self.entry.bind("<Return>", lambda e: self.send_cmd())

        self.send_btn = tk.Button(input_frame, text="Send", bg="#00CCFF", fg="white", relief="flat", command=self.send_cmd)
        self.send_btn.pack(side="left")

    def toggle_visibility(self):
        self.is_visible = not self.is_visible
        if self.is_visible:
            self.root.deiconify()
        else:
            self.root.withdraw()

    def update_status(self, text):
        self.canvas.itemconfig(self.status_label_id, text=f"Status: {text.upper()}")

    def update_ai_status(self, connected):
        color = "#00FF00" if connected else "red"
        self.canvas.itemconfig(self.ai_status_dot, fill=color)

    def update_history(self, commands):
        for i, cmd in enumerate(commands[-3:]):
            idx = 2 - i
            self.canvas.itemconfig(self.history_labels[idx], text=cmd)

    def set_mic_active(self, active):
        bg = "red" if active else "#2a2a40"
        self.mic_btn.configure(bg=bg)

    def on_name_click(self, event):
        new_name = simpledialog.askstring("Name", "Enter pet name:")
        if new_name:
            self.canvas.itemconfig(self.name_text, text=new_name)
            self.change_name_cb(new_name)

    def send_cmd(self):
        cmd = self.entry.get()
        if cmd:
            self.entry.delete(0, tk.END)
            self.send_cmd_cb(cmd)

class DesktopPet:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", "black")
        self.root.config(bg="black")
        
        self.canvas_size = 150
        self.canvas = tk.Canvas(self.root, width=self.canvas_size, height=self.canvas_size, bg="black", highlightthickness=0)
        self.canvas.pack()

        # State management
        self.state = "IDLE"
        self.mode = "none"
        
        # Animation Variables
        self.frame = 0
        self.scale = 0.0
        self.target_scale = 1.0
        self.is_animating_scale = False
        self.particles = []
        self.bubble_alpha = 0
        self.bubble_text = ""
        self.bubble_timer = 0
        self.shake_offset = 0
        self.shake_timer = 0
        self.next_blink = 100
        
        # Positioning
        self.screen_w = self.root.winfo_screenwidth()
        self.screen_h = self.root.winfo_screenheight()
        self.pos_x = self.screen_w // 2 - 75
        self.pos_y = self.screen_h // 2 - 75
        self.root.geometry(f"{self.canvas_size}x{self.canvas_size}+{self.pos_x}+{self.pos_y}")

        # Dragging variables
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        self.is_paused = False

        # Dragging will be bound to individual shapes in draw_pet
        
        self.indicator_id = self.canvas.create_text(75, 140, text="", fill="#00CCFF", font=("Arial", 8, "bold"))
        self.pet_visible = False
        self.root.withdraw() # Start hidden for spawn animation

        # Start animation loop (60 FPS)
        self.animate()
        self.spawn()

    def spawn(self):
        self.pet_visible = True
        self.root.deiconify()
        self.scale = 0.0
        self.target_scale = 1.0
        self.is_animating_scale = True
        # Chime
        threading.Thread(target=lambda: winsound.Beep(1000, 100), daemon=True).start()
        # Sparkles
        for _ in range(15):
            self.particles.append({
                'x': 75, 'y': 75,
                'vx': random.uniform(-3, 3), 'vy': random.uniform(-3, 3),
                'life': 1.0, 'color': random.choice(['#FFD700', '#FFFFFF', '#00CCFF'])
            })

    def despawn(self, callback=None):
        self.state = "WAVING"
        # Wait a bit while waving, then shrink
        def _shrink():
            self.target_scale = 0.0
            self.is_animating_scale = True
            
            def _hide():
                if self.scale <= 0.01:
                    self.pet_visible = False
                    self.root.withdraw()
                    if callback: callback()
                else:
                    self.root.after(50, _hide)
            _hide()
        
        self.root.after(1000, _shrink) # Wave for 1 second first

    def on_drag_start(self, event):
        self.is_paused = True
        self.drag_offset_x = event.x
        self.drag_offset_y = event.y

    def on_dragging(self, event):
        new_x = self.root.winfo_x() + event.x - self.drag_offset_x
        new_y = self.root.winfo_y() + event.y - self.drag_offset_y
        
        # Clamp to screen
        new_x = max(0, min(new_x, self.screen_w - 140))
        new_y = max(0, min(new_y, self.screen_h - 140))
        
        self.root.geometry(f'+{new_x}+{new_y}')

    def on_drag_end(self, event):
        self.root.after(2000, self.resume_movement)

    def resume_movement(self):
        self.is_paused = False

    def show_bubble(self, text):
        self.bubble_text = text
        self.bubble_alpha = 1.0
        self.bubble_timer = 250 # ~4 seconds at 60fps

    def shake_head(self):
        self.shake_timer = 20
        self.show_bubble("Not found!")

    def animate(self):
        self.frame += 1
        
        # Scaling/Blinking logic updates
        if self.frame >= self.next_blink:
            if self.frame > self.next_blink + 10: # End of blink
                self.next_blink = self.frame + random.randint(180, 480) # 3-8 seconds
            self.is_blinking = True
        else:
            self.is_blinking = False

        # Scale logic
        if self.is_animating_scale:
            self.scale += (self.target_scale - self.scale) * 0.15
            if abs(self.scale - self.target_scale) < 0.01:
                self.scale = self.target_scale
                self.is_animating_scale = False

        # Head shake logic
        if self.shake_timer > 0:
            self.shake_timer -= 1
            self.shake_offset = math.sin(self.frame * 0.8) * 10
        else:
            self.shake_offset = 0

        # Particle logic
        for p in self.particles[:]:
            p['x'] += p['vx']
            p['y'] += p['vy']
            p['life'] -= 0.02
            if p['life'] <= 0:
                self.particles.remove(p)

        self.draw_pet()
        self.root.after(16, self.animate)

    def draw_pet(self):
        self.canvas.delete("all")
        if self.scale <= 0.01: return

        cx, cy = 75 + self.shake_offset, 75
        s = self.scale
        
        # Body Floating
        if self.state == "IDLE":
            y_off = math.sin(self.frame * 0.05) * 5
        elif self.state == "ACTIVE":
            y_off = -abs(math.sin(self.frame * 0.15)) * 12
        else:
            y_off = 0
        
        curr_y = cy + y_off

        # Shadow
        shadow_w = (60 - (y_off * 0.5)) * s
        self.canvas.create_oval(cx - shadow_w/2, cy + 45*s, cx + shadow_w/2, cy + 55*s, fill="#222222", outline="")

        # Listening Ring Pulse
        if self.mode == "listening":
            pulse = abs(math.sin(self.frame * 0.1)) * 8
            color = f"#{int(200*abs(math.sin(self.frame*0.1))):02x}CCFF" # Faking transparency with bg awareness
            self.canvas.create_oval(cx - (50+pulse)*s, curr_y - (50+pulse)*s, cx + (50+pulse)*s, curr_y + (50+pulse)*s, outline="#00CCFF", width=2)

        # Particles
        for p in self.particles:
            alpha_hex = f"{int(p['life']*255):02x}"
            self.canvas.create_oval(p['x']-2, p['y']-2, p['x']+2, p['y']+2, fill=p['color'], outline="")

        # Feet
        self.canvas.create_oval(cx - 30*s, curr_y + 35*s, cx - 10*s, curr_y + 45*s, fill="#FFB6C1", outline="#FF8DA1", width=2*s)
        self.canvas.create_oval(cx + 10*s, curr_y + 35*s, cx + 30*s, curr_y + 45*s, fill="#FFB6C1", outline="#FF8DA1", width=2*s)

        # Body
        body = self.canvas.create_oval(cx - 40*s, curr_y - 40*s, cx + 40*s, curr_y + 40*s, fill="#FFB6C1", outline="#FF8DA1", width=2*s)

        # Ears
        left_ear = self.canvas.create_oval(cx - 35*s, curr_y - 45*s, cx - 15*s, curr_y - 25*s, fill="#FFB6C1", outline="#FF8DA1", width=2*s)
        right_ear = self.canvas.create_oval(cx + 15*s, curr_y - 45*s, cx + 35*s, curr_y - 25*s, fill="#FFB6C1", outline="#FF8DA1", width=2*s)
        
        # Waving Arm
        if self.state == "WAVING":
            self.canvas.create_oval(cx + 35*s, curr_y - 10*s + math.sin(self.frame*0.2)*20, cx+50*s, curr_y+5*s + math.sin(self.frame*0.2)*20, fill="#FFB6C1", outline="#FF8DA1")

        # Cheeks
        left_cheek = self.canvas.create_oval(cx - 32*s, curr_y, cx - 22*s, curr_y + 8*s, fill="#FFD1DC", outline="")
        right_cheek = self.canvas.create_oval(cx + 22*s, curr_y, cx + 32*s, curr_y + 8*s, fill="#FFD1DC", outline="")

        # Eyes
        eyes = self.draw_eyes(cx, curr_y, s)
        left_eye, right_eye = eyes[0], eyes[1]

        # Bind to ALL pet canvas shapes:
        for shape_id in [body, left_eye, right_eye, 
                        left_ear, right_ear, 
                        left_cheek, right_cheek]:
            self.canvas.tag_bind(shape_id, '<Button-1>', self.on_drag_start)
            self.canvas.tag_bind(shape_id, '<B1-Motion>', self.on_dragging)
            self.canvas.tag_bind(shape_id, '<ButtonRelease-1>', self.on_drag_end)

        # Speech Bubble
        if self.bubble_timer > 0:
            self.bubble_timer -= 1
            if self.bubble_timer < 30: self.bubble_alpha = self.bubble_timer / 30
            
            bx, by = cx, curr_y - 70*s
            # Scaled bubble
            lines = [self.bubble_text[i:i+20] for i in range(0, len(self.bubble_text), 20)][:3]
            self.canvas.create_rectangle(bx-60, by-10-len(lines)*15, bx+60, by+10, fill="white", outline="#FFB6C1", width=2)
            for i, line in enumerate(lines):
                self.canvas.create_text(bx, by-len(lines)*10 + i*15, text=line, fill="black", font=("Arial", 8))

    def draw_eyes(self, cx, cy, s):
        eye_x_off = 18 * s
        eye_y_off = -5 * s
        eye_size = 10 * s
        eye_ids = []
        
        for side in [-1, 1]:
            ex = cx + (side * eye_x_off)
            ey = cy + eye_y_off
            
            if self.is_blinking:
                eid = self.canvas.create_line(ex - eye_size, ey, ex + eye_size, ey, fill="black", width=2*s)
                eye_ids.append(eid)
            else:
                eid = self.canvas.create_oval(ex - eye_size, ey - eye_size, ex + eye_size, ey + eye_size, fill="white", outline="black")
                eye_ids.append(eid)
                
                # Pupil logic
                pupil_size = eye_size * 0.6
                p_off_x, p_off_y = 0, 0
                if self.mode == "thinking":
                    p_off_x = math.cos(self.frame * 0.3) * 4 * s
                    p_off_y = math.sin(self.frame * 0.3) * 4 * s
                
                self.canvas.create_oval(ex - pupil_size + p_off_x, ey - pupil_size + p_off_y, ex + pupil_size + p_off_x, ey + pupil_size + p_off_y, fill="black")
                self.canvas.create_oval(ex - pupil_size*0.4 + p_off_x - 1, ey - pupil_size*0.4 + p_off_y - 1, ex + p_off_x - 1, ey + p_off_y - 1, fill="white")
        return eye_ids

    def show_indicator(self, text):
        self.canvas.itemconfig(self.indicator_id, text=text)

    def set_state(self, state): self.state = state
    def set_mode(self, mode):
        self.mode = mode
        if mode == "listening": self.show_indicator("Listening...")
        elif mode == "thinking": self.show_indicator("Thinking...")
        else: self.show_indicator("")
        return mode.upper() if mode != "none" else "IDLE"

    def toggle_pet_visibility(self):
        if self.pet_visible: self.despawn()
        else: self.spawn()
        return self.pet_visible

    def run(self): self.root.mainloop()

import threading
