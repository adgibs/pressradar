#!/usr/bin/env python3
"""
PressRadar.me — News Fetcher
Fetches Middle East news from RSS feeds and updates the map data.
Designed to run via GitHub Actions on a schedule.
"""

import feedparser
import json
import re
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── RSS Feed Sources ──────────────────────────────────────────────
FEEDS = [
    # UK Sources
    {"url": "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml", "source": "BBC News"},
    {"url": "https://www.theguardian.com/world/middleeast/rss", "source": "The Guardian"},
    {"url": "https://feeds.skynews.com/feeds/rss/world.xml", "source": "Sky News"},
    {"url": "https://www.telegraph.co.uk/news/world/middle-east/rss.xml", "source": "The Telegraph"},
    # Wire Services
    {"url": "https://www.reuters.com/rssFeed/worldNews/", "source": "Reuters"},
    {"url": "https://rss.app/feeds/v1.1/tGYbfMocOcSGBhDa.xml", "source": "Reuters"},  # backup
    # International
    {"url": "https://www.aljazeera.com/xml/rss/all.xml", "source": "Al Jazeera"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/MiddleEast.xml", "source": "New York Times"},
    {"url": "https://feeds.washingtonpost.com/rss/world", "source": "Washington Post"},
    {"url": "https://rss.cnn.com/rss/edition_meast.rss", "source": "CNN"},
    {"url": "https://www.france24.com/en/middle-east/rss", "source": "France 24"},
    {"url": "https://www.dw.com/rss/en/middle-east/s-31801", "source": "Deutsche Welle"},
    {"url": "https://www3.nhk.or.jp/nhkworld/en/news/rss/index.xml", "source": "NHK World"},
    # US Sources
    {"url": "https://feeds.npr.org/1004/rss.xml", "source": "NPR"},
    {"url": "https://feeds.nbcnews.com/nbcnews/public/world", "source": "NBC News"},
    {"url": "https://www.cbsnews.com/latest/rss/world", "source": "CBS News"},
    {"url": "https://feeds.foxnews.com/foxnews/world", "source": "Fox News"},
    # Regional
    {"url": "https://www.timesofisrael.com/feed/", "source": "Times of Israel"},
    {"url": "https://www.jpost.com/rss/rssfeedsfrontpage.aspx", "source": "Jerusalem Post"},
]

# ── Middle East Keywords & Location Mapping ───────────────────────
# Keywords that indicate Middle East relevance
ME_KEYWORDS = [
    "iran", "israel", "gaza", "lebanon", "hezbollah", "hamas", "tehran",
    "beirut", "syria", "iraq", "yemen", "houthi", "saudi", "uae", "dubai",
    "qatar", "bahrain", "kuwait", "oman", "jordan", "egypt", "cairo",
    "strait of hormuz", "hormuz", "red sea", "middle east", "mideast",
    "netanyahu", "khamenei", "idf", "irgc", "rafah", "west bank",
    "akrotiri", "cyprus", "diego garcia", "epic fury", "roaring lion",
    "oil price", "opec", "persian gulf", "gulf state",
    "starmer", "raf base", "british base",
]

# Map keywords to locations
LOCATION_MAP = {
    "tehran": {"name": "Tehran", "country": "Iran", "lat": 35.6892, "lng": 51.389, "category": "strikes"},
    "isfahan": {"name": "Isfahan", "country": "Iran", "lat": 32.6546, "lng": 51.6680, "category": "strikes"},
    "shiraz": {"name": "Shiraz", "country": "Iran", "lat": 29.5918, "lng": 52.5837, "category": "strikes"},
    "bandar abbas": {"name": "Bandar Abbas", "country": "Iran", "lat": 27.1865, "lng": 56.2808, "category": "strikes"},
    "qom": {"name": "Qom", "country": "Iran", "lat": 34.6401, "lng": 50.8764, "category": "strikes"},
    "iran": {"name": "Tehran", "country": "Iran", "lat": 35.6892, "lng": 51.389, "category": "strikes"},
    "khamenei": {"name": "Tehran", "country": "Iran", "lat": 35.6892, "lng": 51.389, "category": "strikes"},
    "irgc": {"name": "Tehran", "country": "Iran", "lat": 35.6892, "lng": 51.389, "category": "strikes"},
    "tel aviv": {"name": "Tel Aviv", "country": "Israel", "lat": 32.0853, "lng": 34.7818, "category": "strikes"},
    "haifa": {"name": "Haifa", "country": "Israel", "lat": 32.7940, "lng": 34.9896, "category": "strikes"},
    "jerusalem": {"name": "Jerusalem", "country": "Israel", "lat": 31.7683, "lng": 35.2137, "category": "strikes"},
    "israel": {"name": "Tel Aviv", "country": "Israel", "lat": 32.0853, "lng": 34.7818, "category": "strikes"},
    "netanyahu": {"name": "Tel Aviv", "country": "Israel", "lat": 32.0853, "lng": 34.7818, "category": "strikes"},
    "idf": {"name": "Tel Aviv", "country": "Israel", "lat": 32.0853, "lng": 34.7818, "category": "strikes"},
    "beirut": {"name": "Beirut", "country": "Lebanon", "lat": 33.8938, "lng": 35.5018, "category": "strikes"},
    "hezbollah": {"name": "Beirut", "country": "Lebanon", "lat": 33.8938, "lng": 35.5018, "category": "strikes"},
    "lebanon": {"name": "Beirut", "country": "Lebanon", "lat": 33.8938, "lng": 35.5018, "category": "strikes"},
    "tyre": {"name": "Tyre", "country": "Lebanon", "lat": 33.2705, "lng": 35.1968, "category": "strikes"},
    "beqaa": {"name": "Beqaa Valley", "country": "Lebanon", "lat": 33.8500, "lng": 35.9000, "category": "strikes"},
    "gaza": {"name": "Gaza City", "country": "Palestine", "lat": 31.5017, "lng": 34.4668, "category": "humanitarian"},
    "rafah": {"name": "Rafah", "country": "Palestine", "lat": 31.2969, "lng": 34.2455, "category": "humanitarian"},
    "west bank": {"name": "Gaza City", "country": "Palestine", "lat": 31.5017, "lng": 34.4668, "category": "humanitarian"},
    "riyadh": {"name": "Riyadh", "country": "Saudi Arabia", "lat": 24.7136, "lng": 46.6753, "category": "strikes"},
    "saudi": {"name": "Riyadh", "country": "Saudi Arabia", "lat": 24.7136, "lng": 46.6753, "category": "energy"},
    "dubai": {"name": "Dubai", "country": "UAE", "lat": 25.2048, "lng": 55.2708, "category": "strikes"},
    "abu dhabi": {"name": "Dubai", "country": "UAE", "lat": 25.2048, "lng": 55.2708, "category": "strikes"},
    "uae": {"name": "Dubai", "country": "UAE", "lat": 25.2048, "lng": 55.2708, "category": "strikes"},
    "kuwait": {"name": "Kuwait City", "country": "Kuwait", "lat": 29.3759, "lng": 47.9774, "category": "strikes"},
    "bahrain": {"name": "Manama", "country": "Bahrain", "lat": 26.2285, "lng": 50.5860, "category": "strikes"},
    "qatar": {"name": "Doha", "country": "Qatar", "lat": 25.2854, "lng": 51.5310, "category": "energy"},
    "doha": {"name": "Doha", "country": "Qatar", "lat": 25.2854, "lng": 51.5310, "category": "energy"},
    "erbil": {"name": "Erbil", "country": "Iraq", "lat": 36.1901, "lng": 44.0091, "category": "strikes"},
    "iraq": {"name": "Erbil", "country": "Iraq", "lat": 36.1901, "lng": 44.0091, "category": "strikes"},
    "syria": {"name": "Damascus", "country": "Syria", "lat": 33.5138, "lng": 36.2765, "category": "evacuation"},
    "damascus": {"name": "Damascus", "country": "Syria", "lat": 33.5138, "lng": 36.2765, "category": "evacuation"},
    "yemen": {"name": "Sanaa", "country": "Yemen", "lat": 15.3694, "lng": 44.1910, "category": "strikes"},
    "houthi": {"name": "Sanaa", "country": "Yemen", "lat": 15.3694, "lng": 44.1910, "category": "strikes"},
    "sanaa": {"name": "Sanaa", "country": "Yemen", "lat": 15.3694, "lng": 44.1910, "category": "strikes"},
    "red sea": {"name": "Sanaa", "country": "Yemen", "lat": 15.3694, "lng": 44.1910, "category": "strikes"},
    "egypt": {"name": "Cairo", "country": "Egypt", "lat": 30.0444, "lng": 31.2357, "category": "evacuation"},
    "cairo": {"name": "Cairo", "country": "Egypt", "lat": 30.0444, "lng": 31.2357, "category": "evacuation"},
    "jordan": {"name": "Amman", "country": "Jordan", "lat": 31.9454, "lng": 35.9284, "category": "evacuation"},
    "amman": {"name": "Amman", "country": "Jordan", "lat": 31.9454, "lng": 35.9284, "category": "evacuation"},
    "oman": {"name": "Muscat", "country": "Oman", "lat": 23.5880, "lng": 58.3829, "category": "evacuation"},
    "hormuz": {"name": "Strait of Hormuz", "country": "Iran", "lat": 26.5667, "lng": 56.2500, "category": "energy"},
    "strait": {"name": "Strait of Hormuz", "country": "Iran", "lat": 26.5667, "lng": 56.2500, "category": "energy"},
    "akrotiri": {"name": "Akrotiri, Cyprus", "country": "Cyprus", "lat": 34.5839, "lng": 32.9880, "category": "uk"},
    "cyprus": {"name": "Akrotiri, Cyprus", "country": "Cyprus", "lat": 34.5839, "lng": 32.9880, "category": "uk"},
    "raf base": {"name": "Akrotiri, Cyprus", "country": "Cyprus", "lat": 34.5839, "lng": 32.9880, "category": "uk"},
    "british base": {"name": "Akrotiri, Cyprus", "country": "Cyprus", "lat": 34.5839, "lng": 32.9880, "category": "uk"},
    "diego garcia": {"name": "Diego Garcia", "country": "UK (BIOT)", "lat": -7.3195, "lng": 72.4229, "category": "uk"},
    "starmer": {"name": "Akrotiri, Cyprus", "country": "Cyprus", "lat": 34.5839, "lng": 32.9880, "category": "uk"},
    "oil price": {"name": "Strait of Hormuz", "country": "Iran", "lat": 26.5667, "lng": 56.2500, "category": "energy"},
    "opec": {"name": "Strait of Hormuz", "country": "Iran", "lat": 26.5667, "lng": 56.2500, "category": "energy"},
    "strait of hormuz": {"name": "Strait of Hormuz", "country": "Iran", "lat": 26.5667, "lng": 56.2500, "category": "energy"},
    "persian gulf": {"name": "Strait of Hormuz", "country": "Iran", "lat": 26.5667, "lng": 56.2500, "category": "energy"},
    "gulf state": {"name": "Dubai", "country": "UAE", "lat": 25.2048, "lng": 55.2708, "category": "strikes"},
    "middle east": {"name": "Tehran", "country": "Iran", "lat": 35.6892, "lng": 51.389, "category": "strikes"},
    "mideast": {"name": "Tehran", "country": "Iran", "lat": 35.6892, "lng": 51.389, "category": "strikes"},
    "epic fury": {"name": "Tehran", "country": "Iran", "lat": 35.6892, "lng": 51.389, "category": "strikes"},
    "roaring lion": {"name": "Tel Aviv", "country": "Israel", "lat": 32.0853, "lng": 34.7818, "category": "strikes"},
}

# Priority order for location matching (more specific first)
LOCATION_PRIORITY = [
    "bandar abbas", "beqaa", "tyre", "akrotiri", "diego garcia",
    "raf base", "british base", "strait of hormuz", "hormuz",
    "west bank", "red sea", "oil price", "opec",
    "isfahan", "shiraz", "qom", "tehran", "khamenei", "irgc",
    "tel aviv", "haifa", "jerusalem", "netanyahu", "idf",
    "beirut", "hezbollah",
    "gaza", "rafah",
    "erbil", "riyadh", "dubai", "abu dhabi",
    "doha", "sanaa", "houthi", "damascus", "cairo", "amman",
    "iran", "israel", "lebanon", "saudi", "uae", "qatar",
    "bahrain", "kuwait", "iraq", "syria", "yemen",
    "egypt", "jordan", "oman", "cyprus", "starmer",
    "persian gulf", "gulf state", "middle east", "mideast",
    "epic fury", "roaring lion",
]


def is_middle_east_relevant(title, summary=""):
    """Check if an article is relevant to Middle East news."""
    text = (title + " " + summary).lower()
    return any(kw in text for kw in ME_KEYWORDS)


def get_location(title, summary=""):
    """Determine the best location for an article based on keywords."""
    text = (title + " " + summary).lower()
    for kw in LOCATION_PRIORITY:
        if kw in text:
            return LOCATION_MAP[kw]
    return None


def fetch_feeds(hours_back=48):
    """Fetch articles from all RSS feeds."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    articles = []
    seen_titles = set()

    for feed_info in FEEDS:
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries:
                title = entry.get("title", "").strip()
                if not title or title in seen_titles:
                    continue

                # Parse publication time
                pub_time = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    pub_time = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    pub_time = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)

                if pub_time and pub_time < cutoff:
                    continue

                summary = entry.get("summary", "")
                if not is_middle_east_relevant(title, summary):
                    continue

                location = get_location(title, summary)
                if not location:
                    continue

                url = entry.get("link", "")
                if not url:
                    continue

                time_str = pub_time.strftime("%Y-%m-%dT%H:%M:%SZ") if pub_time else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

                # Clean title: remove quotes that would break JS, strip HTML
                clean_title = re.sub(r'<[^>]+>', '', title)
                clean_title = clean_title.replace('"', "'").replace("\\", "")

                articles.append({
                    "title": clean_title,
                    "source": feed_info["source"],
                    "url": url,
                    "time": time_str,
                    "location": location,
                })
                seen_titles.add(title)

        except Exception as e:
            print(f"  Warning: Failed to fetch {feed_info['source']}: {e}")

    print(f"  Found {len(articles)} Middle East articles from {len(FEEDS)} feeds")
    return articles


def group_by_location(articles):
    """Group articles by location."""
    locations = {}
    for article in articles:
        loc = article["location"]
        key = loc["name"]
        if key not in locations:
            locations[key] = {
                "name": loc["name"],
                "country": loc["country"],
                "lat": loc["lat"],
                "lng": loc["lng"],
                "category": loc["category"],
                "articles": [],
            }
        locations[key]["articles"].append({
            "title": article["title"],
            "source": article["source"],
            "url": article["url"],
            "time": article["time"],
        })
    return locations


def generate_js_data(locations):
    """Generate the JavaScript locations array."""
    lines = ["const locations = ["]

    for loc in sorted(locations.values(), key=lambda l: -len(l["articles"])):
        lines.append("  {")
        lines.append(f'    name: "{loc["name"]}", country: "{loc["country"]}",')
        lines.append(f'    lat: {loc["lat"]}, lng: {loc["lng"]},')
        lines.append(f'    category: "{loc["category"]}",')
        lines.append("    articles: [")
        for a in sorted(loc["articles"], key=lambda x: x["time"], reverse=True):
            title = a["title"].replace("\\", "").replace('"', "'")
            lines.append(f'      {{ title: "{title}", source: "{a["source"]}", url: "{a["url"]}", time: "{a["time"]}" }},')
        lines.append("    ]")
        lines.append("  },")

    lines.append("];")
    return "\n".join(lines)


def parse_existing_articles(html):
    """Parse existing articles from the index.html JavaScript data."""
    existing = {}
    # Find all location blocks
    loc_pattern = r'name:\s*"([^"]+)",\s*country:\s*"([^"]+)",\s*\n\s*lat:\s*([\d.-]+),\s*lng:\s*([\d.-]+),\s*\n\s*category:\s*"([^"]+)",\s*\n\s*articles:\s*\[(.*?)\]'
    for m in re.finditer(loc_pattern, html, re.DOTALL):
        name, country, lat, lng, category, articles_block = m.groups()
        articles = []
        art_pattern = r'title:\s*"((?:[^"\\]|\\.)*)"\s*,\s*source:\s*"([^"]*)"\s*,\s*url:\s*"([^"]*)"\s*,\s*time:\s*"([^"]*)"'
        for am in re.finditer(art_pattern, articles_block):
            articles.append({
                "title": am.group(1),
                "source": am.group(2),
                "url": am.group(3),
                "time": am.group(4),
            })
        existing[name] = {
            "name": name,
            "country": country,
            "lat": float(lat),
            "lng": float(lng),
            "category": category,
            "articles": articles,
        }
    return existing


def merge_locations(existing, new_locations):
    """Merge new articles into existing locations, avoiding duplicates."""
    merged = dict(existing)  # Start with all existing data

    for name, new_loc in new_locations.items():
        if name in merged:
            # Add new articles that don't already exist (by URL)
            existing_urls = {a["url"] for a in merged[name]["articles"]}
            for article in new_loc["articles"]:
                if article["url"] not in existing_urls:
                    merged[name]["articles"].append(article)
                    existing_urls.add(article["url"])
        else:
            # New location entirely
            merged[name] = new_loc

    # Trim old articles (keep last 7 days max, or 500 articles per location)
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
    for name in merged:
        merged[name]["articles"] = [
            a for a in merged[name]["articles"]
            if a["time"] >= cutoff_str or a["time"] == ""
        ]
        # Cap at 500 per location
        merged[name]["articles"] = merged[name]["articles"][:500]

    # Remove locations with no articles
    merged = {k: v for k, v in merged.items() if v["articles"]}

    return merged


def update_html(js_data):
    """Update the index.html file with new location data."""
    html_path = Path(__file__).parent / "index.html"
    html = html_path.read_text()

    # Replace the locations array
    pattern = r"const locations = \[.*?\];\s*\n"
    replacement = js_data + "\n"

    # Use re.DOTALL to match across lines
    new_html = re.sub(pattern, replacement, html, flags=re.DOTALL)

    # Update the date badge
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%-d %B %Y")
    new_html = re.sub(
        r'<div class="date-badge">.*?</div>',
        f'<div class="date-badge">{date_str}</div>',
        new_html,
    )

    # Update last-updated timestamp if present, or add one
    update_str = now.strftime("%H:%M UTC, %-d %b %Y")
    if "last-updated" in new_html:
        new_html = re.sub(
            r'<span id="last-updated">.*?</span>',
            f'<span id="last-updated">{update_str}</span>',
            new_html,
        )

    html_path.write_text(new_html)
    print(f"  Updated index.html ({len(new_html)} bytes)")


def main():
    print("PressRadar.me — Fetching news...")

    # Parse existing articles from HTML
    html_path = Path(__file__).parent / "index.html"
    html = html_path.read_text()
    existing = parse_existing_articles(html)
    existing_count = sum(len(loc["articles"]) for loc in existing.values())
    print(f"  Existing: {existing_count} articles across {len(existing)} locations")

    # Fetch new articles from RSS feeds (last 48 hours)
    articles = fetch_feeds(hours_back=48)

    if not articles:
        print("  No new articles found. Keeping existing data.")
        return

    # Group new articles by location
    new_locations = group_by_location(articles)
    print(f"  New: {len(articles)} articles across {len(new_locations)} locations")

    # Merge new with existing (preserves old articles, adds new ones)
    merged = merge_locations(existing, new_locations)
    total = sum(len(loc["articles"]) for loc in merged.values())
    print(f"  Merged: {total} articles across {len(merged)} locations")

    # Generate JS and update HTML
    js_data = generate_js_data(merged)
    update_html(js_data)

    print("  Done!")


if __name__ == "__main__":
    main()
