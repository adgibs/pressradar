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


def update_html(js_data, html_file="index.html"):
    """Update an HTML file with new location data."""
    html_path = Path(__file__).parent / html_file
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
    print(f"  Updated {html_file} ({len(new_html)} bytes)")


# ── Ukraine Region Configuration ─────────────────────────────────
UKRAINE_FEEDS = [
    {"url": "https://feeds.bbci.co.uk/news/world/europe/rss.xml", "source": "BBC News"},
    {"url": "https://www.theguardian.com/world/ukraine/rss", "source": "The Guardian"},
    {"url": "https://feeds.skynews.com/feeds/rss/world.xml", "source": "Sky News"},
    {"url": "https://www.aljazeera.com/xml/rss/all.xml", "source": "Al Jazeera"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Europe.xml", "source": "New York Times"},
    {"url": "https://feeds.washingtonpost.com/rss/world", "source": "Washington Post"},
    {"url": "https://www.france24.com/en/europe/rss", "source": "France 24"},
    {"url": "https://feeds.npr.org/1004/rss.xml", "source": "NPR"},
    {"url": "https://feeds.nbcnews.com/nbcnews/public/world", "source": "NBC News"},
    {"url": "https://www.cbsnews.com/latest/rss/world", "source": "CBS News"},
]

UKRAINE_KEYWORDS = [
    "ukraine", "kyiv", "kiev", "kharkiv", "zaporizhzhia", "odesa", "odessa",
    "kherson", "donetsk", "luhansk", "mariupol", "crimea", "dnipro", "sumy",
    "kursk", "moscow", "russia", "russian", "zelensky", "putin", "kremlin",
    "donbas", "bakhmut", "avdiivka", "nato", "wagner",
]

UKRAINE_LOCATION_MAP = {
    "kyiv": {"name": "Kyiv", "country": "Ukraine", "lat": 50.4501, "lng": 30.5234, "category": "conflict"},
    "kiev": {"name": "Kyiv", "country": "Ukraine", "lat": 50.4501, "lng": 30.5234, "category": "conflict"},
    "kharkiv": {"name": "Kharkiv", "country": "Ukraine", "lat": 49.9935, "lng": 36.2304, "category": "conflict"},
    "zaporizhzhia": {"name": "Zaporizhzhia", "country": "Ukraine", "lat": 47.8388, "lng": 35.1396, "category": "humanitarian"},
    "odesa": {"name": "Odesa", "country": "Ukraine", "lat": 46.4825, "lng": 30.7233, "category": "conflict"},
    "odessa": {"name": "Odesa", "country": "Ukraine", "lat": 46.4825, "lng": 30.7233, "category": "conflict"},
    "kherson": {"name": "Kherson", "country": "Ukraine", "lat": 46.6354, "lng": 32.6169, "category": "humanitarian"},
    "donetsk": {"name": "Donetsk", "country": "Ukraine", "lat": 48.0159, "lng": 37.8029, "category": "conflict"},
    "donbas": {"name": "Donetsk", "country": "Ukraine", "lat": 48.0159, "lng": 37.8029, "category": "conflict"},
    "luhansk": {"name": "Donetsk", "country": "Ukraine", "lat": 48.0159, "lng": 37.8029, "category": "conflict"},
    "mariupol": {"name": "Mariupol", "country": "Ukraine", "lat": 47.0958, "lng": 37.5494, "category": "humanitarian"},
    "crimea": {"name": "Crimea", "country": "Ukraine", "lat": 44.9521, "lng": 34.1024, "category": "conflict"},
    "dnipro": {"name": "Dnipro", "country": "Ukraine", "lat": 48.4647, "lng": 35.0462, "category": "conflict"},
    "sumy": {"name": "Sumy", "country": "Ukraine", "lat": 50.9077, "lng": 34.7981, "category": "conflict"},
    "kursk": {"name": "Kursk", "country": "Russia", "lat": 51.7304, "lng": 36.1926, "category": "conflict"},
    "moscow": {"name": "Moscow", "country": "Russia", "lat": 55.7558, "lng": 37.6173, "category": "diplomacy"},
    "kremlin": {"name": "Moscow", "country": "Russia", "lat": 55.7558, "lng": 37.6173, "category": "diplomacy"},
    "putin": {"name": "Moscow", "country": "Russia", "lat": 55.7558, "lng": 37.6173, "category": "diplomacy"},
    "bakhmut": {"name": "Donetsk", "country": "Ukraine", "lat": 48.0159, "lng": 37.8029, "category": "conflict"},
    "avdiivka": {"name": "Donetsk", "country": "Ukraine", "lat": 48.0159, "lng": 37.8029, "category": "conflict"},
    "zelensky": {"name": "Kyiv", "country": "Ukraine", "lat": 50.4501, "lng": 30.5234, "category": "diplomacy"},
    "ukraine": {"name": "Kyiv", "country": "Ukraine", "lat": 50.4501, "lng": 30.5234, "category": "conflict"},
    "russia": {"name": "Moscow", "country": "Russia", "lat": 55.7558, "lng": 37.6173, "category": "conflict"},
    "russian": {"name": "Moscow", "country": "Russia", "lat": 55.7558, "lng": 37.6173, "category": "conflict"},
    "nato": {"name": "Kyiv", "country": "Ukraine", "lat": 50.4501, "lng": 30.5234, "category": "nato"},
    "wagner": {"name": "Moscow", "country": "Russia", "lat": 55.7558, "lng": 37.6173, "category": "conflict"},
}

UKRAINE_LOCATION_PRIORITY = [
    "bakhmut", "avdiivka", "kharkiv", "zaporizhzhia", "odesa", "odessa",
    "kherson", "donetsk", "donbas", "luhansk", "mariupol", "crimea",
    "dnipro", "sumy", "kursk", "kyiv", "kiev",
    "kremlin", "moscow", "putin",
    "zelensky", "nato", "wagner",
    "ukraine", "russia", "russian",
]


# ── East Asia Region Configuration ───────────────────────────────
EAST_ASIA_FEEDS = [
    {"url": "https://feeds.bbci.co.uk/news/world/asia/rss.xml", "source": "BBC News"},
    {"url": "https://www.theguardian.com/world/asia-pacific/rss", "source": "The Guardian"},
    {"url": "https://feeds.skynews.com/feeds/rss/world.xml", "source": "Sky News"},
    {"url": "https://www.aljazeera.com/xml/rss/all.xml", "source": "Al Jazeera"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/AsiaPacific.xml", "source": "New York Times"},
    {"url": "https://feeds.washingtonpost.com/rss/world", "source": "Washington Post"},
    {"url": "https://www.france24.com/en/asia-pacific/rss", "source": "France 24"},
    {"url": "https://feeds.npr.org/1004/rss.xml", "source": "NPR"},
    {"url": "https://feeds.nbcnews.com/nbcnews/public/world", "source": "NBC News"},
    {"url": "https://www.cbsnews.com/latest/rss/world", "source": "CBS News"},
    {"url": "https://www3.nhk.or.jp/nhkworld/en/news/rss/index.xml", "source": "NHK World"},
]

EAST_ASIA_KEYWORDS = [
    "taiwan", "taipei", "china", "chinese", "beijing", "shanghai",
    "south korea", "korea", "seoul", "north korea", "pyongyang", "kim jong",
    "japan", "tokyo", "okinawa", "philippines", "manila", "south china sea",
    "hong kong", "vietnam", "hanoi", "singapore", "xi jinping",
    "indo-pacific", "indopacific", "aukus", "quad",
]

EAST_ASIA_LOCATION_MAP = {
    "taipei": {"name": "Taipei", "country": "Taiwan", "lat": 25.0330, "lng": 121.5654, "category": "territorial"},
    "taiwan": {"name": "Taipei", "country": "Taiwan", "lat": 25.0330, "lng": 121.5654, "category": "territorial"},
    "beijing": {"name": "Beijing", "country": "China", "lat": 39.9042, "lng": 116.4074, "category": "military"},
    "xi jinping": {"name": "Beijing", "country": "China", "lat": 39.9042, "lng": 116.4074, "category": "diplomacy"},
    "shanghai": {"name": "Shanghai", "country": "China", "lat": 31.2304, "lng": 121.4737, "category": "trade"},
    "hong kong": {"name": "Hong Kong", "country": "China", "lat": 22.3193, "lng": 114.1694, "category": "trade"},
    "seoul": {"name": "Seoul", "country": "South Korea", "lat": 37.5665, "lng": 126.9780, "category": "diplomacy"},
    "south korea": {"name": "Seoul", "country": "South Korea", "lat": 37.5665, "lng": 126.9780, "category": "diplomacy"},
    "pyongyang": {"name": "Pyongyang", "country": "North Korea", "lat": 39.0392, "lng": 125.7625, "category": "military"},
    "north korea": {"name": "Pyongyang", "country": "North Korea", "lat": 39.0392, "lng": 125.7625, "category": "military"},
    "kim jong": {"name": "Pyongyang", "country": "North Korea", "lat": 39.0392, "lng": 125.7625, "category": "military"},
    "tokyo": {"name": "Tokyo", "country": "Japan", "lat": 35.6762, "lng": 139.6503, "category": "diplomacy"},
    "japan": {"name": "Tokyo", "country": "Japan", "lat": 35.6762, "lng": 139.6503, "category": "diplomacy"},
    "okinawa": {"name": "Okinawa", "country": "Japan", "lat": 26.3344, "lng": 127.8056, "category": "military"},
    "manila": {"name": "Manila", "country": "Philippines", "lat": 14.5995, "lng": 120.9842, "category": "territorial"},
    "philippines": {"name": "Manila", "country": "Philippines", "lat": 14.5995, "lng": 120.9842, "category": "territorial"},
    "south china sea": {"name": "South China Sea", "country": "International", "lat": 15.0, "lng": 115.0, "category": "territorial"},
    "hanoi": {"name": "Hanoi", "country": "Vietnam", "lat": 21.0285, "lng": 105.8542, "category": "diplomacy"},
    "vietnam": {"name": "Hanoi", "country": "Vietnam", "lat": 21.0285, "lng": 105.8542, "category": "diplomacy"},
    "singapore": {"name": "Singapore", "country": "Singapore", "lat": 1.3521, "lng": 103.8198, "category": "trade"},
    "china": {"name": "Beijing", "country": "China", "lat": 39.9042, "lng": 116.4074, "category": "military"},
    "chinese": {"name": "Beijing", "country": "China", "lat": 39.9042, "lng": 116.4074, "category": "military"},
    "korea": {"name": "Seoul", "country": "South Korea", "lat": 37.5665, "lng": 126.9780, "category": "diplomacy"},
    "indo-pacific": {"name": "South China Sea", "country": "International", "lat": 15.0, "lng": 115.0, "category": "military"},
    "indopacific": {"name": "South China Sea", "country": "International", "lat": 15.0, "lng": 115.0, "category": "military"},
    "aukus": {"name": "Tokyo", "country": "Japan", "lat": 35.6762, "lng": 139.6503, "category": "military"},
    "quad": {"name": "Tokyo", "country": "Japan", "lat": 35.6762, "lng": 139.6503, "category": "diplomacy"},
}

EAST_ASIA_LOCATION_PRIORITY = [
    "taipei", "south china sea", "hong kong", "okinawa", "shanghai",
    "pyongyang", "north korea", "kim jong",
    "xi jinping", "beijing", "manila", "seoul", "south korea",
    "tokyo", "hanoi", "singapore",
    "taiwan", "philippines", "japan", "vietnam",
    "indo-pacific", "indopacific", "aukus", "quad",
    "china", "chinese", "korea",
]


# ── Africa Region Configuration ───────────────────────────────────
AFRICA_FEEDS = [
    {"url": "https://feeds.bbci.co.uk/news/world/africa/rss.xml", "source": "BBC News"},
    {"url": "https://www.theguardian.com/world/africa/rss", "source": "The Guardian"},
    {"url": "https://feeds.skynews.com/feeds/rss/world.xml", "source": "Sky News"},
    {"url": "https://www.aljazeera.com/xml/rss/all.xml", "source": "Al Jazeera"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Africa.xml", "source": "New York Times"},
    {"url": "https://feeds.washingtonpost.com/rss/world", "source": "Washington Post"},
    {"url": "https://www.france24.com/en/africa/rss", "source": "France 24"},
    {"url": "https://feeds.npr.org/1004/rss.xml", "source": "NPR"},
]

AFRICA_KEYWORDS = [
    "sudan", "khartoum", "nigeria", "lagos", "abuja", "kenya", "nairobi",
    "ethiopia", "addis ababa", "congo", "kinshasa", "goma", "somalia",
    "mogadishu", "south africa", "johannesburg", "cape town", "egypt",
    "cairo", "libya", "tripoli", "mali", "bamako", "sahel", "niger",
    "burkina faso", "chad", "cameroon", "ghana", "accra", "senegal",
    "mozambique", "tanzania", "uganda", "rwanda", "african union",
]

AFRICA_LOCATION_MAP = {
    "khartoum": {"name": "Khartoum", "country": "Sudan", "lat": 15.5007, "lng": 32.5599, "category": "conflict"},
    "sudan": {"name": "Khartoum", "country": "Sudan", "lat": 15.5007, "lng": 32.5599, "category": "conflict"},
    "lagos": {"name": "Lagos", "country": "Nigeria", "lat": 6.5244, "lng": 3.3792, "category": "economic"},
    "abuja": {"name": "Abuja", "country": "Nigeria", "lat": 9.0579, "lng": 7.4951, "category": "political"},
    "nigeria": {"name": "Lagos", "country": "Nigeria", "lat": 6.5244, "lng": 3.3792, "category": "economic"},
    "nairobi": {"name": "Nairobi", "country": "Kenya", "lat": -1.2921, "lng": 36.8219, "category": "political"},
    "kenya": {"name": "Nairobi", "country": "Kenya", "lat": -1.2921, "lng": 36.8219, "category": "political"},
    "addis ababa": {"name": "Addis Ababa", "country": "Ethiopia", "lat": 9.0250, "lng": 38.7469, "category": "conflict"},
    "ethiopia": {"name": "Addis Ababa", "country": "Ethiopia", "lat": 9.0250, "lng": 38.7469, "category": "conflict"},
    "kinshasa": {"name": "Kinshasa", "country": "DR Congo", "lat": -4.4419, "lng": 15.2663, "category": "conflict"},
    "congo": {"name": "Kinshasa", "country": "DR Congo", "lat": -4.4419, "lng": 15.2663, "category": "conflict"},
    "goma": {"name": "Goma", "country": "DR Congo", "lat": -1.6585, "lng": 29.2206, "category": "humanitarian"},
    "mogadishu": {"name": "Mogadishu", "country": "Somalia", "lat": 2.0469, "lng": 45.3182, "category": "conflict"},
    "somalia": {"name": "Mogadishu", "country": "Somalia", "lat": 2.0469, "lng": 45.3182, "category": "conflict"},
    "johannesburg": {"name": "Johannesburg", "country": "South Africa", "lat": -26.2041, "lng": 28.0473, "category": "economic"},
    "south africa": {"name": "Johannesburg", "country": "South Africa", "lat": -26.2041, "lng": 28.0473, "category": "economic"},
    "cape town": {"name": "Cape Town", "country": "South Africa", "lat": -33.9249, "lng": 18.4241, "category": "political"},
    "cairo": {"name": "Cairo", "country": "Egypt", "lat": 30.0444, "lng": 31.2357, "category": "political"},
    "egypt": {"name": "Cairo", "country": "Egypt", "lat": 30.0444, "lng": 31.2357, "category": "political"},
    "tripoli": {"name": "Tripoli", "country": "Libya", "lat": 32.8872, "lng": 13.1913, "category": "conflict"},
    "libya": {"name": "Tripoli", "country": "Libya", "lat": 32.8872, "lng": 13.1913, "category": "conflict"},
    "bamako": {"name": "Bamako", "country": "Mali", "lat": 12.6392, "lng": -8.0029, "category": "conflict"},
    "mali": {"name": "Bamako", "country": "Mali", "lat": 12.6392, "lng": -8.0029, "category": "conflict"},
    "sahel": {"name": "Sahel Region", "country": "West Africa", "lat": 15.0, "lng": 0.0, "category": "conflict"},
    "niger": {"name": "Sahel Region", "country": "West Africa", "lat": 15.0, "lng": 0.0, "category": "conflict"},
    "burkina faso": {"name": "Sahel Region", "country": "West Africa", "lat": 15.0, "lng": 0.0, "category": "conflict"},
    "chad": {"name": "Sahel Region", "country": "West Africa", "lat": 15.0, "lng": 0.0, "category": "conflict"},
    "accra": {"name": "Accra", "country": "Ghana", "lat": 5.6037, "lng": -0.1870, "category": "economic"},
    "ghana": {"name": "Accra", "country": "Ghana", "lat": 5.6037, "lng": -0.1870, "category": "economic"},
    "african union": {"name": "Addis Ababa", "country": "Ethiopia", "lat": 9.0250, "lng": 38.7469, "category": "political"},
}

AFRICA_LOCATION_PRIORITY = [
    "khartoum", "goma", "mogadishu", "bamako", "addis ababa",
    "cape town", "johannesburg", "tripoli", "kinshasa",
    "lagos", "abuja", "nairobi", "cairo", "accra",
    "sahel", "burkina faso", "niger", "chad",
    "sudan", "nigeria", "kenya", "ethiopia", "congo", "somalia",
    "south africa", "egypt", "libya", "mali", "ghana",
    "african union",
]


# ── Europe Region Configuration ──────────────────────────────────
EUROPE_FEEDS = [
    {"url": "https://feeds.bbci.co.uk/news/world/europe/rss.xml", "source": "BBC News"},
    {"url": "https://www.theguardian.com/world/europe-news/rss", "source": "The Guardian"},
    {"url": "https://feeds.skynews.com/feeds/rss/world.xml", "source": "Sky News"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Europe.xml", "source": "New York Times"},
    {"url": "https://feeds.washingtonpost.com/rss/world", "source": "Washington Post"},
    {"url": "https://www.france24.com/en/europe/rss", "source": "France 24"},
    {"url": "https://www.dw.com/rss/en/eu/s-31459", "source": "Deutsche Welle"},
    {"url": "https://feeds.npr.org/1004/rss.xml", "source": "NPR"},
]

EUROPE_KEYWORDS = [
    "london", "britain", "british", "uk ", "brexit", "starmer",
    "brussels", "eu ", "european union", "european commission",
    "paris", "france", "french", "macron",
    "berlin", "germany", "german", "merz", "scholz",
    "rome", "italy", "italian", "meloni",
    "madrid", "spain", "spanish", "sanchez",
    "warsaw", "poland", "polish",
    "ankara", "turkey", "turkish", "erdogan", "istanbul",
    "athens", "greece", "greek",
    "stockholm", "sweden", "swedish", "nato",
    "bucharest", "romania", "romanian",
    "geneva", "switzerland",
    "the hague", "netherlands", "dutch",
    "dublin", "ireland", "irish",
]

EUROPE_LOCATION_MAP = {
    "london": {"name": "London", "country": "United Kingdom", "lat": 51.5074, "lng": -0.1278, "category": "political"},
    "britain": {"name": "London", "country": "United Kingdom", "lat": 51.5074, "lng": -0.1278, "category": "political"},
    "british": {"name": "London", "country": "United Kingdom", "lat": 51.5074, "lng": -0.1278, "category": "political"},
    "starmer": {"name": "London", "country": "United Kingdom", "lat": 51.5074, "lng": -0.1278, "category": "political"},
    "brussels": {"name": "Brussels", "country": "Belgium", "lat": 50.8503, "lng": 4.3517, "category": "political"},
    "european union": {"name": "Brussels", "country": "Belgium", "lat": 50.8503, "lng": 4.3517, "category": "political"},
    "european commission": {"name": "Brussels", "country": "Belgium", "lat": 50.8503, "lng": 4.3517, "category": "political"},
    "paris": {"name": "Paris", "country": "France", "lat": 48.8566, "lng": 2.3522, "category": "political"},
    "france": {"name": "Paris", "country": "France", "lat": 48.8566, "lng": 2.3522, "category": "political"},
    "french": {"name": "Paris", "country": "France", "lat": 48.8566, "lng": 2.3522, "category": "political"},
    "macron": {"name": "Paris", "country": "France", "lat": 48.8566, "lng": 2.3522, "category": "political"},
    "berlin": {"name": "Berlin", "country": "Germany", "lat": 52.5200, "lng": 13.4050, "category": "economic"},
    "germany": {"name": "Berlin", "country": "Germany", "lat": 52.5200, "lng": 13.4050, "category": "economic"},
    "german": {"name": "Berlin", "country": "Germany", "lat": 52.5200, "lng": 13.4050, "category": "economic"},
    "merz": {"name": "Berlin", "country": "Germany", "lat": 52.5200, "lng": 13.4050, "category": "political"},
    "scholz": {"name": "Berlin", "country": "Germany", "lat": 52.5200, "lng": 13.4050, "category": "political"},
    "rome": {"name": "Rome", "country": "Italy", "lat": 41.9028, "lng": 12.4964, "category": "political"},
    "italy": {"name": "Rome", "country": "Italy", "lat": 41.9028, "lng": 12.4964, "category": "political"},
    "italian": {"name": "Rome", "country": "Italy", "lat": 41.9028, "lng": 12.4964, "category": "political"},
    "meloni": {"name": "Rome", "country": "Italy", "lat": 41.9028, "lng": 12.4964, "category": "political"},
    "madrid": {"name": "Madrid", "country": "Spain", "lat": 40.4168, "lng": -3.7038, "category": "economic"},
    "spain": {"name": "Madrid", "country": "Spain", "lat": 40.4168, "lng": -3.7038, "category": "economic"},
    "spanish": {"name": "Madrid", "country": "Spain", "lat": 40.4168, "lng": -3.7038, "category": "economic"},
    "sanchez": {"name": "Madrid", "country": "Spain", "lat": 40.4168, "lng": -3.7038, "category": "political"},
    "warsaw": {"name": "Warsaw", "country": "Poland", "lat": 52.2297, "lng": 21.0122, "category": "security"},
    "poland": {"name": "Warsaw", "country": "Poland", "lat": 52.2297, "lng": 21.0122, "category": "security"},
    "polish": {"name": "Warsaw", "country": "Poland", "lat": 52.2297, "lng": 21.0122, "category": "security"},
    "ankara": {"name": "Ankara", "country": "Turkey", "lat": 39.9334, "lng": 32.8597, "category": "security"},
    "turkey": {"name": "Ankara", "country": "Turkey", "lat": 39.9334, "lng": 32.8597, "category": "security"},
    "turkish": {"name": "Ankara", "country": "Turkey", "lat": 39.9334, "lng": 32.8597, "category": "security"},
    "erdogan": {"name": "Ankara", "country": "Turkey", "lat": 39.9334, "lng": 32.8597, "category": "political"},
    "istanbul": {"name": "Istanbul", "country": "Turkey", "lat": 41.0082, "lng": 28.9784, "category": "economic"},
    "athens": {"name": "Athens", "country": "Greece", "lat": 37.9838, "lng": 23.7275, "category": "social"},
    "greece": {"name": "Athens", "country": "Greece", "lat": 37.9838, "lng": 23.7275, "category": "social"},
    "greek": {"name": "Athens", "country": "Greece", "lat": 37.9838, "lng": 23.7275, "category": "social"},
    "stockholm": {"name": "Stockholm", "country": "Sweden", "lat": 59.3293, "lng": 18.0686, "category": "security"},
    "sweden": {"name": "Stockholm", "country": "Sweden", "lat": 59.3293, "lng": 18.0686, "category": "security"},
    "swedish": {"name": "Stockholm", "country": "Sweden", "lat": 59.3293, "lng": 18.0686, "category": "security"},
    "bucharest": {"name": "Bucharest", "country": "Romania", "lat": 44.4268, "lng": 26.1025, "category": "security"},
    "romania": {"name": "Bucharest", "country": "Romania", "lat": 44.4268, "lng": 26.1025, "category": "security"},
    "geneva": {"name": "Geneva", "country": "Switzerland", "lat": 46.2044, "lng": 6.1432, "category": "political"},
    "switzerland": {"name": "Geneva", "country": "Switzerland", "lat": 46.2044, "lng": 6.1432, "category": "political"},
    "the hague": {"name": "The Hague", "country": "Netherlands", "lat": 52.0705, "lng": 4.3007, "category": "political"},
    "netherlands": {"name": "The Hague", "country": "Netherlands", "lat": 52.0705, "lng": 4.3007, "category": "political"},
    "dutch": {"name": "The Hague", "country": "Netherlands", "lat": 52.0705, "lng": 4.3007, "category": "political"},
    "dublin": {"name": "Dublin", "country": "Ireland", "lat": 53.3498, "lng": -6.2603, "category": "economic"},
    "ireland": {"name": "Dublin", "country": "Ireland", "lat": 53.3498, "lng": -6.2603, "category": "economic"},
    "irish": {"name": "Dublin", "country": "Ireland", "lat": 53.3498, "lng": -6.2603, "category": "economic"},
}

EUROPE_LOCATION_PRIORITY = [
    "european commission", "european union", "the hague",
    "istanbul", "ankara", "erdogan",
    "london", "starmer", "brussels", "paris", "macron",
    "berlin", "merz", "scholz", "rome", "meloni",
    "madrid", "sanchez", "warsaw", "athens",
    "stockholm", "bucharest", "geneva", "dublin",
    "britain", "british", "france", "french", "germany", "german",
    "italy", "italian", "spain", "spanish", "poland", "polish",
    "turkey", "turkish", "greece", "greek", "sweden", "swedish",
    "romania", "switzerland", "netherlands", "dutch", "ireland", "irish",
    "nato",
]


# ── South Asia Region Configuration ──────────────────────────────
SOUTH_ASIA_FEEDS = [
    {"url": "https://feeds.bbci.co.uk/news/world/south_asia/rss.xml", "source": "BBC News"},
    {"url": "https://www.theguardian.com/world/south-and-central-asia/rss", "source": "The Guardian"},
    {"url": "https://feeds.skynews.com/feeds/rss/world.xml", "source": "Sky News"},
    {"url": "https://www.aljazeera.com/xml/rss/all.xml", "source": "Al Jazeera"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/AsiaPacific.xml", "source": "New York Times"},
    {"url": "https://feeds.washingtonpost.com/rss/world", "source": "Washington Post"},
    {"url": "https://www.france24.com/en/asia-pacific/rss", "source": "France 24"},
    {"url": "https://feeds.npr.org/1004/rss.xml", "source": "NPR"},
]

SOUTH_ASIA_KEYWORDS = [
    "india", "indian", "modi", "new delhi", "mumbai", "chennai",
    "pakistan", "pakistani", "islamabad", "karachi", "kashmir",
    "bangladesh", "dhaka", "sri lanka", "colombo",
    "nepal", "kathmandu", "afghanistan", "kabul", "taliban",
    "myanmar", "yangon", "rohingya", "maldives",
]

SOUTH_ASIA_LOCATION_MAP = {
    "new delhi": {"name": "New Delhi", "country": "India", "lat": 28.6139, "lng": 77.2090, "category": "political"},
    "mumbai": {"name": "Mumbai", "country": "India", "lat": 19.0760, "lng": 72.8777, "category": "economic"},
    "chennai": {"name": "Chennai", "country": "India", "lat": 13.0827, "lng": 80.2707, "category": "climate"},
    "modi": {"name": "New Delhi", "country": "India", "lat": 28.6139, "lng": 77.2090, "category": "political"},
    "india": {"name": "New Delhi", "country": "India", "lat": 28.6139, "lng": 77.2090, "category": "political"},
    "indian": {"name": "New Delhi", "country": "India", "lat": 28.6139, "lng": 77.2090, "category": "political"},
    "islamabad": {"name": "Islamabad", "country": "Pakistan", "lat": 33.6844, "lng": 73.0479, "category": "political"},
    "karachi": {"name": "Karachi", "country": "Pakistan", "lat": 24.8607, "lng": 67.0011, "category": "security"},
    "pakistan": {"name": "Islamabad", "country": "Pakistan", "lat": 33.6844, "lng": 73.0479, "category": "political"},
    "pakistani": {"name": "Islamabad", "country": "Pakistan", "lat": 33.6844, "lng": 73.0479, "category": "political"},
    "kashmir": {"name": "Kashmir", "country": "India/Pakistan", "lat": 34.0837, "lng": 74.7973, "category": "security"},
    "dhaka": {"name": "Dhaka", "country": "Bangladesh", "lat": 23.8103, "lng": 90.4125, "category": "climate"},
    "bangladesh": {"name": "Dhaka", "country": "Bangladesh", "lat": 23.8103, "lng": 90.4125, "category": "climate"},
    "colombo": {"name": "Colombo", "country": "Sri Lanka", "lat": 6.9271, "lng": 79.8612, "category": "economic"},
    "sri lanka": {"name": "Colombo", "country": "Sri Lanka", "lat": 6.9271, "lng": 79.8612, "category": "economic"},
    "kathmandu": {"name": "Kathmandu", "country": "Nepal", "lat": 27.7172, "lng": 85.3240, "category": "political"},
    "nepal": {"name": "Kathmandu", "country": "Nepal", "lat": 27.7172, "lng": 85.3240, "category": "political"},
    "kabul": {"name": "Kabul", "country": "Afghanistan", "lat": 34.5553, "lng": 69.2075, "category": "humanitarian"},
    "afghanistan": {"name": "Kabul", "country": "Afghanistan", "lat": 34.5553, "lng": 69.2075, "category": "humanitarian"},
    "taliban": {"name": "Kabul", "country": "Afghanistan", "lat": 34.5553, "lng": 69.2075, "category": "humanitarian"},
    "yangon": {"name": "Yangon", "country": "Myanmar", "lat": 16.8661, "lng": 96.1951, "category": "humanitarian"},
    "myanmar": {"name": "Yangon", "country": "Myanmar", "lat": 16.8661, "lng": 96.1951, "category": "humanitarian"},
    "rohingya": {"name": "Yangon", "country": "Myanmar", "lat": 16.8661, "lng": 96.1951, "category": "humanitarian"},
    "maldives": {"name": "Male", "country": "Maldives", "lat": 4.1755, "lng": 73.5093, "category": "climate"},
}

SOUTH_ASIA_LOCATION_PRIORITY = [
    "new delhi", "mumbai", "chennai", "kashmir",
    "islamabad", "karachi",
    "dhaka", "colombo", "kathmandu", "kabul", "yangon",
    "modi", "taliban", "rohingya",
    "india", "indian", "pakistan", "pakistani",
    "bangladesh", "sri lanka", "nepal", "afghanistan", "myanmar", "maldives",
]


# ── Americas Region Configuration ────────────────────────────────
AMERICAS_FEEDS = [
    {"url": "https://feeds.bbci.co.uk/news/world/latin_america/rss.xml", "source": "BBC News"},
    {"url": "https://www.theguardian.com/world/americas/rss", "source": "The Guardian"},
    {"url": "https://feeds.skynews.com/feeds/rss/world.xml", "source": "Sky News"},
    {"url": "https://www.aljazeera.com/xml/rss/all.xml", "source": "Al Jazeera"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Americas.xml", "source": "New York Times"},
    {"url": "https://feeds.washingtonpost.com/rss/world", "source": "Washington Post"},
    {"url": "https://www.france24.com/en/americas/rss", "source": "France 24"},
    {"url": "https://feeds.npr.org/1004/rss.xml", "source": "NPR"},
    {"url": "https://feeds.nbcnews.com/nbcnews/public/world", "source": "NBC News"},
    {"url": "https://www.cbsnews.com/latest/rss/world", "source": "CBS News"},
]

AMERICAS_KEYWORDS = [
    "mexico", "mexico city", "colombia", "bogota", "venezuela", "caracas",
    "maduro", "argentina", "buenos aires", "milei", "brazil", "brasilia",
    "lula", "sao paulo", "cuba", "havana", "peru", "lima", "chile",
    "santiago", "haiti", "port-au-prince", "guatemala", "panama",
    "canada", "ottawa", "trudeau", "carney",
    "latin america", "central america", "south america",
]

AMERICAS_LOCATION_MAP = {
    "mexico city": {"name": "Mexico City", "country": "Mexico", "lat": 19.4326, "lng": -99.1332, "category": "political"},
    "mexico": {"name": "Mexico City", "country": "Mexico", "lat": 19.4326, "lng": -99.1332, "category": "political"},
    "bogota": {"name": "Bogota", "country": "Colombia", "lat": 4.7110, "lng": -74.0721, "category": "security"},
    "colombia": {"name": "Bogota", "country": "Colombia", "lat": 4.7110, "lng": -74.0721, "category": "security"},
    "caracas": {"name": "Caracas", "country": "Venezuela", "lat": 10.4806, "lng": -66.9036, "category": "political"},
    "venezuela": {"name": "Caracas", "country": "Venezuela", "lat": 10.4806, "lng": -66.9036, "category": "political"},
    "maduro": {"name": "Caracas", "country": "Venezuela", "lat": 10.4806, "lng": -66.9036, "category": "political"},
    "buenos aires": {"name": "Buenos Aires", "country": "Argentina", "lat": -34.6037, "lng": -58.3816, "category": "economic"},
    "argentina": {"name": "Buenos Aires", "country": "Argentina", "lat": -34.6037, "lng": -58.3816, "category": "economic"},
    "milei": {"name": "Buenos Aires", "country": "Argentina", "lat": -34.6037, "lng": -58.3816, "category": "political"},
    "brasilia": {"name": "Brasilia", "country": "Brazil", "lat": -15.7975, "lng": -47.8919, "category": "political"},
    "brazil": {"name": "Brasilia", "country": "Brazil", "lat": -15.7975, "lng": -47.8919, "category": "political"},
    "lula": {"name": "Brasilia", "country": "Brazil", "lat": -15.7975, "lng": -47.8919, "category": "political"},
    "sao paulo": {"name": "Sao Paulo", "country": "Brazil", "lat": -23.5558, "lng": -46.6396, "category": "economic"},
    "havana": {"name": "Havana", "country": "Cuba", "lat": 23.1136, "lng": -82.3666, "category": "political"},
    "cuba": {"name": "Havana", "country": "Cuba", "lat": 23.1136, "lng": -82.3666, "category": "political"},
    "lima": {"name": "Lima", "country": "Peru", "lat": -12.0464, "lng": -77.0428, "category": "economic"},
    "peru": {"name": "Lima", "country": "Peru", "lat": -12.0464, "lng": -77.0428, "category": "economic"},
    "santiago": {"name": "Santiago", "country": "Chile", "lat": -33.4489, "lng": -70.6693, "category": "economic"},
    "chile": {"name": "Santiago", "country": "Chile", "lat": -33.4489, "lng": -70.6693, "category": "economic"},
    "port-au-prince": {"name": "Port-au-Prince", "country": "Haiti", "lat": 18.5944, "lng": -72.3074, "category": "security"},
    "haiti": {"name": "Port-au-Prince", "country": "Haiti", "lat": 18.5944, "lng": -72.3074, "category": "security"},
    "guatemala": {"name": "Guatemala City", "country": "Guatemala", "lat": 14.6349, "lng": -90.5069, "category": "migration"},
    "panama": {"name": "Panama City", "country": "Panama", "lat": 8.9824, "lng": -79.5199, "category": "migration"},
    "ottawa": {"name": "Ottawa", "country": "Canada", "lat": 45.4215, "lng": -75.6972, "category": "political"},
    "canada": {"name": "Ottawa", "country": "Canada", "lat": 45.4215, "lng": -75.6972, "category": "political"},
    "trudeau": {"name": "Ottawa", "country": "Canada", "lat": 45.4215, "lng": -75.6972, "category": "political"},
    "carney": {"name": "Ottawa", "country": "Canada", "lat": 45.4215, "lng": -75.6972, "category": "political"},
    "latin america": {"name": "Mexico City", "country": "Mexico", "lat": 19.4326, "lng": -99.1332, "category": "political"},
    "central america": {"name": "Guatemala City", "country": "Guatemala", "lat": 14.6349, "lng": -90.5069, "category": "migration"},
    "south america": {"name": "Brasilia", "country": "Brazil", "lat": -15.7975, "lng": -47.8919, "category": "political"},
}

AMERICAS_LOCATION_PRIORITY = [
    "mexico city", "buenos aires", "sao paulo", "port-au-prince",
    "bogota", "caracas", "maduro", "brasilia", "lula", "milei",
    "havana", "lima", "santiago", "ottawa", "trudeau", "carney",
    "guatemala", "panama",
    "mexico", "colombia", "venezuela", "argentina", "brazil",
    "cuba", "peru", "chile", "haiti", "canada",
    "latin america", "central america", "south america",
]


def fetch_region(feeds, keywords, location_map, location_priority, region_name, hours_back=48):
    """Fetch articles for a specific region."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    articles = []
    seen_titles = set()

    def is_relevant(title, summary=""):
        text = (title + " " + summary).lower()
        return any(kw in text for kw in keywords)

    def get_loc(title, summary=""):
        text = (title + " " + summary).lower()
        for kw in location_priority:
            if kw in text:
                return location_map[kw]
        return None

    for feed_info in feeds:
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries:
                title = entry.get("title", "").strip()
                if not title or title in seen_titles:
                    continue

                pub_time = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    pub_time = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    pub_time = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)

                if pub_time and pub_time < cutoff:
                    continue

                summary = entry.get("summary", "")
                if not is_relevant(title, summary):
                    continue

                location = get_loc(title, summary)
                if not location:
                    continue

                url = entry.get("link", "")
                if not url:
                    continue

                time_str = pub_time.strftime("%Y-%m-%dT%H:%M:%SZ") if pub_time else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

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

    print(f"  Found {len(articles)} {region_name} articles from {len(feeds)} feeds")
    return articles


def update_region(html_file, feeds, keywords, location_map, location_priority, region_name):
    """Fetch and update a specific region's HTML file."""
    html_path = Path(__file__).parent / html_file
    if not html_path.exists():
        print(f"  Skipping {html_file} — file not found")
        return

    html = html_path.read_text()
    existing = parse_existing_articles(html)
    existing_count = sum(len(loc["articles"]) for loc in existing.values())
    print(f"  [{region_name}] Existing: {existing_count} articles across {len(existing)} locations")

    articles = fetch_region(feeds, keywords, location_map, location_priority, region_name, hours_back=48)

    if not articles and existing_count > 0:
        print(f"  [{region_name}] No new articles found. Keeping existing data.")
        return

    new_locations = group_by_location(articles)
    print(f"  [{region_name}] New: {len(articles)} articles across {len(new_locations)} locations")

    merged = merge_locations(existing, new_locations) if existing else new_locations
    total = sum(len(loc["articles"]) for loc in merged.values())
    print(f"  [{region_name}] Merged: {total} articles across {len(merged)} locations")

    js_data = generate_js_data(merged)
    update_html(js_data, html_file)


def main():
    print("PressRadar.me — Fetching news...")

    # ── Middle East (index.html) ──
    print("\n=== Middle East ===")
    html_path = Path(__file__).parent / "index.html"
    html = html_path.read_text()
    existing = parse_existing_articles(html)
    existing_count = sum(len(loc["articles"]) for loc in existing.values())
    print(f"  Existing: {existing_count} articles across {len(existing)} locations")

    articles = fetch_feeds(hours_back=48)

    if articles or existing_count == 0:
        new_locations = group_by_location(articles)
        print(f"  New: {len(articles)} articles across {len(new_locations)} locations")

        merged = merge_locations(existing, new_locations)
        total = sum(len(loc["articles"]) for loc in merged.values())
        print(f"  Merged: {total} articles across {len(merged)} locations")

        js_data = generate_js_data(merged)
        update_html(js_data, "index.html")
    else:
        print("  No new articles found. Keeping existing data.")

    # ── Ukraine (ukraine.html) ──
    print("\n=== Ukraine ===")
    update_region(
        "ukraine.html",
        UKRAINE_FEEDS,
        UKRAINE_KEYWORDS,
        UKRAINE_LOCATION_MAP,
        UKRAINE_LOCATION_PRIORITY,
        "Ukraine",
    )

    # ── East Asia (east-asia.html) ──
    print("\n=== East Asia ===")
    update_region(
        "east-asia.html",
        EAST_ASIA_FEEDS,
        EAST_ASIA_KEYWORDS,
        EAST_ASIA_LOCATION_MAP,
        EAST_ASIA_LOCATION_PRIORITY,
        "East Asia",
    )

    # ── Africa (africa.html) ──
    print("\n=== Africa ===")
    update_region(
        "africa.html",
        AFRICA_FEEDS,
        AFRICA_KEYWORDS,
        AFRICA_LOCATION_MAP,
        AFRICA_LOCATION_PRIORITY,
        "Africa",
    )

    # ── Europe (europe.html) ──
    print("\n=== Europe ===")
    update_region(
        "europe.html",
        EUROPE_FEEDS,
        EUROPE_KEYWORDS,
        EUROPE_LOCATION_MAP,
        EUROPE_LOCATION_PRIORITY,
        "Europe",
    )

    # ── South Asia (south-asia.html) ──
    print("\n=== South Asia ===")
    update_region(
        "south-asia.html",
        SOUTH_ASIA_FEEDS,
        SOUTH_ASIA_KEYWORDS,
        SOUTH_ASIA_LOCATION_MAP,
        SOUTH_ASIA_LOCATION_PRIORITY,
        "South Asia",
    )

    # ── Americas (americas.html) ──
    print("\n=== Americas ===")
    update_region(
        "americas.html",
        AMERICAS_FEEDS,
        AMERICAS_KEYWORDS,
        AMERICAS_LOCATION_MAP,
        AMERICAS_LOCATION_PRIORITY,
        "Americas",
    )

    print("\nDone!")


if __name__ == "__main__":
    main()
