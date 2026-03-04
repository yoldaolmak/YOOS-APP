import json
import requests

SITE_URL = "https://yoldaolmak.com"
API = f"{SITE_URL}/wp-json/wp/v2/posts?per_page=100&page="

def main():
    page = 1
    all_posts = []

    while True:
        url = API + str(page)
        r = requests.get(url)

        if r.status_code != 200:
            break

        posts = r.json()
        if not posts:
            break

        for p in posts:
            all_posts.append({
                "id": p["id"],
                "title": p["title"]["rendered"],
                "content": p["content"]["rendered"]
            })

        page += 1

    with open("/home/ai/clawdbot/raw_posts.json", "w", encoding="utf-8") as f:
        json.dump(all_posts, f, ensure_ascii=False)

    print("Exported posts:", len(all_posts))

if __name__ == "__main__":
    main()
