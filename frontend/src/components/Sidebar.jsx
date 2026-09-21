import React from 'react';

import {

  LayoutDashboard, Map, Sparkles, Store, FileText,

  Building2, Coffee, ChevronRight, RefreshCw, Download, Eye, EyeOff, Hexagon, X

} from 'lucide-react';

import useAppStore from '../store/useAppStore';

import { getDownloadUrl } from '../services/api';

import { useAuth } from '../context/AuthContext';

import { LogOut } from 'lucide-react';

const LAYERS = [

  // { key: 'hexHeatmap', label: 'Performance Heatmap', color: '#10B981', icon: Hexagon, hint: 'Area-level revenue vs network avg' },

  { key: 'stores', label: 'Existing Stores', color: '#3B82F6' },

  { key: 'requests', label: 'Franchise Requests', color: '#8B5CF6' },

  { key: 'predictions', label: 'Predictions', color: '#22C55E' },

  { key: 'businessUnits', label: 'Business Units', color: '#F59E0B' },

  { key: 'amenities', label: 'Amenities', color: '#06B6D4' },

  { key: 'realEstate', label: 'Real Estate Data', color: '#EC4899' },

  { key: 'competitors', label: 'Competitors', color: '#DC2626' },

];

// Which results array backs each map layer.
const LAYER_DATA_KEY = {
  stores: 'stores',
  requests: 'requests',
  predictions: 'top_picks',
  businessUnits: 'business_units',
  amenities: 'amenities',
  realEstate: 'real_estate',
  competitors: 'competitors',
};

export const layerHasData = (results, key) => {
  const dataKey = LAYER_DATA_KEY[key];
  if (!dataKey) return true;
  return Array.isArray(results?.[dataKey]) && results[dataKey].length > 0;
};

export default function AppSidebar({ activeNav, setActiveNav }) {

  const {

    results, sessionId, reset, country, state,

    mapLayers, toggleLayer, hasBU,

    viewMode, setViewMode,

    mobileSidebarOpen, setMobileSidebarOpen,

  } = useAppStore();

  const { user, logout } = useAuth();

  return (
    <>

      {/* Mobile backdrop */}

      {mobileSidebarOpen && (
        <div

          className="lg:hidden fixed inset-0 bg-black/30 z-40"

          onClick={() => setMobileSidebarOpen(false)}

        />

      )}
      <aside

        className={`

          flex flex-col h-full bg-surface border-r border-border

          fixed lg:static inset-y-0 left-0 z-50

          transition-transform duration-200 ease-out

          ${mobileSidebarOpen ? 'translate-x-0' : '-translate-x-full'} lg:translate-x-0

        `}

        style={{ width: 240, minWidth: 240 }}
      >

        {/* ── Logo ─────────────────────────────────── */}
        <div className="flex items-center justify-between gap-3 px-5 py-5 border-b border-border shrink-0">
          <div className="flex items-center gap-3">
            <div

              className="w-8 h-8 rounded-xl flex items-center justify-center shrink-0"

              style={{ background: 'linear-gradient(135deg, #6C4CF1, #8B5CF6)' }}
            >
              <Sparkles size={15} className="text-white" />
            </div>
            <div>
              <p className="font-bold text-sm text-ink tracking-tight leading-none">FranchiseIQ</p>
              <p className="text-[10px] text-ink-muted mt-0.5">Location Intelligence</p>
            </div>
          </div>

          {/* Close button — mobile only */}
          <button

            onClick={() => setMobileSidebarOpen(false)}

            className="lg:hidden p-1 rounded-lg hover:bg-app-bg text-ink-muted"

            aria-label="Close menu"
          >
            <X size={18} />
          </button>
        </div>

        {/* ── View Mode (Hex vs District) ──────────── */}
        <div className="px-3 py-3 border-b border-border shrink-0">
          <p className="text-[10px] font-semibold text-ink-subtle uppercase tracking-widest mb-2">

            View by
          </p>
          <div className="flex bg-app-bg rounded-lg p-1">
            <button

              onClick={() => setViewMode('hex')}

              className={`flex-1 px-2 py-1.5 rounded text-xs font-medium transition-all ${viewMode === 'hex'

                ? 'bg-white shadow text-ink'

                : 'text-ink-muted hover:text-ink'

                }`}
            >

              Expansion
            </button>
            <button

              onClick={() => setViewMode('district')}

              className={`flex-1 px-2 py-1.5 rounded text-xs font-medium transition-all ${viewMode === 'district'

                ? 'bg-white shadow text-ink'

                : 'text-ink-muted hover:text-ink'

                }`}
            >

              District
            </button>
          </div>
        </div>

        {/* ── Navigation (Layers) ──────────────────── */}
        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
          <p className="text-[10px] font-semibold text-ink-subtle uppercase tracking-widest px-3 mb-3">

            Map Layers
          </p>

          {LAYERS.map(({ key, label, color, icon: Icon, hint }) => {

            if (key === 'businessUnits' && !hasBU) return null;

            // Hide layers that have no data for this country/state (e.g. no
            // franchise requests or competitor file) instead of showing an
            // empty toggle.
            if (results && !layerHasData(results, key)) return null;

            const on = mapLayers[key];

            return (
              <button

                key={key}

                onClick={() => toggleLayer(key)}

                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all

                  ${on ? 'text-ink bg-app-bg' : 'text-ink-muted hover:bg-app-bg hover:text-ink'}`}
              >

                {Icon

                  ? <Icon size={14} style={{ color: on ? color : '#D1D5DB' }} className="shrink-0" />

                  : <span className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: on ? color : '#D1D5DB' }} />

                }
                <div className="flex-1 text-left min-w-0">
                  <div className="font-medium leading-tight">{label}</div>

                  {hint && (
                    <div className="text-[10px] text-ink-subtle truncate mt-0.5">{hint}</div>

                  )}
                </div>

                {on

                  ? <Eye size={14} className="text-primary opacity-80 shrink-0" />

                  : <EyeOff size={14} className="text-ink-faint shrink-0" />

                }
              </button>

            );

          })}
        </nav>

        {/* ── Location context ─────────────────────── */}

        {(country || state) && (
          <div className="mx-3 mb-3 p-3 rounded-xl bg-primary/5 border border-primary/15">
            <p className="text-[10px] text-primary font-semibold uppercase tracking-wider mb-1">

              Active Region
            </p>
            <p className="text-xs font-semibold text-ink truncate">

              {[country, state].filter(Boolean).join(' / ')}
            </p>
          </div>

        )}

      </aside>
    </>

  );

}