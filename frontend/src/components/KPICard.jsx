import React from 'react';
import { motion } from 'framer-motion';

/**
 * KPICard – clean light-theme summary card
 * Props: icon (component), label, value, sub, color, delay, trend
 */
export default function KPICard({ icon: Icon, label, value, sub, color = '#6C4CF1', delay = 0, trend }) {
  const bgAlpha = `${color}18`;
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.35, ease: 'easeOut' }}
      className="card flex flex-col gap-3 p-6 flex-1 min-w-0"
      style={{ minWidth: 140 }}
    >
      {/* Icon + Label row */}
      <div className="flex items-center justify-between">
        <div
          className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0"
          style={{ backgroundColor: bgAlpha }}
        >
          <Icon size={17} style={{ color }} />
        </div>
        {trend != null && (
          <span
            className="text-[11px] font-semibold px-2 py-0.5 rounded-full"
            style={{
              color: trend >= 0 ? '#22C55E' : '#EF4444',
              backgroundColor: trend >= 0 ? '#DCFCE7' : '#FEE2E2',
            }}
          >
            {trend >= 0 ? '+' : ''}{trend}%
          </span>
        )}
      </div>

      {/* Value */}
      <div>
        <p className="text-2xl font-bold text-ink tabular-nums leading-none">{value}</p>
        {sub && <p className="text-xs text-ink-muted mt-1">{sub}</p>}
      </div>

      {/* Label */}
      <p className="text-xs font-medium text-ink-subtle">{label}</p>
    </motion.div>
  );
}
