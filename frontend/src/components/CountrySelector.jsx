import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Globe, ChevronRight, Sparkles } from 'lucide-react';
import toast from 'react-hot-toast';
import useAppStore from '../store/useAppStore';
import { getCountries, selectCountry } from '../services/api';

const FLAG = { India: '🇮🇳', 'Sri Lanka': '🇱🇰' };
const DESCRIPTION = {
  India:      'West Bengal & Odisha — two high-growth eastern states',
  'Sri Lanka':'Nationwide analytics across the island nation',
};

export default function CountrySelector() {
  const [countries, setCountries] = useState([]);
  const [selected, setSelected] = useState(null);
  const [busy, setBusy] = useState(false);
  const { setSessionId, setCountry, setStep, setLoading } = useAppStore();

  useEffect(() => {
    getCountries()
      .then(d => setCountries(d.countries || []))
      .catch(() => toast.error('Could not load countries from server'));
  }, []);

  async function handleSelect() {
    if (!selected) return;
    setBusy(true);
    setLoading(true, 'Connecting to data pipeline…');
    try {
      const data = await selectCountry(selected);
      setSessionId(data.session_id);
      setCountry(selected, data.states, data.currency_symbol, data.currency_code);
      setStep('state');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to select country');
    } finally {
      setBusy(false);
      setLoading(false);
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="max-w-xl mx-auto"
    >
      {/* Header */}
      <div className="text-center mb-10">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-semibold
                        bg-purple/10 border border-purple/30 text-purple-light mb-4">
          <Sparkles size={12} /> Step 1 of 5 — Select Market
        </div>
        <h2 className="text-3xl font-bold text-white mb-2">Choose Your Country</h2>
        <p className="text-slate-400 text-sm">
          Select the market where you want to run franchise intelligence analysis.
        </p>
      </div>

      {/* Country Cards */}
      <div className="space-y-3 mb-8">
        {countries.map((c) => (
          <motion.button
            key={c.name}
            whileHover={{ scale: 1.01 }}
            whileTap={{ scale: 0.99 }}
            onClick={() => setSelected(c.name)}
            className={`w-full flex items-center gap-4 p-5 rounded-xl border text-left
                        transition-all duration-200 group
                        ${selected === c.name
                          ? 'border-purple bg-purple/10 shadow-glow-sm'
                          : 'border-white/8 bg-white/[0.03] hover:border-purple/40 hover:bg-white/[0.06]'
                        }`}
          >
            <span className="text-4xl">{FLAG[c.name] || '🌍'}</span>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <span className="font-bold text-white text-lg">{c.name}</span>
                <span className="text-xs text-slate-500 font-mono">[{c.code}]</span>
              </div>
              <p className="text-slate-400 text-xs">{DESCRIPTION[c.name]}</p>
              <div className="flex gap-1 mt-2">
                {(c.states || []).map(s => (
                  <span key={s.name}
                    className={`text-[10px] px-2 py-0.5 rounded-full font-medium
                                ${s.has_data ? 'bg-green/20 text-green border border-green/30'
                                             : 'bg-white/5 text-slate-500 border border-white/8'}`}>
                    {s.name} {s.has_data ? '✓' : '—'}
                  </span>
                ))}
              </div>
            </div>
            <ChevronRight size={18}
              className={`transition-colors ${selected === c.name ? 'text-purple-light' : 'text-slate-600 group-hover:text-slate-400'}`} />
          </motion.button>
        ))}
      </div>

      <motion.button
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        disabled={!selected || busy}
        onClick={handleSelect}
        className="btn-primary w-full flex items-center justify-center gap-2 py-3 text-base"
      >
        <Globe size={18} />
        {busy ? 'Connecting…' : `Continue with ${selected || '—'}`}
      </motion.button>
    </motion.div>
  );
}
