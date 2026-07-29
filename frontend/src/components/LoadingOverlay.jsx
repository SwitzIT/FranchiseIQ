import React from 'react';
import { motion } from 'framer-motion';
import useAppStore from '../store/useAppStore';

const STEPS_META = [
  { id: 'country',    label: 'Region',    emoji: '🌍' },
  { id: 'state',      label: 'State',     emoji: '🗺️' },
  { id: 'configure',  label: 'Configure', emoji: '⚙️' },
  { id: 'predicting', label: 'Analyze',   emoji: '🧠' },
  { id: 'dashboard',  label: 'Results',   emoji: '✅' },
];

const MESSAGES = {
  country:    'Initializing country data pipeline…',
  state:      'Loading state-level demographics…',
  configure:  'Preparing state data files and cache…',
  predicting: 'Running AI pipeline — crunching numbers…',
};

export default function LoadingOverlay() {
  const { loading, loadingMsg, step } = useAppStore();
  if (!loading) return null;

  const idx = STEPS_META.findIndex(s => s.id === step);

  return (
    <motion.div
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex flex-col items-center justify-center"
      style={{ background: 'rgba(247,248,252,0.92)', backdropFilter: 'blur(16px)' }}
    >
      {/* Spinner rings */}
      <div className="relative w-24 h-24 mb-8">
        {[0, 1, 2].map(i => (
          <motion.div
            key={i}
            animate={{ rotate: 360 }}
            transition={{ duration: 1.8 + i * 0.4, repeat: Infinity, ease: 'linear', delay: i * 0.15 }}
            className="absolute inset-0 rounded-full border-2"
            style={{
              borderColor: i === 0 ? '#6C4CF1' : i === 1 ? '#06b6d4' : '#22C55E',
              borderTopColor: 'transparent',
              opacity: 1 - i * 0.25,
              inset: `${i * 10}px`,
            }}
          />
        ))}
        <div className="absolute inset-0 flex items-center justify-center text-3xl">
          {STEPS_META[idx]?.emoji || '⚙️'}
        </div>
      </div>

      {/* Text */}
      <h3 className="text-xl font-bold text-ink mb-2">Processing…</h3>
      <p className="text-ink-muted text-sm max-w-xs text-center">
        {loadingMsg || MESSAGES[step] || 'Working on it…'}
      </p>

      {/* Step dots */}
      <div className="flex items-center gap-2 mt-8">
        {STEPS_META.slice(0, 4).map((s, i) => (
          <React.Fragment key={s.id}>
            <div
              className={`w-2 h-2 rounded-full transition-all duration-300 ${
                i <= idx ? 'bg-primary scale-110' : 'bg-ink-faint'
              }`}
            />
            {i < 3 && (
              <div className={`w-8 h-px transition-colors duration-300 ${i < idx ? 'bg-primary' : 'bg-ink-faint'}`} />
            )}
          </React.Fragment>
        ))}
      </div>
      <p className="text-[11px] text-ink-subtle mt-3">
        Step {Math.max(idx + 1, 1)} of {STEPS_META.length - 1}
      </p>
    </motion.div>
  );
}
