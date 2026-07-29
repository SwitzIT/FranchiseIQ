import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X, MapPin, TrendingUp, TrendingDown, Minus,
  Store, Info,
} from 'lucide-react';
import useAppStore from '../store/useAppStore';

/**
 * HexDetailPanel
 * ───────────────
 * Slide-out panel that appears when a hex is clicked. Shows:
 *   1. Locality (dominant suburb/city/district from contained stores)
 *   2. Performance summary with the actual math
 *   3. Colour-logic legend (so users understand why this colour)
 *   4. Per-store breakdown (name, revenue, % of network avg)
 *   5. Comparison vs network
 *
 * Every number is traceable to the underlying calculation. No black box.
 */

function classificationLabel(c) {
  if (c === 'above')     return 'Above network average';
  if (c === 'below')     return 'Below network average';
  return 'On target with network average';
}

function classificationStyles(c) {
  if (c === 'above') return {
    bg: 'bg-green-50', border: 'border-green-300', text: 'text-green-700',
    accent: '#22C55E', icon: TrendingUp,
  };
  if (c === 'below') return {
    bg: 'bg-red-50', border: 'border-red-300', text: 'text-red-700',
    accent: '#EF4444', icon: TrendingDown,
  };
  return {
    bg: 'bg-amber-50', border: 'border-amber-300', text: 'text-amber-700',
    accent: '#F59E0B', icon: Minus,
  };
}

function formatCurrency(n, currency = '₹') {
  if (!Number.isFinite(n)) return `${currency} 0`;
  if (Math.abs(n) >= 1e7) return `${currency} ${(n / 1e7).toFixed(2)} Cr`;
  if (Math.abs(n) >= 1e5) return `${currency} ${(n / 1e5).toFixed(2)} L`;
  return `${currency} ${n.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
}

export default function HexDetailPanel() {
  const { selectedHex, setSelectedHex, hexHeatmap, currencySymbol } = useAppStore();

  if (!selectedHex) return null;

  const networkAvg = hexHeatmap?.network_avg || 0;
  const thresholds = hexHeatmap?.thresholds || { above_pct: 110, below_pct: 90 };
  const styles = classificationStyles(selectedHex.classification);
  const ClsIcon = styles.icon;
  const currency = currencySymbol || '₹';

  const diffFromNet  = selectedHex.avg_revenue - networkAvg;
  const diffPct      = networkAvg > 0
    ? Math.round((diffFromNet / networkAvg) * 100)
    : 0;
  const diffSign     = diffFromNet >= 0 ? '+' : '−';

  return (
    <AnimatePresence>
      <motion.div
        initial={{ x: 360, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        exit={{ x: 360, opacity: 0 }}
        transition={{ type: 'spring', damping: 25, stiffness: 220 }}
        className="fixed top-20 right-5 z-[2000] w-96 max-w-[95vw] max-h-[78vh] overflow-hidden
                   bg-white rounded-2xl shadow-card-lg border border-border flex flex-col"
      >
        {/* Header */}
        <div className="flex items-center gap-3 p-4 border-b border-border shrink-0">
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
            style={{ backgroundColor: styles.accent + '18', color: styles.accent }}
          >
            <MapPin size={18} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-xs font-semibold text-ink-subtle uppercase tracking-wider">
              Zone Details
            </div>
            <div className="text-base font-bold text-ink truncate">
              {selectedHex.dominant_locality || '— locality not derived —'}
            </div>
          </div>
          <button
            onClick={() => setSelectedHex(null)}
            className="p-1 rounded hover:bg-app-bg transition-colors shrink-0"
            aria-label="Close"
          >
            <X size={16} className="text-ink-subtle" />
          </button>
        </div>

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">

          {/* 1. Performance summary with the math */}
          <div className={`rounded-xl border ${styles.border} ${styles.bg} p-4`}>
            <div className={`flex items-center gap-2 ${styles.text} mb-2`}>
              <ClsIcon size={14} />
              <span className="text-xs font-bold uppercase tracking-wider">
                {classificationLabel(selectedHex.classification)}
              </span>
            </div>
            <div className="text-2xl font-bold text-ink tabular-nums">
              {selectedHex.pct_of_network_avg.toFixed(1)}%
              <span className="text-xs font-normal text-ink-muted ml-2">of network avg</span>
            </div>
            <div className="text-[11px] text-ink-subtle mt-1 font-mono">
              {formatCurrency(selectedHex.avg_revenue, currency)} ÷ {formatCurrency(networkAvg, currency)}
            </div>
          </div>

          {/* 2. Colour logic legend (the why-this-colour explainer) */}
          <div className="rounded-lg border border-border bg-app-bg/40 p-3">
            <div className="flex items-center gap-1.5 mb-2">
              <Info size={11} className="text-ink-subtle" />
              <span className="text-[10px] font-bold text-ink-subtle uppercase tracking-wider">
                Why this colour
              </span>
            </div>
            <div className="space-y-1 text-[11px] text-ink-muted">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-sm bg-green-500 shrink-0" />
                <span>≥ {thresholds.above_pct.toFixed(0)}% of net avg → above</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-sm bg-amber-500 shrink-0" />
                <span>{thresholds.below_pct.toFixed(0)}–{thresholds.above_pct.toFixed(0)}% → on target</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-sm bg-red-500 shrink-0" />
                <span>≤ {thresholds.below_pct.toFixed(0)}% of net avg → below</span>
              </div>
            </div>
          </div>

          {/* 3. Per-store breakdown */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-bold text-ink-subtle uppercase tracking-wider">
                Stores in this zone ({selectedHex.store_count})
              </span>
            </div>
            <div className="space-y-1.5">
              {(selectedHex.stores_detail || []).map((s, i) => {
                const isAbove = s.pct_of_network_avg >= thresholds.above_pct;
                const isBelow = s.pct_of_network_avg <= thresholds.below_pct;
                const c = isAbove ? styles : (isBelow ? classificationStyles('below') : classificationStyles('on_target'));
                return (
                  <div
                    key={i}
                    className={`rounded-lg border ${c.border} ${c.bg} p-2.5 flex items-center gap-2.5`}
                  >
                    <Store size={14} className={c.text} />
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-semibold text-ink truncate">{s.name || '(unnamed)'}</div>
                      <div className="text-[10px] text-ink-muted font-mono tabular-nums">
                        {formatCurrency(s.revenue, currency)} · {s.pct_of_network_avg.toFixed(1)}% of net
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* 4. Comparison vs network */}
          <div className="rounded-lg border border-border bg-app-bg/40 p-3 space-y-1.5">
            <div className="text-[10px] font-bold text-ink-subtle uppercase tracking-wider mb-1">
              vs Network
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-ink-muted">This zone (avg)</span>
              <span className="font-mono font-semibold text-ink tabular-nums">
                {formatCurrency(selectedHex.avg_revenue, currency)}
              </span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-ink-muted">Network (avg)</span>
              <span className="font-mono font-semibold text-ink tabular-nums">
                {formatCurrency(networkAvg, currency)}
              </span>
            </div>
            <div className="h-px bg-border my-1" />
            <div className="flex justify-between text-xs items-center">
              <span className="text-ink-muted">Difference</span>
              <span
                className="font-mono font-bold tabular-nums px-2 py-0.5 rounded"
                style={{
                  color: styles.accent,
                  backgroundColor: styles.accent + '15',
                }}
              >
                {diffSign}{Math.abs(diffPct)}%
              </span>
            </div>
          </div>

          {/* Tech meta */}
          <div className="text-[9px] text-ink-subtle/70 font-mono text-center pt-1">
            H3 cell: {selectedHex.cell}
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
