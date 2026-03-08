import requests
import json

try:
    r = requests.get("http://localhost:11434/api/tags")
    if r.status_code == 200:
        models = [m['name'] for m in r.json().get('models', [])]
        print(",".join(models))
    else:
        print("Error: " + str(r.status_code))
except Exception as e:
    print("Error: " + str(e))
