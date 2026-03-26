# CLAUDE.md

This file contains project norms and rules for Claude Code. Update it whenever Claude makes a mistake — add a rule so it doesn't happen again. End any correction with: *"Update CLAUDE.md so you don't make that mistake again."*

---

## Repository: PressRadar.me

Interactive global news map with 7 regional pages. Fetches RSS news, geocodes articles, displays on Leaflet maps with AI-generated briefings.

- **GitHub repo:** `adgibs/pressradar`
- **GitHub username:** `adgibs`
- **Live site:** https://pressradar.me
- **Default branch:** `main`
- **Workflow:** Commit directly to `main` (no PRs — auto-deployed via GitHub Pages)

---

## File Structure

```
pressradar/
├── index.html              # Middle East (main page)
├── ukraine.html            # Ukraine & Eastern Europe
├── east-asia.html          # East Asia & Pacific
├── africa.html             # Africa
├── europe.html             # Europe
├── south-asia.html         # South Asia
├── americas.html           # Americas
├── css/style.css           # Shared CSS (all 7 pages link to this)
├── js/app.js               # Shared JavaScript (all 7 pages load this)
├── fetch_news.py           # News fetcher + AI summary generator
├── middle-east-news-map.html  # Legacy file — DO NOT USE
└── .github/workflows/
    └── update-news.yml     # Hourly GitHub Actions workflow
```

### Key architecture decisions
- All 7 HTML pages share `css/style.css` and `js/app.js` — changes only need to be made once.
- Each page defines a `window.pageConfig` object (region name, map center, zoom) before loading `app.js`.
- Each page has inline `<script>` with: `catColors`, `catLabels`, `const locations = [...]`, and timeline data.
- `fetch_news.py` injects data into HTML via regex — it replaces `const locations = [...]`, `date-badge`, `last-updated`, and `ai-summary-box` content.
- `middle-east-news-map.html` is a legacy file with its own inline CSS/JS — do not modify or reference it.

---

## fetch_news.py

Central script that runs hourly via GitHub Actions:

1. Fetches RSS feeds per region (48-hour lookback)
2. Filters articles by keywords and geocodes to known locations
3. Merges new articles into existing HTML page data (avoids duplicates)
4. Generates AI summaries using **Anthropic Claude API** (claude-haiku-4-5-20251001)
5. Injects everything back into the HTML files via regex

### AI Summaries
- Uses **Anthropic API** (not Gemini — free tier had zero quota in UK)
- API key stored as GitHub secret: `ANTHROPIC_API_KEY`
- Briefing covers all articles from the **last 24 hours** (reads from page data, not just new fetches)
- Prompt asks for 6 ranked bullets with headline indices: `(N) [1,3,5] Sentence`
- Indices map to article titles, embedded as `data-titles` JSON attribute on each bullet div
- Clicking a bullet in the UI filters the sidebar to show only related articles

### Regex injection patterns (must be preserved in HTML)
- `const locations = [...];\n` — article data array
- `<div class="date-badge">...</div>` — date display
- `<span id="last-updated">...</span>` — timestamp
- `<div id="ai-summary-box">...</div>` followed by `<div id="map-style-toggle">` — AI briefing

### Known gotchas
- **Never use `r'\1' + variable + r'\2'` in `re.sub` replacements** — backslashes in the variable (e.g. `\u` in JSON) will cause `re.error: bad escape`. Always use a `lambda` replacement instead.
- **HTML attribute escaping for data-titles:** Use single-quoted HTML attributes (`data-titles='...'`) with `&#39;` for apostrophes. Do NOT use `html.escape()` on the full JSON as it converts `'` to `&#x27;` which causes title mismatches with the JS `locations` array.
- The workflow only `git add`s HTML files — `css/style.css` and `js/app.js` don't change during fetches.

---

## js/app.js

Shared JavaScript for all 7 pages. Key systems:

- **Filters:** `activeCountry`, `activeSource`, `activeBriefingTitles` — all feed into `applyFilters()`
- **Timeline:** Preset buttons (1h/6h/12h/24h/48h/All), range sliders, default is **48h**
- **Filter persistence:** Saved to `sessionStorage` — persists across page navigation within same tab
- **AI briefing:** Collapsible (localStorage), clickable bullets filter sidebar via `data-titles`
- **Map:** Leaflet with CARTO Voyager (street), Esri (satellite), OpenTopoMap (terrain)
- **Dark mode:** Toggle with localStorage persistence
- **Favorites:** localStorage-based article bookmarking

### Page-specific config (set before app.js loads)
```javascript
window.pageConfig = {
  region: "Middle East",
  mapCenter: [29.5, 47],
  mapZoom: 5
};
```

**Do NOT hardcode coordinates or region names in app.js** — always use `window.pageConfig`.

---

## css/style.css

Shared styles for all pages. Key sections:
- Layout: header, region-nav, container (flex), sidebar (420px), map (flex:1)
- AI briefing: `.ai-bullet` with `.ai-bar-wrap`/`.ai-bar` mini bars, click states
- Map controls: `#map-style-toggle` (bottom-right of map)
- Dark mode: `body.dark` selectors throughout
- Responsive: `@media (max-width: 800px)` stacks vertically

---

## GitHub Actions Workflow

`.github/workflows/update-news.yml`:
- Runs hourly (`0 * * * *`) and on manual trigger
- Installs `feedparser`, runs `fetch_news.py`
- Passes `ANTHROPIC_API_KEY` from secrets
- Commits and pushes only if HTML files changed
- Only stages HTML files (not CSS/JS)

---

## General Behaviour

- **Ask before making large structural changes.** If a change touches more than one file or could break existing functionality, confirm the approach first.
- **Prefer simple solutions.** Don't over-engineer.
- **Don't refactor unless asked.** Flag unrelated issues — don't silently fix them.
- **Never silently delete or overwrite files.** Always confirm before destructive operations.
- **At the start of each session**, confirm: current directory (`pwd`), current branch (`git branch`), and remote (`git remote -v`).
- **User pushes from Mac.** The Cowork VM cannot push to GitHub — always tell the user to push.

---

## Code Style

### Python (fetch_news.py)
- Use `pathlib` over `os.path`.
- Use f-strings, not `.format()`.
- `pip install --break-system-packages` on this machine.
- Only dependency: `feedparser` (installed in workflow).
- Uses `urllib.request` for API calls (no `requests` library).

### JavaScript (app.js)
- Vanilla JS only — no frameworks.
- `const`/`let`, never `var`.
- `localStorage` for UI preferences (dark mode, favorites, briefing collapsed state).
- `sessionStorage` for filter persistence across page navigation.

---

## Things Claude Has Got Wrong Before

*(Append a new line here after each correction — this is the most important section)*

- Do not assume local file paths — always `ls` or `pwd` to verify first.
- Always run `git remote -v` at the start of a session — do not assume remote URL or branch tracking.
- Do not assume which branch is currently checked out — always check with `git branch`.
- Do NOT use string concatenation in `re.sub` replacement when the string may contain backslashes — use a `lambda` instead. (Caused `re.error: bad escape \u` from JSON in data-titles.)
- Do NOT use `html.escape()` on JSON data that will be compared to JS string values — it converts `'` to `&#x27;` causing mismatches. Use targeted escaping instead.
- Do NOT hardcode map coordinates in `app.js` — use `window.pageConfig`. (Caused all pages to zoom to Middle East.)
- When extracting shared code from multiple HTML files, always verify that `fetch_news.py` regex injection patterns still match the refactored HTML structure.
- Gemini free tier has zero quota in UK region — do not attempt to use it. Use Anthropic API instead.
- The Cowork VM cannot `git push` — always instruct the user to push from their Mac.
- After committing in the VM, remind user to push. Unpushed commits are invisible to GitHub Actions.
