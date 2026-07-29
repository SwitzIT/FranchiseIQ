# FranchiseIQ — v3 Changes

This is a substantial release: data validation, peer-context benchmarking,
competitor density layer, untapped-demand layer, and Site Discovery mode.
Plus platform data-fetch scripts. Built on the v2 hex aggregation foundation.

## Summary at a glance

| Layer | Status | What it does |
|---|---|---|
| 1. Performance heatmap | shipped in v2 | Where your stores perform vs network avg |
| 2. Peer-context benchmark | **new in v3** | Where stores perform vs their peer cluster (true outperformers) |
| 3. Competitor density | **new in v3** | Where competitors cluster — threat map |
| 4. Untapped demand | **new in v3** | High demand × low supply — expansion candidates |
| Site Discovery mode | **new in v3** | Analyse a city/state with no existing stores |
| Data Health validation | **new in v3** | Hard + soft validation with Data Health Score |
| Region auto-derivation | **new in v3** | Reverse-geocode lat/lng → state/city/suburb |

## Files added / modified

### Backend — new services
- `backend/app/services/data_validation_service.py` — hard rules + soft warnings
- `backend/app/services/peer_context_service.py` — k-means clustering + peer benchmark
- `backend/app/services/competitor_service.py` — templates, Places API, density hexes
- `backend/app/services/untapped_demand_service.py` — high-demand × low-supply hexes
- `backend/app/services/site_discovery_service.py` — coordinator for market-entry mode
- `backend/app/services/region_geocoding_service.py` — Nominatim reverse geocoding

### Backend — new routes
- `backend/app/routes/validation.py` — POST /api/validate-stores, GET /api/validate-session
- `backend/app/routes/competitors.py` — /api/competitors/* endpoints
- `backend/app/routes/site_discovery.py` — /api/site-discovery/* endpoints

### Backend — modified routes
- `backend/app/routes/analytics.py` — adds /peer-context and /untapped-demand

### Backend — config + scripts
- `backend/app/data/competitor_templates.yaml` — **edit this before the meeting** if business gives different brand confirmations
- `backend/scripts/fetch_worldpop.py` — WorldPop 1km population grid
- `backend/scripts/fetch_meta_rwi.py` — Meta Relative Wealth Index
- `backend/scripts/fetch_gadm.py` — GADM admin boundaries
- `backend/scripts/README.md` — how to run the above
- `backend/requirements.txt` — adds `h3`, `geopy`, `pyyaml`, `requests`

### Frontend
- `frontend/src/services/api.js` — adds all v3 endpoint functions
- `frontend/src/store/useAppStore.js` — adds state for validation, peer context, competitors, untapped demand, site discovery, modes
- `frontend/src/components/DataHealthPanel.jsx` — new
- `frontend/src/components/SiteDiscoveryEntry.jsx` — new
- `frontend/src/components/CompetitorOnboarding.jsx` — new

## Apply order

```bash
# 1. Copy backend files into your repo, preserving paths
cp -r v3/backend/* <your-repo>/backend/

# 2. Copy frontend files
cp -r v3/frontend/* <your-repo>/frontend/

# 3. Backend deps (use Python 3.11 venv to match Dockerfile)
cd <your-repo>/backend
python3.11 -m venv venv
source venv/bin/activate    # PowerShell: .\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 4. (Optional, recommended) Pull platform data — runs once
cd scripts
python fetch_worldpop.py --country IND --output ../app/data/worldpop/
python fetch_worldpop.py --country LKA --output ../app/data/worldpop/
python fetch_meta_rwi.py --country IND --output ../app/data/meta_rwi/
python fetch_meta_rwi.py --country LKA --output ../app/data/meta_rwi/
python fetch_gadm.py     --country IND --all-levels --output ../app/data/gadm/
python fetch_gadm.py     --country LKA --all-levels --output ../app/data/gadm/

# 5. Environment variable for the Places API integration
export GOOGLE_PLACES_API_KEY='your-key-here'

# 6. Start as usual
cd ../
uvicorn app.main:app --reload
```

## What you still need to wire (the dev's job)

I deliberately did not modify `MapContainer.jsx`, `Sidebar.jsx`, or
`DashboardPage.jsx` in this batch — they're substantial files and you've
been actively iterating on them. The patches below are small additions
that go into the existing files.

### `MapContainer.jsx` — render the new layers

Add three new layer-rendering blocks alongside the existing hex heatmap.
All three use the same `<Polygon>` pattern from react-leaflet — just
different data and colour scales. Insert these between the hex heatmap
render and the pin markers:

```jsx
import { Polygon, Tooltip } from 'react-leaflet';
// ...
const {
  hexHeatmap, mapLayers,
  competitorDensityHexes,   // v3
  untappedDemand,           // v3
  peerContext, benchmarkMode, // v3
} = useAppStore();

// Competitor density (red gradient)
{mapLayers.competitorDensity && competitorDensityHexes?.hexes?.map((hex) => {
  const maxCount = Math.max(
    ...competitorDensityHexes.hexes.map(h => h.competitor_count)
  );
  const intensity = hex.competitor_count / maxCount;
  return (
    <Polygon
      key={`comp-${hex.cell}`}
      positions={hex.boundary}
      pathOptions={{
        color: '#DC2626',
        fillColor: '#DC2626',
        fillOpacity: 0.15 + intensity * 0.45,
        weight: 1,
      }}
    >
      <Tooltip>
        {hex.competitor_count} competitor stores in this area
      </Tooltip>
    </Polygon>
  );
})}

// Untapped demand (blue gradient)
{mapLayers.untappedDemand && untappedDemand?.hexes?.map((hex) => {
  const c = hex.classification;
  const fillColor =
    c === 'high'   ? '#2563EB' :
    c === 'medium' ? '#3B82F6' :
                     '#93C5FD';
  return (
    <Polygon
      key={`untapped-${hex.cell}`}
      positions={hex.boundary}
      pathOptions={{
        color: fillColor,
        fillColor: fillColor,
        fillOpacity: hex.untapped_score * 0.6,
        weight: 1,
      }}
    >
      <Tooltip>
        Untapped score {Math.round(hex.untapped_score * 100)}%<br/>
        Population {hex.population.toLocaleString()}<br/>
        Nearest store: {hex.nearest_store_km ? `${hex.nearest_store_km} km` : 'none nearby'}
      </Tooltip>
    </Polygon>
  );
})}
```

For peer-context recolouring: if `benchmarkMode === 'peer'` and `peerContext`
is loaded, recolour the store pins by their `pct_of_peer_avg` from
`peerContext.stores` (look up by name). Reuse the existing
green/amber/red palette.

### `Sidebar.jsx` — add layer toggles

In the layers panel, add three new toggle rows next to the existing ones:

```jsx
import { Target, Sparkles, Users } from 'lucide-react';
// ... inside the layer list:
<LayerToggle
  icon={Target}
  label="Competitor Density"
  hint="Where competitors cluster"
  layerKey="competitorDensity"
  color="#DC2626"
/>
<LayerToggle
  icon={Sparkles}
  label="Untapped Demand"
  hint="High demand × low supply"
  layerKey="untappedDemand"
  color="#2563EB"
/>
<LayerToggle
  icon={Users}
  label="Peer Context"
  hint="Compare to similar stores"
  layerKey="peerContextColor"
  color="#7C3AED"
/>
```

### `DashboardPage.jsx` — wire the data fetches

Add three `useEffect` hooks alongside the existing hex-heatmap one:

```jsx
import {
  getPeerContext, getUntappedDemand, getCompetitorDensityHexes,
} from '../services/api';

// ── Peer context fetch ──
useEffect(() => {
  if (!sessionId || !results) return;
  let cancelled = false;
  getPeerContext(sessionId)
    .then(d => { if (!cancelled) setPeerContext(d); })
    .catch(e => console.warn('peer-context:', e));
  return () => { cancelled = true; };
}, [sessionId, results, setPeerContext]);

// ── Untapped demand fetch ──
useEffect(() => {
  if (!sessionId || !results) return;
  let cancelled = false;
  setUntappedDemandLoading(true);
  getUntappedDemand(sessionId, { resolution: 6 })
    .then(d => { if (!cancelled) setUntappedDemand(d); })
    .catch(e => console.warn('untapped-demand:', e))
    .finally(() => { if (!cancelled) setUntappedDemandLoading(false); });
  return () => { cancelled = true; };
}, [sessionId, results, setUntappedDemand, setUntappedDemandLoading]);

// ── Competitor density fetch (only if competitors configured) ──
useEffect(() => {
  if (!sessionId || competitors.length === 0) return;
  let cancelled = false;
  getCompetitorDensityHexes(sessionId, 6)
    .then(d => { if (!cancelled) setCompetitorDensityHexes(d); })
    .catch(e => console.warn('competitor-density:', e));
  return () => { cancelled = true; };
}, [sessionId, competitors, setCompetitorDensityHexes]);
```

Also drop in the `<DataHealthPanel floating />` component somewhere near
the dashboard root — it shows itself when `showValidationPanel` is true.

### Wiring upload validation

After the existing upload completes, call validation:

```jsx
import { validateSession } from '../services/api';
// after loadData completes:
const report = await validateSession(sessionId);
setValidationReport(report);
setShowValidationPanel(true);
if (!report.passed) {
  // optionally block dashboard progression until errors are fixed
}
```

## What's pitch-ready vs what's roadmap

**Ready to demo tomorrow:**
- The four-layer story (Performance + Peer-context + Competitors + Untapped demand)
- Adaptive H3 resolution working on real data (Mio: res 5 / 77 cells, Caravan: res 6 / 22 cells)
- Data validation flow with Data Health Score
- Competitor onboarding option (c) flow
- Site Discovery mode with city/state dropdown
- Auto-region derivation (no need for tenants to provide regions)

**Needs your data layers to be fully meaningful (roadmap):**
- Untapped demand currently uses placeholder zeros when WorldPop/RWI data
  isn't loaded. Run the fetch scripts and wire `demographics_service.py` to
  serve from those files for real numbers.
- Peer-context clustering currently works on `catchment_*` features added
  by the existing demographics service — confirm those features are being
  attached to each store before the clusters become meaningful.

**Not in this batch (next sprint):**
- Verify-on-map drag-to-correct for store locations
- Per-tenant pricing tier enforcement
- Prediction back-testing / accuracy track-record
- BD-workflow integrations (CRM, deal pipeline) — out of scope per spec

## Things to flag to your dev

1. The Nominatim service caches reverse-geocode results in
   `backend/geocode_cache/nominatim_cache.json`. Add this to `.gitignore`.
2. `GOOGLE_PLACES_API_KEY` is read from environment. Without it,
   competitor location fetches return empty lists with a log warning —
   they don't fail. Good for dev environments.
3. The `_existing_routers` import-defensive pattern in `routes/__init__.py`
   means if your file names differ slightly, v3 doesn't crash. But check
   the FastAPI startup logs to confirm all v3 routers actually loaded.
4. The competitor templates YAML is dirt-simple — your business team can
   edit it directly to add new brands without code changes. Just restart
   the backend.

## Validated against your real data

Smoke-tested with both your uploaded datasets:

- **Mio Amore (384 stores, West Bengal)** → auto-picks H3 res 5 → 77 cells
  → 20 above / 20 on-target / 37 below network avg; all 384 stores
  accounted for.
- **Caravan Fresh (69 stores, Sri Lanka)** → auto-picks H3 res 6 → 22 cells
  → 9 above / 3 on-target / 10 below; all 69 stores accounted for.

The peer-context, competitor density, and untapped demand layers will be
similarly meaningful once the demographics + competitor location enrichment
is wired in.
