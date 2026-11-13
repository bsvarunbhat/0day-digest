# 0day-digest

Small project I'm building to get a summary of tech news in my inbox every morning at 6am.
Plan is to get it working first, add an ML model, then go back and find/fix the security issues in it.

## Progress

- [x] collect news from RSS feeds
- [ ] send the digest by email + run it daily with GitHub Actions
- [ ] summarise the news with an LLM
- [ ] train my own classifier to tag and rank stories
- [ ] scale it up (database, dashboard)
- [ ] security review and fixes

## Running it

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

python -m techdigest.collector
pytest
```

Feeds are in `config/feeds.yaml`.
