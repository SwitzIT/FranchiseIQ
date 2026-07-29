import React, { Suspense, useState, useRef, useEffect } from 'react';
import ReactDOM from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Store, Activity, FileText, Star, Building2, Sparkles,
  MapPin, Bell, ChevronDown, ChevronUp, Search, Trophy,
  Layers, Eye, EyeOff, TrendingUp, TrendingDown, Filter,
  Maximize2, Minimize2, X, Menu
} from 'lucide-react';
import useAppStore from '../store/useAppStore';
import AppSidebar from '../components/Sidebar';
import KPICard from '../components/KPICard';
import OpportunityPanel from '../components/OpportunityPanel';
import DistrictPerformancePanel from '../components/DistrictPerformancePanel';

const LazyMap = React.lazy(() => import('../components/MapContainer'));

// ─── Dropdown filter pill (unchanged) ─────────────────────────
function FilterDropdown({ icon: Icon, label, items, selectedName, onSelect, placeholder = 'All' }) {
  const [open, setOpen] = useState(false);
  const [filterSearch, setFilterSearch] = useState('');
  const btnRef = useRef(null);
  const panelRef = useRef(null);
  const searchRef = useRef(null);
  const [pos, setPos] = useState({ top: 0, left: 0 });

  useEffect(() => {
    const handler = (e) => {
      if (btnRef.current && !btnRef.current.contains(e.target) &&
        panelRef.current && !panelRef.current.contains(e.target)) {
        setOpen(false);
        setFilterSearch('');
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // Auto-focus the search box when dropdown opens
  useEffect(() => {
    if (open && searchRef.current) {
      setTimeout(() => searchRef.current?.focus(), 50);
    }
    if (!open) setFilterSearch('');
  }, [open]);

  const handleToggle = () => {
    if (!open && btnRef.current) {
      const rect = btnRef.current.getBoundingClientRect();
      setPos({ top: rect.bottom + 6, left: rect.left });
    }
    setOpen(!open);
  };

  const isActive = selectedName != null;

  // Case-insensitive contains filter
  const q = filterSearch.trim().toLowerCase();
  const filteredItems = q
    ? items.filter(it => (it.name || '').toLowerCase().includes(q))
    : items;

  // Show search only when there are enough items to make it worthwhile
  const showSearch = items.length > 8;

  return (
    <>
      <button
        ref={btnRef}
        onClick={handleToggle}
        className={`filter-pill ${isActive ? 'active' : ''}`}
      >
        <Icon size={13} />
        <span className="max-w-[120px] truncate">{selectedName || label}</span>
        <ChevronDown size={11} className={`transition-transform ml-0.5 ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && ReactDOM.createPortal(
        <div
          ref={panelRef}
          className="rounded-xl shadow-card-lg border border-border overflow-hidden"
          style={{
            position: 'fixed', top: pos.top, left: pos.left, zIndex: 99999,
            background: '#FFFFFF', minWidth: 240, maxHeight: 360, display: 'flex', flexDirection: 'column',
          }}
        >
          {showSearch && (
            <div className="border-b border-border bg-app-bg/40 p-2 shrink-0">
              <div className="relative">
                <Search size={11} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-subtle pointer-events-none" />
                <input
                  ref={searchRef}
                  type="text"
                  value={filterSearch}
                  onChange={(e) => setFilterSearch(e.target.value)}
                  placeholder={`Search ${items.length} ${label.toLowerCase()}...`}
                  className="w-full text-xs pl-7 pr-2 py-1.5 rounded-md border border-border
                             bg-white focus:outline-none focus:border-primary/50 focus:ring-2 focus:ring-primary/10"
                />
              </div>
              {q && (
                <div className="text-[10px] text-ink-subtle mt-1 px-1">
                  {filteredItems.length} of {items.length} match
                </div>
              )}
            </div>
          )}

          <div className="overflow-y-auto flex-1">
            <button
              onClick={() => { onSelect(null); setOpen(false); }}
              className="w-full text-left px-4 py-2.5 text-xs text-ink-muted hover:bg-app-bg transition-colors border-b border-border font-semibold"
            >
              All {label}
            </button>
            {filteredItems.length === 0 && (
              <div className="px-4 py-3 text-xs text-ink-subtle">
                {q ? `No matches for "${filterSearch}"` : 'No data available'}
              </div>
            )}
            {filteredItems.map((item, i) => (
              <button
                key={i}
                onClick={() => { onSelect(item.name); setOpen(false); }}
                className={`w-full text-left px-4 py-2 text-xs transition-colors flex items-center gap-2
                  ${selectedName === item.name ? 'bg-primary/10 text-primary font-semibold' : 'text-ink hover:bg-app-bg'}`}
              >
                {item.rank != null && (
                  <span className="text-[10px] font-bold text-ink-subtle w-5 shrink-0">#{item.rank}</span>
                )}
                <span className="truncate flex-1">{item.name}</span>
                {item.score != null && (
                  <span className="text-[10px] font-mono text-ink-subtle shrink-0 tabular-nums">
                    {item.score.toFixed(1)}
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>,
        document.body
      )}
    </>
  );
}

// ─── Map Legend ────────────────────────────────────────────────
function MapLegend() {
  const [open, setOpen] = useState(true);
  return (
    <div className="absolute bottom-5 left-5 z-[1000]">
      <AnimatePresence>
        {open ? (
          <motion.div
            key="legend-open"
            initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 8 }}
            className="bg-white/95 backdrop-blur-sm border border-border rounded-xl shadow-card-md p-3.5 text-xs"
            style={{ minWidth: 220 }}
          >
            <div className="flex items-center justify-between mb-2.5">
              <span className="text-[10px] font-bold text-ink-subtle uppercase tracking-wider">Legend</span>
              <button onClick={() => setOpen(false)} className="p-0.5 rounded hover:bg-app-bg transition-colors">
                <X size={11} className="text-ink-subtle" />
              </button>
            </div>

            {/* Store Performance section — colour of existing store markers */}
            <div className="mb-2.5 pb-2.5 border-b border-border">
              <div className="flex items-center gap-1.5 mb-1.5">
                <Store size={10} className="text-ink-subtle" />
                <span className="text-[9px] font-semibold text-ink-subtle uppercase tracking-wider">
                  Store Performance
                </span>
              </div>
              <div className="space-y-1">
                {[
                  { color: '#22C55E', label: 'Above network avg' },
                  { color: '#F59E0B', label: 'On target' },
                  { color: '#EF4444', label: 'Below network avg' },
                ].map(({ color, label }) => (
                  <div key={label} className="flex items-center gap-2 text-ink-muted">
                    <span className="w-3 h-3 rounded-sm shrink-0 border" style={{ backgroundColor: color + '55', borderColor: color }} />
                    <span>{label}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Pins section */}
            <div>
              <div className="text-[9px] font-semibold text-ink-subtle uppercase tracking-wider mb-1.5">
                Markers
              </div>
              <div className="space-y-1">
                {[
                  { color: '#3B82F6', label: 'Existing Stores' },
                  { color: '#8B5CF6', label: 'Franchise Requests' },
                  { color: '#D4AF37', label: '#1 Top Pick' },
                  { color: '#A8A8A8', label: '#2-3 Top Picks' },
                  { color: '#6C4CF1', label: '#4-10 Top Picks' },
                ].map(({ color, label }) => (
                  <div key={label} className="flex items-center gap-2 text-ink-muted">
                    <span className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: color }} />
                    <span>{label}</span>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        ) : (
          <motion.button
            key="legend-closed"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={() => setOpen(true)}
            className="bg-white/95 border border-border rounded-xl shadow-card px-3 py-2 flex items-center gap-1.5 text-xs text-ink-muted hover:text-ink transition-all"
          >
            <MapPin size={12} className="text-primary" />
            <span className="font-medium">Legend</span>
            <ChevronUp size={11} />
          </motion.button>
        )}
      </AnimatePresence>
    </div>
  );
}

// ─── Store Performance Filter Bar ─────────────────────────────
const STORE_FILTERS = [
  { key: 'all', label: 'All Stores', icon: null },
  { key: 'above', label: 'Above Avg', icon: TrendingUp },
  { key: 'below', label: 'Below Avg', icon: TrendingDown },
];

// ─── Mobile Bottom Sheet for Opportunity Panel ────────────────
function MobileBottomSheet({ children }) {
  const { mobileSheetOpen, setMobileSheetOpen } = useAppStore();
  return (
    <motion.div
      animate={{ y: mobileSheetOpen ? '0%' : '70%' }}
      transition={{ type: 'spring', damping: 28, stiffness: 280 }}
      className="lg:hidden fixed inset-x-0 bottom-0 z-30 bg-surface border-t border-border rounded-t-2xl shadow-card-lg flex flex-col"
      style={{ height: '80vh' }}
    >
      <button
        onClick={() => setMobileSheetOpen(!mobileSheetOpen)}
        className="shrink-0 py-2 flex flex-col items-center"
        aria-label={mobileSheetOpen ? 'Collapse panel' : 'Expand panel'}
      >
        <div className="w-10 h-1 rounded-full bg-ink-faint mb-1" />
        <div className="text-[10px] font-semibold text-ink-subtle uppercase tracking-widest">
          {mobileSheetOpen ? 'Tap to collapse' : 'Top opportunities · Tap to expand'}
        </div>
      </button>
      <div className="flex-1 overflow-hidden p-3">
        {children}
      </div>
    </motion.div>
  );
}

// ─── Main Dashboard ────────────────────────────────────────────
export default function DashboardPage() {
  const {
    results, regionKpis, selectedRegion, setSelectedRegion,
    country, state, currencySymbol, selectedStoreName, flyToStore,
    hasBU, storeFilter, setStoreFilter,
    setMobileSidebarOpen,
  } = useAppStore();

  const kpis = results?.kpis || {};
  const stores = results?.stores || [];
  const predictions = results?.top_picks || [];

  const [activeNav, setActiveNav] = useState('overview');
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [selectedPrediction, setSelectedPrediction] = useState(null);

  const storeItems = stores.map(s => ({ name: s.name }));
  const predItems = predictions.map((p, i) => ({ name: p.name, score: p.score, rank: i + 1 }));
  const regionItems = regionKpis?.regions?.map(r => ({ name: r.name, score: r.avg_final_score })) || [];

  const flyToPrediction = (name) => {
    if (!name) { setSelectedPrediction(null); return; }
    const pred = predictions.find(p => p.name === name);
    if (pred) {
      setSelectedPrediction(name);
      useAppStore.setState({ flyToCoords: { lat: pred.lat, lng: pred.lng, zoom: 15 } });
    }
  };

  const cur = (val) => {
    if (val == null) return '—';
    if (country === 'India') {
      if (val >= 10000000) return `${currencySymbol}${(val / 10000000).toFixed(2)} Cr`;
      if (val >= 100000) return `${currencySymbol}${(val / 100000).toFixed(1)} L`;
      return `${currencySymbol}${val.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
    }
    if (val >= 1000000) return `${currencySymbol}${(val / 1000000).toFixed(2)} M`;
    if (val >= 1000) return `${currencySymbol}${(val / 1000).toFixed(1)} K`;
    return `${currencySymbol}${val.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
  };

  return (
    <div className="flex h-screen overflow-hidden bg-app-bg">
      {!isFullscreen && (
        <AppSidebar activeNav={activeNav} setActiveNav={setActiveNav} />
      )}

      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">

        {/* ── Top Header Bar ──────────────────────── */}
        {!isFullscreen && (
          <header className="flex items-center gap-3 px-4 sm:px-6 py-3 bg-surface border-b border-border shrink-0">
            <button
              onClick={() => setMobileSidebarOpen(true)}
              className="lg:hidden p-2 -ml-1 rounded-lg hover:bg-app-bg text-ink-muted"
              aria-label="Open menu"
            >
              <Menu size={18} />
            </button>

            <div className="flex items-center gap-1.5 text-sm min-w-0">
              <span className="text-ink-muted font-medium truncate">
                {country || 'Global'}
              </span>
              {state && (
                <>
                  <span className="text-ink-faint">/</span>
                  <span className="text-ink font-semibold truncate">{state}</span>
                </>
              )}
            </div>

            <div className="flex-1" />

            {results && (
              <span className="hidden sm:inline-flex badge-success items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-success inline-block" />
                Analysis Complete
              </span>
            )}

            <button className="btn-ghost p-2 rounded-xl relative">
              <Bell size={17} className="text-ink-subtle" />
              <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-primary" />
            </button>

            <div className="flex items-center gap-2.5 pl-2 border-l border-border cursor-pointer group">
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary to-primary-light flex items-center justify-center text-white text-sm font-bold shrink-0">
                A
              </div>
              <div className="hidden sm:block">
                <p className="text-xs font-semibold text-ink leading-none">Admin</p>
                <p className="text-[10px] text-ink-muted mt-0.5">Analyst</p>
              </div>
              <ChevronDown size={13} className="text-ink-subtle group-hover:text-ink transition-colors hidden sm:block" />
            </div>
          </header>
        )}

        <div className="flex-1 overflow-hidden flex flex-col min-h-0">

          {/* ── KPI Cards Row ─────────── */}
          {!isFullscreen && (
            <div className="flex items-stretch gap-3 px-4 sm:px-6 py-3 sm:py-4 border-b border-border shrink-0 overflow-x-auto">
              <KPICard
                icon={Store}
                label="Total Stores"
                value={kpis.total_stores ?? 0}
                sub={`${country || 'Global'} network`}
                color="#6C4CF1"
                delay={0}
              />
              <KPICard
                icon={Activity}
                label="Avg Store Sales"
                value={cur(kpis.avg_sales)}
                sub="per store"
                color="#22C55E"
                delay={0.06}
              />
              <KPICard
                icon={FileText}
                label="Avg Predicted Sales"
                value={cur(kpis.avg_predicted_revenue)}
                sub="AI estimate"
                color="#06B6D4"
                delay={0.12}
              />
              <KPICard
                icon={Star}
                label="Best Score"
                value={`${(kpis.max_score || 0).toFixed(1)}`}
                sub="out of 100"
                color="#F59E0B"
                delay={0.18}
              />
              <KPICard
                icon={Sparkles}
                label="Avg Score"
                value={`${(kpis.avg_score || 0).toFixed(1)}`}
                sub="all candidates"
                color="#8B5CF6"
                delay={0.24}
              />
              <KPICard
                icon={MapPin}
                label="Top Region"
                value={regionKpis?.best_region || '—'}
                sub={
                  regionKpis?.regions?.[0]
                    ? `${cur(regionKpis.regions[0].avg_revenue)} avg · ${regionKpis.regions[0].store_count} store${regionKpis.regions[0].store_count !== 1 ? 's' : ''}`
                    : 'Run analysis first'
                }
                color="#10B981"
                delay={0.30}
              />
            </div>
          )}

          {/* ── Filter Bar ──────────── */}
          {!isFullscreen && (
            <div className="flex items-center gap-2 sm:gap-3 px-4 sm:px-6 py-2.5 border-b border-border bg-surface shrink-0 overflow-x-auto">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-ink-muted shrink-0">
                <Filter size={13} />
                <span className="hidden sm:inline">Filters:</span>
              </div>

              <FilterDropdown
                icon={Building2}
                label="Franchise Store"
                items={storeItems}
                selectedName={selectedStoreName}
                onSelect={(name) => flyToStore(name)}
              />

              <FilterDropdown
                icon={Trophy}
                label="Top Predictions"
                items={predItems}
                selectedName={selectedPrediction}
                onSelect={(name) => flyToPrediction(name)}
              />

              {regionItems.length > 0 && (
                <FilterDropdown
                  icon={MapPin}
                  label="Region"
                  items={regionItems}
                  selectedName={selectedRegion}
                  onSelect={(name) => setSelectedRegion(name)}
                />
              )}

              <div className="flex items-center gap-1.5 ml-1 shrink-0">
                {STORE_FILTERS.map(({ key, label, icon: Ico }) => (
                  <button
                    key={key}
                    onClick={() => setStoreFilter(key)}
                    className={`filter-pill ${storeFilter === key ? 'active' : ''}`}
                  >
                    {Ico && <Ico size={11} />}
                    <span className="hidden sm:inline">{label}</span>
                    <span className="sm:hidden">{key === 'all' ? 'All' : key === 'above' ? '▲' : '▼'}</span>
                  </button>
                ))}
              </div>

              {(selectedStoreName || selectedPrediction || selectedRegion || storeFilter !== 'all') && (
                <button
                  onClick={() => {
                    flyToStore(null);
                    flyToPrediction(null);
                    setSelectedRegion(null);
                    setStoreFilter('all');
                  }}
                  className="btn-ghost text-xs text-danger ml-auto shrink-0"
                >
                  <X size={12} />
                  <span className="hidden sm:inline">Reset Filters</span>
                  <span className="sm:hidden">Reset</span>
                </button>
              )}
            </div>
          )}

          {/* ── Main 2-col content ─── */}
          <div className="flex-1 flex overflow-hidden min-h-0">
            <div className="flex-1 relative overflow-hidden min-h-0 p-2 sm:p-4 lg:pr-2">
              <div className="relative h-full rounded-2xl overflow-hidden border border-border shadow-card">
                <Suspense fallback={
                  <div className="w-full h-full flex items-center justify-center bg-surface-2">
                    <div className="flex flex-col items-center gap-3">
                      <div className="w-10 h-10 rounded-full border-2 border-primary border-t-transparent animate-spin" />
                      <p className="text-sm text-ink-muted font-medium">Loading map…</p>
                    </div>
                  </div>
                }>
                  <LazyMap />
                </Suspense>

                <MapLegend />

                <button
                  onClick={() => setIsFullscreen(v => !v)}
                  className="absolute top-3 right-3 z-[1000] bg-white border border-border rounded-xl p-2 shadow-card hover:border-primary/30 hover:bg-primary/5 transition-all"
                  title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen Map'}
                >
                  {isFullscreen
                    ? <Minimize2 size={15} className="text-ink-subtle" />
                    : <Maximize2 size={15} className="text-ink-subtle" />
                  }
                </button>
              </div>
            </div>

            {!isFullscreen && (
              <div className="hidden lg:block w-80 shrink-0 p-4 pl-2 overflow-hidden min-h-0">
                <OpportunityPanel
                  onSelectPrediction={(name) => flyToPrediction(name)}
                  selectedPrediction={selectedPrediction}
                />
              </div>
            )}
          </div>

        </div>
      </div>

      {!isFullscreen && results && (
        <MobileBottomSheet>
          <OpportunityPanel
            onSelectPrediction={(name) => flyToPrediction(name)}
            selectedPrediction={selectedPrediction}
          />
        </MobileBottomSheet>
      )}

      <DistrictPerformancePanel />

    </div>
  );
}
