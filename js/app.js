// Auto-detect active region tab
(function() {
  const page = window.location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.region-tab').forEach(btn => {
    const href = btn.getAttribute('onclick')?.match(/'([^']+)'/)?.[1];
    if (href === page) btn.classList.add('active');
  });
});

// ===== FAVORITES (early declarations) =====
let showFavoritesOnly = false;
function getFavorites() {
  try { return JSON.parse(localStorage.getItem('pressradar_favorites') || '[]'); } catch(e) { return []; }
}

// ===== PAYWALL SOURCES =====
const PAYWALL_SOURCES = new Set([
  "New York Times", "Washington Post", "The Times", "The Telegraph",
  "Financial Times", "Wall Street Journal", "The Economist",
  "Haaretz", "The Athletic", "Barron's", "Bloomberg"
]);
function isPaywall(source) { return PAYWALL_SOURCES.has(source); }

// ===== HELPER: Format ISO time to readable string =====
function formatTime(isoString) {
  const d = new Date(isoString);
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const month = months[d.getUTCMonth()];
  const date = d.getUTCDate();
  const hours = String(d.getUTCHours()).padStart(2, '0');
  const mins = String(d.getUTCMinutes()).padStart(2, '0');
  return `${month} ${date}, ${hours}:${mins}`;
}


function relativeTime(isoString) {
  const now = Date.now();
  const t = new Date(isoString).getTime();
  const diff = now - t;
  const mins = Math.floor(diff / 60000);
  const hrs = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);
  if (mins < 1) return 'just now';
  if (mins < 60) return mins + 'm ago';
  if (hrs < 24) return hrs + 'h ago';
  if (days === 1) return 'yesterday';
  return days + 'd ago';
}
// ===== DATA — every location has a country =====

// ===== DERIVE COUNTRIES (ordered by article count) =====
function getCountries(timeFilter) {
  const countryMap = {};
  locations.forEach(loc => {
    const filtered = timeFilter ? loc.articles.filter(a => {
      const t = new Date(a.time).getTime();
      return t >= timelineMin && t <= timelineMax;
    }) : loc.articles;
    if (filtered.length > 0) {
      if (!countryMap[loc.country]) countryMap[loc.country] = 0;
      countryMap[loc.country] += filtered.length;
    }
  });
  return Object.entries(countryMap)
    .sort((a, b) => b[1] - a[1])
    .map(([name, count]) => ({ name, count }));
}

let activeCountry = null; // null = show all
let activeSource = null;  // null = show all

// ===== MAP INIT =====
const map = L.map('map', {
  center: window.pageConfig.mapCenter,
  zoom: window.pageConfig.mapZoom,
  zoomControl: true,
  attributionControl: true
});

L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
  subdomains: 'abcd',
  maxZoom: 19
}).addTo(map);

// ===== MARKERS =====
const markerLayer = L.layerGroup().addTo(map);
const labelLayer = L.layerGroup().addTo(map);
let heatLayer = null;
let currentView = 'pins';

// ===== SENTIMENT ANALYSIS =====
function getSentiment(title) {
  const t = title.toLowerCase();
  const escalation = ['strike', 'attack', 'bomb', 'kill', 'dead', 'death', 'missile', 'war', 'destroy', 'assault', 'offensive', 'blast', 'explod', 'casualt', 'wound', 'military', 'combat', 'drone', 'troops', 'invasion', 'retaliat', 'threat', 'launch', 'target', 'fire'];
  const diplomacy = ['ceasefire', 'peace', 'negotiat', 'talks', 'diplomat', 'UN', 'urge', 'restrain', 'de-escalat', 'agreement', 'summit', 'condemn', 'call for', 'resolution'];
  const humanitarian = ['humanitarian', 'aid', 'refugee', 'civilian', 'evacuat', 'flee', 'shelter', 'food', 'hospital', 'school', 'children', 'crisis', 'stranded', 'rescue'];
  const economic = ['oil', 'price', 'energy', 'gas', 'trade', 'market', 'economy', 'shipping', 'tanker', 'LNG', 'supply', 'recession', 'surge', 'export', 'import', 'insurance'];

  let scores = {escalation: 0, diplomacy: 0, humanitarian: 0, economic: 0};
  escalation.forEach(w => { if (t.includes(w)) scores.escalation++; });
  diplomacy.forEach(w => { if (t.includes(w)) scores.diplomacy++; });
  humanitarian.forEach(w => { if (t.includes(w)) scores.humanitarian++; });
  economic.forEach(w => { if (t.includes(w)) scores.economic++; });

  const max = Math.max(scores.escalation, scores.diplomacy, scores.humanitarian, scores.economic);
  if (max === 0) return {type: 'escalation', label: ''};
  if (scores.escalation === max) return {type: 'escalation', label: 'Conflict'};
  if (scores.diplomacy === max) return {type: 'diplomacy', label: 'Diplomacy'};
  if (scores.humanitarian === max) return {type: 'humanitarian', label: 'Humanitarian'};
  return {type: 'economic', label: 'Economic'};
}

// ===== VIEW MODE TOGGLE =====
function renderMarkers() {
  if (heatLayer) { map.removeLayer(heatLayer); heatLayer = null; }
  markerLayer.clearLayers();
  labelLayer.clearLayers();

  // Get search text for filtering
  const searchText = (document.getElementById('search-box')?.value || '').toLowerCase();

  locations.forEach(loc => {
    if (activeCountry && loc.country !== activeCountry) return;

    // Filter articles by time, source, search text, and paywall
    const hidePaywall = document.getElementById('hide-paywall')?.checked;
    const visibleArticles = loc.articles.filter(a => {
      const t = new Date(a.time).getTime();
      if (t < timelineMin || t > timelineMax) return false;
      if (activeSource && a.source !== activeSource) return false;
      if (searchText && !a.title.toLowerCase().includes(searchText)) return false;
      if (hidePaywall && isPaywall(a.source)) return false;
      if (showFavoritesOnly && !getFavorites().includes(a.url)) return false;
      return true;
    });
    if (visibleArticles.length === 0) return;

    const count = visibleArticles.length;
    const r = count <= 1 ? 6 : count <= 2 ? 8 : count <= 4 ? 11 : 15;
    const col = catColors[loc.category] || "#c0392b";

    const marker = L.circleMarker([loc.lat, loc.lng], {
      radius: r,
      fillColor: col,
      color: "#fff",
      weight: 2,
      opacity: 1,
      fillOpacity: 0.85
    }).addTo(markerLayer);

    // Count label inside circle
    if (count >= 3) {
      L.marker([loc.lat, loc.lng], {
        icon: L.divIcon({
          className: 'circle-count',
          html: count,
          iconSize: [r * 2, r * 2],
          iconAnchor: [r, r]
        }),
        interactive: false
      }).addTo(labelLayer);
    }

    // City name label next to circle
    if (count >= 2) {
      L.marker([loc.lat, loc.lng], {
        icon: L.divIcon({
          className: 'city-label',
          html: '<span style="font-size:11px;font-weight:700;color:#1a1a1a;text-shadow:1px 1px 2px #fff,-1px -1px 2px #fff,1px -1px 2px #fff,-1px 1px 2px #fff,0 0 6px #fff;white-space:nowrap;pointer-events:none;">' + loc.name + '</span>',
          iconSize: [0, 0],
          iconAnchor: [-r - 4, 5]
        }),
        interactive: false
      }).addTo(labelLayer);
    }

    marker.bindPopup(
      '<div class="popup-title">' + loc.name + '</div>' +
      '<div class="popup-country">' + loc.country + '</div>' +
      '<div class="popup-count">' + count + ' article' + (count > 1 ? 's' : '') + ' — ' + catLabels[loc.category] + '</div>' +
      '<div class="popup-link" onclick="scrollToLocation(\'' + loc.name + '\')">View articles →</div>'
    );

    marker.on('click', () => scrollToLocation(loc.name));
  });

  // Heatmap rendering
  if (currentView === 'heat') {
    markerLayer.clearLayers();
    labelLayer.clearLayers();
    const heatPoints = [];
    locations.forEach(loc => {
      if (activeCountry && loc.country !== activeCountry) return;
      const searchText = (document.getElementById('search-box')?.value || '').toLowerCase();
      const hidePaywall = document.getElementById('hide-paywall')?.checked;
      const visibleArticles = loc.articles.filter(a => {
        const t = new Date(a.time).getTime();
        if (t < timelineMin || t > timelineMax) return false;
        if (activeSource && a.source !== activeSource) return false;
        if (searchText && !a.title.toLowerCase().includes(searchText)) return false;
        if (hidePaywall && isPaywall(a.source)) return false;
        return true;
      });
      if (visibleArticles.length > 0) {
        heatPoints.push([loc.lat, loc.lng, visibleArticles.length * 0.5]);
      }
    });
    if (heatPoints.length > 0) {
      heatLayer = L.heatLayer(heatPoints, {
        radius: 35,
        blur: 25,
        maxZoom: 10,
        max: 20,
        gradient: {0.2: '#fee', 0.4: '#fc8', 0.6: '#f86', 0.8: '#e44', 1.0: '#a00'}
      }).addTo(map);
    }
  }
}

// ===== DERIVE SOURCES (ordered by article count) =====
function getSources(countryFilter, timeFilter) {
  const sourceMap = {};
  locations.forEach(loc => {
    if (countryFilter && loc.country !== countryFilter) return;
    loc.articles.forEach(a => {
      const t = new Date(a.time).getTime();
      if (timeFilter && (t < timelineMin || t > timelineMax)) return;
      if (!sourceMap[a.source]) sourceMap[a.source] = 0;
      sourceMap[a.source]++;
    });
  });
  return Object.entries(sourceMap)
    .sort((a, b) => b[1] - a[1])
    .map(([name, count]) => ({ name, count }));
}

// ===== FILTER BARS =====
function renderFilterBars() {
  const cSelect = document.getElementById('country-select');
  const sSelect = document.getElementById('source-select');

  const countries = getCountries(true);
  let totalAll = 0;
  locations.forEach(loc => {
    loc.articles.forEach(a => {
      const t = new Date(a.time).getTime();
      if (t >= timelineMin && t <= timelineMax) totalAll++;
    });
  });

  let cHtml = '<option value="">All countries (' + totalAll + ')</option>';
  countries.forEach(c => {
    cHtml += '<option value="' + c.name + '"' + (activeCountry === c.name ? ' selected' : '') + '>' + c.name + ' (' + c.count + ')</option>';
  });
  cSelect.innerHTML = cHtml;

  const sources = getSources(activeCountry, true);
  const sourceTotal = sources.reduce((s, x) => s + x.count, 0);
  let sHtml = '<option value="">All sources (' + sourceTotal + ')</option>';
  sources.forEach(s => {
    sHtml += '<option value="' + s.name + '"' + (activeSource === s.name ? ' selected' : '') + '>' + s.name + ' (' + s.count + ')</option>';
  });
  sSelect.innerHTML = sHtml;
}

// ===== SIDEBAR — grouped by country, filtered by source =====

const SOURCE_FAVICONS = {
  'BBC News': 'https://www.bbc.co.uk/favicon.ico',
  'The Guardian': 'https://www.theguardian.com/favicon.ico',
  'Al Jazeera': 'https://www.aljazeera.com/favicon.ico',
  'Sky News': 'https://news.sky.com/favicon.ico',
  'France 24': 'https://www.france24.com/favicon.ico',
  'New York Times': 'https://www.nytimes.com/favicon.ico',
  'Washington Post': 'https://www.washingtonpost.com/favicon.ico',
  'NPR': 'https://www.npr.org/favicon.ico',
  'NBC News': 'https://www.nbcnews.com/favicon.ico',
  'CBS News': 'https://www.cbsnews.com/favicon.ico',
  'Reuters': 'https://www.reuters.com/favicon.ico',
  'Times of Israel': 'https://www.timesofisrael.com/favicon.ico',
  'Jerusalem Post': 'https://www.jpost.com/favicon.ico',
  'Deutsche Welle': 'https://www.dw.com/favicon.ico',
  'NHK World': 'https://www3.nhk.or.jp/favicon.ico',
};
function srcFavicon(source) {
  const url = SOURCE_FAVICONS[source];
  return url ? '<img class="src-favicon" src="' + url + '" alt="" onerror="this.style.display=\'none\'">' : '';
}
function renderSidebar() {
  const list = document.getElementById('article-list');
  const countEl = document.getElementById('loc-count');

  // Get search text for filtering
  const searchText = (document.getElementById('search-box')?.value || '').toLowerCase();

  // Apply country filter
  let filtered = activeCountry ? locations.filter(l => l.country === activeCountry) : [...locations];

  // Apply time filter
  filtered = filtered.map(loc => {
    const filtered_articles = loc.articles.filter(a => {
      const t = new Date(a.time).getTime();
      return t >= timelineMin && t <= timelineMax;
    });
    if (filtered_articles.length === 0) return null;
    return { ...loc, articles: filtered_articles };
  }).filter(Boolean);

  // Apply source filter: only show articles from that source
  if (activeSource) {
    filtered = filtered.map(loc => {
      const matchingArticles = loc.articles.filter(a => a.source === activeSource);
      if (matchingArticles.length === 0) return null;
      return { ...loc, articles: matchingArticles };
    }).filter(Boolean);
  }

  // Apply search filter: filter articles by title keyword
  if (searchText) {
    filtered = filtered.map(loc => {
      const matchingArticles = loc.articles.filter(a => a.title.toLowerCase().includes(searchText));
      if (matchingArticles.length === 0) return null;
      return { ...loc, articles: matchingArticles };
    }).filter(Boolean);
  }

  // Apply paywall filter
  const hidePaywall = document.getElementById('hide-paywall')?.checked;
  if (hidePaywall) {
    filtered = filtered.map(loc => {
      const matchingArticles = loc.articles.filter(a => !isPaywall(a.source));
      if (matchingArticles.length === 0) return null;
      return { ...loc, articles: matchingArticles };
    }).filter(Boolean);
  }

  // Apply favorites filter
  if (showFavoritesOnly) {
    const favs = getFavorites();
    filtered = filtered.map(loc => {
      const matchingArticles = loc.articles.filter(a => favs.includes(a.url));
      if (matchingArticles.length === 0) return null;
      return { ...loc, articles: matchingArticles };
    }).filter(Boolean);
  }

  const totalArticles = filtered.reduce((s, l) => s + l.articles.length, 0);
  const totalLocs = filtered.length;
  countEl.textContent = totalLocs + ' location' + (totalLocs !== 1 ? 's' : '') + ' · ' + totalArticles + ' article' + (totalArticles !== 1 ? 's' : '');

  if (filtered.length === 0) {
    list.innerHTML = '<div class="no-results">No results match these filters.</div>';
    return;
  }

  // Group by country, sort countries by total articles
  const grouped = {};
  filtered.forEach(loc => {
    if (!grouped[loc.country]) grouped[loc.country] = [];
    grouped[loc.country].push(loc);
  });

  const countryOrder = Object.entries(grouped)
    .map(([country, locs]) => ({
      country,
      locs: locs.sort((a, b) => b.articles.length - a.articles.length),
      total: locs.reduce((s, l) => s + l.articles.length, 0)
    }))
    .sort((a, b) => b.total - a.total);

  let html = '';
  countryOrder.forEach(group => {
    html += '<div class="country-section">';
    html += '<div class="country-heading">' + group.country + ' <span class="country-article-total">' + group.total + ' article' + (group.total !== 1 ? 's' : '') + '</span></div>';

    group.locs.forEach(loc => {
      const col = catColors[loc.category] || "#c0392b";
      html += '<div class="location-group" id="loc-' + loc.name.replace(/[^a-zA-Z0-9]/g, '_') + '">' +
        '<div class="location-group-header" onclick="toggleLocation(this, \'' + loc.name + '\')">' +
          '<span class="pin" style="color:' + col + '">●</span>' +
          '<span class="loc-name">' + loc.name + '</span>' +
          '<span class="article-count" style="background:' + col + '">' + loc.articles.length + '</span>' +
        '</div>' +
        '<div class="location-articles">' +
          loc.articles.map(a => {
            const articleAge = Date.now() - new Date(a.time).getTime();
            const isBreaking = articleAge < 1 * 60 * 60 * 1000;
            const isNew = articleAge < 2 * 60 * 60 * 1000;
            const newBadge = isBreaking ? '<span class="breaking-label">BREAKING</span>' : (isNew ? '<span class="new-badge">NEW</span>' : '');
            const sentiment = getSentiment(a.title);
            const pw = isPaywall(a.source);
            const pwBadge = pw ? '<span class="paywall-badge" title="Paywall">💰</span>' : '';
            return '<div class="article-card' + (isBreaking ? ' breaking-card' : '') + '" style="border-left-color:' + col + '">' +
              '<div class="article-title"><button class="fav-btn' + (isFavorited(a.url) ? ' favorited' : '') + '" onclick="event.stopPropagation();toggleFavorite(\'' + a.url.replace(/'/g, "\\\'") + '\', this)">' + (isFavorited(a.url) ? '\u2605' : '\u2606') + '</button> ' + (isBreaking ? '<span class="breaking-dot"></span>' : '') + '<span class="sentiment-dot sentiment-' + sentiment.type + '" title="' + sentiment.label + '"></span><a href="' + a.url + '" target="_blank" rel="noopener">' + a.title + '</a>' + newBadge + '</div>' +
              '<div class="article-meta">' +
                '<div class="article-source">' + srcFavicon(a.source) + '<span class="src-name" style="color:' + col + '">' + a.source + '</span>' + pwBadge + '</div>' +
                '<div class="article-time">' + relativeTime(a.time) + ' · ' + formatTime(a.time) + '</div>' +
              '</div>' +
            '</div>';
          }).join('') +
        '</div>' +
      '</div>';
    });

    html += '</div>';
  });

  list.innerHTML = html;
}

// ===== TIMELINE FUNCTIONS =====
function updateTimeRange() {
  const minInput = document.getElementById('range-min');
  const maxInput = document.getElementById('range-max');
  let min = parseInt(minInput.value);
  let max = parseInt(maxInput.value);

  if (min > max) {
    [min, max] = [max, min];
    minInput.value = min;
    maxInput.value = max;
  }

  timelineMin = timelineStart + (min / 1000) * timelineRange;
  timelineMax = timelineStart + (max / 1000) * timelineRange;

  updateTimeDisplay();
  applyFilters();
  clearActivePreset();
}

function updateTimeDisplay() {
  const minDate = new Date(timelineMin);
  const maxDate = new Date(timelineMax);
  document.getElementById('timeline-display').textContent = formatTime(minDate.toISOString()) + ' — ' + formatTime(maxDate.toISOString());
  document.getElementById('min-label').textContent = formatTime(minDate.toISOString());
  document.getElementById('max-label').textContent = formatTime(maxDate.toISOString());
}

function setPreset(preset) {
  const now = timelineEnd;
  let start;

  if (preset === 'all') {
    start = timelineStart;
  } else if (preset === '48h') {
    start = now - 48 * 60 * 60 * 1000;
  } else if (preset === '24h') {
    start = now - 24 * 60 * 60 * 1000;
  } else if (preset === '12h') {
    start = now - 12 * 60 * 60 * 1000;
  } else if (preset === '6h') {
    start = now - 6 * 60 * 60 * 1000;
  } else if (preset === '1h') {
    start = now - 1 * 60 * 60 * 1000;
  }

  timelineMin = Math.max(start, timelineStart);
  timelineMax = now;

  const minVal = Math.round(((timelineMin - timelineStart) / timelineRange) * 1000);
  const maxVal = Math.round(((timelineMax - timelineStart) / timelineRange) * 1000);

  document.getElementById('range-min').value = minVal;
  document.getElementById('range-max').value = maxVal;

  updateTimeDisplay();
  applyFilters();
  updatePresetButtons(preset);
}

function updatePresetButtons(active) {
  document.querySelectorAll('.preset-btn').forEach(btn => {
    btn.classList.remove('active');
  });
  document.querySelector('.preset-btn[onclick="setPreset(\'' + active + '\')"]').classList.add('active');
}

function clearActivePreset() {
  document.querySelectorAll('.preset-btn').forEach(btn => {
    btn.classList.remove('active');
  });
}

// ===== TRENDING =====
function renderTrending() {
  const bar = document.getElementById('trending-bar');
  const searchText = (document.getElementById('search-box')?.value || '').toLowerCase();

  // Get visible articles
  let visibleArticles = [];
  locations.forEach(loc => {
    if (activeCountry && loc.country !== activeCountry) return;
    loc.articles.forEach(a => {
      const t = new Date(a.time).getTime();
      if (t < timelineMin || t > timelineMax) return;
      if (activeSource && a.source !== activeSource) return;
      visibleArticles.push(a);
    });
  });

  // Count words
  const stopWords = new Set(['the','a','in','of','to','and','as','for','on','is','it','at','by','from','with','that','has','are','was','its','an','be','or','but','not','this','have','will','can','says','said','after','over','into','us','uk','new','how','why','what','who','where','when','could','would','may','more','than','about','been','day','amid','live','news','updates','update','latest']);
  const wordCount = {};
  visibleArticles.forEach(a => {
    const words = a.title.toLowerCase().replace(/[^a-z\s]/g, '').split(/\s+/);
    const seen = new Set();
    words.forEach(w => {
      if (w.length > 2 && !stopWords.has(w) && !seen.has(w)) {
        wordCount[w] = (wordCount[w] || 0) + 1;
        seen.add(w);
      }
    });
  });

  const top = Object.entries(wordCount)
    .filter(([w, c]) => c >= 2)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8);

  if (top.length === 0) { bar.innerHTML = ''; return; }

  bar.innerHTML = '<div class="trending-label">Trending</div><div class="trending-tags">' +
    top.map(([word, count]) =>
      '<span class="trending-tag" onclick="searchFor(\'' + word + '\')">' + word + ' <small>' + count + '</small></span>'
    ).join('') + '</div>';
}

function searchFor(word) {
  document.getElementById('search-box').value = word;
  applyFilters();
}

// ===== ACTIONS =====
function filterCountry(country) {
  activeCountry = country;
  activeSource = null; // reset source when changing country
  applyFilters();
  autoExpandArticles();

}

function filterSource(source) {
  activeSource = source;
  applyFilters();
  autoExpandArticles();
}

function autoExpandArticles() {
  // Auto-expand all article lists when a filter is active
  if (activeCountry || activeSource) {
    document.querySelectorAll('.location-articles').forEach(el => el.classList.add('open'));
  } else {
    document.querySelectorAll('.location-articles').forEach(el => el.classList.remove('open'));
  }
}

function applyFilters() {
  renderFilterBars();
  renderSidebar();
  renderMarkers();
  renderTrending();
  fitMapToMarkers();
}

function fitMapToMarkers() {
  if (!activeCountry && !activeSource) {
    map.flyTo(window.pageConfig.mapCenter, window.pageConfig.mapZoom, { duration: 0.6 });
    return;
  }
  const layers = [];
  markerLayer.eachLayer(l => layers.push(l));
  if (layers.length === 0) return;
  if (layers.length === 1) {
    map.flyTo(layers[0].getLatLng(), 8, { duration: 0.6 });
  } else {
    const bounds = L.latLngBounds(layers.map(l => l.getLatLng()));
    map.flyToBounds(bounds.pad(0.3), { duration: 0.6 });
  }
}

function toggleLocation(header, locName) {
  const articles = header.nextElementSibling;
  const isOpen = articles.classList.contains('open');
  // Close all
  document.querySelectorAll('.location-articles').forEach(a => a.classList.remove('open'));
  document.querySelectorAll('.location-group-header').forEach(h => h.classList.remove('sticky'));
  if (!isOpen) {
    articles.classList.add('open');
    header.classList.add('sticky');
    header.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

function scrollToLocation(locName) {
  const id = 'loc-' + locName.replace(/[^a-zA-Z0-9]/g, '_');
  const el = document.getElementById(id);
  if (el) {
    const articles = el.querySelector('.location-articles');
    document.querySelectorAll('.location-articles').forEach(a => a.classList.remove('open'));
    articles.classList.add('open');
    el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

// ===== INIT =====
updateTimeDisplay();
setPreset('all');
renderFilterBars();
renderSidebar();
renderMarkers();
renderTrending();

// Set article count
document.getElementById('total-count').textContent = allTimes.length;

// Set last-updated from newest article
if (allTimes.length) {
  const newest = new Date(Math.max(...allTimes));
  document.getElementById('last-updated').textContent = formatTime(newest.toISOString()) + ' UTC';
}

function toggleFilters(el) {
  const body = document.getElementById('filters-body');
  const arrow = el.querySelector('.toggle-arrow');
  body.classList.toggle('open');
  arrow.classList.toggle('open');
}
// Start with filters open
document.addEventListener('DOMContentLoaded', () => {
  const body = document.getElementById('filters-body');
  const arrow = document.querySelector('.filters-toggle .toggle-arrow');
  if (body) body.classList.add('open');
  if (arrow) arrow.classList.add('open');
});

function toggleDarkMode() {
  document.body.classList.toggle('dark');
  const isDark = document.body.classList.contains('dark');
  localStorage.setItem('pressradar-dark', isDark ? '1' : '0');
  document.querySelector('.dark-toggle').textContent = isDark ? '☀️' : '🌙';
  // Update Leaflet tile layer for dark mode
  if (typeof map !== 'undefined' && typeof applyMapTiles === 'function') {
    applyMapTiles();
  }
}
// Restore dark mode preference
(function() {
  if (localStorage.getItem('pressradar-dark') === '1') {
    document.body.classList.add('dark');
    const btn = document.querySelector('.dark-toggle');
    if (btn) btn.textContent = '☀️';
    // Swap tile layer after map loads (handled by applyMapTiles)
    setTimeout(() => {
      if (typeof map !== 'undefined' && typeof applyMapTiles === 'function') {
        applyMapTiles();
      }
    }, 500);
  }
})();

// Count articles and show badge on active tab
(function() {
  let total = 0;
  locations.forEach(loc => { total += loc.articles.length; });
  const activeTab = document.querySelector('.region-tab.active');
  if (activeTab) {
    activeTab.innerHTML += ' <span class="tab-badge">' + total + '</span>';
  }
  // Update subtitle count
  const countEl = document.getElementById('total-count');
  if (countEl) countEl.textContent = total;
})();


// AI Briefing collapse toggle
document.addEventListener('click', function(e) {
  if (e.target && e.target.id === 'ai-summary-title') {
    e.target.parentElement.classList.toggle('collapsed');
    try { localStorage.setItem('pressradar_briefing_collapsed', e.target.parentElement.classList.contains('collapsed')); } catch(ex) {}
  }
});
// Restore collapsed state
try { if (localStorage.getItem('pressradar_briefing_collapsed') === 'true') { document.getElementById('ai-summary-box')?.classList.add('collapsed'); } } catch(ex) {}

// ===== FAVORITES =====

function saveFavorites(favs) {
  localStorage.setItem('pressradar_favorites', JSON.stringify(favs));
}

function toggleFavorite(url, btn) {
  let favs = getFavorites();
  const idx = favs.indexOf(url);
  if (idx > -1) { favs.splice(idx, 1); btn.classList.remove('favorited'); btn.textContent = '☆'; }
  else { favs.push(url); btn.classList.add('favorited'); btn.textContent = '★'; }
  saveFavorites(favs);
  updateFavCount();
  if (showFavoritesOnly) { renderSidebar(); renderMarkers(); }
}

function isFavorited(url) {
  return getFavorites().includes(url);
}

function toggleFavoritesView() {
  showFavoritesOnly = !showFavoritesOnly;
  const btn = document.getElementById('fav-toggle-btn');
  if (btn) btn.classList.toggle('active', showFavoritesOnly);
  renderSidebar();
  renderMarkers();
}

function updateFavCount() {
  const btn = document.getElementById('fav-toggle-btn');
  if (!btn) return;
  const count = getFavorites().length;
  btn.textContent = '★ Favorites' + (count > 0 ? ' (' + count + ')' : '');
}

updateFavCount();

// ===== MAP STYLE SWITCHER =====
let currentMapStyle = localStorage.getItem('pressradar-mapstyle') || 'street';

const MAP_TILES = {
  street: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
  street_dark: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
  satellite: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
  terrain: 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png'
};

const MAP_ATTR = {
  street: '&copy; OpenStreetMap &copy; CARTO',
  satellite: '&copy; Esri &copy; Maxar',
  terrain: '&copy; OpenTopoMap &copy; OpenStreetMap'
};

function setMapStyle(style) {
  currentMapStyle = style;
  localStorage.setItem('pressradar-mapstyle', style);
  applyMapTiles();
  // Update button states
  document.querySelectorAll('.style-btn').forEach(b => {
    b.style.background = 'transparent';
    b.style.color = '#666';
    b.classList.remove('active');
  });
  const btn = document.getElementById('btn-' + style);
  if (btn) { btn.style.background = '#2471a3'; btn.style.color = '#fff'; btn.classList.add('active'); }
}

function applyMapTiles() {
  const isDark = document.body.classList.contains('dark');
  map.eachLayer(l => { if (l._url && (l._url.includes('carto') || l._url.includes('arcgisonline') || l._url.includes('opentopomap'))) map.removeLayer(l); });
  let url;
  if (currentMapStyle === 'street') {
    url = isDark ? MAP_TILES.street_dark : MAP_TILES.street;
  } else {
    url = MAP_TILES[currentMapStyle];
  }
  L.tileLayer(url, { attribution: MAP_ATTR[currentMapStyle] || '', maxZoom: 19, subdomains: currentMapStyle === 'terrain' ? 'abc' : 'abcd' }).addTo(map);
}

// Restore saved map style
(function() {
  if (currentMapStyle !== 'street') {
    setTimeout(function() {
      setMapStyle(currentMapStyle);
    }, 600);
  }
})();
