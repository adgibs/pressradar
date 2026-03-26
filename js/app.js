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
let activeBriefingTitles = null; // null = show all, Set = filter to these titles

// Radius filter (Global page only)
let radiusCenter = null;   // {lat, lng} or null
let radiusKm = 500;        // current radius in km
let radiusCircle = null;   // Leaflet circle layer
let radiusMarker = null;   // Leaflet marker for center point

// Globe view (Global page only) — use var to avoid TDZ issues since
// renderGlobe() can be called from applyFilters() before globe code section runs
var globe = null;
var globeView = false;     // true = globe visible, false = flat map visible

function haversineDistance(lat1, lng1, lat2, lng2) {
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLng = (lng2 - lng1) * Math.PI / 180;
  const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
            Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
            Math.sin(dLng/2) * Math.sin(dLng/2);
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
}

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

// ===== RADIUS CLICK (Global page only) =====
if (window.pageConfig.region === 'Global') {
  map.on('click', function(e) {
    radiusCenter = { lat: e.latlng.lat, lng: e.latlng.lng };
    updateRadiusOverlay();
    applyFilters();
    const section = document.getElementById('radius-section');
    if (section) section.style.display = '';
    const presets = document.getElementById('radius-presets');
    if (presets) presets.style.display = '';
    const clearBtn = document.getElementById('clear-radius-btn');
    if (clearBtn) clearBtn.style.display = '';
    const info = document.getElementById('radius-info');
    if (info) info.textContent = 'Showing articles within ' + radiusKm + ' km';
  });
}

function updateRadiusOverlay() {
  // In globe view, the globe handles its own radius visualization via rings
  if (globeView) return;
  if (radiusCircle) map.removeLayer(radiusCircle);
  if (radiusMarker) map.removeLayer(radiusMarker);
  if (!radiusCenter) return;
  radiusCircle = L.circle([radiusCenter.lat, radiusCenter.lng], {
    radius: radiusKm * 1000,
    color: '#e74c3c', weight: 2, opacity: 0.5,
    fillColor: '#e74c3c', fillOpacity: 0.08, dashArray: '6, 4'
  }).addTo(map);
  radiusMarker = L.circleMarker([radiusCenter.lat, radiusCenter.lng], {
    radius: 6, fillColor: '#e74c3c', color: '#fff', weight: 2, fillOpacity: 1
  }).addTo(map);
  map.fitBounds(radiusCircle.getBounds().pad(0.1));
}

function setRadius(km) {
  radiusKm = km;
  updateRadiusOverlay();
  applyFilters();
  document.querySelectorAll('#radius-presets .preset-btn').forEach(b => b.classList.remove('active'));
  const btn = document.querySelector('#radius-presets .preset-btn[onclick="setRadius(' + km + ')"]');
  if (btn) btn.classList.add('active');
  const info = document.getElementById('radius-info');
  if (info && radiusCenter) info.textContent = 'Showing articles within ' + km + ' km';
  saveFiltersToSession();
}

function clearRadius() {
  radiusCenter = null;
  if (radiusCircle) { map.removeLayer(radiusCircle); radiusCircle = null; }
  if (radiusMarker) { map.removeLayer(radiusMarker); radiusMarker = null; }
  const clearBtn = document.getElementById('clear-radius-btn');
  if (clearBtn) clearBtn.style.display = 'none';
  const presets = document.getElementById('radius-presets');
  if (presets) presets.style.display = 'none';
  const info = document.getElementById('radius-info');
  if (info) info.textContent = 'Click anywhere on the map to set a location';
  applyFilters();
  saveFiltersToSession();
}

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
    // Radius filter (Global page)
    if (radiusCenter && haversineDistance(radiusCenter.lat, radiusCenter.lng, loc.lat, loc.lng) > radiusKm) return;

    // Filter articles by time, source, search text, and paywall
    const hidePaywall = document.getElementById('hide-paywall')?.checked;
    const visibleArticles = loc.articles.filter(a => {
      const t = new Date(a.time).getTime();
      if (t < timelineMin || t > timelineMax) return false;
      if (activeSource && a.source !== activeSource) return false;
      if (searchText && !a.title.toLowerCase().includes(searchText)) return false;
      if (hidePaywall && isPaywall(a.source)) return false;
      if (showFavoritesOnly && !getFavorites().includes(a.url)) return false;
      if (activeBriefingTitles && !activeBriefingTitles.has(a.title)) return false;
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
      if (radiusCenter && haversineDistance(radiusCenter.lat, radiusCenter.lng, loc.lat, loc.lng) > radiusKm) return;
      const searchText = (document.getElementById('search-box')?.value || '').toLowerCase();
      const hidePaywall = document.getElementById('hide-paywall')?.checked;
      const visibleArticles = loc.articles.filter(a => {
        const t = new Date(a.time).getTime();
        if (t < timelineMin || t > timelineMax) return false;
        if (activeSource && a.source !== activeSource) return false;
        if (searchText && !a.title.toLowerCase().includes(searchText)) return false;
        if (hidePaywall && isPaywall(a.source)) return false;
        if (activeBriefingTitles && !activeBriefingTitles.has(a.title)) return false;
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

  // Apply radius filter (Global page)
  if (radiusCenter) {
    filtered = filtered.filter(loc => haversineDistance(radiusCenter.lat, radiusCenter.lng, loc.lat, loc.lng) <= radiusKm);
  }

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

  // Apply AI briefing filter
  if (activeBriefingTitles) {
    filtered = filtered.map(loc => {
      const matchingArticles = loc.articles.filter(a => activeBriefingTitles.has(a.title));
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
  saveFiltersToSession();
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
function clearBriefingFilter() {
  activeBriefingTitles = null;
  document.querySelectorAll('.ai-bullet').forEach(b => b.classList.remove('active'));
}

function saveFiltersToSession() {
  try {
    sessionStorage.setItem('pressradar_filters', JSON.stringify({
      country: activeCountry,
      source: activeSource,
      preset: document.querySelector('.preset-btn.active')?.getAttribute('onclick')?.match(/setPreset\('(.+?)'\)/)?.[1] || null,
      search: document.getElementById('search-box')?.value || '',
      hidePaywall: document.getElementById('hide-paywall')?.checked || false,
      radiusCenter: radiusCenter,
      radiusKm: radiusKm
    }));
  } catch(ex) {}
}

function filterCountry(country) {
  activeCountry = country;
  activeSource = null;
  clearBriefingFilter();
  applyFilters();
  autoExpandArticles();
  saveFiltersToSession();
}

function filterSource(source) {
  activeSource = source;
  clearBriefingFilter();
  applyFilters();
  autoExpandArticles();
  saveFiltersToSession();
}

function autoExpandArticles() {
  // Auto-expand all article lists when a filter is active
  if (activeCountry || activeSource || activeBriefingTitles) {
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
  if (typeof renderGlobe === 'function') renderGlobe();
  saveFiltersToSession();
}

function fitMapToMarkers() {
  // Skip when globe is active (Leaflet map is hidden and can't compute bounds)
  if (globeView) return;
  // When radius is active, the map is already fitted by updateRadiusOverlay
  if (radiusCenter) return;
  if (!activeCountry && !activeSource && !activeBriefingTitles) {
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
// Restore saved filters from session, or default to 48h
(function restoreFilters() {
  try {
    const saved = JSON.parse(sessionStorage.getItem('pressradar_filters') || 'null');
    if (saved) {
      activeCountry = saved.country || null;
      activeSource = saved.source || null;
      if (saved.search) document.getElementById('search-box').value = saved.search;
      if (saved.hidePaywall) document.getElementById('hide-paywall').checked = true;
      // Restore radius state (Global page)
      if (saved.radiusCenter) {
        radiusCenter = saved.radiusCenter;
        radiusKm = saved.radiusKm || 500;
        updateRadiusOverlay();
        const section = document.getElementById('radius-section');
        if (section) {
          const presets = document.getElementById('radius-presets');
          const clearBtn = document.getElementById('clear-radius-btn');
          const info = document.getElementById('radius-info');
          if (presets) presets.style.display = '';
          if (clearBtn) clearBtn.style.display = '';
          if (info) info.textContent = 'Showing articles within ' + radiusKm + ' km';
          // Highlight correct radius button
          document.querySelectorAll('#radius-presets .preset-btn').forEach(b => b.classList.remove('active'));
          const btn = document.querySelector('#radius-presets .preset-btn[onclick="setRadius(' + radiusKm + ')"]');
          if (btn) btn.classList.add('active');
        }
      }
      // setPreset triggers applyFilters which renders everything
      setPreset(saved.preset || '48h');
    } else {
      setPreset('48h');
    }
  } catch(ex) {
    setPreset('48h');
  }
  // Restore dropdown selections after renderFilterBars has populated them
  if (activeCountry) {
    const cSel = document.getElementById('country-select');
    if (cSel) cSel.value = activeCountry;
  }
  if (activeSource) {
    const sSel = document.getElementById('source-select');
    if (sSel) sSel.value = activeSource;
  }
  autoExpandArticles();
})();

// Show radius section on Global page
if (window.pageConfig.region === 'Global') {
  const radiusSec = document.getElementById('radius-section');
  if (radiusSec) radiusSec.style.display = '';
}

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
  // Update globe background for dark mode
  if (globe) {
    globe.backgroundImageUrl(isDark ? '//cdn.jsdelivr.net/npm/three-globe/example/img/night-sky.png' : '')
         .backgroundColor(isDark ? '#0a0a2e' : '#f0f4f8');
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

// AI Briefing bullet click → filter sidebar to related articles
document.addEventListener('click', function(e) {
  const bullet = e.target.closest('.ai-bullet');
  if (!bullet) return;
  // Don't trigger when clicking the title (collapse)
  if (e.target.id === 'ai-summary-title') return;

  const titlesAttr = bullet.getAttribute('data-titles');
  if (!titlesAttr) return;

  try {
    const titles = JSON.parse(titlesAttr);
    if (!titles || titles.length === 0) return;

    // If clicking the already-active bullet, clear the filter
    if (bullet.classList.contains('active')) {
      bullet.classList.remove('active');
      activeBriefingTitles = null;
    } else {
      // Remove active from all bullets, set on this one
      document.querySelectorAll('.ai-bullet').forEach(b => b.classList.remove('active'));
      bullet.classList.add('active');
      activeBriefingTitles = new Set(titles);
    }
    applyFilters();
    autoExpandArticles();
  } catch(ex) {}
});

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

// ===== GLOBE VIEW (Global page only) =====

function initGlobe() {
  if (globe || typeof Globe === 'undefined') return;
  const container = document.getElementById('globe-container');
  if (!container) return;

  const isDark = document.body.classList.contains('dark');

  globe = Globe()(container)
    .globeImageUrl('//cdn.jsdelivr.net/npm/three-globe/example/img/earth-blue-marble.jpg')
    .bumpImageUrl('//cdn.jsdelivr.net/npm/three-globe/example/img/earth-topology.png')
    .backgroundImageUrl(isDark ? '//cdn.jsdelivr.net/npm/three-globe/example/img/night-sky.png' : '')
    .backgroundColor(isDark ? '#0a0a2e' : '#f0f4f8')
    .showAtmosphere(true)
    .atmosphereColor('lightskyblue')
    .atmosphereAltitude(0.15)
    .pointOfView({ lat: 20, lng: 0, altitude: 2.5 })
    // Points layer
    .pointsData([])
    .pointLat('lat')
    .pointLng('lng')
    .pointColor('color')
    .pointAltitude('alt')
    .pointRadius('radius')
    .pointLabel(d => '<div style="font:13px/1.4 sans-serif;padding:4px 8px;background:rgba(0,0,0,0.75);color:#fff;border-radius:6px;max-width:220px;"><b>' + d.name + '</b><br>' + d.country + '<br>' + d.count + ' article' + (d.count > 1 ? 's' : '') + '</div>')
    // Rings layer (for radius visualization)
    .ringsData([])
    .ringLat('lat')
    .ringLng('lng')
    .ringMaxRadius('maxR')
    .ringPropagationSpeed(2)
    .ringRepeatPeriod(1200)
    .ringColor(() => 'rgba(231, 76, 60, 0.6)')
    // Globe click = set radius center
    .onGlobeClick(({ lat, lng }) => {
      radiusCenter = { lat, lng };
      updateRadiusOverlay();
      applyFilters();
      const section = document.getElementById('radius-section');
      if (section) section.style.display = '';
      const presets = document.getElementById('radius-presets');
      if (presets) presets.style.display = '';
      const clearBtn = document.getElementById('clear-radius-btn');
      if (clearBtn) clearBtn.style.display = '';
      const info = document.getElementById('radius-info');
      if (info) info.textContent = 'Showing articles within ' + radiusKm + ' km';
    })
    // Point click = scroll to sidebar
    .onPointClick(point => {
      if (point && point.name) scrollToLocation(point.name);
    });

  // Resize observer
  const ro = new ResizeObserver(() => {
    if (globe && container.offsetWidth > 0) {
      globe.width(container.offsetWidth).height(container.offsetHeight);
    }
  });
  ro.observe(container);
}

function renderGlobe() {
  if (!globe || !globeView) return;

  const searchText = (document.getElementById('search-box')?.value || '').toLowerCase();
  const hidePaywall = document.getElementById('hide-paywall')?.checked;
  const points = [];

  locations.forEach(loc => {
    if (activeCountry && loc.country !== activeCountry) return;
    if (radiusCenter && haversineDistance(radiusCenter.lat, radiusCenter.lng, loc.lat, loc.lng) > radiusKm) return;

    const visibleArticles = loc.articles.filter(a => {
      const t = new Date(a.time).getTime();
      if (t < timelineMin || t > timelineMax) return false;
      if (activeSource && a.source !== activeSource) return false;
      if (searchText && !a.title.toLowerCase().includes(searchText)) return false;
      if (hidePaywall && isPaywall(a.source)) return false;
      if (showFavoritesOnly && !getFavorites().includes(a.url)) return false;
      if (activeBriefingTitles && !activeBriefingTitles.has(a.title)) return false;
      return true;
    });
    if (visibleArticles.length === 0) return;

    const count = visibleArticles.length;
    points.push({
      lat: loc.lat,
      lng: loc.lng,
      name: loc.name,
      country: loc.country,
      count: count,
      color: catColors[loc.category] || '#c0392b',
      alt: 0.01 + count * 0.008,
      radius: Math.max(0.15, Math.min(0.8, count * 0.06))
    });
  });

  globe.pointsData(points);

  // Update rings for radius
  if (radiusCenter) {
    // Convert km to angular degrees (rough: 1 degree ≈ 111km)
    const radiusDeg = radiusKm / 111;
    globe.ringsData([{ lat: radiusCenter.lat, lng: radiusCenter.lng, maxR: radiusDeg }]);
  } else {
    globe.ringsData([]);
  }
}

function switchToGlobe() {
  if (globeView) return;
  globeView = true;

  const mapEl = document.getElementById('map');
  const globeEl = document.getElementById('globe-container');
  const mapStyleToggle = document.getElementById('map-style-toggle');
  const wrapper = document.getElementById('map-wrapper');
  const aiBox = document.getElementById('ai-summary-box');
  if (mapEl) mapEl.style.display = 'none';
  if (globeEl) globeEl.style.display = 'block';
  if (mapStyleToggle) mapStyleToggle.style.display = 'none';
  // Move AI briefing to wrapper so it's visible over globe
  if (aiBox && wrapper) wrapper.appendChild(aiBox);

  document.getElementById('btn-globe')?.classList.add('active');
  document.getElementById('btn-flat')?.classList.remove('active');

  // Lazy init
  if (!globe) initGlobe();
  // Small delay to let container size settle
  setTimeout(() => {
    const container = document.getElementById('globe-container');
    if (globe && container) {
      globe.width(container.offsetWidth).height(container.offsetHeight);
    }
    renderGlobe();
    // Fly to radius center if set
    if (radiusCenter) {
      globe.pointOfView({ lat: radiusCenter.lat, lng: radiusCenter.lng, altitude: 1.5 }, 1000);
    }
  }, 100);

  localStorage.setItem('pressradar-globeview', '1');
}

function switchToFlat() {
  if (!globeView) return;
  globeView = false;

  const mapEl = document.getElementById('map');
  const globeEl = document.getElementById('globe-container');
  const mapStyleToggle = document.getElementById('map-style-toggle');
  const aiBox = document.getElementById('ai-summary-box');
  if (mapEl) mapEl.style.display = '';
  if (globeEl) globeEl.style.display = 'none';
  if (mapStyleToggle) mapStyleToggle.style.display = '';
  // Move AI briefing back into map
  if (aiBox && mapEl) mapEl.insertBefore(aiBox, mapEl.firstChild);

  document.getElementById('btn-flat')?.classList.add('active');
  document.getElementById('btn-globe')?.classList.remove('active');

  // Refresh Leaflet map size (it may have been hidden)
  setTimeout(() => map.invalidateSize(), 100);

  localStorage.setItem('pressradar-globeview', '0');
}

// Auto-init globe on Global page if it was the last used view
if (window.pageConfig.region === 'Global') {
  const pref = localStorage.getItem('pressradar-globeview');
  // Default to globe view on Global page
  if (pref !== '0') {
    switchToGlobe();
  }
}
