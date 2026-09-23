import React from 'react';
import { motion } from 'framer-motion';
import { Sparkles, TrendingUp, MapPin, Users, ArrowRight, ChevronRight } from 'lucide-react';
import useAppStore from '../store/useAppStore';
import { useMoney } from '../utils/money';

export default function OpportunityPanel({ onSelectPrediction, selectedPrediction }) {
  const { results, currencySymbol, country } = useAppStore();
  const picks = (results?.top_picks || []).filter(p => p.verdict !== 'Not Recommended');

  const cur = useMoney();

  if (!picks.length) {
    return (
      <div className="card flex flex-col items-center justify-center p-8 h-full text-center gap-3">
        <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center">
          <Sparkles size={22} className="text-primary" />
        </div>
        <p className="text-sm font-semibold text-ink">No predictions yet</p>
        <p className="text-xs text-ink-muted">Run a prediction to see top opportunities here.</p>
      </div>
    );
  }

  return (
    <div className="card flex flex-col h-full overflow-hidden">
      {/* Panel header */}
      <div className="px-5 py-4 border-b border-border shrink-0">
        <div className="flex items-center gap-2.5 mb-1">
          <div className="w-7 h-7 rounded-lg bg-primary/10 flex items-center justify-center">
            <Sparkles size={14} className="text-primary" />
          </div>
          <h2 className="text-sm font-semibold text-ink">Top Opportunities</h2>
          <span className="ml-auto badge-primary text-[10px]">{picks.length} found</span>
        </div>
        <p className="text-[11px] text-ink-muted ml-9">AI-ranked franchise locations</p>
      </div>

      {/* Scrollable list */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-2">
        {picks.map((pick, i) => {
          const isActive = selectedPrediction === pick.name;
          const isTop = i === 0;
          return (
            <motion.button
              key={i}
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.04, duration: 0.3 }}
              onClick={() => onSelectPrediction(isActive ? null : pick.name)}
              className="w-full text-left"
            >
              <div
                className={`rounded-xl border p-4 transition-all duration-200 group cursor-pointer
                  ${isActive
                    ? 'border-primary/40 bg-primary/5 shadow-[0_0_0_2px_rgba(108,76,241,0.12)]'
                    : isTop
                      ? 'border-warning/30 bg-warning/5 hover:border-warning/50 hover:shadow-card'
                      : 'border-border bg-surface hover:border-primary/20 hover:shadow-card'
                  }`}
              >
                {/* Top row */}
                <div className="flex items-start gap-2.5 mb-3">
                  {/* Rank badge */}
                  <div
                    className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold shrink-0
                      ${isTop ? 'bg-warning text-white' : 'bg-surface-2 text-ink-muted'}`}
                  >
                    {isTop ? '🏆' : `#${i + 1}`}
                  </div>

                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-ink truncate">{pick.name}</p>
                    {pick.address && (
                      <p className="text-[11px] text-ink-muted truncate mt-0.5">{pick.address}</p>
                    )}
                  </div>
                </div>

                {pick.caution_reasons && (
                  <div className="mb-2 text-[10.5px] text-amber-800 bg-amber-50 border border-amber-200 rounded-md px-2 py-1 leading-snug">
                    ⚠️ {pick.caution_reasons}
                  </div>
                )}

                {/* Metrics grid */}
                <div className="grid grid-cols-2 gap-x-3 gap-y-2">
                  <MetricItem
                    icon={<TrendingUp size={11} />}
                    label="Est. Revenue"
                    value={cur(pick.revenue)}
                    highlight
                  />
                  <MetricItem
                    icon={<Users size={11} />}
                    label="Population"
                    value={pick.population ? pick.population.toLocaleString() : '—'}
                  />
                  {pick.nearest_store_km != null && (
                    <MetricItem
                      icon={<MapPin size={11} />}
                      label="Nearest Store"
                      value={`${pick.nearest_store_km.toFixed(1)} km`}
                    />
                  )}
                </div>

                {/* CTA */}
                <div
                  className={`mt-3 pt-3 border-t flex items-center justify-between
                    ${isActive ? 'border-primary/15' : 'border-border'}`}
                >
                  <span className={`text-xs font-medium ${isActive ? 'text-primary' : 'text-ink-muted group-hover:text-primary'} transition-colors`}>
                    {isActive ? 'Viewing on map' : 'View on map'}
                  </span>
                  <ChevronRight
                    size={14}
                    className={`transition-all ${isActive ? 'text-primary rotate-90' : 'text-ink-subtle group-hover:text-primary group-hover:translate-x-0.5'}`}
                  />
                </div>
              </div>
            </motion.button>
          );
        })}
      </div>

      {/* Footer CTA */}
      <div className="px-4 py-3 border-t border-border shrink-0">
        <button className="btn-primary w-full text-xs py-2.5">
          <ArrowRight size={13} />
          View All Opportunities
        </button>
      </div>
    </div>
  );
}

function MetricItem({ icon, label, value, highlight }) {
  return (
    <div className="flex flex-col gap-0.5">
      <div className="flex items-center gap-1 text-ink-subtle">
        {icon}
        <span className="text-[10px] font-medium">{label}</span>
      </div>
      <span className={`text-xs font-semibold tabular-nums ${highlight ? 'text-success' : 'text-ink'}`}>
        {value}
      </span>
    </div>
  );
}
