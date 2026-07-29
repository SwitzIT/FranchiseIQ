// import { create } from 'zustand';

// // ── Steps in the onboarding/workflow ────────────────────────────────
// // 'country' | 'state' | 'category_competitors' | 'upload' | 'amenities'
// // | 'bu_question' | 'predicting' | 'dashboard'
// //
// // 'category_competitors' is a NEW v3 step inserted after state selection:
// // pick category (bakery for now) and choose competitors (option c flow).
// //
// // MODE switch: 'network_performance' (default, sales required)
// // or 'site_discovery' (no sales required, pick city/state).

// const useAppStore = create((set, get) => ({
//   // ── Navigation ───────────────────────────────────────────────
//   step: 'country',
//   setStep: (step) => set({ step }),

//   // ── Mode ─────────────────────────────────────────────────────
//   // 'network_performance' = the original flow with existing stores + sales
//   // 'site_discovery'      = new market entry, no sales required
//   mode: 'network_performance',
//   setMode: (mode) => set({ mode }),
//   viewMode: 'hex',
//   setViewMode: (m) => set({ viewMode: m }),

//   // ── Session ──────────────────────────────────────────────────
//   sessionId: null,
//   setSessionId: (id) => set({ sessionId: id }),

//   // ── Location Selection ───────────────────────────────────────
//   country: null,
//   currencySymbol: '$',
//   currencyCode: 'USD',
//   state: null,
//   stateConfig: null,
//   availableStates: [],
//   // v3: category (bakery/confectionery for now)
//   category: 'Bakery',
//   setCategory: (c) => set({ category: c }),

//   setCountry: (country, states, symbol, code) => set({
//     country, availableStates: states,
//     currencySymbol: symbol || '$', currencyCode: code || 'USD',
//     state: null, stateConfig: null,
//   }),
//   setState: (state, config) => set({ state, stateConfig: config }),

//   // ── Data ─────────────────────────────────────────────────────
//   nStores: 0, nRequests: 0, nDemog: 0,
//   setDataStats: (s) => set({
//     nStores: s.n_stores, nRequests: s.n_requests, nDemog: s.n_demographics,
//   }),

//   // ── v3: Data Validation ──────────────────────────────────────
//   // Populated after upload — fed into the Data Health panel.
//   validationReport: null,
//   setValidationReport: (r) => set({ validationReport: r }),
//   showValidationPanel: false,
//   setShowValidationPanel: (v) => set({ showValidationPanel: v }),

//   // ── Amenities ────────────────────────────────────────────────
//   amenitiesInfo: null,
//   setAmenitiesInfo: (info) => set({ amenitiesInfo: info }),

//   // ── Business Units ───────────────────────────────────────────
//   hasBU: false, buInfo: null,
//   setHasBU: (v) => set({ hasBU: v }),
//   setBUInfo: (info) => set({ buInfo: info }),

//   // ── Results / Map Data ───────────────────────────────────────
//   results: null,
//   setResults: (r) => set({ results: r }),

//   // ── Map UI State ─────────────────────────────────────────────
//   mapLayers: {
//     stores: true,
//     requests: true,
//     predictions: true,
//     businessUnits: true,
//     amenities: true,
//     realEstate: true,
//     hexHeatmap: true,   // v2: performance heatmap
//     competitorDensity: true,  // v3: competitor hex layer
//     untappedDemand: true,   // v3: opportunity hex layer
//     peerContextColor: false,  // v3: recolor stores by peer comparison (toggle)
//   },
//   toggleLayer: (layer) =>
//     set((s) => ({ mapLayers: { ...s.mapLayers, [layer]: !s.mapLayers[layer] } })),

//   selectedMarker: null,
//   setSelectedMarker: (m) => set({ selectedMarker: m }),

//   // ── Fly-to coords (map) ──────────────────────────────────────
//   flyToCoords: null,

//   // ── Store Performance Filter ─────────────────────────────────
//   storeFilter: 'all',
//   setStoreFilter: (f) => set({ storeFilter: f }),

//   // ── Franchise Store Selector ─────────────────────────────────
//   selectedStoreName: null,
//   flyToStore: (name) => {
//     if (!name) { set({ selectedStoreName: null, flyToCoords: null }); return; }
//     const { results } = get();
//     const stores = results?.stores || [];
//     const store = stores.find(s => s.name === name);
//     if (store) {
//       set({
//         selectedStoreName: name,
//         flyToCoords: { lat: store.lat, lng: store.lng, zoom: 16 },
//       });
//     }
//   },

//   // ── Region KPIs ──────────────────────────────────────────────
//   regionKpis: null, selectedRegion: null,
//   setRegionKpis: (kpis) => set({ regionKpis: kpis }),
//   setSelectedRegion: (region) => set({ selectedRegion: region }),

//   // ── Hex Heatmap (v2) ─────────────────────────────────────────
//   hexHeatmap: null,
//   hexResolutionOverride: null,   // null = let backend auto-pick
//   hexLoading: false,
//   setHexHeatmap: (h) => set({ hexHeatmap: h }),
//   setHexResolutionOverride: (r) => set({ hexResolutionOverride: r }),
//   setHexLoading: (v) => set({ hexLoading: v }),

//   // ── v3: Peer-Context Benchmarking ────────────────────────────
//   // benchmarkMode: 'network' (vs network avg) or 'peer' (vs cluster avg)
//   benchmarkMode: 'network',
//   setBenchmarkMode: (m) => set({ benchmarkMode: m }),
//   peerContext: null,   // full peer-context API response
//   setPeerContext: (p) => set({ peerContext: p }),

//   // ── v3: Competitors ──────────────────────────────────────────
//   competitors: [],    // [{ name, selected, locations, last_fetched_at }, ...]
//   setCompetitors: (c) => set({ competitors: c }),
//   competitorDensityHexes: null,
//   setCompetitorDensityHexes: (h) => set({ competitorDensityHexes: h }),
//   competitorRefreshLoading: false,
//   setCompetitorRefreshLoading: (v) => set({ competitorRefreshLoading: v }),

//   // ── v3: Untapped Demand ──────────────────────────────────────
//   untappedDemand: null,
//   setUntappedDemand: (d) => set({ untappedDemand: d }),
//   untappedDemandLoading: false,
//   setUntappedDemandLoading: (v) => set({ untappedDemandLoading: v }),

//   // ── v3: Site Discovery ───────────────────────────────────────
//   availableTerritories: {},   // { country: [territory names] }
//   setAvailableTerritories: (t) => set({ availableTerritories: t }),
//   selectedTerritory: null,
//   setSelectedTerritory: (t) => set({ selectedTerritory: t }),
//   siteDiscoveryResult: null,
//   setSiteDiscoveryResult: (r) => set({ siteDiscoveryResult: r }),

//   // ── Chat ─────────────────────────────────────────────────────
//   chatOpen: false,
//   toggleChat: () => set((s) => ({ chatOpen: !s.chatOpen })),

//   // ── Mobile UI ────────────────────────────────────────────────
//   mobileSidebarOpen: false,
//   setMobileSidebarOpen: (v) => set({ mobileSidebarOpen: v }),
//   mobileSheetOpen: false,
//   setMobileSheetOpen: (v) => set({ mobileSheetOpen: v }),

//   // ── Loading ──────────────────────────────────────────────────
//   loading: false, loadingMsg: '',
//   setLoading: (v, msg = '') => set({ loading: v, loadingMsg: msg }),

//   // ── Reset ────────────────────────────────────────────────────
//   reset: () => set({
//     step: 'country', mode: 'network_performance',
//     sessionId: null, country: null, state: null, stateConfig: null,
//     availableStates: [], category: 'Bakery',
//     nStores: 0, nRequests: 0,
//     validationReport: null, showValidationPanel: false,
//     amenitiesInfo: null, hasBU: false, buInfo: null, results: null,
//     regionKpis: null, selectedRegion: null,
//     hexHeatmap: null, hexResolutionOverride: null, hexLoading: false,
//     benchmarkMode: 'network', peerContext: null,
//     competitors: [], competitorDensityHexes: null, competitorRefreshLoading: false,
//     untappedDemand: null, untappedDemandLoading: false,
//     availableTerritories: {}, selectedTerritory: null, siteDiscoveryResult: null,
//     chatOpen: false, loading: false, loadingMsg: '',
//     selectedStoreName: null, flyToCoords: null, storeFilter: 'all',
//     mobileSidebarOpen: false, mobileSheetOpen: false,
//   }),
// }));

// export default useAppStore;

import { create } from 'zustand';
// ── Steps in the onboarding/workflow ────────────────────────────────
// 'country' | 'state' | 'category_competitors' | 'upload' | 'amenities'
// | 'bu_question' | 'predicting' | 'dashboard'
//
// 'category_competitors' is a NEW v3 step inserted after state selection:
// pick category (bakery for now) and choose competitors (option c flow).
//
// MODE switch: 'network_performance' (default, sales required)
// or 'site_discovery' (no sales required, pick city/state).
const useAppStore = create((set, get) => ({
  // ── Navigation ───────────────────────────────────────────────
  step: 'country',
  setStep: (step) => set({ step }),
  // ── Mode ─────────────────────────────────────────────────────
  // 'network_performance' = the original flow with existing stores + sales
  // 'site_discovery'      = new market entry, no sales required
  mode: 'network_performance',
  setMode: (mode) => set({ mode }),
  viewMode: 'hex',
  setViewMode: (m) => set({ viewMode: m }),
  // ── Session ──────────────────────────────────────────────────
  sessionId: null,
  setSessionId: (id) => set({ sessionId: id }),
  // ── Location Selection ───────────────────────────────────────
  country: null,
  currencySymbol: '$',
  currencyCode: 'USD',
  state: null,
  stateConfig: null,
  availableStates: [],
  // v3: category (bakery/confectionery for now)
  category: 'Bakery',
  setCategory: (c) => set({ category: c }),
  setCountry: (country, states, symbol, code) => set({
    country, availableStates: states,
    currencySymbol: symbol || '$', currencyCode: code || 'USD',
    state: null, stateConfig: null,
  }),
  setState: (state, config) => set({ state, stateConfig: config }),
  // ── Data ─────────────────────────────────────────────────────
  nStores: 0, nRequests: 0, nDemog: 0,
  setDataStats: (s) => set({
    nStores: s.n_stores, nRequests: s.n_requests, nDemog: s.n_demographics,
  }),
  // ── v3: Data Validation ──────────────────────────────────────
  // Populated after upload — fed into the Data Health panel.
  validationReport: null,
  setValidationReport: (r) => set({ validationReport: r }),
  showValidationPanel: false,
  setShowValidationPanel: (v) => set({ showValidationPanel: v }),
  // ── Amenities ────────────────────────────────────────────────
  amenitiesInfo: null,
  setAmenitiesInfo: (info) => set({ amenitiesInfo: info }),
  // ── Business Units ───────────────────────────────────────────
  hasBU: false, buInfo: null,
  setHasBU: (v) => set({ hasBU: v }),
  setBUInfo: (info) => set({ buInfo: info }),
  // ── Results / Map Data ───────────────────────────────────────
  results: null,
  setResults: (r) => set({ results: r }),
  // ── Map UI State ─────────────────────────────────────────────
  mapLayers: {
    stores: true,
    requests: true,
    predictions: true,
    businessUnits: true,
    amenities: true,
    realEstate: true,
    hexHeatmap: true,   // v2: performance heatmap
    competitorDensity: true,  // v3: competitor hex layer
    untappedDemand: true,   // v3: opportunity hex layer
    peerContextColor: false,  // v3: recolor stores by peer comparison (toggle)
  },
  toggleLayer: (layer) =>
    set((s) => ({ mapLayers: { ...s.mapLayers, [layer]: !s.mapLayers[layer] } })),
  selectedMarker: null,
  setSelectedMarker: (m) => set({ selectedMarker: m }),
  // ── Fly-to coords (map) ──────────────────────────────────────
  flyToCoords: null,
  setFlyToCoords: (coords) => set({ flyToCoords: coords }),
  // ── Store Performance Filter ─────────────────────────────────
  storeFilter: 'all',
  setStoreFilter: (f) => set({ storeFilter: f }),
  // ── District Panel Map Filter ────────────────────────────────
  // Used by DistrictPerformancePanel for click-to-filter-map workflows.
  // Shape: { kind: 'district'|'store'|'multi', label, names: [], parentDistrict? }
  mapStoreFilter: null,
  setMapStoreFilter: (filter) => set({ mapStoreFilter: filter }),
  clearMapStoreFilter: () => set({ mapStoreFilter: null }),
  // ── Franchise Store Selector ─────────────────────────────────
  selectedStoreName: null,
  flyToStore: (name) => {
    if (!name) { set({ selectedStoreName: null, flyToCoords: null }); return; }
    const { results } = get();
    const stores = results?.stores || [];
    const store = stores.find(s => s.name === name);
    if (store) {
      set({
        selectedStoreName: name,
        flyToCoords: { lat: store.lat, lng: store.lng, zoom: 16 },
      });
    }
  },
  // ── Region KPIs ──────────────────────────────────────────────
  regionKpis: null, selectedRegion: null,
  setRegionKpis: (kpis) => set({ regionKpis: kpis }),
  setSelectedRegion: (region) => set({ selectedRegion: region }),
  // ── Hex Heatmap (v2) ─────────────────────────────────────────
  hexHeatmap: null,
  hexResolutionOverride: null,   // null = let backend auto-pick
  hexLoading: false,
  setHexHeatmap: (h) => set({ hexHeatmap: h }),
  setHexResolutionOverride: (r) => set({ hexResolutionOverride: r }),
  setHexLoading: (v) => set({ hexLoading: v }),
  // ── v3: Peer-Context Benchmarking ────────────────────────────
  // benchmarkMode: 'network' (vs network avg) or 'peer' (vs cluster avg)
  benchmarkMode: 'network',
  setBenchmarkMode: (m) => set({ benchmarkMode: m }),
  peerContext: null,   // full peer-context API response
  setPeerContext: (p) => set({ peerContext: p }),
  // ── v3: Competitors ──────────────────────────────────────────
  competitors: [],    // [{ name, selected, locations, last_fetched_at }, ...]
  setCompetitors: (c) => set({ competitors: c }),
  competitorDensityHexes: null,
  setCompetitorDensityHexes: (h) => set({ competitorDensityHexes: h }),
  competitorRefreshLoading: false,
  setCompetitorRefreshLoading: (v) => set({ competitorRefreshLoading: v }),
  // ── v3: Untapped Demand ──────────────────────────────────────
  untappedDemand: null,
  setUntappedDemand: (d) => set({ untappedDemand: d }),
  untappedDemandLoading: false,
  setUntappedDemandLoading: (v) => set({ untappedDemandLoading: v }),
  // ── v3: Site Discovery ───────────────────────────────────────
  availableTerritories: {},   // { country: [territory names] }
  setAvailableTerritories: (t) => set({ availableTerritories: t }),
  selectedTerritory: null,
  setSelectedTerritory: (t) => set({ selectedTerritory: t }),
  siteDiscoveryResult: null,
  setSiteDiscoveryResult: (r) => set({ siteDiscoveryResult: r }),
  // ── Chat ─────────────────────────────────────────────────────
  chatOpen: false,
  toggleChat: () => set((s) => ({ chatOpen: !s.chatOpen })),
  // ── Mobile UI ────────────────────────────────────────────────
  mobileSidebarOpen: false,
  setMobileSidebarOpen: (v) => set({ mobileSidebarOpen: v }),
  mobileSheetOpen: false,
  setMobileSheetOpen: (v) => set({ mobileSheetOpen: v }),
  // ── Loading ──────────────────────────────────────────────────
  loading: false, loadingMsg: '',
  setLoading: (v, msg = '') => set({ loading: v, loadingMsg: msg }),
  // ── Reset ────────────────────────────────────────────────────
  reset: () => set({
    step: 'country', mode: 'network_performance',
    sessionId: null, country: null, state: null, stateConfig: null,
    availableStates: [], category: 'Bakery',
    nStores: 0, nRequests: 0,
    validationReport: null, showValidationPanel: false,
    amenitiesInfo: null, hasBU: false, buInfo: null, results: null,
    regionKpis: null, selectedRegion: null,
    hexHeatmap: null, hexResolutionOverride: null, hexLoading: false,
    benchmarkMode: 'network', peerContext: null,
    competitors: [], competitorDensityHexes: null, competitorRefreshLoading: false,
    untappedDemand: null, untappedDemandLoading: false,
    availableTerritories: {}, selectedTerritory: null, siteDiscoveryResult: null,
    chatOpen: false, loading: false, loadingMsg: '',
    selectedStoreName: null, flyToCoords: null, storeFilter: 'all',
    mapStoreFilter: null,
    mobileSidebarOpen: false, mobileSheetOpen: false,
  }),
}));
export default useAppStore;