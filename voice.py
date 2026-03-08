import speech_recognition as sr
import pyttsx3
import threading
import time

class VoiceEngine:
    def __init__(self):
        # Initialize Text-to-Speech
        try:
            self.engine = pyttsx3.init()
            self.engine.setProperty('rate', 175)
            self.engine.setProperty('volume', 0.9)
            
            # Select best available Windows voice (usually index 1 is a nicer female voice on Win10/11)
            voices = self.engine.getProperty('voices')
            if len(voices) > 1:
                self.engine.setProperty('voice', voices[1].id)
            elif len(voices) > 0:
                self.engine.setProperty('voice', voices[0].id)
        except Exception as e:
            print(f"TTS Init Error: {e}")
            self.engine = None

        # Initialize Speech Recognition
        self.recognizer = sr.Recognizer()
        self.mic_available = True
        try:
            self.microphone = sr.Microphone()
            # Test if it can be accessed
            with self.microphone as source:
                pass
        except Exception as e:
            print(f"Microphone Error: {e}")
            self.mic_available = False
            self.microphone = None
        
        # State
        self.is_muted = False
        self.is_listening = False
        self.stop_listening_fn = None

    def toggle_mute(self):
        self.is_muted = not self.is_muted
        return "Muted" if self.is_muted else "Unmuted"

    def speak(self, text):
        """Speak text in a non-blocking thread."""
        if self.is_muted or not self.engine or not text:
            return

        def _run_tts():
            try:
                # We need a fresh check in case muted while thread was starting
                if not self.is_muted:
                    self.engine.say(text)
                    self.engine.runAndWait()
            except Exception as e:
                print(f"Speech Error: {e}")

        threading.Thread(target=_run_tts, daemon=True).start()

    def listen_once(self):
        """Standard blocking listen (used by non-background triggers)."""
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            try:
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=5)
                return self.recognizer.recognize_google(audio)
            except Exception:
                return None

    def start_background_listening(self, callback):
        """Starts listening in the background using r.listen_in_background."""
        if self.is_listening:
            return
            
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            
        def _callback(recognizer, audio):
            try:
                text = recognizer.recognize_google(audio)
                if text:
                    callback(text)
            except sr.UnknownValueError:
                pass # Silent on no speech
            except sr.RequestError:
                 print("Voice Service Down")

        self.stop_listening_fn = self.recognizer.listen_in_background(self.microphone, _callback)
        self.is_listening = True

    def stop_background_listening(self):
        """Stops the background listener."""
        if self.stop_listening_fn:
            self.stop_listening_fn(wait_for_stop=False)
            self.stop_listening_fn = None
        self.is_listening = False

    def toggle_listening(self, callback):
        """Toggles the background listener on or off."""
        if self.is_listening:
            self.stop_background_listening()
            return False
        else:
            self.start_background_listening(callback)
            return True
