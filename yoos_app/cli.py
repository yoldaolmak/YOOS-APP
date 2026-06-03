#!/usr/bin/env python3
"""
YOOS-APP CLI — Universal Author Voice Engine

Commands:
  analyze   Extract voice profile from a corpus folder
  generate  Generate content from a saved voice profile
  export    Export content to a destination in a chosen format
  run       Full pipeline: corpus → analyze → generate → export
  demo      Run the built-in demo

Examples:
  yoos-app analyze --corpus ./texts/ --author "Hemingway" --out hem.json
  yoos-app generate --profile hem.json --type travel_blog --topic "Cuba" --backend openai
  yoos-app export --input out.txt --title "Cuba Morning" --format pdf --dest desktop
  yoos-app run --corpus ./texts/ --type magazine --topic "Tokyo streets" --dest wordpress
  yoos-app demo
"""
import argparse
import sys
import os
import time
from pathlib import Path


def _step(n, total, msg):
    print(f"[{n}/{total}] {msg}", flush=True)

def _ok(msg):
    print(f"      OK  {msg}", flush=True)

def _warn(msg):
    print(f"      !   {msg}", flush=True, file=sys.stderr)

def _fail(msg):
    print(f"\nERROR: {msg}", file=sys.stderr)
    sys.exit(1)

def _load_corpus(corpus_path):
    from yoos_app.ingestion.reader import read_corpus
    p = Path(corpus_path)
    if not p.exists():
        _fail(f"Corpus path not found: {corpus_path}")
    files = [str(f) for f in (p.iterdir() if p.is_dir() else [p])
             if Path(f).suffix.lower() in (".txt", ".pdf", ".html", ".htm")]
    if not files:
        _fail(f"No .txt/.pdf/.html files found in: {corpus_path}")
    texts = read_corpus(files)
    if not texts:
        _fail("All corpus files were empty or unreadable.")
    return texts, files


def cmd_analyze(args):
    from yoos_app.voice.analyzer import analyze
    _step(1, 2, f"Reading corpus: {args.corpus}")
    texts, files = _load_corpus(args.corpus)
    total_words = sum(len(t.split()) for t in texts)
    _ok(f"{len(files)} files, {total_words:,} words")
    _step(2, 2, "Analyzing voice...")
    t0 = time.time()
    profile = analyze(texts, author_name=args.author or "unknown")
    out = args.out or "voice_profile.json"
    profile.save(out)
    print()
    print(profile.summary())
    print()
    _ok(f"Profile saved: {out}  ({time.time()-t0:.1f}s)")


def cmd_generate(args):
    from yoos_app.voice.analyzer import VoiceProfile
    from yoos_app.voice.generator import generate
    from yoos_app.audit import audit
    from yoos_app.voice.scorer import score
    if not Path(args.profile).exists():
        _fail(f"Profile not found: {args.profile}")
    _step(1, 3, f"Loading profile: {args.profile}")
    profile = VoiceProfile.load(args.profile)
    _ok(f"{profile.author_name} — {profile.text_count} texts, {profile.total_words:,} words")
    _step(2, 3, f"Generating '{args.topic}' ({args.type}) via {args.backend}...")
    t0 = time.time()
    try:
        kwargs = {}
        if getattr(args, "model", None):
            kwargs["model"] = args.model
        content = generate(profile, args.type, args.topic, backend=args.backend, **kwargs)
    except RuntimeError as e:
        _fail(str(e))
    _ok(f"{len(content.split()):,} words ({time.time()-t0:.0f}s)")
    _step(3, 3, "Auditing...")
    result = audit(content, profile)
    sim = score(content, profile)
    _ok(f"Score: {result.total_score}/100 ({'PASS' if result.passed() else 'FAIL'}) | similarity: {sim:.2f}")
    if result.issues:
        _warn(f"Issues: {', '.join(result.issues)}")
    out = args.out or "output.txt"
    Path(out).write_text(content, encoding="utf-8")
    _ok(f"Saved: {out}")
    if getattr(args, "verbose", False):
        print("\n" + result.report())


def cmd_export(args):
    from yoos_app.exporter.writer import save_local, save_google_drive, save_wordpress
    if not Path(args.input).exists():
        _fail(f"Input not found: {args.input}")
    content = Path(args.input).read_text(encoding="utf-8")
    fmts = [f.strip() for f in (args.format or "html").split(",")]
    dest = args.dest or "downloads"
    for i, fmt in enumerate(fmts):
        _step(i+1, len(fmts), f"Exporting {fmt.upper()} to {dest}...")
        try:
            if dest == "google_drive":
                _ok(f"Google Drive: {save_google_drive(content, args.title, fmt)}")
            elif dest == "wordpress":
                publish = getattr(args, "publish", False)
                _ok(f"WordPress {'published' if publish else 'draft'}: {save_wordpress(content, args.title, publish=publish)}")
            else:
                _ok(f"Saved: {save_local(content, args.title, fmt, dest)}")
        except RuntimeError as e:
            _fail(str(e))


def cmd_run(args):
    from yoos_app.voice.analyzer import analyze
    from yoos_app.voice.generator import generate
    from yoos_app.audit import audit
    from yoos_app.voice.scorer import score
    from yoos_app.exporter.writer import save_local, save_wordpress, save_google_drive
    STEPS = 5
    _step(1, STEPS, f"Reading corpus: {args.corpus}")
    texts, files = _load_corpus(args.corpus)
    _ok(f"{len(files)} files, {sum(len(t.split()) for t in texts):,} words")
    _step(2, STEPS, "Analyzing voice...")
    profile = analyze(texts, author_name=args.author or "unknown")
    _ok(profile.summary().split("\n")[0])
    if getattr(args, "save_profile", None):
        profile.save(args.save_profile)
        _ok(f"Profile: {args.save_profile}")
    _step(3, STEPS, f"Generating '{args.topic}' ({args.type or 'travel_blog'}) via {args.backend or 'auto'}...")
    t0 = time.time()
    try:
        kwargs = {}
        if getattr(args, "model", None):
            kwargs["model"] = args.model
        content = generate(profile, args.type or "travel_blog", args.topic,
                           backend=args.backend or "auto", **kwargs)
    except RuntimeError as e:
        _fail(str(e))
    _ok(f"{len(content.split()):,} words ({time.time()-t0:.0f}s)")
    _step(4, STEPS, "Auditing...")
    result = audit(content, profile)
    sim = score(content, profile)
    _ok(f"Score: {result.total_score}/100 | similarity: {sim:.2f}")
    if result.issues:
        _warn(f"Issues: {', '.join(result.issues)}")
    _step(5, STEPS, "Exporting...")
    fmts = [f.strip() for f in (args.format or "html,txt").split(",")]
    dest = args.dest or "downloads"
    for fmt in fmts:
        try:
            if dest == "wordpress":
                publish = getattr(args, "publish", False)
                _ok(f"WordPress {'published' if publish else 'draft'}: {save_wordpress(content, args.topic, publish=publish)}")
                break
            elif dest == "google_drive":
                _ok(f"Google Drive ({fmt}): {save_google_drive(content, args.topic, fmt)}")
            else:
                _ok(f"Saved ({fmt}): {save_local(content, args.topic, fmt, dest)}")
        except RuntimeError as e:
            _fail(str(e))
    print(f"\nDone. Score: {result.total_score}/100 | {len(content.split()):,} words")


def cmd_demo(_args):
    from yoos_app.demo.__main__ import run
    run()


def main():
    parser = argparse.ArgumentParser(
        prog="yoos-app",
        description="YOOS-APP — Universal Author Voice Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--version", action="version", version="yoos-app 1.0.0")
    sub = parser.add_subparsers(dest="command", metavar="command")

    p_a = sub.add_parser("analyze", help="Extract voice profile from corpus folder")
    p_a.add_argument("--corpus", required=True, help="Folder or file with author texts")
    p_a.add_argument("--author", default="unknown", help="Author name")
    p_a.add_argument("--out", default="voice_profile.json", help="Output JSON path")

    p_g = sub.add_parser("generate", help="Generate content from a voice profile")
    p_g.add_argument("--profile", required=True, help="voice_profile.json path")
    p_g.add_argument("--type", default="travel_blog",
                     choices=["travel_blog","travel_guide","magazine","news","story","column"])
    p_g.add_argument("--topic", required=True)
    p_g.add_argument("--backend", default="auto",
                     choices=["auto","openai","anthropic","openrouter","ollama","codex"])
    p_g.add_argument("--model", help="Override model (e.g. gpt-4o, claude-opus-4-8)")
    p_g.add_argument("--out", default="output.txt")
    p_g.add_argument("--verbose", action="store_true")

    p_e = sub.add_parser("export", help="Export content to a destination")
    p_e.add_argument("--input", required=True)
    p_e.add_argument("--title", required=True)
    p_e.add_argument("--format", default="html", help="html, pdf, txt (comma-separated ok)")
    p_e.add_argument("--dest", default="downloads",
                     help="downloads | desktop | /path | google_drive | wordpress")
    p_e.add_argument("--publish", action="store_true", help="Publish to WordPress immediately")

    p_r = sub.add_parser("run", help="Full pipeline in one command")
    p_r.add_argument("--corpus", required=True)
    p_r.add_argument("--author", default="unknown")
    p_r.add_argument("--type", default="travel_blog",
                     choices=["travel_blog","travel_guide","magazine","news","story","column"])
    p_r.add_argument("--topic", required=True)
    p_r.add_argument("--backend", default="auto",
                     choices=["auto","openai","anthropic","openrouter","ollama","codex"])
    p_r.add_argument("--model")
    p_r.add_argument("--format", default="html,txt")
    p_r.add_argument("--dest", default="downloads",
                     help="downloads | desktop | /path | google_drive | wordpress")
    p_r.add_argument("--publish", action="store_true")
    p_r.add_argument("--save-profile", metavar="FILE",
                     dest="save_profile", help="Also save voice profile to this path")

    sub.add_parser("demo", help="Run built-in demo (Mark Twain corpus, no key needed)")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    try:
        {"analyze": cmd_analyze, "generate": cmd_generate,
         "export": cmd_export, "run": cmd_run, "demo": cmd_demo}[args.command](args)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
