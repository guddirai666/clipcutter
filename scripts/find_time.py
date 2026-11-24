#!/usr/bin/env python
"""Find the exact timestamp of a line in a video's captions.

You know the moment ("ek tiger hai yahan pe") but not when it happens. This asks the platform for
its own auto-captions (a few hundred KB, no video download) and prints where each line lands, plus
a ready-to-use `--at` span for `clipcutter run`.

    uv run python scripts/find_time.py "https://youtu.be/169ZzvPxvvM" "ek tiger hai yahan pe"
    uv run python scripts/find_time.py .work/169ZzvPxvvM/169ZzvPxvvM.hi-orig.json3 "chor ke ghar mein chori"

A local .json3/.json caption file works too, so this is useful on captions you already downloaded.
"""
from __future__ import annotations

import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

KEEP = re.compile(r"[^\w\u0900-\u097F']+", re.UNICODE)   # keep Devanagari matras (not \w on their own)


def norm(text: str) -> str:
    return KEEP.sub(" ", text.lower()).strip()


def tokens(words: list[dict], roman: bool = False) -> list[tuple[str, float]]:
    """[(word, start seconds)]; roman=True transliterates Hindi first, so a Hinglish quote matches.

    Captions for Hindi streams come down in Devanagari ("चोर के घर में चोरी"), but people quote them
    in Hinglish ("chor ke ghar mein chori"). We try both and keep whichever matches better.
    """
    from clipcutter import translit

    out = []
    for w in words:
        clean = norm(translit.hinglish(w["w"]) if roman else w["w"])
        if clean:
            out.append((clean, float(w["s"])))
    return out


def best_span(toks: list[tuple[str, float]], quote: str) -> tuple[float, float, float, str]:
    """Longest-matching window for `quote` -> (start, end, ratio, matched text)."""
    want = norm(quote).split()
    if not want:
        raise SystemExit("empty quote")
    flat = [t for t, _ in toks]
    best = (0, 0, 0.0)
    matcher = SequenceMatcher(None, autojunk=False)
    for size in range(max(1, len(want) - 2), min(len(want) + 6, len(flat)) + 1):
        matcher.set_seq2(want)
        for i in range(len(flat) - size + 1):
            window = flat[i:i + size]
            if want[0] not in window[:2]:          # cheap filter: quote starts near the window start
                continue
            matcher.set_seq1(window)
            ratio = matcher.ratio()
            if ratio > best[2]:
                best = (i, size, ratio)
    i, size, ratio = best
    if size == 0:
        return 0.0, 0.0, 0.0, ""
    start = toks[i][1]
    end = toks[min(i + size, len(toks)) - 1][1]
    matched = " ".join(flat[i:i + size])
    return start, start + max(1.0, end - start + 0.8), ratio, matched


def fetch_subs(target: str, work: Path) -> Path:
    """Download just the captions (json3, with per-word timings) with yt-dlp."""
    import yt_dlp

    work.mkdir(parents=True, exist_ok=True)
    opts = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["hi-orig", "hi", "en-orig", "en"],
        "subtitlesformat": "json3",
        "outtmpl": str(work / "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "js_runtimes": {"node": {}},     # YouTube 403s without a JS runtime; same rule as ingest.py
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([target])
    files = sorted(work.glob("*.json3"), key=lambda p: ("orig" not in p.name, p.name))
    if not files:
        raise SystemExit(f"no captions for {target} (try --subs-langs with another language)")
    return files[0]


def mmss(sec: float) -> str:
    s = int(round(sec))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def main() -> None:
    args = sys.argv[1:]
    if len(args) < 2:
        raise SystemExit(__doc__)
    target, quotes = args[0], args[1:]

    from clipcutter import ingest

    path = Path(target)
    if not path.exists():
        path = fetch_subs(target, Path(".work/subs"))
    words = ingest.caption_words(path)
    if not words:
        raise SystemExit(f"{path}: no words in these captions")
    toks_deva = tokens(words)
    print(f"{path.name}: {len(words)} words, last at {mmss(toks_deva[-1][1])}\n")

    toks_roman = tokens(words, roman=True)

    for quote in quotes:
        start, end, ratio, matched = max((best_span(toks_deva, quote), best_span(toks_roman, quote)),
                                         key=lambda c: c[2])
        flag = "" if ratio >= 0.72 else "   <- low match, check the quote"
        print(f'{quote!r}\n  {mmss(start)} - {mmss(end)}  (match {ratio:.2f}){flag}')
        if matched:
            print(f"  heard: {matched[:110]}")
        a = max(0, int(start) - 10)
        print(f"  -> --at {mmss(a)}-{mmss(start + max(30, int(end - start)) + 10)}\n")


if __name__ == "__main__":
    main()
