import React from 'react';
import { motion } from 'framer-motion';
import { Map, TrendingUp, Star, Award, Target, ChevronRight } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import useAppStore from '../store/useAppStore';

export default function RegionKPIPanel() {
  const { regionKpis, selectedRegion, setSelectedRegion, currencySymbol, country } = useAppStore();

  if (!regionKpis || !regionKpis.regions || regionKpis.regions.length === 0) return null;

  const { regions, best_region } = regionKpis;

  const fmtCurrency = (val) => {
    if (val == null) return '—';
    const num = Number(val);
    if (country === 'India') {
      if (num >= 10000000) return `${currencySymbol}${(num / 10000000).toFixed(2)}Cr`;
      if (num >= 100000)   return `${currencySymbol}${(num / 100000).toFixed(2)}L`;
    } else {
      if (num >= 1000000) return `${currencySymbol}${(num / 1000000).toFixed(2)}M`;
      if (num >= 1000)    return `${currencySymbol}${(num / 1000).toFixed(1)}K`;
    }
    return `${currencySymbol}${num.toLocaleString()}`;
  };

  const getPerfColor = (label) => {
    if (label === 'top') return '#22C55E';
    if (label === 'low') return '#EF4444';
    return '#3B82F6';
  };

  const avgScore = regions.length > 0
    ? (regions.reduce((a, r) => a + r.avg_final_score, 0) / regions.length).toFixed(1)
    : 0;

  return (
    <div className="space-y-4">

      {/* Overview Cards */}
      <div className="grid grid-cols-3 gap-2">
        <div className="p-3 rounded-xl bg-success/8 border border-success/20">
          <div className="flex items-center gap-1.5 mb-1.5 text-success">
            <Award size={13} />
            <span className="text-[10px] font-semibold uppercase tracking-wider">Top Region</span>
          </div>
          <div className="text-sm font-bold text-ink truncate" title={best_region}>{best_region || '—'}</div>
        </div>
        <div className="p-3 rounded-xl bg-blue-50 border border-blue-200">
          <div className="flex items-center gap-1.5 mb-1.5 text-blue-500">
            <Map size={13} />
            <span className="text-[10px] font-semibold uppercase tracking-wider">Regions</span>
          </div>
          <div className="text-sm font-bold text-ink">{regions.length}</div>
        </div>
        <div className="p-3 rounded-xl bg-primary/8 border border-primary/20">
          <div className="flex items-center gap-1.5 mb-1.5 text-primary">
            <Target size={13} />
            <span className="text-[10px] font-semibold uppercase tracking-wider">Avg Score</span>
          </div>
          <div className="text-sm font-bold text-ink">{avgScore}</div>
        </div>
      </div>

      {/* Bar Chart */}
      <div className="p-4 rounded-xl border border-border bg-surface">
        <h3 className="text-xs font-semibold text-ink mb-3 flex items-center gap-2">
          <TrendingUp size={13} className="text-primary" />
          Revenue by Region
        </h3>
        <div className="h-44">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={regions} layout="vertical" margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <XAxis type="number" hide />
              <YAxis dataKey="name" type="category" axisLine={false} tickLine={false}
                tick={{ fill: '#6B7280', fontSize: 10 }} width={90}
              />
              <Tooltip
                cursor={{ fill: 'rgba(108,76,241,0.05)' }}
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const d = payload[0].payload;
                  return (
                    <div className="bg-white border border-border rounded-xl p-3 shadow-card-md text-xs">
                      <p className="font-semibold text-ink mb-1">{d.name}</p>
                      <p className="text-ink-muted">Stores: <span className="text-ink font-medium">{d.store_count}</span></p>
                      <p className="text-ink-muted">Avg Rev: <span className="text-success font-medium">{fmtCurrency(d.avg_revenue)}</span></p>
                      <p className="text-ink-muted">Avg Score: <span className="text-primary font-medium">{d.avg_final_score.toFixed(1)}</span></p>
                    </div>
                  );
                }}
              />
              <Bar dataKey="avg_revenue" radius={[0, 4, 4, 0]} barSize={14}>
                {regions.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={getPerfColor(entry.performance_label)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Region table */}
      <div className="rounded-xl border border-border overflow-hidden bg-surface">
        <div className="px-4 py-2.5 border-b border-border bg-app-bg">
          <h3 className="text-[10px] font-bold text-ink-subtle uppercase tracking-widest">Regional Leaderboard</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-app-bg text-ink-subtle">
              <tr>
                <th className="px-3 py-2 font-semibold">Region</th>
                <th className="px-3 py-2 font-semibold text-right">Stores</th>
                <th className="px-3 py-2 font-semibold text-right">Avg Rev</th>
                <th className="px-3 py-2 font-semibold text-right">Score</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {regions.map((r, i) => (
                <tr
                  key={i}
                  onClick={() => setSelectedRegion(selectedRegion === r.name ? null : r.name)}
                  className={`cursor-pointer transition-colors hover:bg-primary/5 border-l-2
                    ${selectedRegion === r.name ? 'bg-primary/5 border-primary' : 'border-transparent'}`}
                >
                  <td className="px-3 py-2.5 whitespace-nowrap">
                    <div className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: getPerfColor(r.performance_label) }} />
                      <span className={`font-medium ${selectedRegion === r.name ? 'text-primary' : 'text-ink'}`}>{r.name}</span>
                    </div>
                  </td>
                  <td className="px-3 py-2.5 whitespace-nowrap text-right text-ink-muted tabular-nums">{r.store_count}</td>
                  <td className="px-3 py-2.5 whitespace-nowrap text-right font-semibold text-success tabular-nums">{fmtCurrency(r.avg_revenue)}</td>
                  <td className="px-3 py-2.5 whitespace-nowrap text-right text-primary font-bold tabular-nums">
                    {r.avg_final_score > 0 ? r.avg_final_score.toFixed(1) : '—'}
                  </td>
                  <td className="px-3 py-2.5 whitespace-nowrap text-right">
                    <ChevronRight size={13} className={`text-ink-faint transition-transform ${selectedRegion === r.name ? 'text-primary rotate-90' : ''}`} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
