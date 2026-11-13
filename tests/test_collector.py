from datetime import datetime, timezone

import requests

from techdigest.collector import clean_text, collect, dedupe, normalise_url, parse_entries

NOW = datetime(2026, 11, 13, 0, 0, tzinfo=timezone.utc)

SAMPLE_RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>Sample</title>
  <item><title>New &amp; shiny <b>chip</b> announced</title>
        <link>https://example.com/chip?utm_source=rss</link>
        <description>&lt;p&gt;Faster than   ever.&lt;/p&gt;</description>
        <pubDate>Thu, 12 Nov 2026 20:00:00 GMT</pubDate></item>
  <item><title>Old story</title><link>https://example.com/old</link>
        <pubDate>Mon, 02 Nov 2026 10:00:00 GMT</pubDate></item>
  <item><title>Evil link</title><link>javascript:alert(1)</link>
        <pubDate>Thu, 12 Nov 2026 21:00:00 GMT</pubDate></item>
</channel></rss>"""


class FakeResponse:
    def __init__(self, body): self.body = body
    def raise_for_status(self): pass
    def iter_content(self, size): yield self.body


class FakeSession:
    def __init__(self, pages): self.pages = pages
    def get(self, url, **kw):
        body = self.pages[url]
        if isinstance(body, Exception):
            raise body
        return FakeResponse(body)


def test_clean_text_strips_html_and_entities():
    assert clean_text("<p>Hello <b>world</b></p>") == "Hello world"


def test_parse_rejects_non_http_links():
    titles = [a.title for a in parse_entries(SAMPLE_RSS, "Sample", "general")]
    assert "Evil link" not in titles
    assert "New & shiny chip announced" in titles


def test_normalise_url_drops_tracking():
    assert normalise_url("https://Example.com/a/?utm_source=x&id=5#top") == "https://example.com/a?id=5"


def test_dedupe_by_url_and_title():
    arts = parse_entries(SAMPLE_RSS, "A", "general") + parse_entries(SAMPLE_RSS, "B", "general")
    assert len(dedupe(arts)) == 2


def test_collect_filters_old_and_survives_broken_feed():
    feeds = [{"name": "Good", "url": "https://good/rss"},
             {"name": "Broken", "url": "https://broken/rss"}]
    session = FakeSession({"https://good/rss": SAMPLE_RSS,
                           "https://broken/rss": requests.ConnectionError("down")})
    result = collect(feeds, hours=24, now=NOW, session=session)
    assert [a.title for a in result] == ["New & shiny chip announced"]
