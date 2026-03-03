import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

EDITORIAL_BRAIN_PROMPT = """
You are the Editorial Brain of Yoldaolmak.com.

You MUST:

1. Preserve factual information.
2. Upgrade narrative into Kemal Kaya voice:
   - First person singular
   - Temporal anchors
   - Balanced critique
   - Genius Loci depth
3. Normalize heading hierarchy.
4. Add short definition after each H2 using format:
   H2 - Short Definition
5. Improve SEO structure without keyword stuffing.
6. Keep structure logical.
7. Do NOT generate generic travel tone.
8. Do NOT delete valid information.
9. Add structured FAQ (8 questions).
10. Maintain authority tone, not influencer hype.

Rewrite intelligently.
If section is strong, keep it.
If weak, enrich it.
Return FULL HTML only.
"""

def editorial_rewrite(html_content: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.6,
        messages=[
            {"role": "system", "content": EDITORIAL_BRAIN_PROMPT},
            {"role": "user", "content": html_content}
        ]
    )

    return response.choices[0].message.content
