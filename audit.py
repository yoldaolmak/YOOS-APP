import re
import requests
from bs4 import BeautifulSoup
from collections import Counter
from urllib.parse import urlparse

def fetch_html(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.text

def extract_main_content(soup):
    # WordPress içerik alanı
    article = soup.find("div", class_="td-post-content")
    if article:
        return article
    return soup

def extract_clean_text(element):
    for tag in element(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return element.get_text(separator=" ")

def word_count(text):
    return len(text.split())

def count_internal_links(element, domain):
    links = element.find_all("a", href=True)
    clean_links = []
    for a in links:
        href = a["href"]
        if domain in href and not any(x in href for x in ["#", "javascript", "wp-content"]):
            clean_links.append(href)
    return len(clean_links)

def count_sourced_claims(text):
    # (Kaynak, 2024-02) gibi formatları yakalar
    pattern = r"\([^)]+,\s*\d{4}(-\d{2})?(-\d{2})?\)"
    return len(re.findall(pattern, text))

def count_first_person(text):
    words = re.findall(r"\b\w+\b", text.lower())
    counter = Counter(words)
    return sum(counter[w] for w in ["ben", "benim", "bana", "bence"])

def audit_url(url):
    print(f"\n🔎 Auditing: {url}\n")

    domain = urlparse(url).netloc
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")

    main_content = extract_main_content(soup)
    text = extract_clean_text(main_content)
    print("\n--- DEBUG TEXT SAMPLE ---")
    print(text[:1000])
    print("\n--- END SAMPLE ---\n")

    wc = word_count(text)
    internal_links = count_internal_links(main_content, domain)
    sourced = count_sourced_claims(text)
    first_person = count_first_person(text)

    print("WORD COUNT:", wc)
    print("INTERNAL LINKS (CONTENT ONLY):", internal_links)
    print("SOURCED CLAIMS:", sourced)
    print("FIRST PERSON COUNT:", first_person)

    score = 0

    if wc >= 3000:
        score += 20

    link_density = internal_links / (wc / 1000) if wc > 0 else 0
    print("LINKS PER 1000 WORDS:", round(link_density, 2))

    if 8 <= link_density <= 12:
        score += 20

    if sourced >= (wc / 1000) * 5:
        score += 20

    if first_person >= (wc / 1000) * 3:
        score += 20

    print("\nESTIMATED STRUCTURAL SCORE:", score, "/80")

if __name__ == "__main__":
    url = input("Enter URL: ")
    audit_url(url)
