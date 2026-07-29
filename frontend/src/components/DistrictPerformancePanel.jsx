// import React, { useEffect, useState } from 'react';
// import { motion, AnimatePresence } from 'framer-motion';
// import {
//   X, MapPin, ChevronDown, ChevronUp,
//   TrendingUp, TrendingDown, Minus, Store, Loader2,
//   Crosshair, Eye,
// } from 'lucide-react';
// import useAppStore from '../store/useAppStore';
// import { getDistrictPerformance } from '../services/api';

// /**
//  * DistrictPerformancePanel â€” v3.5
//  * â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
//  * Executive-friendly view: stores grouped by admin district with
//  * per-district performance AND per-store performance shown in BOTH lenses:
//  *   - vs Network avg (whole-Mio baseline)
//  *   - vs District avg (peer-level baseline)
//  *
//  * Interactions:
//  *   - Click district row â†’ expands store list AND filters map to that
//  *     district's stores + flies map to district centroid
//  *   - Click any store row â†’ filters map to that one store + flies to it
//  *   - Click "Clear filter" â†’ restores full map view
//  */

// function formatCurrency(n, sym = 'â‚¹') {
//   if (!Number.isFinite(n)) return `${sym}0`;
//   if (Math.abs(n) >= 1e7) return `${sym}${(n / 1e7).toFixed(2)} Cr`;
//   if (Math.abs(n) >= 1e5) return `${sym}${(n / 1e5).toFixed(2)} L`;
//   return `${sym}${n.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
// }

// function classificationStyles(c) {
//   if (c === 'above') return { bg: 'bg-green-50', border: 'border-green-300', text: 'text-green-700', accent: '#22C55E', icon: TrendingUp };
//   if (c === 'below') return { bg: 'bg-red-50',   border: 'border-red-300',   text: 'text-red-700',   accent: '#EF4444', icon: TrendingDown };
//   return                  { bg: 'bg-amber-50', border: 'border-amber-300', text: 'text-amber-700', accent: '#F59E0B', icon: Minus };
// }

// function pctColor(pct, thresholds) {
//   if (pct >= thresholds.above_pct) return '#22C55E';
//   if (pct <= thresholds.below_pct) return '#EF4444';
//   return '#F59E0B';
// }


// export default function DistrictPerformancePanel() {
//   const {
//     sessionId, results, viewMode, setViewMode,
//     currencySymbol,
//     mapStoreFilter, setMapStoreFilter, clearMapStoreFilter,
//     setFlyToCoords,
//   } = useAppStore();

//   const [data, setData] = useState(null);
//   const [loading, setLoading] = useState(false);
//   const [expandedDistricts, setExpandedDistricts] = useState(new Set());
//   const [error, setError] = useState(null);

//   useEffect(() => {
//     if (viewMode !== 'district' || !sessionId || !results) return;
//     let cancelled = false;
//     setLoading(true);
//     setError(null);

//     getDistrictPerformance(sessionId)
//       .then((d) => { if (!cancelled) setData(d); })
//       .catch((e) => { if (!cancelled) setError(e.message || 'Failed to load districts'); })
//       .finally(() => { if (!cancelled) setLoading(false); });

//     return () => { cancelled = true; };
//   }, [viewMode, sessionId, results]);

//   if (viewMode !== 'district') return null;

//   // â”€â”€ Interactions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
//   const handleDistrictClick = (d) => {
//     // Toggle expansion
//     const next = new Set(expandedDistricts);
//     if (next.has(d.district)) next.delete(d.district);
//     else next.add(d.district);
//     setExpandedDistricts(next);

//     // Filter map + fly to district centroid
//     const storeNames = d.stores.map(s => s.name).filter(Boolean);
//     setMapStoreFilter({ kind: 'district', label: d.district, names: storeNames });

//     const lats = d.stores.map(s => s.lat).filter(v => v && v !== 0);
//     const lngs = d.stores.map(s => s.lng).filter(v => v && v !== 0);
//     if (lats.length > 0) {
//       const cLat = lats.reduce((a, b) => a + b, 0) / lats.length;
//       const cLng = lngs.reduce((a, b) => a + b, 0) / lngs.length;
//       setFlyToCoords({ lat: cLat, lng: cLng, zoom: 10 });
//     }
//   };

//   const handleStoreClick = (s, districtName) => {
//     if (!s.name) return;
//     setMapStoreFilter({ kind: 'store', label: s.name, names: [s.name], parentDistrict: districtName });
//     if (s.lat && s.lng) {
//       setFlyToCoords({ lat: s.lat, lng: s.lng, zoom: 15 });
//     }
//   };

//   const currency = currencySymbol || 'â‚¹';

//   return (
//     <AnimatePresence>
//       <motion.div
//         initial={{ x: 360, opacity: 0 }}
//         animate={{ x: 0, opacity: 1 }}
//         exit={{ x: 360, opacity: 0 }}
//         transition={{ type: 'spring', damping: 25, stiffness: 220 }}
//         className="fixed top-20 right-5 z-[2000] w-[28rem] max-w-[95vw] max-h-[82vh]
//                    bg-white rounded-2xl shadow-card-lg border border-border
//                    flex flex-col overflow-hidden"
//       >
//         {/* Header */}
//         <div className="flex items-center gap-3 p-4 border-b border-border shrink-0
//                         bg-gradient-to-br from-primary/5 to-transparent">
//           <div className="w-10 h-10 rounded-xl bg-primary/15 flex items-center justify-center">
//             <MapPin size={18} className="text-primary" />
//           </div>
//           <div className="flex-1 min-w-0">
//             <div className="text-xs font-semibold text-ink-subtle uppercase tracking-wider">
//               District View
//             </div>
//             <div className="text-base font-bold text-ink truncate">
//               {data ? `${data.total_districts} districts · ${data.total_stores} stores` : 'Performance by district'}
//             </div>
//           </div>
//           <button
//             onClick={() => { setViewMode('hex'); clearMapStoreFilter(); }}
//             className="p-1 rounded hover:bg-app-bg transition-colors"
//             aria-label="Close"
//           >
//             <X size={16} className="text-ink-subtle" />
//           </button>
//         </div>

//         {/* Active filter badge */}
//         {mapStoreFilter && (
//           <div className="px-3 py-2 bg-primary/10 border-b border-primary/20 flex items-center gap-2 shrink-0">
//             <Crosshair size={12} className="text-primary shrink-0" />
//             <div className="flex-1 text-xs text-ink truncate">
//               Map filtered to:{' '}
//               <span className="font-semibold">{mapStoreFilter.label}</span>
//               {mapStoreFilter.kind === 'district' && (
//                 <span className="text-ink-muted ml-1">({mapStoreFilter.names.length} stores)</span>
//               )}
//             </div>
//             <button
//               onClick={clearMapStoreFilter}
//               className="text-[10px] text-primary font-bold hover:underline shrink-0"
//             >
//               CLEAR
//             </button>
//           </div>
//         )}

//         {/* Body */}
//         <div className="flex-1 overflow-y-auto p-3">
//           {loading && (
//             <div className="flex items-center justify-center gap-2 py-8 text-ink-muted text-sm">
//               <Loader2 size={14} className="animate-spin" />
//               Aggregating districtsâ€¦
//             </div>
//           )}

//           {error && (
//             <div className="rounded-lg border border-danger/30 bg-danger/5 p-3 text-xs text-danger">
//               {error}
//             </div>
//           )}

//           {data && !loading && (
//             <>
//               {/* Network avg banner */}
//               <div className="rounded-lg border border-border bg-app-bg/40 p-3 mb-3 text-center">
//                 <div className="text-[10px] font-bold text-ink-subtle uppercase tracking-wider">
//                   Network average
//                 </div>
//                 <div className="text-lg font-bold text-ink tabular-nums">
//                   {formatCurrency(data.network_avg, currency)}
//                 </div>
//                 <div className="text-[10px] text-ink-muted">
//                   across {data.total_stores} stores
//                 </div>
//               </div>

//               {/* Lens explainer */}
//               <div className="rounded-lg border border-primary/20 bg-primary/5 p-2.5 mb-3 text-[10px] text-ink-muted leading-relaxed">
//                 <span className="font-bold text-primary">Two lenses per store:</span>{' '}
//                 <span className="font-semibold">vs Net</span> = vs whole-Mio avg.{' '}
//                 <span className="font-semibold">vs Dist</span> = vs same-district peers.
//               </div>

//               {/* District cards */}
//               <div className="space-y-1.5">
//                 {data.districts.map((d, i) => {
//                   const styles = classificationStyles(d.classification);
//                   const ClsIcon = styles.icon;
//                   const isExpanded = expandedDistricts.has(d.district);
//                   const isFilteredHere = mapStoreFilter?.kind === 'district' && mapStoreFilter.label === d.district;
//                   const rank = i + 1;
//                   const deltaPct = d.pct_of_network_avg - 100;
//                   const deltaSign = deltaPct >= 0 ? '+' : 'âˆ’';

//                   return (
//                     <div
//                       key={d.district}
//                       className={`rounded-lg border ${styles.border} overflow-hidden
//                                   ${isFilteredHere ? 'ring-2 ring-primary/40' : ''}`}
//                     >
//                       <button
//                         onClick={() => handleDistrictClick(d)}
//                         className={`w-full ${styles.bg} px-3 py-2.5 flex items-center gap-3
//                                     hover:brightness-95 transition-all text-left`}
//                       >
//                         <div className="text-[10px] font-mono text-ink-subtle w-6 shrink-0">
//                           #{rank}
//                         </div>
//                         <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: styles.accent }} />
//                         <div className="flex-1 min-w-0">
//                           <div className="font-semibold text-ink text-sm truncate">{d.district}</div>
//                           <div className="text-[11px] text-ink-muted flex items-center gap-1.5">
//                             <span>{d.store_count} stores</span>
//                             <span className="text-ink-subtle/50">·</span>
//                             <span className="font-mono tabular-nums">{formatCurrency(d.avg_revenue, currency)} avg</span>
//                           </div>
//                         </div>
//                         <div className="text-right shrink-0 flex items-center gap-2">
//                           <div
//                             className="text-xs font-bold font-mono tabular-nums px-2 py-0.5 rounded"
//                             style={{ color: styles.accent, backgroundColor: styles.accent + '15' }}
//                           >
//                             {deltaSign}{Math.abs(deltaPct).toFixed(1)}%
//                           </div>
//                           {isExpanded
//                             ? <ChevronUp size={14} className="text-ink-subtle" />
//                             : <ChevronDown size={14} className="text-ink-subtle" />}
//                         </div>
//                       </button>

//                       {isExpanded && (
//                         <div className="border-t border-border bg-white p-2 space-y-1">
//                           <div className="text-[10px] font-bold text-ink-subtle uppercase tracking-wider px-1 py-1
//                                           flex items-center justify-between">
//                             <span>Stores in {d.district}</span>
//                             <span className="font-mono text-[9px] text-ink-subtle">vs Net · vs Dist</span>
//                           </div>
//                           {d.stores.slice(0, 40).map((s, idx) => {
//                             const isFilteredStore = mapStoreFilter?.kind === 'store' && mapStoreFilter.label === s.name;
//                             return (
//                               <button
//                                 key={`${d.district}-${idx}`}
//                                 onClick={(e) => { e.stopPropagation(); handleStoreClick(s, d.district); }}
//                                 className={`w-full flex items-center gap-2 px-2 py-1.5 rounded text-xs
//                                             hover:bg-primary/5 transition-colors text-left
//                                             ${isFilteredStore ? 'bg-primary/10 ring-1 ring-primary/30' : ''}`}
//                                 title="Click to filter map to this store"
//                               >
//                                 <Store size={11} className="text-ink-subtle shrink-0" />
//                                 <div className="flex-1 min-w-0 truncate text-ink">{s.name || '(unnamed)'}</div>
//                                 <div className="font-mono tabular-nums text-ink-subtle text-[10px] w-20 text-right">
//                                   {formatCurrency(s.revenue, currency)}
//                                 </div>
//                                 <div
//                                   className="font-mono text-[10px] tabular-nums w-10 text-right font-semibold"
//                                   style={{ color: pctColor(s.pct_of_network_avg, data.thresholds) }}
//                                   title="vs Network avg"
//                                 >
//                                   {s.pct_of_network_avg >= 100 ? "+" : "âˆ’"}{Math.abs(s.pct_of_network_avg - 100).toFixed(0)}%
//                                 </div>
//                                 <div
//                                   className="font-mono text-[10px] tabular-nums w-10 text-right"
//                                   style={{ color: pctColor(s.pct_of_district_avg, data.thresholds) }}
//                                   title="vs District avg"
//                                 >
//                                   {s.pct_of_district_avg >= 100 ? "+" : "âˆ’"}{Math.abs(s.pct_of_district_avg - 100).toFixed(0)}%
//                                 </div>
//                               </button>
//                             );
//                           })}
//                           {d.stores.length > 40 && (
//                             <div className="text-[10px] text-ink-subtle italic text-center py-1">
//                               â€¦and {d.stores.length - 40} more stores
//                             </div>
//                           )}
//                           {/* District stats footer */}
//                           <div className="border-t border-border mt-1 pt-2 px-1 grid grid-cols-3 gap-2 text-[10px]">
//                             <div>
//                               <div className="text-ink-subtle">Min</div>
//                               <div className="font-mono font-semibold text-ink">{formatCurrency(d.min_revenue, currency)}</div>
//                             </div>
//                             <div>
//                               <div className="text-ink-subtle">Avg</div>
//                               <div className="font-mono font-semibold text-ink">{formatCurrency(d.avg_revenue, currency)}</div>
//                             </div>
//                             <div>
//                               <div className="text-ink-subtle">Max</div>
//                               <div className="font-mono font-semibold text-ink">{formatCurrency(d.max_revenue, currency)}</div>
//                             </div>
//                           </div>
//                         </div>
//                       )}
//                     </div>
//                   );
//                 })}
//               </div>

//               {/* Legend */}
//               <div className="mt-3 rounded-lg border border-border bg-app-bg/30 p-2.5">
//                 <div className="text-[10px] font-bold text-ink-subtle uppercase tracking-wider mb-1.5">
//                   Color legend
//                 </div>
//                 <div className="flex flex-wrap gap-3 text-[11px] text-ink-muted">
//                   <span className="flex items-center gap-1.5">
//                     <span className="w-2 h-2 rounded-full bg-green-500" />
//                     â‰¥ +{(data.thresholds.above_pct - 100).toFixed(0)}%
//                   </span>
//                   <span className="flex items-center gap-1.5">
//                     <span className="w-2 h-2 rounded-full bg-amber-500" />
//                     ±{(data.thresholds.above_pct - 100).toFixed(0)}%
//                   </span>
//                   <span className="flex items-center gap-1.5">
//                     <span className="w-2 h-2 rounded-full bg-red-500" />
//                     â‰¤ âˆ’{(100 - data.thresholds.below_pct).toFixed(0)}%
//                   </span>
//                 </div>
//               </div>
//             </>
//           )}
//         </div>
//       </motion.div>
//     </AnimatePresence>
//   );
// }

import React, { useEffect, useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X, MapPin, ChevronDown, ChevronUp,
  TrendingUp, TrendingDown, Minus, Store, Loader2,
  Crosshair, Check, CheckSquare,
} from 'lucide-react';
import useAppStore from '../store/useAppStore';
import { getDistrictPerformance } from '../services/api';
/**
* DistrictPerformancePanel — v3.6
* ─────────────────────────────
* Executive-friendly view: stores grouped by admin district with
* per-district performance AND per-store performance shown in BOTH lenses.
*
* Interactions:
*   - Click district row → expands + filters map to district + flies to centroid
*   - Click store row → flies map to that store
*   - Tap store checkbox → toggle in multi-selection (map shows all selected,
*     auto-fits zoom to selection bounds)
*   - Clear filter → restores full map view
*/
function formatCurrency(n, sym = '₹') {
  if (!Number.isFinite(n)) return `${sym}0`;
  if (Math.abs(n) >= 1e7) return `${sym}${(n / 1e7).toFixed(2)} Cr`;
  if (Math.abs(n) >= 1e5) return `${sym}${(n / 1e5).toFixed(2)} L`;
  return `${sym}${n.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
}
function classificationStyles(c) {
  if (c === 'above') return { bg: 'bg-green-50', border: 'border-green-300', text: 'text-green-700', accent: '#22C55E', icon: TrendingUp };
  if (c === 'below') return { bg: 'bg-red-50', border: 'border-red-300', text: 'text-red-700', accent: '#EF4444', icon: TrendingDown };
  return { bg: 'bg-amber-50', border: 'border-amber-300', text: 'text-amber-700', accent: '#F59E0B', icon: Minus };
}
function pctColor(pct, thresholds) {
  if (pct >= thresholds.above_pct) return '#22C55E';
  if (pct <= thresholds.below_pct) return '#EF4444';
  return '#F59E0B';
}
// Pick a reasonable zoom for a bounding box of lat/lng spreads
function zoomForBounds(latRange, lngRange) {
  const maxRange = Math.max(latRange, lngRange);
  if (maxRange > 2) return 7;
  if (maxRange > 1) return 8;
  if (maxRange > 0.5) return 9;
  if (maxRange > 0.2) return 10;
  if (maxRange > 0.1) return 11;
  if (maxRange > 0.05) return 12;
  return 13;
}
export default function DistrictPerformancePanel() {
  const {
    sessionId, results, viewMode, setViewMode,
    currencySymbol,
    mapStoreFilter, setMapStoreFilter, clearMapStoreFilter,
    setFlyToCoords,
  } = useAppStore();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [expandedDistricts, setExpandedDistricts] = useState(new Set());
  const [error, setError] = useState(null);
  useEffect(() => {
    if (viewMode !== 'district' || !sessionId || !results) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    getDistrictPerformance(sessionId)
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setError(e.message || 'Failed to load districts'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [viewMode, sessionId, results]);
  // Flat lookup of all stores (across all districts) — used for multi-select bounds calc
  const allStoresIndex = useMemo(() => {
    const map = new Map();
    (data?.districts || []).forEach(d => {
      d.stores.forEach(s => { if (s.name) map.set(s.name, s); });
    });
    return map;
  }, [data]);
  if (viewMode !== 'district') return null;
  // Currently selected names (from multi or single store kind)
  const selectedNames = (
    mapStoreFilter?.kind === 'multi' || mapStoreFilter?.kind === 'store'
  ) ? new Set(mapStoreFilter.names || []) : new Set();
  const multiCount = mapStoreFilter?.kind === 'multi' ? mapStoreFilter.names.length : 0;
  // ── Interactions ──────────────────────────────────────────
  const handleDistrictClick = (d) => {
    // Toggle expansion
    const next = new Set(expandedDistricts);
    if (next.has(d.district)) next.delete(d.district);
    else next.add(d.district);
    setExpandedDistricts(next);
    // Filter map + fly to district centroid
    const storeNames = d.stores.map(s => s.name).filter(Boolean);
    setMapStoreFilter({ kind: 'district', label: d.district, names: storeNames });
    const lats = d.stores.map(s => s.lat).filter(v => v && v !== 0);
    const lngs = d.stores.map(s => s.lng).filter(v => v && v !== 0);
    if (lats.length > 0) {
      const cLat = lats.reduce((a, b) => a + b, 0) / lats.length;
      const cLng = lngs.reduce((a, b) => a + b, 0) / lngs.length;
      setFlyToCoords({ lat: cLat, lng: cLng, zoom: 10 });
    }
  };
  // Click on store name body → fly to that store (preserves multi-selection if active)
  const handleStoreClick = (s, districtName) => {
    if (!s.name) return;
    // If we're in multi-select mode and the store is part of selection, just fly
    if (mapStoreFilter?.kind === 'multi' && selectedNames.has(s.name)) {
      if (s.lat && s.lng) setFlyToCoords({ lat: s.lat, lng: s.lng, zoom: 15 });
      return;
    }
    // Otherwise: switch to single-store filter
    setMapStoreFilter({ kind: 'store', label: s.name, names: [s.name], parentDistrict: districtName });
    if (s.lat && s.lng) {
      setFlyToCoords({ lat: s.lat, lng: s.lng, zoom: 15 });
    }
  };
  // Tap checkbox → toggle store in multi-selection
  const handleStoreCheckboxToggle = (s, districtName, e) => {
    e.stopPropagation();
    if (!s.name) return;
    let currentNames = [];
    if (mapStoreFilter?.kind === 'multi') {
      currentNames = [...mapStoreFilter.names];
    } else if (mapStoreFilter?.kind === 'store') {
      // Starting multi-select: include the previously-single-selected store
      currentNames = [...mapStoreFilter.names];
    }
    let newNames;
    if (currentNames.includes(s.name)) {
      newNames = currentNames.filter(n => n !== s.name);
    } else {
      newNames = [...currentNames, s.name];
    }
    if (newNames.length === 0) {
      clearMapStoreFilter();
      return;
    }
    if (newNames.length === 1) {
      // Just one left → treat as single-store
      const only = allStoresIndex.get(newNames[0]);
      setMapStoreFilter({ kind: 'store', label: newNames[0], names: newNames });
      if (only?.lat && only?.lng) {
        setFlyToCoords({ lat: only.lat, lng: only.lng, zoom: 15 });
      }
      return;
    }
    // 2+ stores → multi-select; fit bounds to all selected
    setMapStoreFilter({
      kind: 'multi',
      label: `${newNames.length} selected stores`,
      names: newNames,
    });
    const selectedStores = newNames
      .map(n => allStoresIndex.get(n))
      .filter(Boolean);
    const lats = selectedStores.map(st => st.lat).filter(v => v && v !== 0);
    const lngs = selectedStores.map(st => st.lng).filter(v => v && v !== 0);
    if (lats.length > 0) {
      const cLat = lats.reduce((a, b) => a + b, 0) / lats.length;
      const cLng = lngs.reduce((a, b) => a + b, 0) / lngs.length;
      const latRange = Math.max(...lats) - Math.min(...lats);
      const lngRange = Math.max(...lngs) - Math.min(...lngs);
      setFlyToCoords({ lat: cLat, lng: cLng, zoom: zoomForBounds(latRange, lngRange) });
    }
  };
  const currency = currencySymbol || '₹';
  return (
    <AnimatePresence>
      <motion.div
        initial={{ x: 360, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        exit={{ x: 360, opacity: 0 }}
        transition={{ type: 'spring', damping: 25, stiffness: 220 }}
        className="fixed top-20 right-5 z-[2000] w-[28rem] max-w-[95vw] max-h-[82vh]
                  bg-white rounded-2xl shadow-card-lg border border-border
                  flex flex-col overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-center gap-3 p-4 border-b border-border shrink-0
                       bg-gradient-to-br from-primary/5 to-transparent">
          <div className="w-10 h-10 rounded-xl bg-primary/15 flex items-center justify-center">
            <MapPin size={18} className="text-primary" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-xs font-semibold text-ink-subtle uppercase tracking-wider">
              District View
            </div>
            <div className="text-base font-bold text-ink truncate">
              {data ? `${data.total_districts} districts · ${data.total_stores} stores` : 'Performance by district'}
            </div>
          </div>
          <button
            onClick={() => { setViewMode('hex'); clearMapStoreFilter(); }}
            className="p-1 rounded hover:bg-app-bg transition-colors"
            aria-label="Close"
          >
            <X size={16} className="text-ink-subtle" />
          </button>
        </div>
        {/* Active filter badge */}
        {mapStoreFilter && (
          <div className="px-3 py-2 bg-primary/10 border-b border-primary/20 flex items-center gap-2 shrink-0">
            {mapStoreFilter.kind === 'multi'
              ? <CheckSquare size={12} className="text-primary shrink-0" />
              : <Crosshair size={12} className="text-primary shrink-0" />}
            <div className="flex-1 text-xs text-ink truncate">
              {mapStoreFilter.kind === 'multi' ? 'Multi-select: ' : 'Map filtered to: '}
              <span className="font-semibold">{mapStoreFilter.label}</span>
              {mapStoreFilter.kind === 'district' && (
                <span className="text-ink-muted ml-1">({mapStoreFilter.names.length} stores)</span>
              )}
            </div>
            <button
              onClick={clearMapStoreFilter}
              className="text-[10px] text-primary font-bold hover:underline shrink-0"
            >
              CLEAR
            </button>
          </div>
        )}
        {/* Body */}
        <div className="flex-1 overflow-y-auto p-3">
          {loading && (
            <div className="flex items-center justify-center gap-2 py-8 text-ink-muted text-sm">
              <Loader2 size={14} className="animate-spin" />
              Aggregating districts…
            </div>
          )}
          {error && (
            <div className="rounded-lg border border-danger/30 bg-danger/5 p-3 text-xs text-danger">
              {error}
            </div>
          )}
          {data && !loading && (
            <>
              {/* Network avg banner */}
              <div className="rounded-lg border border-border bg-app-bg/40 p-3 mb-3 text-center">
                <div className="text-[10px] font-bold text-ink-subtle uppercase tracking-wider">
                  Network average
                </div>
                <div className="text-lg font-bold text-ink tabular-nums">
                  {formatCurrency(data.network_avg, currency)}
                </div>
                <div className="text-[10px] text-ink-muted">
                  across {data.total_stores} stores
                </div>
              </div>
              {/* Lens explainer */}
              <div className="rounded-lg border border-primary/20 bg-primary/5 p-2.5 mb-3 text-[10px] text-ink-muted leading-relaxed">
                <span className="font-bold text-primary">Two lenses per store:</span>{' '}
                <span className="font-semibold">vs Net</span> = vs whole-Mio avg.{' '}
                <span className="font-semibold">vs Dist</span> = vs same-district peers.
                <br />
                <span className="text-ink-muted/80">Tip: tap the ☐ checkbox to add multiple stores to the map.</span>
              </div>
              {/* District cards */}
              <div className="space-y-1.5">
                {data.districts.map((d, i) => {
                  const styles = classificationStyles(d.classification);
                  const isExpanded = expandedDistricts.has(d.district);
                  const isFilteredHere = mapStoreFilter?.kind === 'district' && mapStoreFilter.label === d.district;
                  const rank = i + 1;
                  const deltaPct = d.pct_of_network_avg - 100;
                  const deltaSign = deltaPct >= 0 ? '+' : '−';
                  return (
                    <div
                      key={d.district}
                      className={`rounded-lg border ${styles.border} overflow-hidden
                                 ${isFilteredHere ? 'ring-2 ring-primary/40' : ''}`}
                    >
                      <button
                        onClick={() => handleDistrictClick(d)}
                        className={`w-full ${styles.bg} px-3 py-2.5 flex items-center gap-3
                                   hover:brightness-95 transition-all text-left cursor-pointer`}
                      >
                        <div className="text-[10px] font-mono text-ink-subtle w-6 shrink-0">
                          #{rank}
                        </div>
                        <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: styles.accent }} />
                        <div className="flex-1 min-w-0">
                          <div className="font-semibold text-ink text-sm truncate">{d.district}</div>
                          <div className="text-[11px] text-ink-muted flex items-center gap-1.5">
                            <span>{d.store_count} stores</span>
                            <span className="text-ink-subtle/50">·</span>
                            <span className="font-mono tabular-nums">{formatCurrency(d.avg_revenue, currency)} avg</span>
                          </div>
                        </div>
                        <div className="text-right shrink-0 flex items-center gap-2">
                          <div
                            className="text-xs font-bold font-mono tabular-nums px-2 py-0.5 rounded"
                            style={{ color: styles.accent, backgroundColor: styles.accent + '15' }}
                          >
                            {deltaSign}{Math.abs(deltaPct).toFixed(1)}%
                          </div>
                          {isExpanded
                            ? <ChevronUp size={14} className="text-ink-subtle" />
                            : <ChevronDown size={14} className="text-ink-subtle" />}
                        </div>
                      </button>
                      {isExpanded && (
                        <div className="border-t border-border bg-white p-2 space-y-1">
                          <div className="text-[10px] font-bold text-ink-subtle uppercase tracking-wider px-1 py-1
                                         flex items-center justify-between">
                            <span>Stores in {d.district}</span>
                            <span className="font-mono text-[9px] text-ink-subtle">vs Net · vs Dist</span>
                          </div>
                          {d.stores.slice(0, 40).map((s, idx) => {
                            const isInMulti = selectedNames.has(s.name);
                            const isCurrentSingle = mapStoreFilter?.kind === 'store' && mapStoreFilter.label === s.name;
                            return (
                              <div
                                key={`${d.district}-${idx}`}
                                className={`flex items-center gap-2 px-1 py-1 rounded text-xs
                                           hover:bg-primary/5 transition-colors
                                           ${isCurrentSingle ? 'bg-primary/10 ring-1 ring-primary/30' : ''}
                                           ${isInMulti ? 'bg-primary/5' : ''}`}
                              >
                                {/* Checkbox — adds/removes store from multi-selection */}
                                <div
                                  role="checkbox"
                                  aria-checked={isInMulti}
                                  tabIndex={0}
                                  onClick={(e) => handleStoreCheckboxToggle(s, d.district, e)}
                                  onKeyDown={(e) => {
                                    if (e.key === ' ' || e.key === 'Enter') {
                                      handleStoreCheckboxToggle(s, d.district, e);
                                    }
                                  }}
                                  className={`w-4 h-4 rounded border shrink-0 cursor-pointer transition-colors
                                             flex items-center justify-center
                                             ${isInMulti
                                      ? 'bg-primary border-primary'
                                      : 'border-ink-faint bg-white hover:border-primary/50'}`}
                                  title={isInMulti ? 'Remove from selection' : 'Add to selection'}
                                >
                                  {isInMulti && <Check size={10} className="text-white" strokeWidth={3} />}
                                </div>
                                {/* Store row body — click to fly to */}
                                <button
                                  onClick={(e) => { e.stopPropagation(); handleStoreClick(s, d.district); }}
                                  className="flex-1 flex items-center gap-2 min-w-0 text-left cursor-pointer"
                                  title="Click to fly to this store"
                                >
                                  <Store size={11} className="text-ink-subtle shrink-0" />
                                  <div className="flex-1 min-w-0 truncate text-ink">{s.name || '(unnamed)'}</div>
                                  <div className="font-mono tabular-nums text-ink-subtle text-[10px] w-20 text-right shrink-0">
                                    {formatCurrency(s.revenue, currency)}
                                  </div>
                                  <div
                                    className="font-mono text-[10px] tabular-nums w-10 text-right font-semibold shrink-0"
                                    style={{ color: pctColor(s.pct_of_network_avg, data.thresholds) }}
                                    title="vs Network avg"
                                  >
                                    {s.pct_of_network_avg >= 100 ? "+" : "−"}{Math.abs(s.pct_of_network_avg - 100).toFixed(0)}%
                                  </div>
                                  <div
                                    className="font-mono text-[10px] tabular-nums w-10 text-right shrink-0"
                                    style={{ color: pctColor(s.pct_of_district_avg, data.thresholds) }}
                                    title="vs District avg"
                                  >
                                    {s.pct_of_district_avg >= 100 ? "+" : "−"}{Math.abs(s.pct_of_district_avg - 100).toFixed(0)}%
                                  </div>
                                </button>
                              </div>
                            );
                          })}
                          {d.stores.length > 40 && (
                            <div className="text-[10px] text-ink-subtle italic text-center py-1">
                              …and {d.stores.length - 40} more stores
                            </div>
                          )}
                          {/* District stats footer */}
                          <div className="border-t border-border mt-1 pt-2 px-1 grid grid-cols-3 gap-2 text-[10px]">
                            <div>
                              <div className="text-ink-subtle">Min</div>
                              <div className="font-mono font-semibold text-ink">{formatCurrency(d.min_revenue, currency)}</div>
                            </div>
                            <div>
                              <div className="text-ink-subtle">Avg</div>
                              <div className="font-mono font-semibold text-ink">{formatCurrency(d.avg_revenue, currency)}</div>
                            </div>
                            <div>
                              <div className="text-ink-subtle">Max</div>
                              <div className="font-mono font-semibold text-ink">{formatCurrency(d.max_revenue, currency)}</div>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
              {/* Legend */}
              <div className="mt-3 rounded-lg border border-border bg-app-bg/30 p-2.5">
                <div className="text-[10px] font-bold text-ink-subtle uppercase tracking-wider mb-1.5">
                  Color legend
                </div>
                <div className="flex flex-wrap gap-3 text-[11px] text-ink-muted">
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-green-500" />
                    ≥ +{(data.thresholds.above_pct - 100).toFixed(0)}%
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-amber-500" />
                    ±{(data.thresholds.above_pct - 100).toFixed(0)}%
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-red-500" />
                    ≤ −{(100 - data.thresholds.below_pct).toFixed(0)}%
                  </span>
                </div>
              </div>
            </>
          )}
        </div>
      </motion.div>
    </AnimatePresence>
  );
}