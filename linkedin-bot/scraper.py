"""
scraper.py  -  RSS feed scraper with trusted-source reputation scoring.
Only returns articles with reputation score >= MIN_REPUTATION_SCORE (8/10).
"""

import logging
import random
from urllib.parse import urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

from config import NEWS_FEEDS

log = logging.getLogger(__name__)
MIN_REPUTATION_SCORE = 8

TRUSTED_SOURCES = {
    "thehackernews.com":        {"score": 10, "name": "The Hacker News",      "specialty": "Cybersecurity"},
    "bleepingcomputer.com":     {"score": 10, "name": "BleepingComputer",      "specialty": "Cybersecurity/Malware"},
    "krebsonsecurity.com":      {"score": 10, "name": "Krebs on Security",     "specialty": "Investigative Cybersecurity"},
    "darkreading.com":          {"score": 9,  "name": "Dark Reading",          "specialty": "Enterprise Security"},
    "wired.com":                {"score": 9,  "name": "Wired",                 "specialty": "Tech & Security"},
    "techcrunch.com":           {"score": 9,  "name": "TechCrunch",            "specialty": "AI & Tech"},
    "cisa.gov":                 {"score": 10, "name": "CISA",                  "specialty": "US Gov Cybersecurity"},
    "arxiv.org":                {"score": 9,  "name": "ArXiv",                 "specialty": "Academic Research"},
    "technologyreview.mit.edu": {"score": 10, "name": "MIT Technology Review", "specialty": "AI & Emerging Tech"},
    "reuters.com":              {"score": 10, "name": "Reuters",               "specialty": "Breaking News"},
    "bbc.co.uk":                {"score": 10, "name": "BBC Technology",        "specialty": "Tech & Cybersecurity"},
    "bbc.com":                  {"score": 10, "name": "BBC Technology",        "specialty": "Tech & Cybersecurity"},
    "securityweek.com":         {"score": 9,  "name": "SecurityWeek",          "specialty": "Enterprise Security"},
    "therecord.media":          {"score": 9,  "name": "The Record",            "specialty": "Cybercrime & APTs"},
    "arstechnica.com":          {"score": 9,  "name": "Ars Technica",          "specialty": "Deep-Dive Tech"},
    "venturebeat.com":          {"score": 8,  "name": "VentureBeat",           "specialty": "AI & Enterprise"},
    "eset.com":                 {"score": 8,  "name": "ESET Research",         "specialty": "Threat Research"},
    "feeds.feedburner.com":     {"score": 8,  "name": "FeedBurner",            "specialty": "RSS Aggregator"},
}


def _get_domain(url):
    try:
        return urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return ""


def _score_url(url):
    """Return (score, source_name, verified) tuple for a URL."""
    domain = _get_domain(url)
    if domain in TRUSTED_SOURCES:
        info = TRUSTED_SOURCES[domain]
        return info["score"], info["name"], True
    for td, info in TRUSTED_SOURCES.items():
        if domain.endswith("." + td) or domain == td:
            return info["score"], info["name"], True
    return 5, domain or "Unknown", False


def fetch_news(max_per_feed=5):
    """
    Fetch from all RSS feeds.
    Returns only articles whose source has score >= MIN_REPUTATION_SCORE.
    Each article dict includes source_score and source_verified fields.
    """
    articles = []
    for feed_url in NEWS_FEEDS:
        try:
            feed       = feedparser.parse(feed_url)
            feed_title = feed.feed.get("title", feed_url)
            for entry in feed.entries[:max_per_feed]:
                art_url = entry.get("link", "")
                score, src_name, verified = _score_url(art_url)
                if score < MIN_REPUTATION_SCORE:
                    log.debug("Skipping low-reputation source (score=%s): %s", score, art_url)
                    continue
                articles.append({
                    "title":           entry.get("title", ""),
                    "url":             art_url,
                    "summary":         entry.get("summary", entry.get("description", "")),
                    "published":       entry.get("published", ""),
                    "source":          src_name or feed_title,
                    "source_score":    score,
                    "source_verified": verified,
                })
        except Exception as exc:
            log.warning("Error fetching feed %s: %s", feed_url, exc)
    log.info("Fetched %d verified articles (score>=%d)", len(articles), MIN_REPUTATION_SCORE)
    return articles


def get_article_content(url, max_chars=4000):
    """Fetch and extract main text content from an article URL."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; LinkedInBot/2.0)"}
        resp    = requests.get(url, headers=headers, timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)[:max_chars]
    except Exception as exc:
        log.warning("get_article_content failed for %s: %s", url, exc)
        return ""


def pick_best_article(articles, used_topics=None):
    """Pick best article avoiding recently used topics; prefer higher reputation score."""
    if not articles:
        return None
    candidates = articles
    if used_topics:
        filtered = [
            a for a in articles
            if not any(t.lower() in a["title"].lower() for t in used_topics)
        ]
        if filtered:
            candidates = filtered
    candidates.sort(key=lambda a: a.get("source_score", 5), reverse=True)
    return random.choice(candidates[:min(10, len(candidates))])
