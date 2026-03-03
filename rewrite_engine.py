import requests
import json
import os
from bs4 import BeautifulSoup
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path

# .env dosyasını açıkça belirt
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError("OPENAI_API_KEY bulunamadı. .env dosyasını kontrol et.")

client = OpenAI(api_key=api_key)

def load_brain():
    with open("editorial_brain.json", "r", encoding="utf-8") as f:
        return json.load(f)

def fetch_html(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.text

def extract_content(html):
    soup = BeautifulSoup(html, "html.parser")
    content = soup.find("div", class_="td-post-content")
    return content.get_text(separator="\n")

def build_prompt(text, brain):
    return f"""
You are an advanced editorial rewrite engine.

Follow these constitutional rules strictly.

VOICE RULES:
{json.dumps(brain["voice_identity"], indent=2)}

STRUCTURAL RULES:
{json.dumps(brain["structural_rules"], indent=2)}

AUTHORITY LAYER:
{json.dumps(brain["authority_layer"], indent=2)}

SEO LAYER:
{json.dumps(brain["seo_layer"], indent=2)}

REWRITE POLICY:
{json.dumps(brain["rewrite_policy"], indent=2)}

Rewrite the text below according to these rules.
Preserve factual information but restructure, inject authority, fix flow,
normalize headings, add FAQ + Schema JSON-LD, and insert MAP box placeholder.

Return full HTML output.

TEXT:
{text}
"""

def rewrite_text(text, brain):
    prompt = build_prompt(text, brain)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a professional travel editorial architect."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )

    return response.choices[0].message.content

def transform(url):
    print("Fetching content...")
    html = fetch_html(url)
    text = extract_content(html)
    brain = load_brain()

    print("Rewriting with editorial brain...")
    new_content = rewrite_text(text, brain)

    with open("rewrite_output.html", "w", encoding="utf-8") as f:
        f.write(new_content)

    print("Rewrite complete → rewrite_output.html")

if __name__ == "__main__":
    url = input("Enter URL: ")
    transform(url)
