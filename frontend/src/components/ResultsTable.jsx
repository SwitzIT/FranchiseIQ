import React from 'react';
import { motion } from 'framer-motion';
import { Trophy, TrendingUp, MapPin, Users, Building2, Star } from 'lucide-react';
import useAppStore from '../store/useAppStore';

const scoreColor = (s) => {
  if (s >= 80) return { text: 'text-green',   bg: 'bg-green/10',   border: 'border-green/30' };
  if (s >= 60) return { text: 'text-amber',   bg: 'bg-amber/10',   border: 'border-amber/30' };
  if (s >= 40) return { text: 'text-cyan',    bg: 'bg-cyan/10',    border: 'border-cyan/30' };
  return           { text: 'text-slate-400', bg: 'bg-white/5',    border: 'border-white/10' };
};
const rankIcon = (i) => {
  if (i === 0) return '🏆';
  if (i === 1) return '🥈';
  if (i === 2) return '🥉';
  return `${i + 1}`;
};

export default function ResultsTable() {
  const { results, currencySymbol, country } = useAppStore();
  const picks = results?.top_picks || [];

  const fmt = (n) => {
    if (n == null) return '—';
    const locale = country === 'India' ? 'en-IN' : 'en-US';
    return n.toLocaleString(locale, { maximumFractionDigits: 0 });
  };

  const cur = (val) => {
    if (val == null) return '—';
    let formatted = '';
    if (country === 'India') {
      if (val >= 10000000) formatted = (val / 10000000).toFixed(2) + ' Cr';
      else if (val >= 100000) formatted = (val / 100000).toFixed(2) + ' L';
      else formatted = fmt(val);
    } else {
      if (val >= 1000000) formatted = (val / 1000000).toFixed(2) + ' M';
      else if (val >= 1000) formatted = (val / 1000).toFixed(1) + ' K';
      else formatted = fmt(val);
    }
    return `${currencySymbol}${formatted}`;
  };

  if (!picks.length) return null;

  return (
    <div className="space-y-2.5">
      <div className="flex items-center gap-2 px-1 mb-3">
        <Trophy size={16} className="text-amber" />
        <h3 className="text-sm font-bold text-white">Top Locations</h3>
        <span className="ml-auto text-xs text-slate-500 tabular-nums">{picks.length} results</span>
      </div>

      {picks.map((pick, i) => {
        const sc = scoreColor(pick.score);
        return (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.05 }}
            className={`rounded-lg border p-3.5 cursor-pointer transition-all duration-200
                        hover:border-purple/40 hover:bg-white/[0.06]
                        ${i === 0
                          ? 'border-amber/30 bg-amber/5'
                          : 'border-white/8 bg-white/[0.03]'
                        }`}
          >
            {/* Top row */}
            <div className="flex items-start gap-2.5 mb-2">
              <div className={`text-lg leading-none mt-0.5 ${i === 0 ? 'animate-pulse-slow' : ''}`}>
                {rankIcon(i)}
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-sm text-white truncate">{pick.name}</p>
                {pick.address && (
                  <p className="text-xs text-slate-500 truncate mt-0.5">{pick.address}</p>
                )}
              </div>
              {/* Score badge */}
              <span className={`score-badge ${sc.bg} ${sc.border} ${sc.text}`}>
                <Star size={10} />
                {pick.score?.toFixed(1)}
              </span>
            </div>

            {/* Stats row */}
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 mt-2 text-xs">
              <StatRow icon={<TrendingUp size={10} />} label="Est. Revenue" value={cur(pick.revenue)} highlight />
              <StatRow icon={<Users size={10} />}      label="Population"  value={fmt(pick.population)} />
              {pick.nearest_store && (
                <StatRow icon={<MapPin size={10} />} label="Nearest Store"
                  value={`${pick.nearest_store_km?.toFixed(1)}km`} />
              )}
              {pick.bu_name && pick.bu_name !== 'N/A' && (
                <StatRow icon={<Building2 size={10} />} label="BU Unit" value={pick.bu_name} />
              )}
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}

function StatRow({ icon, label, value, highlight }) {
  return (
    <div className="flex items-center gap-1">
      <span className="text-slate-600">{icon}</span>
      <span className="text-slate-500 truncate">{label}:</span>
      <span className={`ml-auto font-semibold truncate ${highlight ? 'text-green' : 'text-slate-300'}`}>
        {value}
      </span>
    </div>
  );
}
