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
    "mashhad", "tabriz", "bushehr", "natanz", "ahvaz", "kish island",
    "mehrabad", "abadan", "kharg island", "parchin", "fordow",
    "aleppo", "homs", "latakia", "idlib", "deir ez-zor",
    "mosul", "baghdad", "basra", "kirkuk", "tikrit",
    "aden", "hodeidah", "marib",
    "ramallah", "nablus", "jenin", "khan younis", "jabalia",
    "dahiyeh", "sidon", "tripoli",
    "jeddah", "neom", "dammam", "dhahran",
    "al udeid", "camp arifjan", "incirlik",
    "suez canal", "bab el-mandeb", "indian ocean", "mediterranean",
    "pentagon", "hegseth", "rubio", "vance", "congress",
    "turkey", "ankara", "nato",
    "pakistan", "sri lanka",
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
    # Iranian cities
    "mashhad": {"name": "Mashhad", "country": "Iran", "lat": 36.2605, "lng": 59.6168, "category": "strikes"},
    "tabriz": {"name": "Tabriz", "country": "Iran", "lat": 38.0800, "lng": 46.2919, "category": "strikes"},
    "bushehr": {"name": "Bushehr", "country": "Iran", "lat": 28.9234, "lng": 50.8203, "category": "energy"},
    "natanz": {"name": "Natanz", "country": "Iran", "lat": 33.5131, "lng": 51.9164, "category": "strikes"},
    "ahvaz": {"name": "Ahvaz", "country": "Iran", "lat": 31.3183, "lng": 48.6706, "category": "strikes"},
    "kish island": {"name": "Kish Island", "country": "Iran", "lat": 26.5579, "lng": 53.9804, "category": "energy"},
    "mehrabad": {"name": "Tehran", "country": "Iran", "lat": 35.6892, "lng": 51.389, "category": "strikes"},
    "abadan": {"name": "Abadan", "country": "Iran", "lat": 30.3392, "lng": 48.3043, "category": "energy"},
    "kharg island": {"name": "Kharg Island", "country": "Iran", "lat": 29.2333, "lng": 50.3167, "category": "energy"},
    "parchin": {"name": "Tehran", "country": "Iran", "lat": 35.6892, "lng": 51.389, "category": "strikes"},
    "fordow": {"name": "Qom", "country": "Iran", "lat": 34.6401, "lng": 50.8764, "category": "strikes"},
    # Syrian cities
    "aleppo": {"name": "Aleppo", "country": "Syria", "lat": 36.2021, "lng": 37.1343, "category": "strikes"},
    "homs": {"name": "Homs", "country": "Syria", "lat": 34.7324, "lng": 36.7137, "category": "strikes"},
    "latakia": {"name": "Latakia", "country": "Syria", "lat": 35.5317, "lng": 35.7918, "category": "strikes"},
    "idlib": {"name": "Idlib", "country": "Syria", "lat": 35.9306, "lng": 36.6339, "category": "humanitarian"},
    "deir ez-zor": {"name": "Deir ez-Zor", "country": "Syria", "lat": 35.3359, "lng": 40.1408, "category": "strikes"},
    # Iraqi cities
    "baghdad": {"name": "Baghdad", "country": "Iraq", "lat": 33.3152, "lng": 44.3661, "category": "strikes"},
    "mosul": {"name": "Mosul", "country": "Iraq", "lat": 36.3350, "lng": 43.1189, "category": "strikes"},
    "basra": {"name": "Basra", "country": "Iraq", "lat": 30.5085, "lng": 47.7804, "category": "energy"},
    "kirkuk": {"name": "Kirkuk", "country": "Iraq", "lat": 35.4681, "lng": 44.3922, "category": "energy"},
    "tikrit": {"name": "Tikrit", "country": "Iraq", "lat": 34.6137, "lng": 43.6792, "category": "strikes"},
    # Yemeni cities
    "aden": {"name": "Aden", "country": "Yemen", "lat": 12.7855, "lng": 45.0187, "category": "strikes"},
    "hodeidah": {"name": "Hodeidah", "country": "Yemen", "lat": 14.7980, "lng": 42.9536, "category": "humanitarian"},
    "marib": {"name": "Marib", "country": "Yemen", "lat": 15.4542, "lng": 45.3264, "category": "strikes"},
    # Palestinian areas
    "ramallah": {"name": "Ramallah", "country": "Palestine", "lat": 31.9038, "lng": 35.2034, "category": "humanitarian"},
    "nablus": {"name": "Nablus", "country": "Palestine", "lat": 32.2211, "lng": 35.2544, "category": "humanitarian"},
    "jenin": {"name": "Jenin", "country": "Palestine", "lat": 32.4609, "lng": 35.2999, "category": "humanitarian"},
    "khan younis": {"name": "Khan Younis", "country": "Palestine", "lat": 31.3462, "lng": 34.3061, "category": "humanitarian"},
    "jabalia": {"name": "Jabalia", "country": "Palestine", "lat": 31.5281, "lng": 34.4831, "category": "humanitarian"},
    "hamas": {"name": "Gaza City", "country": "Palestine", "lat": 31.5017, "lng": 34.4668, "category": "strikes"},
    # Lebanese cities
    "dahiyeh": {"name": "Beirut (Dahiyeh)", "country": "Lebanon", "lat": 33.8547, "lng": 35.5022, "category": "strikes"},
    "sidon": {"name": "Sidon", "country": "Lebanon", "lat": 33.5633, "lng": 35.3697, "category": "strikes"},
    "tripoli": {"name": "Tripoli", "country": "Lebanon", "lat": 34.4367, "lng": 35.8497, "category": "humanitarian"},
    # Saudi cities
    "jeddah": {"name": "Jeddah", "country": "Saudi Arabia", "lat": 21.5433, "lng": 39.1728, "category": "energy"},
    "neom": {"name": "NEOM", "country": "Saudi Arabia", "lat": 27.9500, "lng": 35.3000, "category": "energy"},
    "dammam": {"name": "Dammam", "country": "Saudi Arabia", "lat": 26.3927, "lng": 49.9777, "category": "energy"},
    "dhahran": {"name": "Dhahran", "country": "Saudi Arabia", "lat": 26.2361, "lng": 50.0393, "category": "energy"},
    # Military bases
    "al udeid": {"name": "Al Udeid Air Base", "country": "Qatar", "lat": 25.1173, "lng": 51.3150, "category": "strikes"},
    "camp arifjan": {"name": "Camp Arifjan", "country": "Kuwait", "lat": 29.1228, "lng": 48.0766, "category": "strikes"},
    "incirlik": {"name": "Incirlik Air Base", "country": "Turkey", "lat": 37.0020, "lng": 35.4259, "category": "strikes"},
    # Geographic features
    "suez canal": {"name": "Suez Canal", "country": "Egypt", "lat": 30.4550, "lng": 32.3500, "category": "energy"},
    "bab el-mandeb": {"name": "Bab el-Mandeb", "country": "Yemen", "lat": 12.5833, "lng": 43.3333, "category": "energy"},
    "indian ocean": {"name": "Indian Ocean", "country": "International", "lat": 0.0, "lng": 65.0, "category": "strikes"},
    "mediterranean": {"name": "Eastern Mediterranean", "country": "International", "lat": 34.0, "lng": 33.0, "category": "strikes"},
    # US/Western political figures → Washington DC
    "pentagon": {"name": "Washington DC", "country": "United States", "lat": 38.8719, "lng": -77.0563, "category": "strikes"},
    "hegseth": {"name": "Washington DC", "country": "United States", "lat": 38.8719, "lng": -77.0563, "category": "strikes"},
    "rubio": {"name": "Washington DC", "country": "United States", "lat": 38.8719, "lng": -77.0563, "category": "strikes"},
    "vance": {"name": "Washington DC", "country": "United States", "lat": 38.8719, "lng": -77.0563, "category": "strikes"},
    "congress": {"name": "Washington DC", "country": "United States", "lat": 38.8719, "lng": -77.0563, "category": "strikes"},
    "trump": {"name": "Washington DC", "country": "United States", "lat": 38.8719, "lng": -77.0563, "category": "strikes"},
    # Other countries mentioned in ME context
    "turkey": {"name": "Ankara", "country": "Turkey", "lat": 39.9334, "lng": 32.8597, "category": "strikes"},
    "ankara": {"name": "Ankara", "country": "Turkey", "lat": 39.9334, "lng": 32.8597, "category": "strikes"},
    "nato": {"name": "Brussels", "country": "Belgium", "lat": 50.8503, "lng": 4.3517, "category": "strikes"},
    "pakistan": {"name": "Islamabad", "country": "Pakistan", "lat": 33.6844, "lng": 73.0479, "category": "evacuation"},
    "sri lanka": {"name": "Colombo", "country": "Sri Lanka", "lat": 6.9271, "lng": 79.8612, "category": "strikes"},
}

# Priority order for location matching (more specific first)
LOCATION_PRIORITY = [
    # Most specific first
    "al udeid", "camp arifjan", "incirlik", "diego garcia",
    "bab el-mandeb", "suez canal", "strait of hormuz", "kharg island", "kish island",
    "dahiyeh", "mehrabad", "parchin", "fordow", "natanz",
    "khan younis", "jabalia", "deir ez-zor",
    "bandar abbas", "beqaa", "tyre", "akrotiri",
    "raf base", "british base",
    "west bank", "red sea", "oil price", "opec", "indian ocean", "mediterranean",
    # Iranian cities
    "mashhad", "tabriz", "bushehr", "ahvaz", "abadan", "isfahan", "shiraz", "qom",
    "tehran", "khamenei", "irgc",
    # Israeli cities
    "tel aviv", "haifa", "jerusalem", "netanyahu", "idf",
    # Lebanese cities
    "sidon", "tripoli", "beirut", "hezbollah",
    # Palestinian areas
    "ramallah", "nablus", "jenin", "gaza", "rafah", "hamas",
    # Syrian cities
    "aleppo", "homs", "latakia", "idlib", "damascus",
    # Iraqi cities
    "baghdad", "mosul", "basra", "kirkuk", "tikrit", "erbil",
    # Saudi cities
    "jeddah", "neom", "dammam", "dhahran", "riyadh",
    # Gulf/other ME
    "dubai", "abu dhabi", "doha",
    "aden", "hodeidah", "marib", "sanaa", "houthi",
    "cairo", "amman",
    # US political
    "pentagon", "hegseth", "rubio", "vance", "congress",
    # Countries
    "iran", "israel", "lebanon", "saudi", "uae", "qatar",
    "bahrain", "kuwait", "iraq", "syria", "yemen",
    "egypt", "jordan", "oman", "turkey", "ankara",
    "pakistan", "sri lanka", "cyprus", "starmer",
    "nato", "trump",
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
    "mykolaiv", "poltava", "vinnytsia", "chernihiv", "zhytomyr", "lviv",
    "rivne", "ternopil", "ivano-frankivsk", "uzhhorod", "lutsk",
    "kramatorsk", "sloviansk", "severodonetsk", "lysychansk", "tokmak",
    "melitopol", "berdyansk", "nova kakhovka", "energodar",
    "sevastopol", "simferopol", "kerch", "azov",
    "belgorod", "bryansk", "rostov", "voronezh", "st petersburg",
    "black sea", "sea of azov", "kerch strait",
    "minsk", "belarus", "lukashenko",
    "shahed", "leopard", "himars", "patriot", "abrams",
    "ramstein", "pentagon",
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
    "luhansk": {"name": "Luhansk", "country": "Ukraine", "lat": 48.5740, "lng": 39.3078, "category": "conflict"},
    "mariupol": {"name": "Mariupol", "country": "Ukraine", "lat": 47.0958, "lng": 37.5494, "category": "humanitarian"},
    "crimea": {"name": "Crimea", "country": "Ukraine", "lat": 44.9521, "lng": 34.1024, "category": "conflict"},
    "dnipro": {"name": "Dnipro", "country": "Ukraine", "lat": 48.4647, "lng": 35.0462, "category": "conflict"},
    "sumy": {"name": "Sumy", "country": "Ukraine", "lat": 50.9077, "lng": 34.7981, "category": "conflict"},
    "kursk": {"name": "Kursk", "country": "Russia", "lat": 51.7304, "lng": 36.1926, "category": "conflict"},
    "moscow": {"name": "Moscow", "country": "Russia", "lat": 55.7558, "lng": 37.6173, "category": "diplomacy"},
    "kremlin": {"name": "Moscow", "country": "Russia", "lat": 55.7558, "lng": 37.6173, "category": "diplomacy"},
    "putin": {"name": "Moscow", "country": "Russia", "lat": 55.7558, "lng": 37.6173, "category": "diplomacy"},
    "bakhmut": {"name": "Bakhmut", "country": "Ukraine", "lat": 48.5953, "lng": 38.0003, "category": "conflict"},
    "avdiivka": {"name": "Avdiivka", "country": "Ukraine", "lat": 48.1397, "lng": 37.7487, "category": "conflict"},
    "zelensky": {"name": "Kyiv", "country": "Ukraine", "lat": 50.4501, "lng": 30.5234, "category": "diplomacy"},
    "ukraine": {"name": "Kyiv", "country": "Ukraine", "lat": 50.4501, "lng": 30.5234, "category": "conflict"},
    "russia": {"name": "Moscow", "country": "Russia", "lat": 55.7558, "lng": 37.6173, "category": "conflict"},
    "russian": {"name": "Moscow", "country": "Russia", "lat": 55.7558, "lng": 37.6173, "category": "conflict"},
    "nato": {"name": "Brussels", "country": "Belgium", "lat": 50.8503, "lng": 4.3517, "category": "nato"},
    "wagner": {"name": "Moscow", "country": "Russia", "lat": 55.7558, "lng": 37.6173, "category": "conflict"},
    # New Ukrainian cities
    "mykolaiv": {"name": "Mykolaiv", "country": "Ukraine", "lat": 46.9750, "lng": 31.9946, "category": "conflict"},
    "poltava": {"name": "Poltava", "country": "Ukraine", "lat": 49.5883, "lng": 34.5514, "category": "conflict"},
    "vinnytsia": {"name": "Vinnytsia", "country": "Ukraine", "lat": 49.2331, "lng": 28.4682, "category": "conflict"},
    "chernihiv": {"name": "Chernihiv", "country": "Ukraine", "lat": 51.4982, "lng": 31.2893, "category": "conflict"},
    "zhytomyr": {"name": "Zhytomyr", "country": "Ukraine", "lat": 50.2547, "lng": 28.6587, "category": "conflict"},
    "lviv": {"name": "Lviv", "country": "Ukraine", "lat": 49.8397, "lng": 24.0297, "category": "humanitarian"},
    "rivne": {"name": "Rivne", "country": "Ukraine", "lat": 50.6199, "lng": 26.2516, "category": "conflict"},
    "ternopil": {"name": "Ternopil", "country": "Ukraine", "lat": 49.5535, "lng": 25.5948, "category": "humanitarian"},
    "ivano-frankivsk": {"name": "Ivano-Frankivsk", "country": "Ukraine", "lat": 48.9226, "lng": 24.7111, "category": "humanitarian"},
    "uzhhorod": {"name": "Uzhhorod", "country": "Ukraine", "lat": 48.6208, "lng": 22.2879, "category": "humanitarian"},
    "lutsk": {"name": "Lutsk", "country": "Ukraine", "lat": 50.7472, "lng": 25.3254, "category": "conflict"},
    # Donbas front-line towns
    "kramatorsk": {"name": "Kramatorsk", "country": "Ukraine", "lat": 48.7364, "lng": 37.5917, "category": "conflict"},
    "sloviansk": {"name": "Sloviansk", "country": "Ukraine", "lat": 48.8510, "lng": 37.6178, "category": "conflict"},
    "severodonetsk": {"name": "Severodonetsk", "country": "Ukraine", "lat": 48.9484, "lng": 38.4937, "category": "conflict"},
    "lysychansk": {"name": "Lysychansk", "country": "Ukraine", "lat": 48.9044, "lng": 38.4281, "category": "conflict"},
    "tokmak": {"name": "Tokmak", "country": "Ukraine", "lat": 47.2517, "lng": 35.7069, "category": "conflict"},
    # Southern occupied areas
    "melitopol": {"name": "Melitopol", "country": "Ukraine", "lat": 46.8427, "lng": 35.3676, "category": "conflict"},
    "berdyansk": {"name": "Berdyansk", "country": "Ukraine", "lat": 46.7583, "lng": 36.7942, "category": "conflict"},
    "nova kakhovka": {"name": "Nova Kakhovka", "country": "Ukraine", "lat": 46.7553, "lng": 33.3731, "category": "humanitarian"},
    "energodar": {"name": "Energodar", "country": "Ukraine", "lat": 47.4989, "lng": 34.6573, "category": "humanitarian"},
    # Crimea cities
    "sevastopol": {"name": "Sevastopol", "country": "Ukraine", "lat": 44.6167, "lng": 33.5254, "category": "conflict"},
    "simferopol": {"name": "Simferopol", "country": "Ukraine", "lat": 44.9521, "lng": 34.1024, "category": "conflict"},
    "kerch": {"name": "Kerch", "country": "Ukraine", "lat": 45.3531, "lng": 36.4681, "category": "conflict"},
    # Russian border/staging areas
    "belgorod": {"name": "Belgorod", "country": "Russia", "lat": 50.5997, "lng": 36.5876, "category": "conflict"},
    "bryansk": {"name": "Bryansk", "country": "Russia", "lat": 53.2521, "lng": 34.3717, "category": "conflict"},
    "rostov": {"name": "Rostov-on-Don", "country": "Russia", "lat": 47.2357, "lng": 39.7015, "category": "conflict"},
    "voronezh": {"name": "Voronezh", "country": "Russia", "lat": 51.6755, "lng": 39.2089, "category": "conflict"},
    "st petersburg": {"name": "St Petersburg", "country": "Russia", "lat": 59.9343, "lng": 30.3351, "category": "diplomacy"},
    # Water bodies
    "black sea": {"name": "Black Sea", "country": "International", "lat": 43.0, "lng": 35.0, "category": "conflict"},
    "sea of azov": {"name": "Sea of Azov", "country": "International", "lat": 46.0, "lng": 36.5, "category": "conflict"},
    "azov": {"name": "Sea of Azov", "country": "International", "lat": 46.0, "lng": 36.5, "category": "conflict"},
    "kerch strait": {"name": "Kerch", "country": "Ukraine", "lat": 45.3531, "lng": 36.4681, "category": "conflict"},
    # Belarus
    "minsk": {"name": "Minsk", "country": "Belarus", "lat": 53.9045, "lng": 27.5615, "category": "diplomacy"},
    "belarus": {"name": "Minsk", "country": "Belarus", "lat": 53.9045, "lng": 27.5615, "category": "diplomacy"},
    "lukashenko": {"name": "Minsk", "country": "Belarus", "lat": 53.9045, "lng": 27.5615, "category": "diplomacy"},
    # Weapons systems (mapped to relevant area)
    "shahed": {"name": "Kyiv", "country": "Ukraine", "lat": 50.4501, "lng": 30.5234, "category": "conflict"},
    "himars": {"name": "Kyiv", "country": "Ukraine", "lat": 50.4501, "lng": 30.5234, "category": "conflict"},
    "patriot": {"name": "Kyiv", "country": "Ukraine", "lat": 50.4501, "lng": 30.5234, "category": "conflict"},
    # Support locations
    "ramstein": {"name": "Ramstein", "country": "Germany", "lat": 49.4369, "lng": 7.6003, "category": "nato"},
    "pentagon": {"name": "Washington DC", "country": "United States", "lat": 38.8719, "lng": -77.0563, "category": "diplomacy"},
}

UKRAINE_LOCATION_PRIORITY = [
    # Most specific first
    "nova kakhovka", "energodar", "kerch strait",
    "bakhmut", "avdiivka", "kramatorsk", "sloviansk", "severodonetsk", "lysychansk",
    "tokmak", "melitopol", "berdyansk",
    "sevastopol", "simferopol", "kerch",
    "kharkiv", "zaporizhzhia", "odesa", "odessa", "mykolaiv",
    "kherson", "donetsk", "donbas", "luhansk", "mariupol",
    "poltava", "vinnytsia", "chernihiv", "zhytomyr", "lviv",
    "rivne", "ternopil", "ivano-frankivsk", "uzhhorod", "lutsk",
    "dnipro", "sumy", "crimea",
    "belgorod", "bryansk", "rostov", "voronezh", "st petersburg",
    "kursk", "kyiv", "kiev",
    "minsk", "lukashenko", "belarus",
    "kremlin", "moscow", "putin",
    "ramstein", "pentagon",
    "zelensky", "nato", "wagner",
    "shahed", "himars", "patriot",
    "black sea", "sea of azov", "azov",
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
    # Expanded cities & regions
    "shenzhen", "guangzhou", "chengdu", "wuhan", "nanjing", "tianjin",
    "chongqing", "xiamen", "kunming", "hangzhou", "xian", "lhasa", "tibet",
    "xinjiang", "uyghur", "inner mongolia", "hainan", "guangdong",
    "osaka", "yokosuka", "nagasaki", "hiroshima", "hokkaido", "fukushima",
    "busan", "incheon", "dmz", "panmunjom", "kaesong",
    "davao", "cebu", "mindanao", "scarborough", "spratly",
    "ho chi minh", "saigon", "da nang", "haiphong",
    "phnom penh", "cambodia", "laos", "vientiane",
    "kuala lumpur", "malaysia", "malaysian",
    "jakarta", "indonesia", "indonesian", "bali", "java",
    "bangkok", "thailand", "thai",
    "mongolia", "ulaanbaatar",
    "brunei", "timor-leste", "east timor",
    "taiwan strait", "east china sea", "yellow sea",
    "asean", "pacific island", "pacific fleet",
    "two sessions", "yao ming",
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
    # Expanded Chinese cities
    "shenzhen": {"name": "Shenzhen", "country": "China", "lat": 22.5431, "lng": 114.0579, "category": "trade"},
    "guangzhou": {"name": "Guangzhou", "country": "China", "lat": 23.1291, "lng": 113.2644, "category": "trade"},
    "guangdong": {"name": "Guangzhou", "country": "China", "lat": 23.1291, "lng": 113.2644, "category": "trade"},
    "chengdu": {"name": "Chengdu", "country": "China", "lat": 30.5728, "lng": 104.0668, "category": "military"},
    "wuhan": {"name": "Wuhan", "country": "China", "lat": 30.5928, "lng": 114.3055, "category": "trade"},
    "nanjing": {"name": "Nanjing", "country": "China", "lat": 32.0603, "lng": 118.7969, "category": "military"},
    "tianjin": {"name": "Tianjin", "country": "China", "lat": 39.3434, "lng": 117.3616, "category": "trade"},
    "chongqing": {"name": "Chongqing", "country": "China", "lat": 29.4316, "lng": 106.9123, "category": "trade"},
    "xiamen": {"name": "Xiamen", "country": "China", "lat": 24.4798, "lng": 118.0894, "category": "territorial"},
    "kunming": {"name": "Kunming", "country": "China", "lat": 25.0389, "lng": 102.7183, "category": "trade"},
    "hangzhou": {"name": "Hangzhou", "country": "China", "lat": 30.2741, "lng": 120.1551, "category": "trade"},
    "xian": {"name": "Xi'an", "country": "China", "lat": 34.3416, "lng": 108.9398, "category": "military"},
    "lhasa": {"name": "Lhasa", "country": "China/Tibet", "lat": 29.6500, "lng": 91.1000, "category": "territorial"},
    "tibet": {"name": "Lhasa", "country": "China/Tibet", "lat": 29.6500, "lng": 91.1000, "category": "territorial"},
    "xinjiang": {"name": "Urumqi", "country": "China", "lat": 43.8256, "lng": 87.6168, "category": "territorial"},
    "uyghur": {"name": "Urumqi", "country": "China", "lat": 43.8256, "lng": 87.6168, "category": "territorial"},
    "inner mongolia": {"name": "Hohhot", "country": "China", "lat": 40.8422, "lng": 111.7500, "category": "territorial"},
    "hainan": {"name": "Haikou", "country": "China", "lat": 20.0174, "lng": 110.3492, "category": "military"},
    "two sessions": {"name": "Beijing", "country": "China", "lat": 39.9042, "lng": 116.4074, "category": "diplomacy"},
    "yao ming": {"name": "Beijing", "country": "China", "lat": 39.9042, "lng": 116.4074, "category": "diplomacy"},
    # Expanded Japanese cities
    "osaka": {"name": "Osaka", "country": "Japan", "lat": 34.6937, "lng": 135.5023, "category": "trade"},
    "yokosuka": {"name": "Yokosuka", "country": "Japan", "lat": 35.2814, "lng": 139.6722, "category": "military"},
    "nagasaki": {"name": "Nagasaki", "country": "Japan", "lat": 32.7503, "lng": 129.8777, "category": "diplomacy"},
    "hiroshima": {"name": "Hiroshima", "country": "Japan", "lat": 34.3853, "lng": 132.4553, "category": "diplomacy"},
    "hokkaido": {"name": "Sapporo", "country": "Japan", "lat": 43.0618, "lng": 141.3545, "category": "territorial"},
    "fukushima": {"name": "Fukushima", "country": "Japan", "lat": 37.7500, "lng": 140.4678, "category": "trade"},
    # Expanded Korean locations
    "busan": {"name": "Busan", "country": "South Korea", "lat": 35.1796, "lng": 129.0756, "category": "trade"},
    "incheon": {"name": "Incheon", "country": "South Korea", "lat": 37.4563, "lng": 126.7052, "category": "trade"},
    "dmz": {"name": "DMZ", "country": "Korea", "lat": 37.9500, "lng": 126.6800, "category": "military"},
    "panmunjom": {"name": "DMZ", "country": "Korea", "lat": 37.9500, "lng": 126.6800, "category": "military"},
    "kaesong": {"name": "Kaesong", "country": "North Korea", "lat": 37.9710, "lng": 126.5630, "category": "military"},
    # Expanded Philippines
    "davao": {"name": "Davao", "country": "Philippines", "lat": 7.1907, "lng": 125.4553, "category": "territorial"},
    "cebu": {"name": "Cebu", "country": "Philippines", "lat": 10.3157, "lng": 123.8854, "category": "trade"},
    "mindanao": {"name": "Davao", "country": "Philippines", "lat": 7.1907, "lng": 125.4553, "category": "territorial"},
    "scarborough": {"name": "Scarborough Shoal", "country": "Disputed", "lat": 15.1500, "lng": 117.7500, "category": "territorial"},
    "spratly": {"name": "Spratly Islands", "country": "Disputed", "lat": 8.6333, "lng": 111.9167, "category": "territorial"},
    # Vietnam expanded
    "ho chi minh": {"name": "Ho Chi Minh City", "country": "Vietnam", "lat": 10.8231, "lng": 106.6297, "category": "trade"},
    "saigon": {"name": "Ho Chi Minh City", "country": "Vietnam", "lat": 10.8231, "lng": 106.6297, "category": "trade"},
    "da nang": {"name": "Da Nang", "country": "Vietnam", "lat": 16.0544, "lng": 108.2022, "category": "military"},
    "haiphong": {"name": "Haiphong", "country": "Vietnam", "lat": 20.8449, "lng": 106.6881, "category": "trade"},
    # Southeast Asia
    "phnom penh": {"name": "Phnom Penh", "country": "Cambodia", "lat": 11.5564, "lng": 104.9282, "category": "diplomacy"},
    "cambodia": {"name": "Phnom Penh", "country": "Cambodia", "lat": 11.5564, "lng": 104.9282, "category": "diplomacy"},
    "laos": {"name": "Vientiane", "country": "Laos", "lat": 17.9757, "lng": 102.6331, "category": "diplomacy"},
    "vientiane": {"name": "Vientiane", "country": "Laos", "lat": 17.9757, "lng": 102.6331, "category": "diplomacy"},
    "kuala lumpur": {"name": "Kuala Lumpur", "country": "Malaysia", "lat": 3.1390, "lng": 101.6869, "category": "trade"},
    "malaysia": {"name": "Kuala Lumpur", "country": "Malaysia", "lat": 3.1390, "lng": 101.6869, "category": "trade"},
    "malaysian": {"name": "Kuala Lumpur", "country": "Malaysia", "lat": 3.1390, "lng": 101.6869, "category": "trade"},
    "jakarta": {"name": "Jakarta", "country": "Indonesia", "lat": -6.2088, "lng": 106.8456, "category": "trade"},
    "indonesia": {"name": "Jakarta", "country": "Indonesia", "lat": -6.2088, "lng": 106.8456, "category": "trade"},
    "indonesian": {"name": "Jakarta", "country": "Indonesia", "lat": -6.2088, "lng": 106.8456, "category": "trade"},
    "bali": {"name": "Bali", "country": "Indonesia", "lat": -8.3405, "lng": 115.0920, "category": "trade"},
    "java": {"name": "Jakarta", "country": "Indonesia", "lat": -6.2088, "lng": 106.8456, "category": "trade"},
    "bangkok": {"name": "Bangkok", "country": "Thailand", "lat": 13.7563, "lng": 100.5018, "category": "trade"},
    "thailand": {"name": "Bangkok", "country": "Thailand", "lat": 13.7563, "lng": 100.5018, "category": "trade"},
    "thai": {"name": "Bangkok", "country": "Thailand", "lat": 13.7563, "lng": 100.5018, "category": "trade"},
    "brunei": {"name": "Bandar Seri Begawan", "country": "Brunei", "lat": 4.9031, "lng": 114.9398, "category": "trade"},
    "timor-leste": {"name": "Dili", "country": "Timor-Leste", "lat": -8.5569, "lng": 125.5603, "category": "diplomacy"},
    "east timor": {"name": "Dili", "country": "Timor-Leste", "lat": -8.5569, "lng": 125.5603, "category": "diplomacy"},
    # Mongolia
    "mongolia": {"name": "Ulaanbaatar", "country": "Mongolia", "lat": 47.8864, "lng": 106.9057, "category": "diplomacy"},
    "ulaanbaatar": {"name": "Ulaanbaatar", "country": "Mongolia", "lat": 47.8864, "lng": 106.9057, "category": "diplomacy"},
    # Maritime
    "taiwan strait": {"name": "Taiwan Strait", "country": "International", "lat": 24.0, "lng": 119.0, "category": "territorial"},
    "east china sea": {"name": "East China Sea", "country": "International", "lat": 30.0, "lng": 125.0, "category": "territorial"},
    "yellow sea": {"name": "Yellow Sea", "country": "International", "lat": 35.0, "lng": 123.0, "category": "military"},
    "asean": {"name": "Jakarta", "country": "Indonesia", "lat": -6.2088, "lng": 106.8456, "category": "diplomacy"},
    "pacific island": {"name": "South China Sea", "country": "International", "lat": 15.0, "lng": 115.0, "category": "territorial"},
    "pacific fleet": {"name": "Yokosuka", "country": "Japan", "lat": 35.2814, "lng": 139.6722, "category": "military"},
}

EAST_ASIA_LOCATION_PRIORITY = [
    # Specific cities/features first
    "taipei", "taiwan strait", "south china sea", "east china sea", "yellow sea",
    "scarborough", "spratly",
    "hong kong", "okinawa", "shanghai", "shenzhen", "guangzhou", "guangdong",
    "chengdu", "wuhan", "nanjing", "tianjin", "chongqing", "xiamen", "kunming",
    "hangzhou", "xian", "lhasa", "hainan",
    "pyongyang", "north korea", "kim jong", "dmz", "panmunjom", "kaesong",
    "two sessions", "yao ming", "xi jinping", "beijing",
    "osaka", "yokosuka", "nagasaki", "hiroshima", "hokkaido", "fukushima",
    "manila", "davao", "cebu", "mindanao",
    "seoul", "south korea", "busan", "incheon",
    "ho chi minh", "saigon", "da nang", "haiphong", "hanoi",
    "phnom penh", "vientiane", "kuala lumpur", "jakarta", "bali",
    "bangkok", "singapore", "ulaanbaatar",
    # Countries & broad terms
    "taiwan", "tibet", "xinjiang", "uyghur", "inner mongolia",
    "philippines", "japan", "vietnam", "cambodia", "laos",
    "malaysia", "malaysian", "indonesia", "indonesian", "thailand", "thai",
    "mongolia", "brunei", "timor-leste", "east timor",
    "indo-pacific", "indopacific", "aukus", "quad", "asean",
    "pacific island", "pacific fleet",
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
    "sudan", "khartoum", "darfur", "nigeria", "lagos", "abuja", "kenya", "nairobi",
    "ethiopia", "addis ababa", "congo", "kinshasa", "goma", "somalia",
    "mogadishu", "south africa", "johannesburg", "cape town", "pretoria", "egypt",
    "cairo", "libya", "tripoli", "benghazi", "haftar", "mali", "bamako", "sahel", "niger",
    "burkina faso", "chad", "cameroon", "ghana", "accra", "senegal", "dakar",
    "mozambique", "maputo", "tanzania", "dar es salaam", "uganda", "kampala",
    "rwanda", "kigali", "african union",
    # Expanded
    "angola", "luanda", "eritrea", "asmara", "eswatini", "swaziland",
    "zimbabwe", "harare", "zambia", "lusaka", "malawi", "lilongwe",
    "botswana", "gaborone", "namibia", "windhoek",
    "tunisia", "tunis", "morocco", "rabat", "casablanca", "algeria", "algiers",
    "ivory coast", "cote d'ivoire", "abidjan",
    "sierra leone", "freetown", "liberia", "monrovia",
    "togo", "benin", "guinea", "conakry",
    "south sudan", "juba", "central african",
    "horn of africa", "east africa", "west africa",
    "al-shabaab", "boko haram", "wagner",
    "adichie", "ramaphosa", "afrikaner",
    "robben island", "sahara",
    "drc", "m23",
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
    # Expanded locations
    "darfur": {"name": "Darfur", "country": "Sudan", "lat": 13.5000, "lng": 25.0000, "category": "conflict"},
    "pretoria": {"name": "Pretoria", "country": "South Africa", "lat": -25.7479, "lng": 28.2293, "category": "political"},
    "ramaphosa": {"name": "Pretoria", "country": "South Africa", "lat": -25.7479, "lng": 28.2293, "category": "political"},
    "afrikaner": {"name": "Pretoria", "country": "South Africa", "lat": -25.7479, "lng": 28.2293, "category": "political"},
    "robben island": {"name": "Cape Town", "country": "South Africa", "lat": -33.9249, "lng": 18.4241, "category": "political"},
    "benghazi": {"name": "Benghazi", "country": "Libya", "lat": 32.1194, "lng": 20.0868, "category": "conflict"},
    "haftar": {"name": "Benghazi", "country": "Libya", "lat": 32.1194, "lng": 20.0868, "category": "conflict"},
    "dakar": {"name": "Dakar", "country": "Senegal", "lat": 14.7167, "lng": -17.4677, "category": "political"},
    "senegal": {"name": "Dakar", "country": "Senegal", "lat": 14.7167, "lng": -17.4677, "category": "political"},
    "maputo": {"name": "Maputo", "country": "Mozambique", "lat": -25.9692, "lng": 32.5732, "category": "conflict"},
    "mozambique": {"name": "Maputo", "country": "Mozambique", "lat": -25.9692, "lng": 32.5732, "category": "conflict"},
    "dar es salaam": {"name": "Dar es Salaam", "country": "Tanzania", "lat": -6.7924, "lng": 39.2083, "category": "economic"},
    "tanzania": {"name": "Dar es Salaam", "country": "Tanzania", "lat": -6.7924, "lng": 39.2083, "category": "economic"},
    "kampala": {"name": "Kampala", "country": "Uganda", "lat": 0.3476, "lng": 32.5825, "category": "political"},
    "uganda": {"name": "Kampala", "country": "Uganda", "lat": 0.3476, "lng": 32.5825, "category": "political"},
    "kigali": {"name": "Kigali", "country": "Rwanda", "lat": -1.9403, "lng": 29.8739, "category": "political"},
    "rwanda": {"name": "Kigali", "country": "Rwanda", "lat": -1.9403, "lng": 29.8739, "category": "political"},
    "luanda": {"name": "Luanda", "country": "Angola", "lat": -8.8390, "lng": 13.2894, "category": "economic"},
    "angola": {"name": "Luanda", "country": "Angola", "lat": -8.8390, "lng": 13.2894, "category": "economic"},
    "asmara": {"name": "Asmara", "country": "Eritrea", "lat": 15.3229, "lng": 38.9251, "category": "conflict"},
    "eritrea": {"name": "Asmara", "country": "Eritrea", "lat": 15.3229, "lng": 38.9251, "category": "conflict"},
    "eswatini": {"name": "Mbabane", "country": "Eswatini", "lat": -26.3054, "lng": 31.1367, "category": "political"},
    "swaziland": {"name": "Mbabane", "country": "Eswatini", "lat": -26.3054, "lng": 31.1367, "category": "political"},
    "harare": {"name": "Harare", "country": "Zimbabwe", "lat": -17.8252, "lng": 31.0335, "category": "political"},
    "zimbabwe": {"name": "Harare", "country": "Zimbabwe", "lat": -17.8252, "lng": 31.0335, "category": "political"},
    "lusaka": {"name": "Lusaka", "country": "Zambia", "lat": -15.3875, "lng": 28.3228, "category": "economic"},
    "zambia": {"name": "Lusaka", "country": "Zambia", "lat": -15.3875, "lng": 28.3228, "category": "economic"},
    "lilongwe": {"name": "Lilongwe", "country": "Malawi", "lat": -13.9626, "lng": 33.7741, "category": "economic"},
    "malawi": {"name": "Lilongwe", "country": "Malawi", "lat": -13.9626, "lng": 33.7741, "category": "economic"},
    "gaborone": {"name": "Gaborone", "country": "Botswana", "lat": -24.6282, "lng": 25.9231, "category": "economic"},
    "botswana": {"name": "Gaborone", "country": "Botswana", "lat": -24.6282, "lng": 25.9231, "category": "economic"},
    "windhoek": {"name": "Windhoek", "country": "Namibia", "lat": -22.5609, "lng": 17.0658, "category": "economic"},
    "namibia": {"name": "Windhoek", "country": "Namibia", "lat": -22.5609, "lng": 17.0658, "category": "economic"},
    "tunis": {"name": "Tunis", "country": "Tunisia", "lat": 36.8065, "lng": 10.1815, "category": "political"},
    "tunisia": {"name": "Tunis", "country": "Tunisia", "lat": 36.8065, "lng": 10.1815, "category": "political"},
    "rabat": {"name": "Rabat", "country": "Morocco", "lat": 34.0209, "lng": -6.8416, "category": "political"},
    "casablanca": {"name": "Casablanca", "country": "Morocco", "lat": 33.5731, "lng": -7.5898, "category": "economic"},
    "morocco": {"name": "Rabat", "country": "Morocco", "lat": 34.0209, "lng": -6.8416, "category": "political"},
    "algiers": {"name": "Algiers", "country": "Algeria", "lat": 36.7538, "lng": 3.0588, "category": "political"},
    "algeria": {"name": "Algiers", "country": "Algeria", "lat": 36.7538, "lng": 3.0588, "category": "political"},
    "abidjan": {"name": "Abidjan", "country": "Ivory Coast", "lat": 5.3600, "lng": -4.0083, "category": "economic"},
    "ivory coast": {"name": "Abidjan", "country": "Ivory Coast", "lat": 5.3600, "lng": -4.0083, "category": "economic"},
    "cote d'ivoire": {"name": "Abidjan", "country": "Ivory Coast", "lat": 5.3600, "lng": -4.0083, "category": "economic"},
    "freetown": {"name": "Freetown", "country": "Sierra Leone", "lat": 8.4657, "lng": -13.2317, "category": "political"},
    "sierra leone": {"name": "Freetown", "country": "Sierra Leone", "lat": 8.4657, "lng": -13.2317, "category": "political"},
    "monrovia": {"name": "Monrovia", "country": "Liberia", "lat": 6.2907, "lng": -10.7605, "category": "political"},
    "liberia": {"name": "Monrovia", "country": "Liberia", "lat": 6.2907, "lng": -10.7605, "category": "political"},
    "conakry": {"name": "Conakry", "country": "Guinea", "lat": 9.6412, "lng": -13.5784, "category": "political"},
    "guinea": {"name": "Conakry", "country": "Guinea", "lat": 9.6412, "lng": -13.5784, "category": "political"},
    "cameroon": {"name": "Yaounde", "country": "Cameroon", "lat": 3.8480, "lng": 11.5021, "category": "political"},
    "juba": {"name": "Juba", "country": "South Sudan", "lat": 4.8594, "lng": 31.5713, "category": "conflict"},
    "south sudan": {"name": "Juba", "country": "South Sudan", "lat": 4.8594, "lng": 31.5713, "category": "conflict"},
    "central african": {"name": "Bangui", "country": "Central African Republic", "lat": 4.3947, "lng": 18.5582, "category": "conflict"},
    "horn of africa": {"name": "Mogadishu", "country": "Somalia", "lat": 2.0469, "lng": 45.3182, "category": "conflict"},
    "east africa": {"name": "Nairobi", "country": "Kenya", "lat": -1.2921, "lng": 36.8219, "category": "political"},
    "west africa": {"name": "Sahel Region", "country": "West Africa", "lat": 15.0, "lng": 0.0, "category": "conflict"},
    "al-shabaab": {"name": "Mogadishu", "country": "Somalia", "lat": 2.0469, "lng": 45.3182, "category": "conflict"},
    "boko haram": {"name": "Abuja", "country": "Nigeria", "lat": 9.0579, "lng": 7.4951, "category": "conflict"},
    "wagner": {"name": "Sahel Region", "country": "West Africa", "lat": 15.0, "lng": 0.0, "category": "conflict"},
    "adichie": {"name": "Lagos", "country": "Nigeria", "lat": 6.5244, "lng": 3.3792, "category": "economic"},
    "drc": {"name": "Kinshasa", "country": "DR Congo", "lat": -4.4419, "lng": 15.2663, "category": "conflict"},
    "m23": {"name": "Goma", "country": "DR Congo", "lat": -1.6585, "lng": 29.2206, "category": "conflict"},
    "sahara": {"name": "Sahel Region", "country": "West Africa", "lat": 15.0, "lng": 0.0, "category": "conflict"},
    "togo": {"name": "Lome", "country": "Togo", "lat": 6.1256, "lng": 1.2254, "category": "political"},
    "benin": {"name": "Porto-Novo", "country": "Benin", "lat": 6.4969, "lng": 2.6289, "category": "political"},
}

AFRICA_LOCATION_PRIORITY = [
    # Specific cities first
    "darfur", "khartoum", "goma", "benghazi", "mogadishu",
    "bamako", "addis ababa", "asmara", "juba",
    "cape town", "pretoria", "johannesburg", "robben island",
    "tripoli", "kinshasa", "luanda", "maputo", "harare",
    "lagos", "abuja", "nairobi", "cairo", "accra", "dakar",
    "dar es salaam", "kampala", "kigali", "lusaka", "lilongwe",
    "gaborone", "windhoek", "tunis", "rabat", "casablanca",
    "algiers", "abidjan", "freetown", "monrovia", "conakry",
    # People & groups
    "haftar", "ramaphosa", "afrikaner", "adichie",
    "al-shabaab", "boko haram", "wagner", "m23",
    # Regions
    "sahel", "horn of africa", "east africa", "west africa",
    "burkina faso", "niger", "chad", "cameroon", "togo", "benin",
    "south sudan", "central african",
    # Countries
    "sudan", "nigeria", "kenya", "ethiopia", "eritrea", "congo", "drc",
    "somalia", "south africa", "egypt", "libya", "mali", "ghana",
    "senegal", "mozambique", "tanzania", "uganda", "rwanda",
    "angola", "eswatini", "swaziland", "zimbabwe", "zambia", "malawi",
    "botswana", "namibia", "tunisia", "morocco", "algeria",
    "ivory coast", "cote d'ivoire", "sierra leone", "liberia", "guinea",
    "sahara", "african union",
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
    "rome", "italy", "italian", "meloni", "milan",
    "madrid", "spain", "spanish", "sanchez", "sánchez", "pedro sanchez",
    "warsaw", "poland", "polish",
    "ankara", "turkey", "turkish", "erdogan", "istanbul",
    "athens", "greece", "greek",
    "stockholm", "sweden", "swedish", "nato",
    "bucharest", "romania", "romanian",
    "geneva", "switzerland",
    "the hague", "netherlands", "dutch",
    "dublin", "ireland", "irish",
    # Expanded
    "cyprus", "nicosia", "raf akrotiri", "akrotiri",
    "iceland", "reykjavik",
    "oslo", "norway", "norwegian",
    "helsinki", "finland", "finnish",
    "copenhagen", "denmark", "danish",
    "lisbon", "portugal", "portuguese",
    "vienna", "austria", "austrian",
    "prague", "czech", "czechia",
    "budapest", "hungary", "hungarian", "orban",
    "bratislava", "slovakia", "slovak",
    "zagreb", "croatia", "croatian",
    "belgrade", "serbia", "serbian",
    "sofia", "bulgaria", "bulgarian",
    "tallinn", "estonia", "riga", "latvia", "vilnius", "lithuania", "baltic",
    "kyiv", "moldova", "chisinau",
    "maastricht", "tefaf",
    "gibraltar", "malta",
    "golden dawn", "frontex",
    "hms dragon", "royal navy",
    "european parliament", "von der leyen",
    "scotland", "edinburgh", "wales",
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
    # Expanded locations
    "milan": {"name": "Milan", "country": "Italy", "lat": 45.4642, "lng": 9.1900, "category": "economic"},
    "sánchez": {"name": "Madrid", "country": "Spain", "lat": 40.4168, "lng": -3.7038, "category": "political"},
    "pedro sanchez": {"name": "Madrid", "country": "Spain", "lat": 40.4168, "lng": -3.7038, "category": "political"},
    "nicosia": {"name": "Nicosia", "country": "Cyprus", "lat": 35.1856, "lng": 33.3823, "category": "security"},
    "cyprus": {"name": "Nicosia", "country": "Cyprus", "lat": 35.1856, "lng": 33.3823, "category": "security"},
    "raf akrotiri": {"name": "RAF Akrotiri", "country": "Cyprus/UK", "lat": 34.5884, "lng": 32.9879, "category": "military"},
    "akrotiri": {"name": "RAF Akrotiri", "country": "Cyprus/UK", "lat": 34.5884, "lng": 32.9879, "category": "military"},
    "reykjavik": {"name": "Reykjavik", "country": "Iceland", "lat": 64.1466, "lng": -21.9426, "category": "political"},
    "iceland": {"name": "Reykjavik", "country": "Iceland", "lat": 64.1466, "lng": -21.9426, "category": "political"},
    "oslo": {"name": "Oslo", "country": "Norway", "lat": 59.9139, "lng": 10.7522, "category": "economic"},
    "norway": {"name": "Oslo", "country": "Norway", "lat": 59.9139, "lng": 10.7522, "category": "economic"},
    "norwegian": {"name": "Oslo", "country": "Norway", "lat": 59.9139, "lng": 10.7522, "category": "economic"},
    "helsinki": {"name": "Helsinki", "country": "Finland", "lat": 60.1699, "lng": 24.9384, "category": "security"},
    "finland": {"name": "Helsinki", "country": "Finland", "lat": 60.1699, "lng": 24.9384, "category": "security"},
    "finnish": {"name": "Helsinki", "country": "Finland", "lat": 60.1699, "lng": 24.9384, "category": "security"},
    "copenhagen": {"name": "Copenhagen", "country": "Denmark", "lat": 55.6761, "lng": 12.5683, "category": "political"},
    "denmark": {"name": "Copenhagen", "country": "Denmark", "lat": 55.6761, "lng": 12.5683, "category": "political"},
    "danish": {"name": "Copenhagen", "country": "Denmark", "lat": 55.6761, "lng": 12.5683, "category": "political"},
    "lisbon": {"name": "Lisbon", "country": "Portugal", "lat": 38.7223, "lng": -9.1393, "category": "economic"},
    "portugal": {"name": "Lisbon", "country": "Portugal", "lat": 38.7223, "lng": -9.1393, "category": "economic"},
    "portuguese": {"name": "Lisbon", "country": "Portugal", "lat": 38.7223, "lng": -9.1393, "category": "economic"},
    "vienna": {"name": "Vienna", "country": "Austria", "lat": 48.2082, "lng": 16.3738, "category": "political"},
    "austria": {"name": "Vienna", "country": "Austria", "lat": 48.2082, "lng": 16.3738, "category": "political"},
    "austrian": {"name": "Vienna", "country": "Austria", "lat": 48.2082, "lng": 16.3738, "category": "political"},
    "prague": {"name": "Prague", "country": "Czech Republic", "lat": 50.0755, "lng": 14.4378, "category": "political"},
    "czech": {"name": "Prague", "country": "Czech Republic", "lat": 50.0755, "lng": 14.4378, "category": "political"},
    "czechia": {"name": "Prague", "country": "Czech Republic", "lat": 50.0755, "lng": 14.4378, "category": "political"},
    "budapest": {"name": "Budapest", "country": "Hungary", "lat": 47.4979, "lng": 19.0402, "category": "political"},
    "hungary": {"name": "Budapest", "country": "Hungary", "lat": 47.4979, "lng": 19.0402, "category": "political"},
    "hungarian": {"name": "Budapest", "country": "Hungary", "lat": 47.4979, "lng": 19.0402, "category": "political"},
    "orban": {"name": "Budapest", "country": "Hungary", "lat": 47.4979, "lng": 19.0402, "category": "political"},
    "bratislava": {"name": "Bratislava", "country": "Slovakia", "lat": 48.1486, "lng": 17.1077, "category": "political"},
    "slovakia": {"name": "Bratislava", "country": "Slovakia", "lat": 48.1486, "lng": 17.1077, "category": "political"},
    "slovak": {"name": "Bratislava", "country": "Slovakia", "lat": 48.1486, "lng": 17.1077, "category": "political"},
    "zagreb": {"name": "Zagreb", "country": "Croatia", "lat": 45.8150, "lng": 15.9819, "category": "political"},
    "croatia": {"name": "Zagreb", "country": "Croatia", "lat": 45.8150, "lng": 15.9819, "category": "political"},
    "croatian": {"name": "Zagreb", "country": "Croatia", "lat": 45.8150, "lng": 15.9819, "category": "political"},
    "belgrade": {"name": "Belgrade", "country": "Serbia", "lat": 44.7866, "lng": 20.4489, "category": "political"},
    "serbia": {"name": "Belgrade", "country": "Serbia", "lat": 44.7866, "lng": 20.4489, "category": "political"},
    "serbian": {"name": "Belgrade", "country": "Serbia", "lat": 44.7866, "lng": 20.4489, "category": "political"},
    "sofia": {"name": "Sofia", "country": "Bulgaria", "lat": 42.6977, "lng": 23.3219, "category": "political"},
    "bulgaria": {"name": "Sofia", "country": "Bulgaria", "lat": 42.6977, "lng": 23.3219, "category": "political"},
    "bulgarian": {"name": "Sofia", "country": "Bulgaria", "lat": 42.6977, "lng": 23.3219, "category": "political"},
    "tallinn": {"name": "Tallinn", "country": "Estonia", "lat": 59.4370, "lng": 24.7536, "category": "security"},
    "estonia": {"name": "Tallinn", "country": "Estonia", "lat": 59.4370, "lng": 24.7536, "category": "security"},
    "riga": {"name": "Riga", "country": "Latvia", "lat": 56.9496, "lng": 24.1052, "category": "security"},
    "latvia": {"name": "Riga", "country": "Latvia", "lat": 56.9496, "lng": 24.1052, "category": "security"},
    "vilnius": {"name": "Vilnius", "country": "Lithuania", "lat": 54.6872, "lng": 25.2797, "category": "security"},
    "lithuania": {"name": "Vilnius", "country": "Lithuania", "lat": 54.6872, "lng": 25.2797, "category": "security"},
    "baltic": {"name": "Tallinn", "country": "Estonia", "lat": 59.4370, "lng": 24.7536, "category": "security"},
    "kyiv": {"name": "Brussels", "country": "Belgium", "lat": 50.8503, "lng": 4.3517, "category": "political"},
    "moldova": {"name": "Chisinau", "country": "Moldova", "lat": 47.0105, "lng": 28.8638, "category": "political"},
    "chisinau": {"name": "Chisinau", "country": "Moldova", "lat": 47.0105, "lng": 28.8638, "category": "political"},
    "maastricht": {"name": "Maastricht", "country": "Netherlands", "lat": 50.8514, "lng": 5.6910, "category": "economic"},
    "tefaf": {"name": "Maastricht", "country": "Netherlands", "lat": 50.8514, "lng": 5.6910, "category": "economic"},
    "gibraltar": {"name": "Gibraltar", "country": "UK/Spain", "lat": 36.1408, "lng": -5.3536, "category": "political"},
    "malta": {"name": "Valletta", "country": "Malta", "lat": 35.8989, "lng": 14.5146, "category": "political"},
    "golden dawn": {"name": "Athens", "country": "Greece", "lat": 37.9838, "lng": 23.7275, "category": "political"},
    "frontex": {"name": "Warsaw", "country": "Poland", "lat": 52.2297, "lng": 21.0122, "category": "security"},
    "hms dragon": {"name": "London", "country": "United Kingdom", "lat": 51.5074, "lng": -0.1278, "category": "military"},
    "royal navy": {"name": "London", "country": "United Kingdom", "lat": 51.5074, "lng": -0.1278, "category": "military"},
    "european parliament": {"name": "Brussels", "country": "Belgium", "lat": 50.8503, "lng": 4.3517, "category": "political"},
    "von der leyen": {"name": "Brussels", "country": "Belgium", "lat": 50.8503, "lng": 4.3517, "category": "political"},
    "scotland": {"name": "Edinburgh", "country": "United Kingdom", "lat": 55.9533, "lng": -3.1883, "category": "political"},
    "edinburgh": {"name": "Edinburgh", "country": "United Kingdom", "lat": 55.9533, "lng": -3.1883, "category": "political"},
    "wales": {"name": "Cardiff", "country": "United Kingdom", "lat": 51.4816, "lng": -3.1791, "category": "political"},
    "nato": {"name": "Brussels", "country": "Belgium", "lat": 50.8503, "lng": 4.3517, "category": "security"},
    "uk ": {"name": "London", "country": "United Kingdom", "lat": 51.5074, "lng": -0.1278, "category": "political"},
    "brexit": {"name": "London", "country": "United Kingdom", "lat": 51.5074, "lng": -0.1278, "category": "political"},
    "eu ": {"name": "Brussels", "country": "Belgium", "lat": 50.8503, "lng": 4.3517, "category": "political"},
    "romanian": {"name": "Bucharest", "country": "Romania", "lat": 44.4268, "lng": 26.1025, "category": "security"},
}

EUROPE_LOCATION_PRIORITY = [
    # Specific cities/bases first
    "raf akrotiri", "akrotiri", "nicosia", "maastricht", "tefaf",
    "european commission", "european parliament", "european union", "von der leyen",
    "the hague", "golden dawn", "hms dragon", "royal navy",
    "istanbul", "ankara", "erdogan",
    "london", "starmer", "edinburgh", "milan",
    "brussels", "paris", "macron",
    "berlin", "merz", "scholz", "rome", "meloni", "madrid", "sanchez", "sánchez", "pedro sanchez",
    "warsaw", "athens", "lisbon", "vienna", "prague", "budapest", "orban",
    "copenhagen", "oslo", "helsinki", "stockholm",
    "bucharest", "geneva", "dublin", "bratislava", "zagreb", "belgrade", "sofia",
    "tallinn", "riga", "vilnius", "chisinau", "reykjavik", "gibraltar",
    "frontex",
    # Countries & demonyms
    "cyprus", "iceland", "scotland", "wales",
    "britain", "british", "france", "french", "germany", "german",
    "italy", "italian", "spain", "spanish", "poland", "polish",
    "turkey", "turkish", "greece", "greek", "sweden", "swedish",
    "norway", "norwegian", "finland", "finnish", "denmark", "danish",
    "portugal", "portuguese", "austria", "austrian",
    "czech", "czechia", "hungary", "hungarian",
    "slovakia", "slovak", "croatia", "croatian", "serbia", "serbian",
    "bulgaria", "bulgarian", "romania", "romanian",
    "estonia", "latvia", "lithuania", "baltic",
    "moldova", "malta", "kyiv",
    "netherlands", "dutch", "ireland", "irish",
    "nato", "uk ", "eu ", "brexit",
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
    # Expanded
    "bangalore", "bengaluru", "hyderabad", "kolkata", "pune", "ahmedabad",
    "jaipur", "lucknow", "kerala", "goa", "rajasthan", "gujarat",
    "lahore", "peshawar", "quetta", "balochistan", "waziristan",
    "khyber", "sindh", "punjab",
    "chittagong", "cox's bazar",
    "kandahar", "helmand", "jalalabad", "herat",
    "naypyidaw", "mandalay", "rakhine",
    "bhutan", "thimphu",
    "indian ocean", "persian gulf", "bay of bengal",
    "himalaya", "himalayan", "hindu kush", "karakoram",
    "gen z", "gen-z",
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
    # Expanded Indian cities
    "bangalore": {"name": "Bangalore", "country": "India", "lat": 12.9716, "lng": 77.5946, "category": "economic"},
    "bengaluru": {"name": "Bangalore", "country": "India", "lat": 12.9716, "lng": 77.5946, "category": "economic"},
    "hyderabad": {"name": "Hyderabad", "country": "India", "lat": 17.3850, "lng": 78.4867, "category": "economic"},
    "kolkata": {"name": "Kolkata", "country": "India", "lat": 22.5726, "lng": 88.3639, "category": "economic"},
    "pune": {"name": "Pune", "country": "India", "lat": 18.5204, "lng": 73.8567, "category": "economic"},
    "ahmedabad": {"name": "Ahmedabad", "country": "India", "lat": 23.0225, "lng": 72.5714, "category": "economic"},
    "jaipur": {"name": "Jaipur", "country": "India", "lat": 26.9124, "lng": 75.7873, "category": "political"},
    "lucknow": {"name": "Lucknow", "country": "India", "lat": 26.8467, "lng": 80.9462, "category": "political"},
    "kerala": {"name": "Kochi", "country": "India", "lat": 9.9312, "lng": 76.2673, "category": "political"},
    "goa": {"name": "Goa", "country": "India", "lat": 15.2993, "lng": 74.1240, "category": "economic"},
    "rajasthan": {"name": "Jaipur", "country": "India", "lat": 26.9124, "lng": 75.7873, "category": "political"},
    "gujarat": {"name": "Ahmedabad", "country": "India", "lat": 23.0225, "lng": 72.5714, "category": "economic"},
    # Expanded Pakistan
    "lahore": {"name": "Lahore", "country": "Pakistan", "lat": 31.5204, "lng": 74.3587, "category": "political"},
    "peshawar": {"name": "Peshawar", "country": "Pakistan", "lat": 34.0151, "lng": 71.5249, "category": "security"},
    "quetta": {"name": "Quetta", "country": "Pakistan", "lat": 30.1798, "lng": 66.9750, "category": "security"},
    "balochistan": {"name": "Quetta", "country": "Pakistan", "lat": 30.1798, "lng": 66.9750, "category": "security"},
    "waziristan": {"name": "Waziristan", "country": "Pakistan", "lat": 32.3000, "lng": 69.8500, "category": "security"},
    "khyber": {"name": "Peshawar", "country": "Pakistan", "lat": 34.0151, "lng": 71.5249, "category": "security"},
    "sindh": {"name": "Karachi", "country": "Pakistan", "lat": 24.8607, "lng": 67.0011, "category": "political"},
    "punjab": {"name": "Lahore", "country": "Pakistan", "lat": 31.5204, "lng": 74.3587, "category": "political"},
    # Expanded Bangladesh
    "chittagong": {"name": "Chittagong", "country": "Bangladesh", "lat": 22.3569, "lng": 91.7832, "category": "economic"},
    "cox's bazar": {"name": "Cox's Bazar", "country": "Bangladesh", "lat": 21.4272, "lng": 92.0058, "category": "humanitarian"},
    # Expanded Afghanistan
    "kandahar": {"name": "Kandahar", "country": "Afghanistan", "lat": 31.6280, "lng": 65.7372, "category": "humanitarian"},
    "helmand": {"name": "Helmand", "country": "Afghanistan", "lat": 31.5000, "lng": 64.0000, "category": "security"},
    "jalalabad": {"name": "Jalalabad", "country": "Afghanistan", "lat": 34.4215, "lng": 70.4536, "category": "security"},
    "herat": {"name": "Herat", "country": "Afghanistan", "lat": 34.3529, "lng": 62.2040, "category": "humanitarian"},
    # Expanded Myanmar
    "naypyidaw": {"name": "Naypyidaw", "country": "Myanmar", "lat": 19.7633, "lng": 96.0785, "category": "humanitarian"},
    "mandalay": {"name": "Mandalay", "country": "Myanmar", "lat": 21.9588, "lng": 96.0891, "category": "humanitarian"},
    "rakhine": {"name": "Rakhine", "country": "Myanmar", "lat": 20.1500, "lng": 92.8833, "category": "humanitarian"},
    # Bhutan
    "bhutan": {"name": "Thimphu", "country": "Bhutan", "lat": 27.4728, "lng": 89.6390, "category": "political"},
    "thimphu": {"name": "Thimphu", "country": "Bhutan", "lat": 27.4728, "lng": 89.6390, "category": "political"},
    # Maritime/Geographic
    "indian ocean": {"name": "Indian Ocean", "country": "International", "lat": 0.0, "lng": 75.0, "category": "security"},
    "persian gulf": {"name": "Persian Gulf", "country": "International", "lat": 26.0, "lng": 52.0, "category": "economic"},
    "bay of bengal": {"name": "Bay of Bengal", "country": "International", "lat": 15.0, "lng": 88.0, "category": "security"},
    "himalaya": {"name": "Kathmandu", "country": "Nepal", "lat": 27.7172, "lng": 85.3240, "category": "political"},
    "himalayan": {"name": "Kathmandu", "country": "Nepal", "lat": 27.7172, "lng": 85.3240, "category": "political"},
    "hindu kush": {"name": "Kabul", "country": "Afghanistan", "lat": 34.5553, "lng": 69.2075, "category": "security"},
    "karakoram": {"name": "Kashmir", "country": "India/Pakistan", "lat": 34.0837, "lng": 74.7973, "category": "security"},
    "gen z": {"name": "Kathmandu", "country": "Nepal", "lat": 27.7172, "lng": 85.3240, "category": "political"},
    "gen-z": {"name": "Kathmandu", "country": "Nepal", "lat": 27.7172, "lng": 85.3240, "category": "political"},
}

SOUTH_ASIA_LOCATION_PRIORITY = [
    # Specific cities first
    "new delhi", "mumbai", "chennai", "bangalore", "bengaluru",
    "hyderabad", "kolkata", "pune", "ahmedabad", "jaipur", "lucknow",
    "kashmir", "karakoram",
    "islamabad", "karachi", "lahore", "peshawar", "quetta", "waziristan",
    "dhaka", "chittagong", "cox's bazar",
    "colombo", "kathmandu",
    "kabul", "kandahar", "helmand", "jalalabad", "herat",
    "yangon", "naypyidaw", "mandalay", "rakhine",
    "thimphu",
    # Maritime/geographic
    "indian ocean", "persian gulf", "bay of bengal",
    "himalaya", "himalayan", "hindu kush",
    # People/groups
    "modi", "taliban", "rohingya", "gen z", "gen-z",
    # Regions
    "kerala", "goa", "rajasthan", "gujarat",
    "balochistan", "khyber", "sindh", "punjab",
    # Countries
    "india", "indian", "pakistan", "pakistani",
    "bangladesh", "sri lanka", "nepal", "afghanistan", "myanmar",
    "maldives", "bhutan",
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
    # Expanded
    "ecuador", "quito", "guayaquil",
    "bolivia", "la paz", "evo morales",
    "uruguay", "montevideo",
    "paraguay", "asuncion",
    "dominican republic", "santo domingo",
    "puerto rico", "san juan",
    "honduras", "tegucigalpa", "el salvador", "bukele",
    "nicaragua", "managua", "ortega",
    "costa rica", "san jose",
    "jamaica", "kingston", "trinidad", "barbados",
    "guyana", "georgetown", "suriname",
    "toronto", "montreal", "vancouver", "alberta",
    "mercosur", "oas",
    "cartels", "cartel", "fentanyl", "narco",
    "hegseth",
    "cuban", "gringo",
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
    # Expanded locations
    "quito": {"name": "Quito", "country": "Ecuador", "lat": -0.1807, "lng": -78.4678, "category": "security"},
    "ecuador": {"name": "Quito", "country": "Ecuador", "lat": -0.1807, "lng": -78.4678, "category": "security"},
    "guayaquil": {"name": "Guayaquil", "country": "Ecuador", "lat": -2.1710, "lng": -79.9223, "category": "security"},
    "la paz": {"name": "La Paz", "country": "Bolivia", "lat": -16.4897, "lng": -68.1193, "category": "political"},
    "bolivia": {"name": "La Paz", "country": "Bolivia", "lat": -16.4897, "lng": -68.1193, "category": "political"},
    "evo morales": {"name": "La Paz", "country": "Bolivia", "lat": -16.4897, "lng": -68.1193, "category": "political"},
    "montevideo": {"name": "Montevideo", "country": "Uruguay", "lat": -34.9011, "lng": -56.1645, "category": "economic"},
    "uruguay": {"name": "Montevideo", "country": "Uruguay", "lat": -34.9011, "lng": -56.1645, "category": "economic"},
    "asuncion": {"name": "Asuncion", "country": "Paraguay", "lat": -25.2637, "lng": -57.5759, "category": "economic"},
    "paraguay": {"name": "Asuncion", "country": "Paraguay", "lat": -25.2637, "lng": -57.5759, "category": "economic"},
    "santo domingo": {"name": "Santo Domingo", "country": "Dominican Republic", "lat": 18.4861, "lng": -69.9312, "category": "political"},
    "dominican republic": {"name": "Santo Domingo", "country": "Dominican Republic", "lat": 18.4861, "lng": -69.9312, "category": "political"},
    "san juan": {"name": "San Juan", "country": "Puerto Rico", "lat": 18.4655, "lng": -66.1057, "category": "political"},
    "puerto rico": {"name": "San Juan", "country": "Puerto Rico", "lat": 18.4655, "lng": -66.1057, "category": "political"},
    "tegucigalpa": {"name": "Tegucigalpa", "country": "Honduras", "lat": 14.0723, "lng": -87.1921, "category": "migration"},
    "honduras": {"name": "Tegucigalpa", "country": "Honduras", "lat": 14.0723, "lng": -87.1921, "category": "migration"},
    "el salvador": {"name": "San Salvador", "country": "El Salvador", "lat": 13.6929, "lng": -89.2182, "category": "security"},
    "bukele": {"name": "San Salvador", "country": "El Salvador", "lat": 13.6929, "lng": -89.2182, "category": "security"},
    "managua": {"name": "Managua", "country": "Nicaragua", "lat": 12.1150, "lng": -86.2362, "category": "political"},
    "nicaragua": {"name": "Managua", "country": "Nicaragua", "lat": 12.1150, "lng": -86.2362, "category": "political"},
    "ortega": {"name": "Managua", "country": "Nicaragua", "lat": 12.1150, "lng": -86.2362, "category": "political"},
    "costa rica": {"name": "San Jose", "country": "Costa Rica", "lat": 9.9281, "lng": -84.0907, "category": "economic"},
    "san jose": {"name": "San Jose", "country": "Costa Rica", "lat": 9.9281, "lng": -84.0907, "category": "economic"},
    "kingston": {"name": "Kingston", "country": "Jamaica", "lat": 18.0179, "lng": -76.8099, "category": "political"},
    "jamaica": {"name": "Kingston", "country": "Jamaica", "lat": 18.0179, "lng": -76.8099, "category": "political"},
    "trinidad": {"name": "Port of Spain", "country": "Trinidad & Tobago", "lat": 10.6918, "lng": -61.2225, "category": "economic"},
    "barbados": {"name": "Bridgetown", "country": "Barbados", "lat": 13.1132, "lng": -59.5988, "category": "economic"},
    "georgetown": {"name": "Georgetown", "country": "Guyana", "lat": 6.8013, "lng": -58.1551, "category": "economic"},
    "guyana": {"name": "Georgetown", "country": "Guyana", "lat": 6.8013, "lng": -58.1551, "category": "economic"},
    "suriname": {"name": "Paramaribo", "country": "Suriname", "lat": 5.8520, "lng": -55.2038, "category": "economic"},
    "toronto": {"name": "Toronto", "country": "Canada", "lat": 43.6532, "lng": -79.3832, "category": "economic"},
    "montreal": {"name": "Montreal", "country": "Canada", "lat": 45.5017, "lng": -73.5673, "category": "economic"},
    "vancouver": {"name": "Vancouver", "country": "Canada", "lat": 49.2827, "lng": -123.1207, "category": "economic"},
    "alberta": {"name": "Calgary", "country": "Canada", "lat": 51.0447, "lng": -114.0719, "category": "economic"},
    "mercosur": {"name": "Brasilia", "country": "Brazil", "lat": -15.7975, "lng": -47.8919, "category": "political"},
    "oas": {"name": "Washington DC", "country": "USA", "lat": 38.9072, "lng": -77.0369, "category": "political"},
    "cartels": {"name": "Mexico City", "country": "Mexico", "lat": 19.4326, "lng": -99.1332, "category": "security"},
    "cartel": {"name": "Mexico City", "country": "Mexico", "lat": 19.4326, "lng": -99.1332, "category": "security"},
    "fentanyl": {"name": "Mexico City", "country": "Mexico", "lat": 19.4326, "lng": -99.1332, "category": "security"},
    "narco": {"name": "Mexico City", "country": "Mexico", "lat": 19.4326, "lng": -99.1332, "category": "security"},
    "hegseth": {"name": "Washington DC", "country": "USA", "lat": 38.9072, "lng": -77.0369, "category": "political"},
    "cuban": {"name": "Havana", "country": "Cuba", "lat": 23.1136, "lng": -82.3666, "category": "political"},
    "gringo": {"name": "Mexico City", "country": "Mexico", "lat": 19.4326, "lng": -99.1332, "category": "political"},
}

AMERICAS_LOCATION_PRIORITY = [
    # Specific cities first
    "mexico city", "buenos aires", "sao paulo", "port-au-prince",
    "bogota", "caracas", "brasilia", "guayaquil", "quito",
    "havana", "lima", "santiago", "la paz", "montevideo", "asuncion",
    "santo domingo", "san juan", "tegucigalpa", "managua", "san jose",
    "kingston", "georgetown",
    "ottawa", "toronto", "montreal", "vancouver",
    # People
    "maduro", "lula", "milei", "trudeau", "carney",
    "bukele", "ortega", "evo morales", "hegseth",
    # Specific terms
    "cartels", "cartel", "fentanyl", "narco", "gringo", "cuban",
    "mercosur", "oas",
    "guatemala", "panama",
    # Countries
    "mexico", "colombia", "venezuela", "argentina", "brazil",
    "ecuador", "bolivia", "uruguay", "paraguay",
    "cuba", "peru", "chile", "haiti", "canada",
    "dominican republic", "puerto rico", "honduras", "el salvador",
    "nicaragua", "costa rica", "jamaica", "trinidad", "barbados",
    "guyana", "suriname", "alberta",
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
