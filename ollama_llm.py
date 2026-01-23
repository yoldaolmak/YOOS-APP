import requests

def ollama_llm(prompt):

    r = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model":"qwen2.5:14b",
            "prompt":prompt,
            "stream":False
        }
    )

    return r.json()["response"]
# DEBUG: timeout araştır
