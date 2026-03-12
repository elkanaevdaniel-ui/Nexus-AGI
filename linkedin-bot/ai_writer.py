"""
ai_writer.py  -  LinkedIn post generation + Gemini image-prompt factory
"""

import json
import logging
import os
import re
from urllib.parse import urlparse

import requests

from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, LLM_MODEL, GOOGLE_API_KEY, STRATEGY_FILE

log = logging.getLogger(__name__)


# ── Gemini text fallback when OpenRouter is unavailable ──────────────────────
_GEMINI_MODELS = ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-1.5-pro"]


def _call_gemini(messages: list, temperature: float = 0.7,
                 max_tokens: int = 2000) -> str:
    """Call Google Gemini for text generation as fallback.
    Tries multiple models in order if one is unavailable."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GOOGLE_API_KEY)

    # Convert OpenAI-style messages to Gemini format
    system_text = ""
    user_text = ""
    for msg in messages:
        if msg["role"] == "system":
            system_text = msg["content"]
        elif msg["role"] == "user":
            user_text = msg["content"]

    config = types.GenerateContentConfig(
        temperature=temperature,
        max_output_tokens=max_tokens,
    )
    if system_text:
        config.system_instruction = system_text

    last_error = None
    for model_name in _GEMINI_MODELS:
        try:
            log.info("Trying Gemini model: %s", model_name)
            response = client.models.generate_content(
                model=model_name,
                contents=user_text or "Hello",
                config=config,
            )
            text = response.text
            if not text:
                log.warning("Gemini model %s returned empty/None response", model_name)
                continue
            log.info("Gemini model %s succeeded", model_name)
            return text.strip()
        except Exception as e:
            log.warning("Gemini model %s failed: %s", model_name, e)
            last_error = e
            continue

    raise RuntimeError(f"All Gemini models failed. Last error: {last_error}")


# ── NSFW / inappropriate domain & keyword blocklist ─────────────────────────
BLOCKED_DOMAINS = {
    # Porn / adult sites
    "xvideos.com", "pornhub.com", "xhamster.com", "xnxx.com",
    "redtube.com", "youporn.com", "tube8.com", "spankbang.com",
    "brazzers.com", "bangbros.com", "naughtyamerica.com",
    "realitykings.com", "mofos.com", "kink.com", "chaturbate.com",
    "stripchat.com", "bongacams.com", "cam4.com", "livejasmin.com",
    "myfreecams.com", "onlyfans.com", "fansly.com", "manyvids.com",
    # Hentai / anime porn
    "hanime.tv", "nhentai.net", "hentaihaven.xxx", "hentai.tv",
    "e-hentai.org", "exhentai.org", "rule34.xxx", "rule34.paheal.net",
    "gelbooru.com", "danbooru.donmai.us", "sankakucomplex.com",
    "hitomi.la", "tsumino.com", "fakku.net",
    # Other adult / NSFW
    "literotica.com", "adultfriendfinder.com", "fetlife.com",
    "imagefap.com", "motherless.com", "4chan.org",
    "theporndude.com", "pornmd.com", "fuq.com",
    "omegle.com", "chatroulette.com",
}

NSFW_URL_KEYWORDS = {
    "porn", "hentai", "xxx", "sex", "nude", "naked", "nsfw",
    "adult", "erotic", "fetish", "milf", "anal", "blowjob",
    "boobs", "pussy", "dick", "cock", "cum", "orgasm",
    "stripper", "escort", "camgirl", "onlyfans", "fansly",
    "rule34", "r34", "xrated", "x-rated", "lewd",
}


NON_ENGLISH_DOMAINS = {
    "baidu.com", "zhidao.baidu.com", "tieba.baidu.com", "wenku.baidu.com",
    "sogou.com", "qq.com", "163.com", "sina.com.cn", "csdn.net",
    "jianshu.com", "zhihu.com", "bilibili.com", "weibo.com",
    "naver.com", "daum.net",
    "yandex.ru", "mail.ru", "rambler.ru",
    "question-orthographe.fr", "commentcamarche.net", "01net.com",
}

NON_ENGLISH_TLD = {
    ".cn", ".jp", ".kr", ".ru",
    ".pl", ".cz", ".hu", ".ro", ".bg", ".ua", ".by", ".kz",
    ".ir", ".sa", ".tw",
}


def _is_non_english(url: str, title: str = "") -> bool:
    """Return True if URL or title is likely non-English content."""
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower().lstrip("www.")

        # Check known non-English domains
        if any(netloc == nd or netloc.endswith("." + nd) for nd in NON_ENGLISH_DOMAINS):
            return True

        # Check non-English TLDs
        if any(netloc.endswith(tld) for tld in NON_ENGLISH_TLD):
            return True

        # Check for non-ASCII characters in title (Chinese, Japanese, Korean, Cyrillic, etc.)
        if title:
            non_ascii = sum(1 for c in title if ord(c) > 127)
            if non_ascii > len(title) * 0.3:  # >30% non-ASCII = likely non-English
                return True

        return False
    except Exception:
        return False  # allow through on error — other filters will catch bad results


def _is_nsfw(url: str, title: str = "") -> bool:
    """Return True if URL or title contains NSFW/inappropriate content."""
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower().lstrip("www.")
        full_url_lower = url.lower()
        title_lower = title.lower()

        # Check blocked domains
        if any(netloc == bd or netloc.endswith("." + bd) for bd in BLOCKED_DOMAINS):
            return True

        # Check URL path and query for NSFW keywords
        for kw in NSFW_URL_KEYWORDS:
            if kw in full_url_lower or kw in title_lower:
                return True

        return False
    except Exception:
        return True  # block on error — safer to exclude


TRUSTED_DOMAINS = {
    # ── Government & national cyber agencies ──────────────────────────
    "cisa.gov", "nist.gov", "cert.org", "us-cert.gov",
    "cyber.gov.il",                          # Israel National Cyber Directorate
    "ncsc.gov.uk",                           # UK NCSC
    "enisa.europa.eu",                       # EU Agency for Cybersecurity
    "cyber.gc.ca",                           # Canadian Centre for Cyber Security
    "bsi.bund.de",                           # German BSI
    "anssi.fr",                              # French ANSSI
    "acsc.gov.au",                           # Australian Cyber Security Centre
    "nisc.go.jp",                            # Japan NISC
    "fbi.gov", "justice.gov", "europol.europa.eu", "interpol.int",
    "whitehouse.gov", "state.gov",
    # ── Major vendor / manufacturer security ──────────────────────────
    "microsoft.com", "security.microsoft.com", "msrc.microsoft.com",
    "cloud.google.com", "security.googleblog.com", "blog.google",
    "aws.amazon.com", "apple.com", "support.apple.com",
    "cisco.com", "fortinet.com", "paloaltonetworks.com",
    "crowdstrike.com", "mandiant.com", "fireeye.com",
    "checkpoint.com", "trendmicro.com", "sophos.com",
    "kaspersky.com", "symantec.com", "broadcom.com",
    "ibm.com", "oracle.com", "vmware.com",
    "splunk.com", "elastic.co", "sentinelone.com",
    "okta.com", "cloudflare.com",
    # ── Top-tier media & research ─────────────────────────────────────
    "reuters.com", "bbc.co.uk", "bbc.com", "nytimes.com",
    "washingtonpost.com", "theguardian.com", "ft.com",
    "wired.com", "techcrunch.com", "arstechnica.com",
    "venturebeat.com", "zdnet.com", "technologyreview.mit.edu",
    "arxiv.org", "forbes.com", "cnbc.com", "bloomberg.com",
    # ── Cybersecurity-specific media ──────────────────────────────────
    "thehackernews.com", "bleepingcomputer.com", "krebsonsecurity.com",
    "darkreading.com", "securityweek.com", "therecord.media",
    "csoonline.com", "infosecurity-magazine.com", "cyberscoop.com",
    "helpnetsecurity.com", "threatpost.com", "schneier.com",
    "eset.com", "welivesecurity.com",
}


def _is_trusted(url):
    try:
        netloc = urlparse(url).netloc.lower().lstrip("www.")
        return any(netloc == td or netloc.endswith("." + td) for td in TRUSTED_DOMAINS)
    except Exception:
        return False


def _sanitize_post_urls(text: str) -> str:
    """Remove any lines containing NSFW URLs from LLM-generated post text."""
    url_pattern = re.compile(r'https?://[^\s)\]]+')
    clean_lines = []
    for line in text.split("\n"):
        urls = url_pattern.findall(line)
        if any(_is_nsfw(u, line) for u in urls):
            log.warning("Stripped NSFW line from LLM output: %s", line[:120])
            continue
        clean_lines.append(line)
    return "\n".join(clean_lines)


def _call_openrouter(messages, temperature=0.7, max_tokens=2000):
    # Fall back to Gemini when OpenRouter key is not configured
    if not OPENROUTER_API_KEY and GOOGLE_API_KEY:
        log.info("No OPENROUTER_API_KEY — using Gemini text fallback")
        return _call_gemini(messages, temperature, max_tokens)

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://linkedin-bot.local",
        "X-Title": "LinkedIn AI Bot",
    }
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    try:
        resp = requests.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers=headers, json=payload, timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        if GOOGLE_API_KEY:
            log.warning("OpenRouter failed (%s) — falling back to Gemini", exc)
            return _call_gemini(messages, temperature, max_tokens)
        raise


def find_additional_sources(title: str, primary_url: str = "",
                            max_sources: int = 2) -> list[dict]:
    """Search DuckDuckGo for additional authoritative sources. Only returns trusted."""
    sources: list[dict] = []
    seen_urls: set[str] = {primary_url} if primary_url else set()

    try:
        from duckduckgo_search import DDGS
    except ImportError:
        log.warning("duckduckgo_search not installed")
        return []

    # Extract meaningful keywords (3+ chars, skip common words)
    stop_words = {"the", "and", "for", "with", "from", "that", "this", "are", "was",
                  "has", "had", "not", "but", "can", "its", "new", "how", "what"}
    words = [w for w in re.sub(r"[^a-zA-Z0-9 ]", " ", title).split()
             if len(w) >= 3 and w.lower() not in stop_words]
    clean_title = " ".join(words[:12]) if words else title[:120]

    # Targeted queries for authoritative sources
    queries = [
        f'"{clean_title}" cybersecurity advisory',
        f'{clean_title} site:cisa.gov OR site:microsoft.com OR site:bleepingcomputer.com',
        f'{clean_title} threat report vulnerability',
    ]

    try:
        with DDGS() as ddgs:
            for query in queries:
                try:
                    results = list(ddgs.text(query, max_results=8))
                except Exception:
                    continue
                for r in results:
                    url = r.get("href", "")
                    r_title = r.get("title", "")
                    if not url or url in seen_urls:
                        continue
                    if _is_nsfw(url, r_title):
                        log.warning("Blocked NSFW source: %s", url)
                        continue
                    if _is_non_english(url, r_title):
                        log.debug("Blocked non-English source: %s — %s", r_title[:60], url)
                        continue
                    if not _is_trusted(url):
                        continue  # skip untrusted sources entirely
                    # Relevance check: at least 2 title keywords must appear
                    # in the result title or snippet to prevent garbage results
                    result_text = (r_title + " " + r.get("body", "")).lower()
                    keyword_hits = sum(1 for w in words[:6] if w.lower() in result_text)
                    if keyword_hits < 2:
                        log.debug("Skipped low-relevance result: %s", r_title[:80])
                        continue
                    sources.append({
                        "title":   r_title,
                        "url":     url,
                        "snippet": r.get("body", "")[:300],
                        "trusted": True,
                    })
                    seen_urls.add(url)
                if len(sources) >= max_sources:
                    break

        return sources[:max_sources]
    except Exception as exc:
        log.warning("find_additional_sources failed: %s", exc)
        return []


def cross_validate_facts(title, primary_content, additional_sources):
    """Cross-validate facts across multiple sources via LLM."""
    if not additional_sources:
        return {"validated_facts": [], "confidence": "single source", "key_stats": [], "discrepancies": []}

    parts = ["PRIMARY SOURCE:\n" + primary_content[:1500] + "\n"]
    for i, src in enumerate(additional_sources, 1):
        parts.append("SOURCE " + str(i + 1) + " (" + src.get("url", "") + "):\n" + src.get("snippet", "") + "\n")
    sources_text = "\n".join(parts)

    system = (
        "You are a fact-checking analyst. Cross-reference multiple sources and "
        "extract only VERIFIED facts. Respond ONLY with valid JSON."
    )
    user = (
        "Cross-validate this cybersecurity story across " + str(len(additional_sources) + 1) + " sources.\n"
        "Topic: " + title + "\n\n" + sources_text + "\n"
        'Return ONLY this JSON:\n'
        '{\n'
        '  "validated_facts": ["fact confirmed by 2+ sources"],\n'
        '  "confidence": "high/medium/low",\n'
        '  "key_stats": ["stat1", "stat2"],\n'
        '  "discrepancies": ["any conflicting info"]\n'
        '}'
    )
    try:
        raw = _call_openrouter(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.1, max_tokens=500,
        )
        raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`")
        return json.loads(raw)
    except Exception as exc:
        log.warning("cross_validate_facts failed: %s", exc)
        return {"validated_facts": [], "confidence": "unknown", "key_stats": [], "discrepancies": []}


def analyze_article(title, content, url):
    """Extract structured intelligence from article via LLM."""
    system = (
        "You are a cybersecurity & AI intelligence analyst. "
        "Extract structured metadata from articles as compact JSON. "
        "Respond ONLY with valid JSON - no markdown fences, no explanation."
    )
    user = (
        "Analyze this article. Return ONLY this JSON:\n"
        '{\n'
        '  "key_facts": ["fact1", "fact2", "fact3"],\n'
        '  "stats": ["42 million records", "$2.3M ransom"],\n'
        '  "names": ["CompanyName", "ThreatActorName", "ToolName"],\n'
        '  "geography": ["USA", "Russia"],\n'
        '  "attack_type": "ransomware",\n'
        '  "summary": "2-3 sentence plain summary"\n'
        "}\n\n"
        "Title: " + title + "\nURL: " + url + "\n"
        "Content (first 3000 chars):\n" + content[:3000]
    )
    try:
        raw = _call_openrouter(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.2, max_tokens=600,
        )
        raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`")
        return json.loads(raw)
    except Exception as exc:
        log.warning("analyze_article failed (%s) - using defaults", exc)
        return {
            "key_facts": [title], "stats": [], "names": [],
            "geography": [], "attack_type": "cybersecurity", "summary": title,
        }


def generate_image_prompt(article_title: str, article_content: str,
                          article_url: str, style: str = "photorealistic") -> str:
    """Use LLM to create a unique, creative image prompt for the article.

    Instead of mapping keywords to hardcoded cliché scenes, this asks the
    LLM to generate a fresh visual concept each time.
    """
    summary = (article_title + ". " + article_content[:400]).strip()

    system = (
        "You are a premium visual director. Given an article summary, "
        "create a short image-generation prompt (2-3 sentences). "
        "Use creative visual METAPHORS — architecture, nature, physical objects, "
        "abstract geometry — NOT literal tech clichés like glowing brains, "
        "binary code, hooded hackers, or floating network nodes. "
        "Output ONLY the scene description."
    )
    user = f"Article: {summary}\nStyle preference: {style}"

    try:
        scene = _call_openrouter(
            [{"role": "system", "content": system},
             {"role": "user", "content": user}],
            temperature=1.0, max_tokens=200,
        )
    except Exception as exc:
        log.warning("LLM image prompt generation failed: %s — using fallback", exc)
        scene = (
            f"A clean, professional editorial illustration that conceptually "
            f"represents: {article_title[:200]}. Use elegant visual metaphors, "
            f"not literal tech imagery."
        )

    return (
        scene + " "
        "Professional editorial quality, cinematic lighting, 16:9 landscape. "
        "NO text, NO watermarks, NO logos."
    )


def _load_strategy_context():
    try:
        if os.path.exists(STRATEGY_FILE):
            with open(STRATEGY_FILE) as fh:
                data = json.load(fh)
            advice = data.get("strategy_advice", "")
            if advice:
                return "\n\nContent strategy guidance (apply this week):\n" + advice[:500]
    except Exception as exc:
        log.debug("Could not load strategy.json: %s", exc)
    return ""


def _pick_framework():
    """Randomly pick a copywriting framework for variety."""
    import random
    frameworks = [
        ("PAS", "Use Problem-Agitate-Solve: state the problem, make it feel urgent/painful, present the solution."),
        ("AIDA", "Use Attention-Interest-Desire-Action: hook attention, build interest with facts, create desire, clear CTA."),
        ("CONTRARIAN", "Use Contrarian Hook: start with a provocative/unpopular opinion, back it with data, ask audience to weigh in."),
    ]
    return random.choice(frameworks)


def _pick_cta_type():
    """Randomly pick a CTA type for engagement variety."""
    import random
    cta_types = [
        ("DEBATE", "End with a debate question that forces people to pick a side and comment. Example: 'Do you agree that X is dead? Drop your take below.'"),
        ("EXPERIENCE", "End by inviting personal stories. Example: 'What's the craziest breach you've seen this year? Share below.'"),
        ("TAG_SHARE", "End with a tag/share CTA. Example: 'Tag a CISO who needs to see this.' or 'Share if you agree.'"),
        ("ACTION", "End with a practical action step. Example: 'Here's what to do RIGHT NOW: [step]. What's your first move?'"),
    ]
    return random.choice(cta_types)


def generate_post(article):
    """
    Generate viral LinkedIn post validated across multiple sources.
    Returns dict: post_text, image_prompt, metadata.
    """
    title   = article.get("title", "").strip()
    content = (article.get("content") or article.get("summary") or "").strip()
    url     = article.get("url", "").strip()

    # STEP 1: Analyze primary article
    log.info("generate_post: analyzing primary article")
    meta       = analyze_article(title, content, url)
    key_facts  = meta.get("key_facts",  [])
    stats      = meta.get("stats",      [])
    names      = meta.get("names",      [])
    geography  = meta.get("geography",  [])
    attack_str = meta.get("attack_type", "")
    summary    = meta.get("summary",    title)

    # STEP 2: Find additional sources via DuckDuckGo
    log.info("generate_post: searching for additional sources")
    additional_sources = find_additional_sources(title, primary_url=url, max_sources=3)
    log.info("Found %d additional sources", len(additional_sources))

    # STEP 3: Cross-validate facts
    if additional_sources:
        log.info("generate_post: cross-validating facts")
        validation      = cross_validate_facts(title, content, additional_sources)
        validated_facts = validation.get("validated_facts", [])
        confidence      = validation.get("confidence", "medium")
        extra_stats     = validation.get("key_stats", [])
        all_facts       = list(dict.fromkeys(key_facts + validated_facts))[:6]
        all_stats       = list(dict.fromkeys(stats + extra_stats))[:4]
    else:
        all_facts  = key_facts
        all_stats  = stats
        confidence = "single source"

    # STEP 4: Build sources list (with NSFW filtering)
    all_sources = []
    if url and not _is_nsfw(url, title):
        all_sources.append({"title": title, "url": url, "trusted": _is_trusted(url)})
    for src in additional_sources:
        if not _is_nsfw(src.get("url", ""), src.get("title", "")):
            all_sources.append(src)

    # STEP 5: Pick framework and CTA type for variety
    fw_name, fw_instruction = _pick_framework()
    cta_name, cta_instruction = _pick_cta_type()
    log.info("generate_post: framework=%s, cta=%s", fw_name, cta_name)

    # STEP 6: Generate post with LLM
    facts_block     = "\n".join("  - " + f for f in all_facts) if all_facts else "  - " + summary
    stats_str       = ", ".join(all_stats[:3])  if all_stats  else "see sources"
    geo_str         = ", ".join(geography[:3])  if geography  else "global"
    names_str       = ", ".join(names[:3])      if names      else "unknown"
    strategy        = _load_strategy_context()
    sources_context = "\n".join(
        "  - " + s.get("title", "")[:80] + " (" + s.get("url", "") + ")"
        for s in all_sources[:4]
    ) if all_sources else "  - primary article only"

    system_msg = (
        "You are an elite LinkedIn content strategist for cybersecurity and AI. "
        "You write punchy posts (EXACTLY 120-180 words — not less, not more) that stop the scroll. "
        "You use psychological techniques: pattern interrupts, curiosity gaps, urgency, "
        "and engagement magnets. Your posts drive massive engagement. "
        "You ONLY use facts verified across multiple sources. "
        "MINIMUM 120 words, MAXIMUM 180 words — count carefully. "
        "Use MAX 2 emojis in the entire post — LinkedIn is professional, not Instagram. "
        "Use line breaks between sections, not emojis as bullet markers."
    )
    user_msg = (
        "Write a VIRAL LinkedIn post based on VERIFIED data.\n\n"
        "== VERIFIED INTELLIGENCE (confidence: " + confidence + ") ==\n"
        "Title      : " + title + "\n"
        "Topic/Type : " + attack_str + "\n"
        "Key Facts  :\n" + facts_block + "\n"
        "Stats      : " + stats_str + "\n"
        "Key Players: " + names_str + "\n"
        "Geography  : " + geo_str + "\n"
        "Summary    : " + summary + "\n"
        "Sources    :\n" + sources_context + "\n"
        + strategy + "\n\n"
        "== FRAMEWORK: " + fw_name + " ==\n"
        + fw_instruction + "\n\n"
        "== STRICT REQUIREMENTS ==\n"
        "1. HOOK (max 12 words): pattern interrupt, unexpected/alarming opener.\n"
        "2. OPEN LOOP (1-2 lines): create a curiosity gap.\n"
        "3. USE ONLY REAL VERIFIED STATS: " + stats_str + " — never fabricate.\n"
        "4. 3-4 SHORT bullet insights — escalating in impact. Use dashes (-) not emojis as bullets.\n"
        "5. URGENCY CLOSE: one sentence making readers feel they must act NOW.\n"
        "6. CTA (" + cta_name + "): " + cta_instruction + "\n"
        "7. HASHTAGS: 3-5 at the very end. Mix broad + niche.\n"
        "8. LENGTH: MINIMUM 120 words, MAXIMUM 180 words. Count carefully. Under 120 = too thin. Over 180 = too long.\n"
        "9. TONE: urgent, expert, slightly alarming, constructive. Professional LinkedIn voice.\n"
        "10. DO NOT include any URLs in the post body.\n"
        "11. Use short punchy lines — NO walls of text, NO long paragraphs.\n"
        "12. MAX 2 emojis total in the entire post. LinkedIn is professional — emojis cheapen the message.\n\n"
        "Output ONLY the post text (no URLs, no sources — added separately)."
    )

    llm_failed = False
    used_template_fallback = False
    try:
        post_text = _call_openrouter(
            [{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}],
            temperature=0.85, max_tokens=800,
        )
        # Detect if LLM returned empty or trivially short content
        stripped = re.sub(r"#\w+", "", post_text).strip()
        if len(stripped.split()) < 30:
            log.warning("LLM returned suspiciously short post (%d words) — marking as failed", len(stripped.split()))
            llm_failed = True
    except Exception as exc:
        log.error("generate_post LLM call failed: %s", exc)
        post_text = ""
        llm_failed = True

    if llm_failed:
        # OpenRouter → Gemini fallback chain already exhausted inside _call_openrouter.
        # Use a simple template fallback instead of calling Gemini again.
        log.warning("LLM call chain exhausted — using template fallback")
        bullet_facts = "\n".join("- " + f for f in all_facts[:4]) if all_facts else "- " + summary
        stats_line = ("Key stats: " + ", ".join(all_stats[:3]) + "\n\n") if all_stats else ""
        post_text = (
            f"{title}\n\n"
            f"Here's what we know so far:\n\n"
            f"{bullet_facts}\n\n"
            f"{stats_line}"
            f"This is a developing story — stay tuned for updates.\n\n"
            f"What's your take? Drop your thoughts below.\n\n"
            f"#Cybersecurity #InfoSec #ThreatIntel"
        )
        stripped = re.sub(r"#\w+", "", post_text).strip()
        if len(stripped.split()) >= 15:
            llm_failed = False
            used_template_fallback = True
            log.info("Template fallback produced usable post — skipping image generation")

    if llm_failed or not post_text.strip():
        # Return a clearly-marked failure instead of a garbage post
        used_template_fallback = True
        post_text = (
            "⚠️ POST GENERATION FAILED — LLM unavailable\n\n"
            "Topic: " + title + "\n\n"
            "Please use ✏️ Edit Text or 🔄 New Topic to retry."
        )
        log.error("All LLM attempts failed — returning error placeholder for topic: %s", title[:80])

    post_text = post_text.rstrip()

    # STEP 7a: Strip any URLs the LLM may have injected into the post body
    post_text = _sanitize_post_urls(post_text)

    # STEP 7b: Append Resources — only 2 verified/trusted sources
    verified_sources = [s for s in all_sources if s.get("trusted")]
    if not verified_sources and all_sources:
        verified_sources = all_sources[:1]  # at least include primary
    if verified_sources:
        post_text += "\n\n📚 Resources:"
        for i, src in enumerate(verified_sources[:2], 1):
            src_title = src.get("title", "") or "Source"
            src_title = (src_title[:70] + "...") if len(src_title) > 70 else src_title
            src_url = src.get("url", "")
            post_text += "\n" + str(i) + ". " + src_title + " ✅"
            post_text += "\n   " + src_url

    # Skip LLM-based image prompt generation for template/placeholder posts
    # to avoid a redundant Gemini call when all LLMs are already down.
    if used_template_fallback:
        image_prompt = None
        log.info("Skipping image generation for template/placeholder post")
    else:
        image_prompt = generate_image_prompt(title, content, url, style="photorealistic")

    return {
        "post_text": post_text,
        "image_prompt": image_prompt,
        "metadata": meta,
        "is_placeholder": used_template_fallback,
    }


# Backward-compat wrappers
def write_linkedin_post(article):
    return generate_post(article)["post_text"]


def rewrite_post(post_text, instruction):
    prompt = (
        "Rewrite this LinkedIn post per the instruction. "
        "Preserve: pattern interrupt opener, curiosity gap, engagement question, hashtags.\n\n"
        "Original:\n" + post_text + "\n\nInstruction: " + instruction + "\n\nReturn ONLY the updated post text."
    )
    try:
        return _call_openrouter(
            [{"role": "system", "content": "You are a viral LinkedIn content strategist."},
             {"role": "user", "content": prompt}],
            temperature=0.8, max_tokens=1500,
        )
    except Exception as exc:
        log.error("rewrite_post failed: %s", exc)
        return post_text
