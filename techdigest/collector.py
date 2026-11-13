# collects tech news from rss feeds and saves the recent ones to json
# usage: python -m techdigest.collector

import argparse
import html
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import feedparser
import requests
import yaml

from .models import Article

log = logging.getLogger("collector")

USER_AGENT = "TechDigestBot/0.1 (student project)"
TIMEOUT = 15
MAX_FEED_SIZE = 5 * 1024 * 1024  # 5MB

TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")
TRACKING_PARAMS = {"fbclid", "gclid", "ref", "cmpid", "mc_cid", "mc_eid"}


def load_feeds(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)["feeds"]


def clean_text(raw, limit=500):
    # remove html tags and extra spaces
    text = html.unescape(TAG_RE.sub(" ", raw or ""))
    text = SPACE_RE.sub(" ", text).strip()
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0] + "..."
    return text


def normalise_url(url):
    # used for finding duplicates - removes utm_ stuff and #fragments
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query)
             if not k.lower().startswith("utm_") and k.lower() not in TRACKING_PARAMS]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def title_key(title):
    return re.sub(r"[^a-z0-9]", "", title.lower())


def get_date(entry):
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    if t:
        return datetime(*t[:6], tzinfo=timezone.utc)
    return None


def fetch_feed(url, session):
    resp = session.get(url, timeout=TIMEOUT, stream=True, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()

    data = b""
    for chunk in resp.iter_content(64 * 1024):
        data += chunk
        if len(data) > MAX_FEED_SIZE:
            raise ValueError("feed too big")
    return data


def parse_entries(raw, source, category):
    feed = feedparser.parse(raw)
    articles = []
    for e in feed.entries:
        title = clean_text(e.get("title"), limit=300)
        link = (e.get("link") or "").strip()

        # only allow http/https links (no javascript: etc)
        if not title or not link.lower().startswith(("http://", "https://")):
            continue

        articles.append(Article(
            title=title,
            url=link,
            source=source,
            category=category,
            published=get_date(e),
            summary=clean_text(e.get("summary") or e.get("description")),
        ))
    return articles


def dedupe(articles):
    seen_urls = set()
    seen_titles = set()
    result = []
    for a in articles:
        u = normalise_url(a.url)
        t = title_key(a.title)
        if u in seen_urls or t in seen_titles:
            continue
        seen_urls.add(u)
        seen_titles.add(t)
        result.append(a)
    return result


def collect(feeds, hours=24, now=None, session=None):
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)
    session = session or requests.Session()

    articles = []
    for feed in feeds:
        try:
            raw = fetch_feed(feed["url"], session)
            items = parse_entries(raw, feed["name"], feed.get("category", "general"))
        except Exception as e:
            log.warning("skipping %s: %s", feed.get("name"), e)
            continue

        recent = [a for a in items if a.published is None or a.published >= cutoff]
        log.info("%s: %d items, %d recent", feed["name"], len(items), len(recent))
        articles.extend(recent)

    # newest first, ones without a date at the end
    oldest = datetime.min.replace(tzinfo=timezone.utc)
    articles.sort(key=lambda a: a.published or oldest, reverse=True)
    return dedupe(articles)


def save(articles, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump([a.to_dict() for a in articles], f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--feeds", default="config/feeds.yaml")
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--out", default="data/articles.json")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    articles = collect(load_feeds(args.feeds), hours=args.hours)
    save(articles, args.out)

    print(f"\nsaved {len(articles)} articles to {args.out}")
    for a in articles[:10]:
        print(f"  [{a.source}] {a.title}")


if __name__ == "__main__":
    main()
