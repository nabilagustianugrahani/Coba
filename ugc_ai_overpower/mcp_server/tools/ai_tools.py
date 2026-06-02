import os
import json
import requests

class AIRouter:
    def __init__(self, base_url="http://localhost:20128", api_key=None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.getenv("ROUTER_KEY", "sk-8028a980b0c7366a-4a45za-36eef5ef")
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    def chat(self, prompt, model="gemini/gemini-2.5-flash", max_tokens=1024):
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "stream": False
        }
        try:
            r = requests.post(f"{self.base_url}/v1/chat/completions",
                            headers=self.headers, json=payload, timeout=30)
            data = r.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            return f"AI Error: {e}"

    def chat_structured(self, prompt, model="gemini/gemini-2.5-flash"):
        result = self.chat(prompt + "\n\nOutput HARUS JSON valid.", model=model)
        try:
            return json.loads(result)
        except:
            return {"raw": result}

    def analyze_product(self, product_name, description=""):
        prompt = f"""Analisis produk afiliasi:
Nama: {product_name}
Deskripsi: {description}

Beri:
1. Target konsumen (wanita/pria/orang tua/anak muda)
2. Trigger emosi utama
3. Angle konten terbaik
4. Platform terbaik
5. Komisi estimasi"""
        return self.chat(prompt)

    def generate_hook(self, product, platform, target):
        prompt = f"""Buat 5 hook untuk konten UGC {product} di {platform}.
Target: {target}.
Setiap hook maks 5 kata, Bahasa Indonesia, bikin orang berhenti scroll."""
        result = self.chat(prompt)
        return [h.strip("- ") for h in result.split("\n") if h.strip()]

    def translate(self, text, target_lang):
        prompt = f"Terjemahkan ke {target_lang}: {text}"
        return self.chat(prompt)