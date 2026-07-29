import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Globe, ChevronRight, Sparkles, Database } from 'lucide-react';
import toast from 'react-hot-toast';
import useAppStore from '../store/useAppStore';
import { selectState } from '../services/api';
import CountrySelector from '../components/CountrySelector';
import DataPreview from '../components/DataPreview';

const STEP_ORDER = ['country', 'state', 'configure'];

function StepProgress({ current }) {
  const steps = [
    { id: 'country',     label: 'Country' },
    { id: 'state',       label: 'State' },
    { id: 'configure',   label: 'Configure' },
  ];
  const ci = steps.findIndex(s => s.id === current);
  return (
    <div className="flex items-center gap-0 mb-12">
      {steps.map((s, i) => (
        <React.Fragment key={s.id}>
          <div className="flex flex-col items-center">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold
                            transition-all duration-300 border
                            ${i < ci  ? 'bg-purple border-purple text-white'
                            : i === ci ? 'border-purple-light text-purple-light bg-purple/10 shadow-glow-sm'
                            : 'border-white/10 text-slate-600 bg-white/[0.02]'}`}>
              {i < ci ? '✓' : i + 1}
            </div>
            <span className={`text-[10px] mt-1.5 font-medium
                              ${i === ci ? 'text-purple-light' : i < ci ? 'text-slate-400' : 'text-slate-700'}`}>
              {s.label}
            </span>
          </div>
          {i < steps.length - 1 && (
            <div className={`flex-1 h-px mx-1 transition-colors duration-300
                            ${i < ci ? 'bg-purple' : 'bg-white/10'}`} />
          )}
        </React.Fragment>
      ))}
    </div>
  );
}

function StateSelector() {
  const { sessionId, availableStates, country, setState, setStep, setLoading } = useAppStore();
  const [selected, setSelected] = useState(null);
  const [busy, setBusy] = useState(false);

  async function handleSelect() {
    if (!selected) return;
    setBusy(true); setLoading(true, 'Loading state configuration…');
    try {
      const data = await selectState(sessionId, selected);
      setState(selected, data);
      setStep('configure');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to select state');
    } finally { setBusy(false); setLoading(false); }
  }

  return (
    <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }} className="max-w-xl mx-auto">
      <div className="text-center mb-10">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-semibold
                        bg-purple/10 border border-purple/30 text-purple-light mb-4">
          <Database size={12} /> Step 2 of 5 — Select State
        </div>
        <h2 className="text-3xl font-bold text-white mb-2">Choose State / Region</h2>
        <p className="text-slate-400 text-sm">
          Select the state where you want to analyse franchise opportunities in {country}.
        </p>
      </div>

      <div className="space-y-3 mb-8">
        {(availableStates || []).map(s => (
          <motion.button key={s.name} whileHover={{ scale: 1.01 }} whileTap={{ scale: 0.99 }}
            onClick={() => s.has_data && setSelected(s.name)}
            disabled={!s.has_data}
            className={`w-full flex items-center gap-4 p-5 rounded-xl border text-left
                        transition-all duration-200
                        ${selected === s.name
                          ? 'border-purple bg-purple/10 shadow-glow-sm'
                          : s.has_data
                            ? 'border-white/8 bg-white/[0.03] hover:border-purple/40 hover:bg-white/[0.06]'
                            : 'border-white/5 bg-white/[0.01] opacity-40 cursor-not-allowed'
                        }`}>
            <Globe size={24} className={selected === s.name ? 'text-purple-light' : 'text-slate-600'} />
            <div>
              <p className="font-bold text-white">{s.name}</p>
              <p className="text-xs text-slate-500 mt-0.5">
                {s.has_data ? '✅ Demographics data available' : '⚠️ No demographics data'}
              </p>
            </div>
            <ChevronRight size={16} className="ml-auto text-slate-600" />
          </motion.button>
        ))}
      </div>

      <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
        disabled={!selected || busy} onClick={handleSelect}
        className="btn-primary w-full py-3 text-base flex items-center justify-center gap-2">
        {busy ? 'Loading…' : `Continue with ${selected || '—'}`}
      </motion.button>
    </motion.div>
  );
}

export default function HomePage() {
  const step = useAppStore(s => s.step);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-6 py-12 relative">
      {/* Background glow */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-purple/8 rounded-full blur-[120px]" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-cyan/6 rounded-full blur-[120px]" />
      </div>

      {/* Logo */}
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}
        className="text-center mb-10 relative">
        <div className="inline-flex items-center gap-3 mb-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple to-cyan
                          flex items-center justify-center shadow-glow-md">
            <Sparkles size={20} className="text-white" />
          </div>
          <h1 className="text-2xl font-black neon-text">FranchiseIQ</h1>
        </div>
        <p className="text-slate-500 text-xs font-medium tracking-widest uppercase">
          Location Intelligence Platform
        </p>
      </motion.div>

      {/* Step progress */}
      {STEP_ORDER.includes(step) && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="w-full max-w-xl">
          <StepProgress current={step} />
        </motion.div>
      )}

      {/* Step content */}
      <div className="w-full max-w-xl relative z-10">
        <AnimatePresence mode="wait">
          {step === 'country'   && <CountrySelector key="country" />}
          {step === 'state'     && <StateSelector   key="state" />}
          {step === 'configure' && <DataPreview     key="configure" />}
        </AnimatePresence>
      </div>
    </div>
  );
}
