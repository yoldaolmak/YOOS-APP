#!/usr/bin/env python3
"""
Pennovia CLI — Open-source author voice toolkit

Commands:
  analyze   Extract voice profile from a corpus folder
  generate  Generate content from a saved voice profile
  export    Export content to a destination in a chosen format
  run       Full pipeline: corpus → analyze → generate → export
  demo      Run the built-in demo

Examples:
  pennovia analyze --corpus ./texts/ --author "Hemingway" --out hem.json
  pennovia generate --profile hem.json --type travel_blog --topic "Cuba" --backend openai
  pennovia export --input out.txt --title "Cuba Morning" --format pdf --dest desktop
  pennovia run --corpus ./texts/ --type magazine --topic "Tokyo streets" --dest wordpress
  pennovia demo
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

def _export_formats(raw, destination, default):
    """Validate formats before creating files or making network requests."""
    formats = [value.strip().lower() for value in (raw if raw is not None else default).split(",")]
    supported = {"html", "pdf", "txt"}
    if not formats or any(value not in supported for value in formats):
        _fail("Unsupported export format. Supported formats are html, pdf and txt.")
    if len(set(formats)) != len(formats):
        _fail("Duplicate export formats are not allowed.")
    if destination == "wordpress" and formats != ["html"]:
        _fail("WordPress export accepts one HTML format only (--format html).")
    return formats


def _check_output_path(path, overwrite):
    """Refuse an accidental overwrite before doing expensive work."""
    if not overwrite and Path(path).exists():
        _fail(f"Output already exists: {path}. Use --overwrite to replace it.")


def _load_corpus(corpus_path):
    from pennovia.ingestion.reader import SUPPORTED_EXTENSIONS, read_corpus

    path = Path(corpus_path)
    if not path.exists():
        _fail(f"Corpus path not found: {corpus_path}")

    if path.is_dir():
        files = [
            str(candidate)
            for candidate in sorted(path.iterdir())
            if candidate.is_file() and candidate.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
    elif path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
        files = [str(path)]
    else:
        _fail(f"Corpus must be a file or directory with supported TXT, HTML or PDF files: {corpus_path}")

    if not files:
        _fail(f"No supported TXT, HTML or PDF files found in: {corpus_path}")
    texts = read_corpus(files)
    if not texts:
        _fail("No usable corpus texts (each file must have more than 50 words).")
    return texts, files

def cmd_analyze(args):
    from pennovia.voice.analyzer import analyze
    out = args.out or "voice_profile.json"
    _check_output_path(out, getattr(args, "overwrite", False))
    _step(1, 2, f"Reading corpus: {args.corpus}")
    texts, files = _load_corpus(args.corpus)
    total_words = sum(len(t.split()) for t in texts)
    _ok(f"{len(texts)} usable of {len(files)} files, {total_words:,} words")
    _step(2, 2, "Analyzing voice...")
    t0 = time.time()
    profile = analyze(texts, author_name=args.author or "unknown", language=args.language)
    profile.save(out, overwrite=getattr(args, "overwrite", False))
    print()
    print(profile.summary())
    print()
    _ok(f"Profile saved: {out}  ({time.time()-t0:.1f}s)")


def cmd_generate(args):
    from pennovia.voice.analyzer import VoiceProfile
    from pennovia.voice.generator import generate
    from pennovia.audit import audit
    from pennovia.voice.scorer import score
    from pennovia.storage import write_private_text
    out = args.out or "output.txt"
    _check_output_path(out, getattr(args, "overwrite", False))
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
    write_private_text(out, content, overwrite=getattr(args, "overwrite", False))
    _ok(f"Saved: {out}")
    if getattr(args, "verbose", False):
        print("\n" + result.report())


def cmd_export(args):
    from pennovia.exporter.writer import save_local, save_google_drive, save_wordpress
    if not Path(args.input).exists():
        _fail(f"Input not found: {args.input}")
    content = Path(args.input).read_text(encoding="utf-8")
    dest = args.dest or "downloads"
    fmts = _export_formats(args.format, dest, "html")
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
        except (RuntimeError, ValueError) as e:
            _fail(str(e))


def cmd_run(args):
    dest = args.dest or "downloads"
    fmts = _export_formats(args.format, dest, "html" if dest == "wordpress" else "html,txt")
    if getattr(args, "save_profile", None):
        _check_output_path(args.save_profile, getattr(args, "overwrite", False))
    from pennovia.voice.analyzer import analyze
    from pennovia.voice.generator import generate
    from pennovia.audit import audit
    from pennovia.voice.scorer import score
    from pennovia.exporter.writer import save_local, save_wordpress, save_google_drive
    STEPS = 5
    _step(1, STEPS, f"Reading corpus: {args.corpus}")
    texts, files = _load_corpus(args.corpus)
    _ok(f"{len(texts)} usable of {len(files)} files, {sum(len(t.split()) for t in texts):,} words")
    _step(2, STEPS, "Analyzing voice...")
    profile = analyze(texts, author_name=args.author or "unknown", language=args.language)
    _ok(profile.summary().split("\n")[0])
    if getattr(args, "save_profile", None):
        profile.save(args.save_profile, overwrite=getattr(args, "overwrite", False))
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
        except (RuntimeError, ValueError) as e:
            _fail(str(e))
    print(f"\nDone. Score: {result.total_score}/100 | {len(content.split()):,} words")


def cmd_demo(_args):
    from pennovia.demo.__main__ import run
    run()


def main():
    parser = argparse.ArgumentParser(
        prog="pennovia",
        description="Pennovia — Open-source author voice toolkit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    from pennovia import __version__
    parser.add_argument("--version", action="version", version=f"pennovia {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="command")

    p_a = sub.add_parser("analyze", help="Extract voice profile from corpus folder")
    p_a.add_argument("--corpus", required=True, help="Folder or file with author texts")
    p_a.add_argument("--author", default="unknown", help="Author name")
    p_a.add_argument("--language", choices=["auto", "tr", "en"], default="auto",
                     help="Corpus language; auto abstains when uncertain")
    p_a.add_argument("--out", default="voice_profile.json", help="Output JSON path")
    p_a.add_argument("--overwrite", action="store_true", help="Replace existing profile output")

    p_g = sub.add_parser("generate", help="Generate content from a voice profile")
    p_g.add_argument("--profile", required=True, help="voice_profile.json path")
    p_g.add_argument("--type", default="travel_blog",
                     choices=["travel_blog","travel_guide","magazine","news","story","column"])
    p_g.add_argument("--topic", required=True)
    p_g.add_argument("--backend", default=os.environ.get("PENNOVIA_BACKEND", "auto"),
                     choices=["auto","openai","anthropic","openrouter","ollama","codex"])
    p_g.add_argument("--model", help="Override model (e.g. gpt-4o, claude-opus-4-8)")
    p_g.add_argument("--out", default="output.txt")
    p_g.add_argument("--overwrite", action="store_true", help="Replace existing draft output")
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
    p_r.add_argument("--language", choices=["auto", "tr", "en"], default="auto",
                     help="Corpus language; auto abstains when uncertain")
    p_r.add_argument("--type", default="travel_blog",
                     choices=["travel_blog","travel_guide","magazine","news","story","column"])
    p_r.add_argument("--topic", required=True)
    p_r.add_argument("--backend", default=os.environ.get("PENNOVIA_BACKEND", "auto"),
                     choices=["auto","openai","anthropic","openrouter","ollama","codex"])
    p_r.add_argument("--model")
    p_r.add_argument("--format", default=None,
                     help="html, pdf, txt; defaults to html,txt locally or html for WordPress")
    p_r.add_argument("--dest", default="downloads",
                     help="downloads | desktop | /path | google_drive | wordpress")
    p_r.add_argument("--publish", action="store_true")
    p_r.add_argument("--save-profile", metavar="FILE",
                     dest="save_profile", help="Also save voice profile to this path")
    p_r.add_argument("--overwrite", action="store_true", help="Replace existing --save-profile file")

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
    except FileExistsError as exc:
        _fail(f"Output already exists: {exc.filename}. Use --overwrite to replace it.")
    except (OSError, ValueError) as exc:
        _fail(str(exc))

if __name__ == "__main__":
    main()
