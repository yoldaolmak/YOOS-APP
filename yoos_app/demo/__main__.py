"""
YOOS-APP Demo
Usage: python -m yoos_app.demo

Analyzes 3 Mark Twain travel texts (public domain),
then generates a travel blog post about Istanbul using
the extracted voice profile.

Outputs to examples/output/:
  - demo_profile.json   (extracted voice profile)
  - demo_result.html
  - demo_result.txt
"""
import sys
import os
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
CORPUS_DIR = ROOT / "examples" / "corpus"
OUTPUT_DIR = ROOT / "examples" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT))

from yoos_app.ingestion.reader import read_corpus
from yoos_app.voice.analyzer import analyze
from yoos_app.voice.generator import generate
from yoos_app.exporter.writer import save_local


def run():
    print("YOOS-APP Demo")
    print("=" * 40)

    # 1. Read corpus
    corpus_files = list(CORPUS_DIR.glob("*.txt")) + list(CORPUS_DIR.glob("*.pdf"))
    if not corpus_files:
        print("ERROR: No corpus files found in examples/corpus/")
        sys.exit(1)

    print(f"[1/4] Reading {len(corpus_files)} corpus files...")
    texts = read_corpus([str(f) for f in sorted(corpus_files)])
    print(f"      {len(texts)} texts loaded, {sum(len(t.split()) for t in texts)} words total")

    # 2. Analyze voice
    print("[2/4] Analyzing voice profile...")
    profile = analyze(texts, author_name="Mark Twain (Demo)")
    profile_path = str(OUTPUT_DIR / "demo_profile.json")
    profile.save(profile_path)
    print(f"      Avg sentence: {profile.avg_sentence_words} words")
    print(f"      First person: %{int(profile.first_person_rate*100)}")
    print(f"      Top transitions: {', '.join(profile.top_transitions[:4])}")
    print(f"      Profile saved: {profile_path}")

    # 3. Generate content
    print("[3/4] Generating content...")
    backend = os.environ.get("YOOS_BACKEND", "openai")

    if backend == "openai" and not os.environ.get("OPENAI_API_KEY"):
        print("      [DEMO MODE] No OPENAI_API_KEY — using mock output")
        content = _mock_content()
    else:
        try:
            content = generate(profile, "travel_blog", "Istanbul, Turkey", backend=backend)
        except Exception as e:
            print(f"      [DEMO MODE] LLM error ({e}) — using mock output")
            content = _mock_content()

    words = len(content.split())
    print(f"      Generated: {words} words")

    # 4. Export
    print("[4/4] Saving outputs...")
    html_path = save_local(content, "Istanbul Demo", "html", str(OUTPUT_DIR))
    txt_path = save_local(content, "Istanbul Demo", "txt", str(OUTPUT_DIR))
    print(f"      HTML: {html_path}")
    print(f"      TXT:  {txt_path}")

    print("=" * 40)
    print("Demo complete.")
    print(f"Set OPENAI_API_KEY to use real LLM generation.")
    print(f"Set YOOS_BACKEND=ollama to use local Ollama.")


def _mock_content() -> str:
    return """Istanbul is a city that refuses to be summarized. I have tried. I have failed. I recommend trying anyway.

The Bosphorus, which divides the city between two continents, is one of those geographical facts that sounds made up until you see it. You stand on the European side and look at Asia. Then you take a boat and look at Europe. It is the same city. It is a completely different city.

The Grand Bazaar has four thousand shops. I know this because the guidebook said so, and I counted perhaps forty of them before I gave up and bought a rug I did not need. The rugs are very beautiful, and the merchants are very persuasive, and the combination is financially dangerous.

The mosques are magnificent. The Blue Mosque has six minarets, which was considered excessive when it was built and remains impressive today. You remove your shoes to enter, and you stand in a space so large and so quiet that you feel, briefly, like a very small person in a very large universe. This is not unpleasant.

The food deserves its own chapter. Perhaps its own book. The kebabs, the bread, the tea served in small tulip-shaped glasses at all hours—these are things that require no translation. I ate well in Istanbul. I ate often. I have no regrets.

If I were to give one piece of advice, it would be this: take the ferry. Go across the water. Look back at the city from the middle of the strait. It is the only way to see the whole impossible thing at once."""


if __name__ == "__main__":
    run()
