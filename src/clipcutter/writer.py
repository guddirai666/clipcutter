"""Hook text, title, description and hashtags, in Gen Z voice.

Providers (config llm.provider):
  claude    - Anthropic API (best quality; needs ANTHROPIC_API_KEY or `ant auth login`)
  ollama    - local model via Ollama (free, offline)
  templates - built-in Gen Z lines, no AI at all (free, instant)
  auto      - claude if credentials exist, else ollama if running, else templates
"""
from __future__ import annotations

import json
import os
import random
import re
import urllib.request
from pathlib import Path

BANNED = ["epic", "awesome", "check this out", "amazing", "incredible", "you won't believe"]

STYLE_GUIDE = {
    "genz": (
        "Write like a Gen Z TikTok clipper. all lowercase, short, chaotic, funny. "
        "Use slang naturally (bro, fr, ong, nah, lowkey, cooked, aura, crashing out, "
        "built different, he's him, the way he—). Use 1-2 emoji max from 💀😭🔥😳🫠🫡. "
        f"Never use these cringe words: {', '.join(BANNED)}."
    ),
    "hype": "Write like a high-energy gaming highlights channel. CAPS for impact, 1 emoji max.",
    "clean": "Write clear, punchy, professional titles. No slang, no emoji.",
}

# situation -> hook lines (game-neutral: the game name comes from the topic pack below)
TEMPLATES = [
    (r"\bcops?\b|police|wanted|chase|arrest|stars", [
        "nah these cops are NOT real 😭", "bro had 5 stars in 0.2 seconds 💀",
        "these cops are built different fr", "he really tried to outrun them 😭"]),
    (r"\bcrash|\bcar\b|drive|drift|\bbike\b|plane|heli", [
        "bro cannot drive to save his life 💀", "the way he crashed— 🫠",
        "the physics got me crying 😭", "who gave him a license fr 💀"]),
    (r"\bdie\b|\bdead\b|died|\bkill|\bshot\b|wasted", [
        "he's so cooked 💀", "bro did NOT see that coming 😭",
        "wasted in record time fr", "the aura loss here is crazy 💀"]),
    (r"heist|\bbank\b|\brob\b|robbery", [
        "worst heist of all time ong 😭", "bro thought he was in a movie 💀",
        "the heist went left real quick 🫠"]),
]
GENERIC = [
    "wait for it… 💀", "bro really thought he was him 😭", "nah this is crazy 😳",
    "the way he just— 🫠", "he's cooked fr 💀", "i can't believe this happened 😭",
    "nobody was ready for this 😭", "this part goes crazy fr 🔥", "his reaction is everything 😭",
    "chat lost it here 💀", "this is peak content fr 🔥", "bro did not see that coming 😳",
]

# topic packs: matched against title + transcript, most specific first. Hooks never name a game
# the video isn't about (a GTA V stream must not get "GTA 6" hooks).
TOPICS = [
    ("gta6", r"\bgta\s*(6|vi)\b|gta6|grand theft auto (6|vi)\b|vice city|leonida|जीटीए\s*6|ग्तिया\s*6",
     ["gta 6 is actually unreal fr 🔥", "rockstar cooked with gta 6 🔥", "vice city really said welcome back 😳",
      "nobody expected this in gta 6 😳", "gta 6 physics are NOT real 😭", "this is why we waited 12 years for gta 6 😭"],
     ["bhai GTA 6 mein ye bhi hai?? 😳", "GTA 6 ka level hi alag hai 🔥", "rockstar ne bawaal kar diya 💀",
      "ye dekh ke GTA 5 bhool jaoge 😭", "vice city wapas aa gaya bhai 🔥", "GTA 6 mein ye kisne socha tha 😳",
      "GTA 6 ka sabse pagal moment 🔥"],
     ["#gta6", "#gtavi", "#gta", "#gaming"]),
    ("gta5", r"\bgta\s*(5|v)\b|gta5|grand theft auto (5|v)\b|los santos|gta online|\brp\b|roleplay|nopixel|fivem|जीटीए\s*5",
     ["los santos is undefeated 😭", "only in gta rp 😭", "the rp went left real quick 🫠",
      "gta players are built different 💀", "this server is unhinged fr 😭", "rockstar never planned for this 💀"],
     ["bhai los santos mein ye kya ho gaya 💀", "GTA V ka sabse pagal moment 🔥", "bhai ne poora server hila diya 😭",
      "GTA RP ka scene hi alag hai 😭", "ye sirf GTA mein ho sakta hai 😭"],
     ["#gta5", "#gtav", "#gtarp", "#gaming"]),
    ("gta", r"\bgta\b|grand theft auto|जीटीए|ग्तिया|rockstar",
     ["this is why gta is undefeated 🔥", "only in gta 😭", "rockstar cooked with this one 🔥"],
     ["bhai GTA ka level hi alag hai 🔥", "ye sirf GTA mein ho sakta hai 😭"],
     ["#gta", "#gaming"]),
    ("minecraft", r"minecraft|creeper|enderman|\bnether\b|माइनक्राफ्ट",
     ["the creeper had other plans 💀", "minecraft players will understand 😭", "bro lost everything in 2 seconds 😭",
      "this is why we don't dig straight down 💀"],
     ["bhai creeper ne sab uda diya 💀", "minecraft mein ye kya ho gaya 😭"],
     ["#minecraft", "#gaming"]),
    ("fortnite", r"fortnite|victory royale",
     ["that victory royale was disrespectful 😭", "bro built a whole house in 0.3 seconds 💀", "the zone had other plans 😭"],
     ["bhai ka fortnite skill dekho 🔥"], ["#fortnite", "#gaming"]),
    ("valorant", r"valorant|\bvandal\b|\bphantom\b|\bspike\b",
     ["that clutch was illegal 😳", "bro hit the 1v5 💀", "the aim is not human fr 🔥"],
     ["bhai ka aim dekho 😳", "ye clutch illegal hai 🔥"], ["#valorant", "#gaming"]),
    ("bgmi", r"\bbgmi\b|\bpubg\b|chicken dinner|erangel",
     ["chicken dinner in the craziest way 🔥", "bro wiped the whole squad 💀"],
     ["bhai ne poora squad wipe kar diya 🔥", "ye clutch dekh ke hil gaye 😳"], ["#bgmi", "#pubg", "#gaming"]),
    ("cs", r"counter[- ]?strike|\bcs2\b|\bcsgo\b",
     ["that ace was not legal 😳", "bro read their minds 💀"], ["bhai ka ace dekho 🔥"], ["#cs2", "#gaming"]),
    ("irl", r"podcast|\birl\b|just chatting|reacts?\b|reaction",
     ["he really said this on stream 😭", "chat could not believe this 💀", "the way he said it 😭"],
     ["bhai ne live pe ye bol diya 😭", "chat bhi shock ho gaya 💀"], ["#podcast", "#reaction"]),
]
HYPE_EN = re.compile(r"\b(no way|oh my god|omg|what|bro|bruh|let'?s go|run|help|wtf|dude|holy|insane|crazy|"
                     r"dead|nah|stop|why|how|wait|look)\b|!", re.I)


def topic_of(title: str, transcript: str) -> tuple | None:
    """The title decides first (it's reliable); the transcript only if the title says nothing."""
    for blob in (title.lower(), transcript.lower()):
        for t in TOPICS:
            if re.search(t[1], blob, re.I):
                return t
    return None


STRONG_EN = re.compile(r"\b(no way|oh my god|oh my gosh|let'?s go+|holy|insane|crazy|unreal|bro|dude|bruh|"
                       r"what the|wtf|run|help me|i'?m dead|we'?re dead|i'?m done|are you serious|"
                       r"no no|stop|why would|how did)\b|!", re.I)
PROFANITY = [(r"\bfuck", "f*ck"), (r"\bshit", "sh*t"), (r"\bbitch", "b*tch"), (r"\bass\b", "a**"),
             (r"\bdamn", "d*mn")]


def censor(text: str) -> str:
    for pat, rep in PROFANITY:
        text = re.sub(pat, rep, text, flags=re.I)
    return text


def quote_hook(transcript: str, rnd: random.Random) -> str | None:
    """Turn the streamer's own best line into the hook: what works best on English clips.
    Only complete short sentences with a real reaction in them; profanity is masked."""
    if is_hindi(transcript):
        return None
    clean = re.sub(r"\[[^\]]*\]|>>", " ", transcript)
    sentences = [p.strip(" ,.-\"'") for p in re.split(r"(?<=[.!?])\s+", clean) if p.strip()]
    good = [p for p in sentences if 3 <= len(p.split()) <= 8 and STRONG_EN.search(p)
            and not re.search(r"http|\d{3,}", p)]
    if not good:
        return None
    q = min(good, key=lambda p: (-len(STRONG_EN.findall(p)), -p.count("!"), len(p)))
    q = censor(q.lower().rstrip("."))
    return rnd.choice([f'"{q}" 💀', f'he really said "{q}" 😭', f'"{q}"… 😳', f'the way he said "{q}" 😭'])


# Hinglish (Roman Hindi) Gen Z hooks for Hindi videos
HI_TEMPLATES = [
    (r"cop|police|पुलिस|wanted|chase", ["bhai police ne toh hila diya 😭", "ye cops real hai kya 💀"]),
    (r"crash|car|गाड़ी|गाडी|drive", ["bhai ye driving dekho 💀", "physics ne toh pagal kar diya 😭"]),
    (r"detail|feature|फीचर|डिटेल|realistic|रियलिस्टिक", [
        "ye detail kisi ne notice nahi ki 😳", "bhai ye feature sach mein hai?? 😳",
        "GTA 6 ka ye detail dekh ke hil gaya 🫠"]),
]
HI_GTA = ["bhai GTA 6 mein ye bhi hai?? 😳", "GTA 6 ka level hi alag hai 🔥", "rockstar ne bawaal kar diya 💀",
          "ye dekh ke GTA 5 bhool jaoge 😭", "vice city wapas aa gaya bhai 🔥", "GTA 6 mein ye kisne socha tha 😳",
          "bhai ye game nahi, movie hai 🫠", "rockstar ne dimaag hila diya 💀", "ye scene dekh ke hasi ruki nahi 😭",
          "GTA 6 ka sabse pagal moment 🔥"]
HI_GENERIC = ["bhai ye kya ho gaya 💀", "end tak dekhna 😳", "ye toh bawaal hai 🔥", "koi isko roko 😭",
              "bhai ne toh hila diya 🫠", "ye part sabse best hai 🔥", "iske baad jo hua 😳", "bhai full pagalpan 💀",
              "ye moment miss mat karna 🔥", "kisi ne socha nahi tha ye hoga 😭", "bhai ka reaction dekho 😂",
              "ye clip viral hogi pakka 🔥"]
HI_QUESTIONS = ["tumhe kya laga? comment karo 👇", "GTA 6 ke liye ready ho? 😳", "1-10 rating do 🔥",
                "isse better kuch dekha hai? 💀"]

GTA_RE = re.compile(r"gta|grand theft|vice city|leonida|rockstar|जीटीए|ग्तिया|जीटीए|रॉकस्टार", re.I)
DEVANAGARI = re.compile(r"[\u0900-\u097F]")
BASE_TAGS = ["#fyp", "#viral", "#clips", "#trending"]
GTA_TAGS = ["#gta6", "#gtavi", "#gta", "#gaming"]

CAPTION_EMOJI_HI = [
    ("भाई", "💀"), ("पागल", "🤯"), ("बवाल", "🔥"), ("गज़ब", "🔥"), ("गजब", "🔥"), ("क्या", "😳"),
    ("हाहा", "😭"), ("मज़ा", "🔥"), ("रियलिस्टिक", "😳"), ("बाप", "😭"),
]
CAPTION_EMOJI = [
    (r"^(lol|lmao|haha+|hahaha+)$", "😭"), (r"^(dead|died|cooked|rip)$", "💀"),
    (r"^(fire|insane|crazy)$", "🔥"), (r"^(what|how|wait)\??$", "😳"),
    (r"^(bro|bruh)$", "💀"), (r"^(no way|omg)$", "😳"),
    (r"^(bhai|bhaiyon)$", "💀"), (r"^(kya)\??$", "😳"), (r"^(pagal|pagalpan)$", "🤯"), (r"^(bawaal|bawal)$", "🔥"),
    (r"^(gazab|kamaal|kamal)$", "🔥"), (r"^(haha+|hahaha+)$", "😭"),
]


def caption_emoji(word: str) -> str:
    for hw, emo in CAPTION_EMOJI_HI:
        if hw in word:
            return emo
    w = re.sub(r"[^\w' ]", "", word.lower())
    for pat, emo in CAPTION_EMOJI:
        if re.match(pat, w):
            return emo
    return ""


def _clean(text: str, style: str) -> str:
    text = text.strip()
    if len(text) > 1 and text[0] == text[-1] == '"':   # only unwrap fully-quoted text, keep quote hooks intact
        text = text[1:-1].strip()
    for b in BANNED:
        text = re.sub(re.escape(b), "", text, flags=re.I)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text.lower() if style == "genz" else text


# ---------- providers ----------

_FAILED: set[str] = set()  # providers that failed this run; don't retry them per clip


def _has_claude_creds() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY")) or (Path.home() / ".config" / "anthropic").exists()


def _ollama_up() -> bool:
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=0.5)
        return True
    except Exception:
        return False


def _prompt(transcript: str, chat: list[str], title: str) -> str:
    chat_part = "\n".join(f"- {c}" for c in chat[:25]) or "(no chat)"
    lang = ("The speaker talks in Hindi: write hooks in Hinglish (Hindi in Roman letters, "
            "like 'bhai ye kya ho gaya 💀'). " if is_hindi(transcript) else
            "Write in natural, current English the way top US clippers do. ")
    t = topic_of(title, transcript)
    if t:
        lang += (f"The video is about {t[0].upper()}. Only mention that game, never a different one "
                 "(e.g. don't call a GTA V stream GTA 6). ")
    lang += "If the speaker says a short, wild line, quoting it in the hook often works best. "
    return (
        f"A clip from the video \"{title}\". {lang}Transcript of what the speaker says:\n\"\"\"{transcript}\"\"\"\n\n"
        f"Chat reactions at the peak moment:\n{chat_part}\n\n"
        "Return ONLY a JSON object with keys:\n"
        '  "hooks": 3 different on-screen hook texts (max 8 words each) shown in the first 2 seconds. '
        "Create a curiosity gap; don't spoil the ending.\n"
        '  "best": index (0-2) of the strongest hook\n'
        '  "title": video title (max 70 chars)\n'
        '  "description": one short line for the post caption, ending with a question that baits comments\n'
        '  "hashtags": 5-8 hashtags'
    )


def _claude(prompt: str, system: str, model: str) -> dict | None:
    import anthropic

    client = anthropic.Anthropic()
    kwargs = {}
    if model in ("claude-opus-5-5", "claude-opus-5", "claude-fable-5-2", "claude-fable-5-1"):
        kwargs = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
    resp = client.beta.messages.create(
        model=model,
        max_tokens=2000,
        system=system,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": prompt}],
        **kwargs,
    )
    if resp.stop_reason == "refusal":
        return None
    text = "".join(b.text for b in resp.content if b.type == "text")
    return _json(text)


def _ollama(prompt: str, system: str, model: str) -> dict | None:
    body = json.dumps({"model": model, "system": system, "prompt": prompt,
                       "format": "json", "stream": False}).encode()
    req = urllib.request.Request("http://localhost:11434/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return _json(json.loads(r.read())["response"])


def _json(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def is_hindi(text: str) -> bool:
    return len(DEVANAGARI.findall(text)) > 0.3 * max(1, len(re.sub(r"\s", "", text)))


def _templates(transcript: str, chat: list[str], seed: int, title: str = "", avoid: set | None = None) -> dict:
    rnd = random.Random(seed)
    blob = (transcript + " " + " ".join(chat)).lower()
    topic = topic_of(title, transcript)
    hindi = is_hindi(transcript)
    avoid = avoid or set()
    pool: list[str] = []
    if hindi:
        for pat, lines in HI_TEMPLATES:
            if re.search(pat, blob):
                pool += [ln for ln in lines if topic and topic[0] == "gta6" or "6" not in ln]
        pool += topic[3] if topic else HI_GENERIC
        if not topic or len(pool) < 6:
            pool += HI_GENERIC
        questions = HI_QUESTIONS if topic and topic[0] == "gta6" else [q for q in HI_QUESTIONS if "GTA" not in q]
    else:
        for pat, lines in TEMPLATES:
            if re.search(pat, blob):
                pool += lines
        pool += (topic[2] if topic else []) + GENERIC
        questions = ["who's fault was this 💀", "rate this 1-10 😭", "would you have survived this?",
                     "be honest… 💀", "tag someone who needs to see this 😭"]
    hook = None
    q = quote_hook(transcript, rnd)
    phrase = q.split('"')[1] if q and q.count('"') >= 2 else None
    if q and not any(phrase in a for a in avoid) and rnd.random() < 0.6:   # their own words beat any template
        hook = q                                                          # (each line used once per video)
    if not hook and topic:   # lines written for this game/channel come first
        own = [h for h in (topic[3] if hindi else topic[2]) if h.lower() not in avoid]
        if own and rnd.random() < 0.65:
            hook = rnd.choice(own)
    if not hook:
        fresh = [h for h in pool if h.lower() not in avoid]   # every clip of a video gets its own hook
        hook = rnd.choice(fresh or pool)
    tags = (topic[4] if topic else ["#gaming"] if "gaming" in title.lower() else []) \
        + (["#hindi", "#india"] if hindi else []) + BASE_TAGS
    return {"hooks": [hook], "best": 0, "title": hook if len(hook) < 60 else hook[:57] + "…",
            "description": rnd.choice(questions), "hashtags": tags}


def write(transcript: str, chat: list[str], cfg: dict, seed: int, title: str = "", avoid: set | None = None) -> dict:
    style = cfg["style"]
    llm = cfg["llm"]
    provider = llm["provider"]
    if provider == "auto":
        provider = "claude" if _has_claude_creds() else ("ollama" if _ollama_up() else "templates")
    if provider in _FAILED:
        provider = "templates"

    system = "You write viral short-form video hooks and captions for gaming clips. " + STYLE_GUIDE[style]
    data = None
    used = provider
    try:
        if provider == "claude":
            data = _claude(_prompt(transcript, chat, title), system, llm["model"])
        elif provider == "ollama":
            data = _ollama(_prompt(transcript, chat, title), system, llm["ollama_model"])
    except Exception as e:  # network down, no credits, etc. -> never block the pipeline
        print(f"   ! {provider} failed ({type(e).__name__}: {e}); using templates for the rest of this run")
        _FAILED.add(provider)
    if not data or not data.get("hooks"):
        data = _templates(transcript, chat, seed, title, avoid)
        used = "templates"

    hooks = [str(h) for h in data["hooks"]]
    best = data.get("best", 0)
    hook = hooks[best if isinstance(best, int) and 0 <= best < len(hooks) else 0]
    tags = [t if t.startswith("#") else "#" + t for t in data.get("hashtags") or BASE_TAGS]
    if "#fyp" not in tags:
        tags.append("#fyp")
    return {
        "hook": _clean(hook, style),
        "title": _clean(str(data.get("title", hook)), style),
        "description": _clean(str(data.get("description", "")), style),
        "hashtags": tags[:10],
        "writer": used,
    }
