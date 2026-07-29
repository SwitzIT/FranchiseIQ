import React, { useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Building2, X, Upload, CheckCircle, AlertCircle } from 'lucide-react';
import toast from 'react-hot-toast';
import useAppStore from '../store/useAppStore';
import { uploadBusinessUnits, clearBusinessUnits, runPrediction } from '../services/api';

export default function BusinessUnitModal() {
  const { sessionId, setHasBU, setBUInfo, setResults, setStep, setLoading } = useAppStore();
  const [choice,  setChoice]  = useState(null);  // 'yes' | 'no'
  const [buFile,  setBuFile]  = useState(null);
  const [preview, setPreview] = useState(null);
  const [busy,    setBusy]    = useState(false);
  const fileRef = useRef();

  async function handleContinue() {
    setBusy(true);
    try {
      if (choice === 'yes' && buFile) {
        setLoading(true, 'Processing business unit locations…');
        const buRes = await uploadBusinessUnits(sessionId, buFile);
        setHasBU(true); setBUInfo(buRes); setPreview(buRes.preview);
        toast.success(`${buRes.n_units} business units loaded`);
      } else {
        await clearBusinessUnits(sessionId);
        setHasBU(false);
      }
      // Run prediction immediately
      setStep('predicting');
      setLoading(true, 'Running Random Forest prediction pipeline…');
      const results = await runPrediction(sessionId);
      setResults(results);
      setStep('dashboard');
      toast.success(`Analysis complete — ${results.top_picks?.length || 0} top locations found!`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Prediction failed');
      setStep('bu_question');
    } finally {
      setBusy(false); setLoading(false);
    }
  }

  return (
    <motion.div initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4 }} className="max-w-lg mx-auto">

      <div className="text-center mb-8">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-semibold
                        bg-amber/10 border border-amber/30 text-amber mb-4">
          Step 4 of 5 — Business Units
        </div>
        <h2 className="text-2xl font-bold text-white mb-2">
          Do you have Business Units?
        </h2>
        <p className="text-slate-400 text-sm">
          Central kitchens or distribution hubs influence location scoring
          via distance-based weighting.
        </p>
      </div>

      {/* YES / NO choice */}
      <div className="grid grid-cols-2 gap-3 mb-6">
        {[
          { val: 'yes', label: 'Yes, I have them', sub: 'Upload locations to apply distance weighting', icon: <Building2 size={24} /> },
          { val: 'no',  label: 'No, skip this',    sub: 'Continue with base scoring model',             icon: <AlertCircle size={24} /> },
        ].map(({ val, label, sub, icon }) => (
          <motion.button key={val} whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
            onClick={() => setChoice(val)}
            className={`flex flex-col items-center gap-2 p-5 rounded-xl border text-center transition-all
                        ${choice === val
                          ? val === 'yes'
                            ? 'border-green bg-green/10 shadow-[0_0_20px_rgba(16,185,129,0.2)]'
                            : 'border-slate-500 bg-white/[0.06]'
                          : 'border-white/8 bg-white/[0.03] hover:border-white/20'
                        }`}>
            <span className={choice === val && val === 'yes' ? 'text-green' : 'text-slate-500'}>{icon}</span>
            <p className="font-semibold text-sm text-white">{label}</p>
            <p className="text-xs text-slate-500">{sub}</p>
          </motion.button>
        ))}
      </div>

      {/* BU file upload */}
      <AnimatePresence>
        {choice === 'yes' && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }} className="mb-5 overflow-hidden">
            <div className="glass-card p-4">
              <p className="text-xs text-slate-400 mb-3">
                Required columns: <span className="font-mono text-green">Name, Latitude, Longitude</span>
              </p>
              <input ref={fileRef} type="file" accept=".xlsx,.xls,.csv" className="hidden"
                onChange={e => setBuFile(e.target.files?.[0])} />
              {buFile ? (
                <div className="flex items-center gap-3">
                  <CheckCircle size={18} className="text-green shrink-0" />
                  <span className="text-sm text-white truncate">{buFile.name}</span>
                  <button onClick={() => setBuFile(null)} className="ml-auto text-slate-500 hover:text-white">
                    <X size={16} />
                  </button>
                </div>
              ) : (
                <button onClick={() => fileRef.current?.click()}
                  className="w-full py-3 rounded-lg border border-dashed border-white/15
                             text-sm text-slate-500 hover:border-green/50 hover:text-green
                             flex items-center justify-center gap-2 transition-colors">
                  <Upload size={16} /> Upload Business Units File
                </button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
        disabled={!choice || (choice === 'yes' && !buFile) || busy}
        onClick={handleContinue}
        className="btn-primary w-full py-3 text-base flex items-center justify-center gap-2">
        {busy ? (
          <><div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            Running Analysis…</>
        ) : 'Generate Predictions →'}
      </motion.button>
    </motion.div>
  );
}
