#!/usr/bin/env python3
"""
YOOS-APP CLI
Usage:
  yoos-app analyze  --corpus ./texts/ --author "Author Name" --out profile.json
  yoos-app generate --profile profile.json --type travel_blog --topic "Paris" --backend openai
  yoos-app export   --input content.txt --title "My Article" --format html --dest downloads
  yoos-app run      --corpus ./texts/ --type travel_guide --topic "Rome" --dest wordpress
"""
import argparse
import sys
import os
from pathlib import Path


def cmd_analyze(args):
    from yoos_app.ingestion.reader import read_corpus
    from yoos_app.voice.analyzer import analyze

    files = []
    for p in Path(args.corpus).iterdir():
        if p.suffix.lower() in (".txt", ".pdf", ".html", ".htm"):
            files.append(str(p))

    if not files:
        print(f"No readable files in {args.corpus}")
        sys.exit(1)

    print(f"Reading {len(files)} files...")
    texts = read_corpus(files)
    print(f"Analyzing {len(texts)} texts...")
    profile = analyze(texts, author_name=args.author or "unknown")
    out = args.out or "voice_profile.json"
    profile.save(out)
    print(f"Profile saved: {out}")
    print(f"  Avg sentence: {profile.avg_sentence_words} words")
    print(f"  First person: %{int(profile.first_person_rate*100)}")


def cmd_generate(args):
    from yoos_app.voice.analyzer import VoiceProfile
    from yoos_app.voice.generator import generate

    profile = VoiceProfile.load(args.profile)
    print(f"Generating '{args.topic}' as {args.type} using {args.backend}...")
    content = generate(profile, args.type, args.topic, backend=args.backend)
    out = args.out or "output.txt"
    Path(out).write_text(content, encoding="utf-8")
    print(f"Saved: {out} ({len(content.split())} words)")


def cmd_export(args):
    from yoos_app.exporter.writer import save_local, save_google_drive, save_wordpress

    content = Path(args.input).read_text(encoding="utf-8")
    fmt = args.format or "html"
    dest = args.dest or "downloads"

    if dest == "google_drive":
        url = save_google_drive(content, args.title, fmt)
        print(f"Google Drive: {url}")
    elif dest == "wordpress":
        url = save_wordpress(content, args.title)
        print(f"WordPress draft: {url}")
    else:
        path = save_local(content, args.title, fmt, dest)
        print(f"Saved: {path}")


def cmd_run(args):
    """Full pipeline: corpus → analyze → generate → export"""
    from yoos_app.ingestion.reader import read_corpus
    from yoos_app.voice.analyzer import analyze
    from yoos_app.voice.generator import generate
    from yoos_app.exporter.writer import save_local, save_wordpress

    files = [str(p) for p in Path(args.corpus).iterdir()
             if p.suffix.lower() in (".txt", ".pdf", ".html", ".htm")]
    texts = read_corpus(files)
    profile = analyze(texts, author_name=args.author or "unknown")
    content = generate(profile, args.type or "travel_blog", args.topic,
                       backend=args.backend or "openai")

    fmts = (args.format or "html,txt").split(",")
    for fmt in fmts:
        fmt = fmt.strip()
        dest = args.dest or "downloads"
        if dest == "wordpress":
            url = save_wordpress(content, args.topic)
            print(f"WordPress: {url}")
        else:
            path = save_local(content, args.topic, fmt, dest)
            print(f"Saved ({fmt}): {path}")


def main():
    parser = argparse.ArgumentParser(prog="yoos-app", description="YOOS-APP Voice Engine")
    sub = parser.add_subparsers(dest="command")

    p_analyze = sub.add_parser("analyze", help="Extract voice profile from corpus")
    p_analyze.add_argument("--corpus", required=True)
    p_analyze.add_argument("--author", default="unknown")
    p_analyze.add_argument("--out", default="voice_profile.json")

    p_gen = sub.add_parser("generate", help="Generate content from voice profile")
    p_gen.add_argument("--profile", required=True)
    p_gen.add_argument("--type", default="travel_blog",
                       choices=["travel_blog","travel_guide","magazine","news","story","column"])
    p_gen.add_argument("--topic", required=True)
    p_gen.add_argument("--backend", default="openai",
                       choices=["openai","ollama","codex"])
    p_gen.add_argument("--out", default="output.txt")

    p_exp = sub.add_parser("export", help="Export content to destination")
    p_exp.add_argument("--input", required=True)
    p_exp.add_argument("--title", required=True)
    p_exp.add_argument("--format", default="html", choices=["html","pdf","txt"])
    p_exp.add_argument("--dest", default="downloads",
                       help="downloads | desktop | /path | google_drive | wordpress")

    p_run = sub.add_parser("run", help="Full pipeline in one command")
    p_run.add_argument("--corpus", required=True)
    p_run.add_argument("--author", default="unknown")
    p_run.add_argument("--type", default="travel_blog")
    p_run.add_argument("--topic", required=True)
    p_run.add_argument("--backend", default="openai", choices=["openai","ollama","codex"])
    p_run.add_argument("--format", default="html,txt")
    p_run.add_argument("--dest", default="downloads")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    {"analyze": cmd_analyze, "generate": cmd_generate,
     "export": cmd_export, "run": cmd_run}[args.command](args)


if __name__ == "__main__":
    main()
