import axios from 'axios';

const RAW_BASE = import.meta.env.VITE_API_URL || 'https://franchise-iq-backend.onrender.com';
let BASE = RAW_BASE.replace(/\/+$/, '');
if (BASE && !BASE.startsWith('http')) {
  BASE = `https://${BASE}`;
}

const api = axios.create({
  baseURL: `${BASE}/api`,
  timeout: 300_000,
});

// ── Auth: attach JWT to every request ───────────────────────────────
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('franchiseiq_token');
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// If a token expires/is invalid, bounce back to the login screen.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      localStorage.removeItem('franchiseiq_token');
      window.dispatchEvent(new CustomEvent('franchiseiq:unauthorized'));
    }
    return Promise.reject(error);
  }
);

// ── Countries / States ──────────────────────────────────────────────
export const getCountries = () =>
  api.get('/countries').then(r => r.data);

export const selectCountry = (country) =>
  api.post('/select_country', { country }).then(r => r.data);

export const selectState = (session_id, state) =>
  api.post('/select_state', { session_id, state }).then(r => r.data);

// ── Data ─────────────────────────────────────────────────────────────
export const loadData = (session_id, storesFile, requestsFile) => {
  const fd = new FormData();
  fd.append('session_id', session_id);
  fd.append('stores_file', storesFile);
  if (requestsFile) fd.append('requests_file', requestsFile);
  return api.post('/load_data', fd).then(r => r.data);
};

export const loadPreloaded = (session_id) =>
  api.post('/load_preloaded', { session_id }).then(r => r.data);

// ── Amenities ────────────────────────────────────────────────────────
export const fetchAmenities = (session_id) =>
  api.post('/fetch_amenities', { session_id }).then(r => r.data);

export const getAmenitiesStatus = (session_id, country, state) =>
  api.get('/amenities_status', { params: { session_id, country, state } }).then(r => r.data);

// ── Business Units ───────────────────────────────────────────────────
export const uploadBusinessUnits = (session_id, buFile) => {
  const fd = new FormData();
  fd.append('session_id', session_id);
  fd.append('bu_file', buFile);
  return api.post('/upload_business_units', fd).then(r => r.data);
};

export const clearBusinessUnits = (session_id) =>
  api.delete(`/business_units?session_id=${session_id}`).then(r => r.data);

// ── Predict ──────────────────────────────────────────────────────────
export const runPrediction = async (sessionId, topN = 10) => {
  const { data } = await api.post('/predict', { session_id: sessionId, top_n: topN });
  return data;
};

// ── Results ──────────────────────────────────────────────────────────
export const getResults = async (sessionId) => {
  const { data } = await api.get(`/results/get_results?session_id=${sessionId}`);
  return data;
};

export const getRegionKpis = async (sessionId) => {
  const { data } = await api.get(`/region-kpis?session_id=${sessionId}`);
  return data;
};

// ── v2: Hex Heatmap (auto-resolution) ────────────────────────────────
export const getHexHeatmap = async (sessionId, resolution = null) => {
  const params = { session_id: sessionId };
  if (resolution != null) params.resolution = resolution;
  const { data } = await api.get('/hex-heatmap', { params });
  return data;
};

export const getSuggestedHexResolution = async (sessionId) => {
  const { data } = await api.get('/hex-heatmap/suggest-resolution', {
    params: { session_id: sessionId },
  });
  return data;
};

// ── v3: Data Validation ─────────────────────────────────────────────
export const validateStoresPayload = async (rows, country = null, requireRevenue = true) => {
  const { data } = await api.post('/validate-stores', {
    rows, country, require_revenue: requireRevenue,
  });
  return data;
};

export const validateSession = async (sessionId) => {
  const { data } = await api.get('/validate-session', { params: { session_id: sessionId } });
  return data;
};

// ── v3: Peer-Context Benchmarking ───────────────────────────────────
// Returns each store's classification vs its peer cluster (not network avg).
// `k` is the number of clusters (default ~4, auto-capped by dataset size).
export const getPeerContext = async (sessionId, k = null) => {
  const params = { session_id: sessionId };
  if (k != null) params.k = k;
  const { data } = await api.get('/peer-context', { params });
  return data;
};

// ── v3: Untapped Demand Layer ───────────────────────────────────────
export const getUntappedDemand = async (sessionId, opts = {}) => {
  const params = {
    session_id: sessionId,
    resolution: opts.resolution ?? 6,
    supply_radius_km: opts.supplyRadiusKm ?? 3.0,
    min_demand_percentile: opts.minDemandPercentile ?? 50,
  };
  const { data } = await api.get('/untapped-demand', { params });
  return data;
};

// ── v3: Competitor Management (option c onboarding) ─────────────────
export const getCompetitorTemplates = async () => {
  const { data } = await api.get('/competitors/templates');
  return data;
};

export const getSuggestedCompetitors = async (country, category) => {
  const { data } = await api.get('/competitors/suggested', { params: { country, category } });
  return data;
};

export const getAvailableCategories = async (country) => {
  const { data } = await api.get('/competitors/categories', { params: { country } });
  return data;
};

export const initializeCompetitors = async (sessionId, country, category, customAdditions = []) => {
  const { data } = await api.post('/competitors/initialize', {
    session_id: sessionId, country, category,
    custom_additions: customAdditions,
  });
  return data;
};

export const listTenantCompetitors = async (sessionId) => {
  const { data } = await api.get('/competitors/list', { params: { session_id: sessionId } });
  return data;
};

export const updateCompetitors = async (sessionId, brands) => {
  const { data } = await api.put('/competitors/update', {
    session_id: sessionId, brands,
  });
  return data;
};

export const refreshCompetitorLocations = async (sessionId, regionHint = null) => {
  const { data } = await api.post('/competitors/refresh-locations', {
    session_id: sessionId, region_hint: regionHint,
  });
  return data;
};

export const getCompetitorDensityHexes = async (sessionId, resolution = 6) => {
  const { data } = await api.get('/competitors/density-hexes', {
    params: { session_id: sessionId, resolution },
  });
  return data;
};

// ── v3: Site Discovery (market-entry mode) ──────────────────────────
export const getAvailableTerritories = async (country = null) => {
  const params = country ? { country } : {};
  const { data } = await api.get('/site-discovery/territories', { params });
  return data;
};

export const getTerritoryDetail = async (country, territory) => {
  const { data } = await api.get('/site-discovery/territory', {
    params: { country, territory },
  });
  return data;
};

export const analyseTerritory = async (sessionId, country, territory, resolution = 6) => {
  const { data } = await api.post('/site-discovery/analyse', {
    session_id: sessionId, country, territory, resolution,
  });
  return data;
};

// ── Download ─────────────────────────────────────────────────────────
export const getDownloadUrl = (session_id) =>
  `${BASE}/api/download_results?session_id=${session_id}`;

// ── v3.4: District View ───────────────────────────────────────────── 
export const getDistrictPerformance = async (sessionId) => { const { data } = await api.get('/district-performance', { params: { session_id: sessionId }, }); return data; };

export async function sendChatMessage(messages, sessionId) {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages, session_id: sessionId || null }),
  });
  if (!res.ok) {
    throw new Error(`Chat request failed: ${res.status}`);
  }
  const data = await res.json();
  return data.reply;
}