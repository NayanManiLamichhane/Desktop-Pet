import requests
import json
import pc_control
import browser
import subprocess
import time

class AssistantBrain:
    def __init__(self, base_url="http://localhost:11434/api/chat"):
        self.base_url = base_url
        self.conversation_history = []
        self.model = "llama3" # Default model
        # Try to use a common fallback if llama3 isn't found? No, let's stick to user request.
        self.system_prompt = (
            f"You are a helpful cute desktop assistant. You control the user's PC. "
            "Always respond in max 2 sentences. When user wants to open/close apps, "
            "search, or control PC return ONLY a JSON command like:\n"
            "{ \"action\": \"openApp\", \"target\": \"chrome\" }\n"
            "{ \"action\": \"closeApp\", \"target\": \"spotify\" }\n"
            "{ \"action\": \"search\", \"query\": \"cats\" }\n"
            "{ \"action\": \"openFile\", \"path\": \"resume\" }\n"
            "{ \"action\": \"typeText\", \"text\": \"hello\" }\n"
            "{ \"action\": \"chat\", \"response\": \"your reply\" }\n"
            "Never add explanation, return ONLY the JSON object."
        )

    def start_ollama(self):
        """Try to launch Ollama serve if not running."""
        try:
            subprocess.Popen(['ollama', 'serve'], creationflags=subprocess.CREATE_NO_WINDOW)
            return True
        except Exception as e:
            print(f"Failed to start Ollama: {e}")
            return False

    def check_connection(self):
        """Check if Ollama server is responsive."""
        try:
            r = requests.get('http://localhost:11434', timeout=2)
            return r.status_code == 200
        except:
            return False

    def ask_ai(self, user_message):
        """Ask Ollama for a response and return parsed JSON."""
        # Update history
        self.conversation_history.append({"role": "user", "content": user_message})
        if len(self.conversation_history) > 5:
            self.conversation_history = self.conversation_history[-5:]

        messages = [{"role": "system", "content": self.system_prompt}] + self.conversation_history

        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False
            }
            
            response = requests.post(
                self.base_url,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                content = response.json()['message']['content'].strip()
                # Try to extract JSON
                if "{" in content and "}" in content:
                    start = content.find("{")
                    end = content.rfind("}") + 1
                    json_str = content[start:end]
                    try:
                        data = json.loads(json_str)
                        self.conversation_history.append({"role": "assistant", "content": json_str})
                        return data
                    except json.JSONDecodeError:
                        return {"action": "chat", "response": "My brain produced invalid JSON."}
                else:
                    return {"action": "chat", "response": content}
            else:
                return {"action": "chat", "response": "Ollama error. Is the model downloaded?"}
        except Exception:
            return {"action": "chat", "response": "Ollama is not responding."}

    def parse_command(self, json_response):
        """Execute action from JSON and return string message."""
        action = json_response.get("action")
        
        try:
            if action == "openApp":
                target = json_response.get("target")
                return pc_control.open_app(target)
            elif action == "closeApp":
                target = json_response.get("target")
                return pc_control.close_app(target)
            elif action == "search":
                query = json_response.get("query")
                return pc_control.google_search(query)
            elif action == "openFile":
                path = json_response.get("path")
                return pc_control.open_file(path)
            elif action == "typeText":
                text = json_response.get("text")
                return pc_control.type_text(text)
            elif action == "pressKey":
                keys = json_response.get("keys")
                return pc_control.press_key(keys)
            elif action == "chat":
                return json_response.get("response", "Hehe!")
            else:
                return "I'm not sure how to do that yet!"
        except Exception as e:
            return f"Action failed: {e}"

    def process_command(self, text):
        ai_json = self.ask_ai(text)
        return self.parse_command(ai_json)
