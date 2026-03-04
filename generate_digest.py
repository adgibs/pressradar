#!/usr/bin/env python3
"""
PressRadar.me — Daily Email Digest Generator
Reads index.html and generates an HTML email summary of the last 24 hours.
"""

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import Counter

def main():
    html_path = Path(__file__).parent / "index.html"
    html = html_path.read_text()

    # Parse articles
    articles = []
    loc_pattern = r'name:\s*"([^"]+)",\s*country:\s*"([^"]+)"'
    art_pattern = r'title:\s*"((?:[^"\\]|\\.)*)"\s*,\s*source:\s*"([^"]*)"\s*,\s*url:\s*"([^"]*)"\s*,\s*time:\s*"([^"]*)"'

    # Find location blocks
    block_pattern = r'\{\s*name:\s*"([^"]+)",\s*country:\s*"([^"]+)",.*?articles:\s*\[(.*?)\]'
    for m in re.finditer(block_pattern, html, re.DOTALL):
        loc_name, country, articles_block = m.groups()
        for am in re.finditer(art_pattern, articles_block):
            articles.append({
                "title": am.group(1),
                "source": am.group(2),
                "url": am.group(3),
                "time": am.group(4),
                "location": loc_name,
                "country": country,
            })

    # Filter last 24 hours
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
    recent = [a for a in articles if a["time"] >= cutoff_str]
    recent.sort(key=lambda a: a["time"], reverse=True)

    # Stats
    total = len(recent)
    sources = Counter(a["source"] for a in recent)
    countries = Counter(a["country"] for a in recent)
    top_sources = sources.most_common(5)
    top_countries = countries.most_common(5)

    # Sentiment analysis
    def get_sentiment(title):
        t = title.lower()
        escalation = ['strike', 'attack', 'bomb', 'kill', 'dead', 'death', 'missile', 'war', 'destroy', 'drone', 'troops', 'retaliat']
        diplomacy = ['ceasefire', 'peace', 'negotiat', 'talks', 'diplomat', 'urge', 'restrain']
        humanitarian = ['humanitarian', 'aid', 'refugee', 'civilian', 'evacuat', 'flee', 'crisis']
        economic = ['oil', 'price', 'energy', 'gas', 'trade', 'market', 'shipping']

        scores = {
            'Conflict': sum(1 for w in escalation if w in t),
            'Diplomacy': sum(1 for w in diplomacy if w in t),
            'Humanitarian': sum(1 for w in humanitarian if w in t),
            'Economic': sum(1 for w in economic if w in t),
        }
        max_score = max(scores.values())
        if max_score == 0:
            return 'Conflict'
        return max(scores, key=scores.get)

    sentiment_counts = Counter(get_sentiment(a["title"]) for a in recent)
    sentiment_colors = {
        'Conflict': '#e74c3c',
        'Diplomacy': '#27ae60',
        'Humanitarian': '#e67e22',
        'Economic': '#3498db',
    }

    # Generate HTML email
    now = datetime.now(timezone.utc).strftime("%d %B %Y, %H:%M UTC")

    email = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:600px;margin:0 auto;padding:20px;background:#f5f5f5;">

<div style="background:#fff;border-radius:12px;padding:24px;margin-bottom:16px;border-top:4px solid #e74c3c;">
  <h1 style="margin:0 0 4px;font-size:24px;">PressRadar<span style="color:#e74c3c">.me</span></h1>
  <p style="margin:0;color:#888;font-size:13px;">Daily Digest — {now}</p>
</div>

<div style="background:#fff;border-radius:12px;padding:20px;margin-bottom:16px;">
  <h2 style="margin:0 0 12px;font-size:16px;">Summary</h2>
  <p style="margin:0 0 8px;font-size:14px;"><strong>{total}</strong> articles in the last 24 hours</p>
  <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:12px;">
"""

    for sentiment, count in sentiment_counts.most_common():
        color = sentiment_colors.get(sentiment, '#999')
        email += f'    <span style="font-size:12px;padding:3px 10px;border-radius:10px;background:{color}20;color:{color};font-weight:600;">{sentiment}: {count}</span>\n'

    email += """  </div>
  <p style="margin:0;font-size:13px;color:#666;">"""
    email += "Top sources: " + ", ".join(f"{s} ({c})" for s, c in top_sources)
    email += "<br>Top countries: " + ", ".join(f"{c} ({n})" for c, n in top_countries)
    email += """</p>
</div>
"""

    # Top stories (first 15)
    email += """<div style="background:#fff;border-radius:12px;padding:20px;margin-bottom:16px;">
  <h2 style="margin:0 0 12px;font-size:16px;">Top Stories</h2>
"""

    for a in recent[:15]:
        sentiment = get_sentiment(a["title"])
        color = sentiment_colors.get(sentiment, '#999')
        time_str = a["time"][11:16] if len(a["time"]) > 16 else ""
        email += f"""  <div style="padding:10px 0;border-bottom:1px solid #eee;">
    <a href="{a['url']}" style="color:#222;text-decoration:none;font-size:14px;font-weight:500;line-height:1.4;">
      <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{color};margin-right:6px;vertical-align:middle;"></span>
      {a['title']}
    </a>
    <div style="font-size:11px;color:#888;margin-top:3px;">{a['source']} · {a['location']} · {time_str} UTC</div>
  </div>
"""

    email += """</div>

<div style="text-align:center;padding:16px;color:#aaa;font-size:11px;">
  <a href="https://adgibs.github.io/pressradar" style="color:#e74c3c;text-decoration:none;">View full map →</a><br>
  PressRadar.me — Automated news intelligence
</div>

</body>
</html>"""

    print(email)


if __name__ == "__main__":
    main()
