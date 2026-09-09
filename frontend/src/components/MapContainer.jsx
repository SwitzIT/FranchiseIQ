import React, { useMemo, useEffect } from 'react';
import { MapContainer, TileLayer, CircleMarker, Marker, Popup, Tooltip, ZoomControl, useMap } from 'react-leaflet';
import MarkerClusterGroup from 'react-leaflet-cluster';
import L from 'leaflet';
import useAppStore from '../store/useAppStore';

// ─── FlyTo on store/prediction selection ──────────────────────
function FlyToLocation() {
  const map = useMap();
  const flyToCoords = useAppStore(s => s.flyToCoords);

  useEffect(() => {
    if (flyToCoords?.lat && flyToCoords?.lng) {
      map.flyTo([flyToCoords.lat, flyToCoords.lng], flyToCoords.zoom || 15, { duration: 1.2 });
    }
  }, [flyToCoords, map]);

  return null;
}

// ─── Icons ────────────────────────────────────────────────────
const emojiIcon = (emoji, size = 26) => L.divIcon({
  html: `<div style="font-size:${size}px;line-height:1;filter:drop-shadow(0 2px 6px rgba(0,0,0,0.25));">${emoji}</div>`,
  className: '',
  iconSize: [size, size],
  iconAnchor: [size / 2, size / 2],
});

const storeMarkerIcon = (classification) => {
  const colors = { above: '#22C55E', on_target: '#F59E0B', below: '#EF4444' };
  const color = colors[classification] || colors.on_target;
  // Lucide-style "Store" SVG path, rendered in white inside a colored circle
  return L.divIcon({
    html: `<div style="
      width:20px;height:20px;border-radius:50%;
      background:${color};border:2px solid white;
      display:flex;align-items:center;justify-content:center;
      box-shadow:0 2px 5px rgba(0,0,0,0.35);
    ">
      <svg width="11" height="11" viewBox="0 0 24 24" fill="none"
           stroke="white" stroke-width="2.5"
           stroke-linecap="round" stroke-linejoin="round">
        <path d="m2 7 4.41-4.41A2 2 0 0 1 7.83 2h8.34a2 2 0 0 1 1.42.59L22 7"/>
        <line x1="2" x2="22" y1="11" y2="11"/>
        <path d="M5 11v10h14V11"/>
        <path d="M10 21v-6h4v6"/>
      </svg>
    </div>`,
    className: 'fiq-store-marker',
    iconSize: [24, 24],
    iconAnchor: [12, 12],
    popupAnchor: [0, -14],
  });
};

// ─── Rank-based prediction marker icon ────────────────────────
// #1 = gold, #2 = silver, #3 = bronze, #4-10 = brand purple
const rankMarkerIcon = (rank) => {
  const bgColor =
    rank === 1 ? '#D4AF37' :        // gold
      rank === 2 ? '#A8A8A8' :        // silver
        rank === 3 ? '#B87333' :        // bronze
          '#6C4CF1';                       // brand purple for #4-#10

  const size = rank <= 3 ? 36 : 30;
  const fontSize = rank <= 3 ? 15 : 13;

  return L.divIcon({
    html: `<div style="
      width:${size}px;height:${size}px;border-radius:50%;
      background:${bgColor};
      border:3px solid white;
      display:flex;align-items:center;justify-content:center;
      color:white;font-weight:800;font-family:Inter,sans-serif;
      font-size:${fontSize}px;line-height:1;
      box-shadow:0 3px 8px rgba(0,0,0,0.35);
    ">#${rank}</div>`,
    className: 'fiq-rank-marker',
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    popupAnchor: [0, -size / 2 + 2],
  });
};

const rankColor = (rank) =>
  rank === 1 ? '#D4AF37' :
    rank === 2 ? '#A8A8A8' :
      rank === 3 ? '#B87333' :
        '#6C4CF1';

const rankLabel = (rank) =>
  rank === 1 ? '🏆 Top Pick' :
    rank === 2 ? '🥈 #2 Pick' :
      rank === 3 ? '🥉 #3 Pick' :
        `#${rank} Pick`;

// ─── Human-readable labels for the raw feature names the model returns
// in Top_Positive_Drivers / Top_Negative_Drivers — a business user should
// never see "cnt_health" or "income_property_ratio" verbatim.
const FEATURE_LABELS = {
  cnt_food: 'Restaurants & Cafés Nearby',
  cnt_retail: 'Retail Shops Nearby',
  cnt_education: 'Schools & Colleges Nearby',
  cnt_health: 'Clinics & Pharmacies Nearby',
  cnt_leisure: 'Parks & Leisure Nearby',
  cnt_transport: 'Transport Links Nearby',
  cnt_finance: 'Banks & ATMs Nearby',
  cnt_hospitality: 'Hotels Nearby',
  cnt_civic: 'Civic Amenities Nearby',
  Population: 'Local Population',
  Income: 'Local Income Level',
  Nearest_Store_km: 'Distance to Nearest Own Store',
  stores_2km: 'Own Stores Within 2km',
  stores_5km: 'Own Stores Within 5km',
  Cannibalization_Score: 'Self-Cannibalization Risk',
  Nearby_Store_Avg_Sales: 'Nearby Stores\' Sales Performance',
  Competitor_2km: 'Competitor Shops Within 2km',
  Competitor_5km: 'Competitor Shops Within 5km',
  dist_to_nearest_road_m: 'Road Accessibility',
  is_commercial: 'Commercial Zoning',
  is_residential: 'Residential Zoning',
  is_industrial: 'Industrial Zoning',
  is_agricultural: 'Agricultural Zoning',
  is_natural: 'Natural/Undeveloped Land',
  income_property_ratio: 'Income-to-Property-Cost Ratio',
  avg_property_price_3km: 'Property Price (3km avg)',
  property_cost_index: 'Property Cost Index',
  population_commercial_score: 'Population × Commercial Fit',
  amenity_growth_score: 'Amenity Growth Trend',
  market_saturation_score: 'Market Saturation',
  franchise_density_score: 'Franchise Density',
};
const readableFeature = (raw) => FEATURE_LABELS[raw?.trim()] || raw;
const readableFeatureList = (csv) =>
  (csv || '').split(',').map((f) => readableFeature(f.trim())).filter(Boolean).join(', ');

const VERDICT_STYLE = {
  'Strong Candidate':          { bg: '#DCFCE7', text: '#166534', border: '#86EFAC', icon: '✅' },
  'Promising Candidate':       { bg: '#DBEAFE', text: '#1E40AF', border: '#93C5FD', icon: '👍' },
  'Viable — Review Cautions':  { bg: '#FEF3C7', text: '#92400E', border: '#FCD34D', icon: '⚠️' },
  'Not Recommended':           { bg: '#FEE2E2', text: '#991B1B', border: '#FCA5A5', icon: '⛔' },
};

// ─── Light-theme popup card (unchanged) ────────────────────────
function InfoCard({ d, avgSales, rank }) {
  const { currencySymbol, country } = useAppStore();

  const fmt = (n) => {
    if (n == null) return '—';
    return n.toLocaleString(country === 'India' ? 'en-IN' : 'en-US', { maximumFractionDigits: 0 });
  };

  const cur = (val) => {
    if (val == null) return '—';
    if (country === 'India') {
      if (val >= 10000000) return `${currencySymbol}${(val / 10000000).toFixed(2)} Cr`;
      if (val >= 100000) return `${currencySymbol}${(val / 100000).toFixed(1)} L`;
      return `${currencySymbol}${fmt(val)}`;
    }
    if (val >= 1000000) return `${currencySymbol}${(val / 1000000).toFixed(2)} M`;
    if (val >= 1000) return `${currencySymbol}${(val / 1000).toFixed(1)} K`;
    return `${currencySymbol}${fmt(val)}`;
  };

  const typeLabel = d.type === 'prediction' ? (rank ? rankLabel(rank) : 'Candidate')
    : d.type === 'store' ? 'Existing Store'
      : d.type === 'request' ? 'Franchise Request'
        : 'Business Unit';

  const headerColor =
    d.type === 'prediction' ? 'linear-gradient(135deg,#6C4CF1,#8B5CF6)' :
      d.type === 'store' && avgSales > 0
        ? (d.revenue >= avgSales
          ? 'linear-gradient(135deg,#16a34a,#22C55E)'
          : 'linear-gradient(135deg,#dc2626,#EF4444)')
        : 'linear-gradient(135deg,#6C4CF1,#06b6d4)';

  const rows = [
    [d.type === 'store' ? 'Total Revenue' : 'Est. Revenue', cur(d.revenue)],
    ['Population', d.population != null ? fmt(d.population) : null],
    ['Avg Income', d.income > 0 ? cur(d.income) : null],
    ['Property Price', d.avg_property_price_3km > 0 ? cur(d.avg_property_price_3km) : (d.avg_property_price_5km > 0 ? cur(d.avg_property_price_5km) : 'N/A')],
    ['Nearest Store', d.nearest_store ? `${d.nearest_store} (${d.nearest_store_km?.toFixed(1)} km)` : null],
    ['Business Unit', d.bu_name || null],
    ['BU Distance', (['store', 'prediction', 'request'].includes(d.type) && d.bu_name) ? `${d.bu_dist_km?.toFixed(1)} km` : null],
  ].filter(([, v]) => v != null);

  return (
    <div style={{ fontFamily: 'Inter,system-ui,sans-serif', width: 280, padding: 0 }}>
      <div style={{ background: headerColor, padding: '10px 14px', borderRadius: '12px 12px 0 0' }}>
        <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.8)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
          <span>{typeLabel}</span>
          {d.region && d.region !== 'Unassigned' && (
            <span style={{ fontSize: 9, padding: '2px 6px', borderRadius: 4, background: 'rgba(255,255,255,0.2)', border: '1px solid rgba(255,255,255,0.3)' }}>
              📍 {d.region}
            </span>
          )}
          {d.type === 'store' && avgSales > 0 && (
            <span style={{ fontSize: 9, padding: '2px 6px', borderRadius: 4, background: 'rgba(0,0,0,0.15)' }}>
              {d.revenue >= avgSales ? '▲ Above Avg' : '▼ Below Avg'}
            </span>
          )}
        </div>
        <div style={{ fontSize: 15, color: '#fff', fontWeight: 800, marginTop: 4, lineHeight: 1.3 }}>{d.name || 'Unknown'}</div>

        {d.type === 'prediction' && d.verdict ? (
          <div style={{ marginTop: 6 }}>
            <div style={{ fontSize: 16, letterSpacing: 1, color: '#FDE047', lineHeight: 1 }}>
              {'★'.repeat(d.star_rating || 3)}{'☆'.repeat(5 - (d.star_rating || 3))}
            </div>
            <div style={{ fontSize: 13, fontWeight: 800, color: '#fff', marginTop: 3 }}>
              {d.verdict}
            </div>
            {d.score > 0 && (
              <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.65)', marginTop: 2 }}>
                Score: {d.score?.toFixed(1)}/100 (archetype-similarity index)
              </div>
            )}
          </div>
        ) : d.score > 0 && (
          <div style={{ fontSize: 22, fontWeight: 900, color: '#fff', marginTop: 4 }}>
            {d.score?.toFixed(1)}<span style={{ fontSize: 11, fontWeight: 500 }}>/100</span>
          </div>
        )}
      </div>

      <div style={{ padding: '12px 14px', background: '#ffffff', borderRadius: '0 0 12px 12px' }}>
        {rows.map(([lbl, val]) => (
          <div key={lbl} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', padding: '4px 0', borderBottom: '1px solid #F3F4F6', fontSize: 12 }}>
            <span style={{ color: '#6B7280' }}>{lbl}</span>
            <span style={{ fontWeight: 700, color: '#111827', fontSize: 11, textAlign: 'right', maxWidth: 150 }}>{val}</span>
          </div>
        ))}

        {d.type === 'prediction' && d.verdict && (
          <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid #F3F4F6' }}>
            <div style={{ fontSize: 9, fontWeight: 700, color: '#9CA3AF', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 8 }}>
              Why This Rating
            </div>

            {d.caution_reasons && (
              <div style={{ fontSize: 10.5, color: '#92400E', background: '#FFFBEB', border: '1px solid #FDE68A',
                            borderRadius: 6, padding: '6px 8px', marginBottom: 8, lineHeight: 1.4 }}>
                ⚠️ {d.caution_reasons}
              </div>
            )}

            {d.top_positive_drivers && (
              <div style={{ fontSize: 10.5, marginBottom: 4 }}>
                <span style={{ color: '#16A34A', fontWeight: 700 }}>Helping this score: </span>
                <span style={{ color: '#374151' }}>{readableFeatureList(d.top_positive_drivers)}</span>
              </div>
            )}
            {d.top_negative_drivers && (
              <div style={{ fontSize: 10.5, marginBottom: 8 }}>
                <span style={{ color: '#DC2626', fontWeight: 700 }}>Hurting this score: </span>
                <span style={{ color: '#374151' }}>{readableFeatureList(d.top_negative_drivers)}</span>
              </div>
            )}

            {d.nearby_store_count > 0 && (
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, padding: '4px 0',
                            borderTop: '1px solid #F3F4F6' }}>
                <span style={{ color: '#6B7280' }}>
                  Nearby Stores' Avg Sales ({d.nearby_store_count} within 5km)
                  {d.nearby_underperformance_flag && ' ⚠️'}
                </span>
                <span style={{ fontWeight: 700, color: d.nearby_underperformance_flag ? '#DC2626' : '#111827' }}>
                  {cur(d.nearby_store_avg_sales)}
                </span>
              </div>
            )}

            {d.profitability_flag && d.profitability_flag !== 'Insufficient Data' && (
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, padding: '4px 0' }}>
                <span style={{ color: '#6B7280' }}>Cost vs. Revenue Signal</span>
                <span style={{
                  fontWeight: 700,
                  color: d.profitability_flag === 'Cost-Heavy' ? '#DC2626'
                       : d.profitability_flag === 'Cost-Efficient' ? '#16A34A' : '#111827',
                }}>
                  {d.profitability_flag}
                </span>
              </div>
            )}

            {d.comparable_stores && (
              <div style={{ marginTop: 6 }}>
                <div style={{ fontSize: 9.5, fontWeight: 700, color: '#9CA3AF', marginBottom: 3 }}>COMPARABLE EXISTING STORES</div>
                <div style={{ fontSize: 10, color: '#4B5563', lineHeight: 1.5 }}>
                  {d.comparable_stores.split(';').slice(0, 3).map((s) => s.trim()).join(' · ')}
                </div>
              </div>
            )}
          </div>
        )}

        {d.total_amenities != null && (
          <div style={{ marginTop: 10, paddingTop: 8, borderTop: '1px solid #F3F4F6' }}>
            <div style={{ fontSize: 9, fontWeight: 700, color: '#9CA3AF', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 8 }}>Key Amenities (10km)</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 16px' }}>
              {[
                ['🍽️ Food', d.cnt_food], ['🛒 Retail', d.cnt_retail],
                ['🏫 Education', d.cnt_education], ['🏥 Health', d.cnt_health],
                ['🏨 Hospitality', d.cnt_hospitality], ['🏛️ Civic', d.cnt_civic],
                ['⚔️ Competitors (2km)', d.competitor_2km], ['⚔️ Competitors (5km)', d.competitor_5km],
              ]
                .filter(([, v]) => v != null)
                .map(([lbl, cnt]) => (
                  <div key={lbl} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#6B7280', padding: '2px 0' }}>
                    <span>{lbl}</span>
                    <span style={{ fontWeight: 700, color: '#111827' }}>{cnt ?? 0}</span>
                  </div>
                ))}
            </div>
          </div>
        )}

        <div style={{ marginTop: 12, textAlign: 'center' }}>
          <a
            href={`https://www.google.com/maps/search/?api=1&query=${d.lat},${d.lng}`}
            target="_blank" rel="noopener noreferrer"
            style={{ color: '#6C4CF1', fontSize: 12, textDecoration: 'none', fontWeight: 600 }}
          >
            🗺️ Open in Google Maps
          </a>
        </div>
      </div>
    </div>
  );
}

// v3.5.4: Amenity category styles (colored border + emoji)
const getAmenityStyle = (type) => {
  if (['hospital', 'clinic', 'pharmacy'].includes(type))
    return { color: '#DC2626', emoji: '🏥', label: 'Healthcare' };
  if (['school', 'college', 'university'].includes(type))
    return { color: '#2563EB', emoji: type === 'school' ? '🏫' : '🎓', label: 'Education' };
  if (['restaurant', 'fast_food', 'cafe'].includes(type))
    return { color: '#EA580C', emoji: type === 'cafe' ? '☕' : '🍽️', label: 'Food' };
  if (['supermarket', 'mall', 'department_store'].includes(type))
    return { color: '#7C3AED', emoji: type === 'supermarket' ? '🛒' : '🏬', label: 'Retail' };
  return { color: '#6B7280', emoji: '📍', label: 'Other' };
};

const amenityIcon = (type) => {
  const { color, emoji } = getAmenityStyle(type);
  return L.divIcon({
    html: `<div style="
      width:18px;height:18px;border-radius:50%;
      background:white;border:1.5px solid ${color};
      display:flex;align-items:center;justify-content:center;
      font-size:10px;line-height:1;
      box-shadow:0 1px 3px rgba(0,0,0,0.25);
    ">${emoji}</div>`,
    className: 'fiq-amenity-icon',
    iconSize: [20, 20],
    iconAnchor: [10, 10],
    popupAnchor: [0, -10],
  });
};

// ─── Main Map ─────────────────────────────────────────────────
export default function MapContainer_() {
  const {
    results, stateConfig, mapLayers, storeFilter, selectedRegion,
    currencySymbol, country, mapStoreFilter,
  } = useAppStore();
  const center = stateConfig?.center || [20, 78];
  const zoom = stateConfig?.zoom || 6;

  const { stores, requests, predictions, business_units, amenities, real_estate, competitors, avgSales } = useMemo(() => {
    const allStores = results?.stores || [];
    const allPreds = results?.top_picks || [];

    const totalSales = allStores.reduce((sum, s) => sum + (s.revenue || 0), 0);
    const avg = allStores.length > 0 ? totalSales / allStores.length : 0;

    let filteredStores = allStores;
    let filteredRequests = results?.requests || [];
    let filteredPreds = allPreds;

    if (storeFilter === 'above') filteredStores = filteredStores.filter(s => s.revenue >= avg);
    if (storeFilter === 'below') filteredStores = filteredStores.filter(s => s.revenue < avg);

    if (selectedRegion) {
      filteredStores = filteredStores.filter(s => s.region === selectedRegion);
      filteredRequests = filteredRequests.filter(r => r.region === selectedRegion);
      filteredPreds = filteredPreds.filter(p => p.region === selectedRegion);
    }

    return {
      stores: filteredStores,
      requests: filteredRequests,
      predictions: filteredPreds,
      business_units: results?.business_units || [],
      amenities: results?.amenities || [],
      real_estate: results?.real_estate || [],
      competitors: results?.competitors || [],
      avgSales: avg,
    };
  }, [results, storeFilter, selectedRegion, mapStoreFilter]);

  if (!results) return (
    <div className="w-full h-full flex flex-col items-center justify-center bg-surface-2 gap-3">
      <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center">
        <span style={{ fontSize: 28 }}>🗺️</span>
      </div>
      <p className="text-sm font-semibold text-ink">No map data yet</p>
      <p className="text-xs text-ink-muted">Run a prediction to visualise opportunities on the map.</p>
    </div>
  );

  return (
    <MapContainer
      center={center}
      zoom={zoom}
      style={{ width: '100%', height: '100%' }}
      zoomControl={false}
    >
      <ZoomControl position="bottomright" />
      <FlyToLocation />
      {/* Light CartoDB tile — v8.3: CARTO now requires an API key on all
          raster tile requests (a platform-wide change, not specific to
          this app — free key at https://carto.com/basemaps/apikey).
          Without VITE_CARTO_API_KEY set, tiles still load but show a
          "API KEY REQUIRED" watermark. */}
      <TileLayer
        url={`https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png${import.meta.env.VITE_CARTO_API_KEY ? `?key=${import.meta.env.VITE_CARTO_API_KEY}` : ''}`}
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>, &copy; <a href="https://carto.com/attributions">CARTO</a>'
        maxZoom={19}
      />

      {/* ── Amenities (clustered) ──────────────── */}
      {(mapLayers.amenities ?? true) && amenities.length > 0 && (
        <MarkerClusterGroup chunkedLoading maxClusterRadius={50}>
          {amenities.map((d, i) => (
            <Marker key={`am-${i}`} position={[d.lat, d.lng]} icon={amenityIcon(d.type)}>
              <Tooltip sticky direction="top">
                <span style={{ fontFamily: 'Inter', fontSize: 11, fontWeight: 600, color: '#111827' }}>
                  {d.name || d.type.replace('_', ' ')}
                </span>
              </Tooltip>
            </Marker>
          ))}
        </MarkerClusterGroup>
      )}

      {/* ── Existing Stores (3-state by performance) ──────────────── */}
      {mapLayers.stores && stores.length > 0 && stores.map((d, i) => {
        const ratio = avgSales > 0 ? d.revenue / avgSales : 1;
        const classification =
          ratio >= 1.10 ? 'above' :
            ratio <= 0.90 ? 'below' : 'on_target';
        const color =
          classification === 'above' ? '#22C55E' :
            classification === 'below' ? '#EF4444' : '#F59E0B';
        const label =
          classification === 'above' ? 'Above network avg' :
            classification === 'below' ? 'Below network avg' : 'On target';
        return (
          <Marker key={`store-${i}`} position={[d.lat, d.lng]} icon={storeMarkerIcon(classification)}>
            <Popup maxWidth={300}><InfoCard d={d} avgSales={avgSales} /></Popup>
            <Tooltip sticky direction="top">
              <div style={{ fontFamily: 'Inter' }}>
                <div style={{ fontWeight: 700, fontSize: 12, color }}>{d.name}</div>
                <div style={{ fontSize: 10, color: '#6B7280', marginTop: 2 }}>{label}</div>
              </div>
            </Tooltip>
          </Marker>
        );
      })}

      {/* ── Franchise Requests (clustered) ────── */}
      {mapLayers.requests && requests.length > 0 && (
        <MarkerClusterGroup chunkedLoading>
          {requests.map((d, i) => (
            <Marker key={`req-${i}`} position={[d.lat, d.lng]} icon={emojiIcon('📩', 22)}>
              <Popup maxWidth={300}><InfoCard d={d} avgSales={avgSales} /></Popup>
              <Tooltip sticky direction="top">
                <span style={{ fontFamily: 'Inter', fontSize: 11, color: '#111827' }}>Request: {d.name}</span>
              </Tooltip>
            </Marker>
          ))}
        </MarkerClusterGroup>
      )}

      {/* ── Predictions (rank-based numbered markers) ─────── */}
      {mapLayers.predictions && predictions.map((d, i) => {
        const rank = i + 1;
        const color = rankColor(rank);
        return (
          <Marker
            key={`pred-${i}`}
            position={[d.lat, d.lng]}
            icon={rankMarkerIcon(rank)}
            zIndexOffset={rank <= 3 ? 1000 : 500}
          >
            <Popup maxWidth={300}><InfoCard d={d} avgSales={avgSales} rank={rank} /></Popup>
            <Tooltip sticky direction="top">
              <div style={{ fontFamily: 'Inter', minWidth: 130 }}>
                <div style={{ fontWeight: 800, fontSize: 13, color }}>
                  {rankLabel(rank)}
                </div>
                <div style={{ fontSize: 11, color: '#6B7280', marginTop: 2 }}>
                  Score {d.score?.toFixed(1)}/100 · {d.name}
                </div>
              </div>
            </Tooltip>
          </Marker>
        );
      })}

      {/* ── Business Units ────────────────────── */}
      {mapLayers.businessUnits && business_units.length > 0 && business_units.map((d, i) => (
        <Marker key={`bu-${i}`} position={[d.lat, d.lng]} icon={emojiIcon('🏭', 28)}>
          <Popup maxWidth={260}><InfoCard d={d} avgSales={avgSales} /></Popup>
          <Tooltip sticky direction="top">
            <span style={{ fontFamily: 'Inter', fontSize: 12, fontWeight: 600, color: '#111827' }}>BU: {d.name}</span>
          </Tooltip>
        </Marker>
      ))}

      {/* ── Competitors (clustered, click for name + Google Maps link) ── */}
      {mapLayers.competitors && competitors.length > 0 && (
        <MarkerClusterGroup chunkedLoading maxClusterRadius={50}>
          {competitors.map((d, i) => (
            <Marker key={`comp-${i}`} position={[d.lat, d.lng]} icon={emojiIcon('⚔️', 22)}>
              <Popup maxWidth={280}>
                <div style={{ fontFamily: 'Inter', minWidth: 200 }}>
                  <div style={{ fontWeight: 800, fontSize: 13, color: '#111827' }}>{d.name}</div>
                  {(d.brand || d.category) && (
                    <div style={{ fontSize: 11, color: '#6B7280', marginTop: 2 }}>
                      {[d.brand, d.category].filter(Boolean).join(' · ')}
                    </div>
                  )}
                  {d.rating != null && (
                    <div style={{ fontSize: 11, color: '#6B7280', marginTop: 2 }}>
                      ★ {d.rating}{d.review_count != null ? ` (${d.review_count} reviews)` : ''}
                    </div>
                  )}
                  {(d.address || d.area || d.city) && (
                    <div style={{ fontSize: 11, color: '#6B7280', marginTop: 2 }}>
                      {[d.address, d.area, d.city].filter(Boolean).join(', ')}
                    </div>
                  )}
                  {d.google_maps_url && (
                    <a
                      href={d.google_maps_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        display: 'inline-block', marginTop: 8, fontSize: 11, fontWeight: 700,
                        color: '#fff', background: '#DC2626', padding: '5px 10px', borderRadius: 6,
                        textDecoration: 'none',
                      }}
                    >
                      📍 Open in Google Maps
                    </a>
                  )}
                </div>
              </Popup>
              <Tooltip sticky direction="top">
                <span style={{ fontFamily: 'Inter', fontSize: 11, fontWeight: 600, color: '#111827' }}>{d.name}</span>
              </Tooltip>
            </Marker>
          ))}
        </MarkerClusterGroup>
      )}

      {mapLayers.realEstate && real_estate.length > 0 && real_estate.map((d, i) => {
        const costIndex = d.property_cost_index || 50;
        const growthScore = d.property_growth_score || 50;
        const radius = 5 + (costIndex / 100) * 15;
        const color = growthScore > 60 ? '#22C55E' : growthScore < 40 ? '#EF4444' : '#F59E0B';

        return (
          <CircleMarker key={`re-${i}`} center={[d.lat, d.lng]} radius={radius}
            pathOptions={{ color, fillColor: color, fillOpacity: 0.5, weight: 1, opacity: 0.8 }}
          >
            <Tooltip sticky direction="top">
              <div style={{ fontFamily: 'Inter', minWidth: 120 }}>
                <div style={{ fontWeight: 800, fontSize: 13, color }}>Real Estate Data</div>
                <div style={{ fontSize: 11, color: '#6B7280', marginTop: 2 }}>
                  {d.price ? `Price: ${currencySymbol || ''}${Math.round(d.price).toLocaleString()}` : d.rent ? `Rent: ${currencySymbol || ''}${Math.round(d.rent).toLocaleString()}` : 'Price/Rent: N/A'}
                </div>
                <div style={{ fontSize: 11, color: '#6B7280' }}>Cost Index: {costIndex.toFixed(1)}</div>
                <div style={{ fontSize: 11, color: '#6B7280' }}>Growth Score: {growthScore.toFixed(1)}</div>
              </div>
            </Tooltip>
          </CircleMarker>
        );
      })}
    </MapContainer>
  );
}
