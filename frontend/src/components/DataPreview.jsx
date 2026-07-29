import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Database, HelpCircle, AlertCircle, Play, CheckCircle, Sparkles, Sliders } from 'lucide-react';
import toast from 'react-hot-toast';
import useAppStore from '../store/useAppStore';
import { loadPreloaded, fetchAmenities, runPrediction, getRegionKpis } from '../services/api';

export default function DataPreview() {
  const { sessionId, country, state, setDataStats, setAmenitiesInfo, setHasBU, setResults, setStep, setLoading } = useAppStore();
  const [stats, setStats] = useState(null);
  const [loadingData, setLoadingData] = useState(true);
  const [topN, setTopN] = useState(10);
  const [busy, setBusy] = useState(false);
  const [phase, setPhase] = useState('idle'); // idle | amenities | predicting

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const res = await loadPreloaded(sessionId);
        if (active) {
          setStats(res);
          setDataStats(res);
          setHasBU(res.has_bu);
          setLoadingData(false);
        }
      } catch (err) {
        if (active) {
          toast.error(err?.response?.data?.detail || 'Failed to load preloaded data files.');
          setLoadingData(false);
        }
      }
    }
    load();
    return () => { active = false; };
  }, [sessionId, setDataStats, setHasBU]);

  async function handleRunPipeline() {
    setBusy(true);
    
    // Phase 1: Fetch Amenities
    setPhase('amenities');
    setLoading(true, `Fetching local amenities for ${state}…`);
    try {
      const amenRes = await fetchAmenities(sessionId);
      setAmenitiesInfo(amenRes);
      toast.success(
        amenRes.was_cached
          ? `Local amenities loaded (${amenRes.amenities_count.toLocaleString()} POIs)`
          : `Fetched ${amenRes.amenities_count.toLocaleString()} amenities via OSMnx`
      );

      // Phase 2: Run Prediction
      setPhase('predicting');
      setLoading(true, `Running location intelligence model with top ${topN} picks…`);
      const predRes = await runPrediction(sessionId, topN);
      setResults(predRes);
      
      // Phase 3: Fetch Region KPIs
      const regionKpis = await getRegionKpis(sessionId);
      useAppStore.getState().setRegionKpis(regionKpis);
      
      toast.success(`Pipeline executed successfully!`);
      
      // Step 3: Transition to Dashboard
      setStep('dashboard');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Pipeline execution failed.');
    } finally {
      setBusy(false);
      setPhase('idle');
      setLoading(false);
    }
  }

  if (loadingData) {
    return (
      <div className="max-w-xl mx-auto glass-card p-10 text-center flex flex-col items-center justify-center min-h-[300px]">
        <div className="w-10 h-10 border-4 border-purple border-t-transparent rounded-full animate-spin mb-4" />
        <h3 className="text-lg font-bold text-white mb-2">Analyzing Backend Data Assets…</h3>
        <p className="text-slate-400 text-xs">Locating stores, logistics hubs, and demographics for {state}.</p>
      </div>
    );
  }

  return (
    <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }} className="max-w-xl mx-auto">

      <div className="text-center mb-8">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-semibold
                        bg-purple/10 border border-purple/30 text-purple-light mb-4">
          <Sparkles size={12} /> Step 3 of 3 — Configure & Run
        </div>
        <h2 className="text-3xl font-bold text-white mb-2">Verify Datasets</h2>
        <p className="text-slate-400 text-sm">
          All data files for <span className="text-purple-light font-semibold">{state} ({country})</span> have been loaded from the server's workspace downloads repository.
        </p>
      </div>

      {stats && (
        <div className="space-y-4 mb-6">
          {/* Loaded Files Card */}
          <div className="glass-card p-5 border-white/10 space-y-3.5">
            <div className="flex items-center gap-2 border-b border-white/8 pb-3">
              <Database size={15} className="text-purple-light" />
              <h3 className="text-xs font-black text-slate-300 uppercase tracking-widest">Active State Datasets</h3>
            </div>
            
            <div className="space-y-2.5">
              {/* Stores */}
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-400">🏪 Existing Franchise Stores</span>
                <span className="text-xs font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-0.5 rounded-full">
                  {stats.n_stores} loaded
                </span>
              </div>

              {/* Requests */}
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-400">📩 Expansion Request Locations</span>
                {stats.n_requests > 0 ? (
                  <span className="text-xs font-bold text-cyan bg-cyan/10 border border-cyan/20 px-2.5 py-0.5 rounded-full">
                    {stats.n_requests} loaded
                  </span>
                ) : (
                  <span className="text-xs font-bold text-amber bg-amber/10 border border-amber/20 px-2.5 py-0.5 rounded-full">
                    None (Grid Mode)
                  </span>
                )}
              </div>

              {/* Business Units */}
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-400">🏭 Central Kitchens & BUs</span>
                {stats.n_bu > 0 ? (
                  <span className="text-xs font-bold text-purple-light bg-purple/10 border border-purple/20 px-2.5 py-0.5 rounded-full">
                    {stats.n_bu} loaded
                  </span>
                ) : (
                  <span className="text-[10px] text-slate-500">None Configured</span>
                )}
              </div>

              {/* Demographics */}
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-400">👥 Demographic Reference Nodes</span>
                <span className="text-xs font-bold text-slate-300 bg-white/[0.06] border border-white/10 px-2.5 py-0.5 rounded-full">
                  {stats.n_demographics.toLocaleString()} nodes
                </span>
              </div>
            </div>

            {stats.n_requests === 0 && (
              <div className="flex items-start gap-2 p-2.5 rounded-lg bg-amber/5 border border-amber/15 mt-3">
                <AlertCircle size={14} className="text-amber shrink-0 mt-0.5" />
                <p className="text-[10px] text-amber/80 leading-normal">
                  No request list is preloaded. FranchiseIQ will auto-generate candidate analysis grids over key population clusters in {state}.
                </p>
              </div>
            )}
          </div>

          {/* Model Config Panel */}
          <div className="glass-card p-5 border-white/10 space-y-4">
            <div className="flex items-center gap-2 border-b border-white/8 pb-3">
              <Sliders size={15} className="text-purple-light" />
              <h3 className="text-xs font-black text-slate-300 uppercase tracking-widest">Model Settings</h3>
            </div>
            
            <div className="space-y-2">
              <div className="flex justify-between items-center text-xs">
                <span className="text-slate-400 font-medium">Top Pick Candidates</span>
                <span className="text-purple-light font-black">{topN} picks</span>
              </div>
              <input 
                type="range" 
                min="5" 
                max="50" 
                step="5" 
                value={topN} 
                onChange={(e) => setTopN(parseInt(e.target.value))}
                className="w-full h-1.5 bg-white/10 rounded-lg appearance-none cursor-pointer accent-purple-light"
              />
              <div className="flex justify-between text-[9px] text-slate-600 font-bold">
                <span>5</span>
                <span>25</span>
                <span>50</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Busy status panel */}
      <AnimatePresence>
        {busy && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }} className="mb-5">
            <div className="glass-card p-4 flex items-center gap-3 border-purple/30">
              <div className="w-8 h-8 rounded-full border-2 border-purple border-t-transparent animate-spin" />
              <div>
                <p className="text-sm font-semibold text-white">
                  {phase === 'amenities' ? `Retrieving Local Amenities for ${state}…` : 'Executing Machine Learning Predictions…'}
                </p>
                <p className="text-xs text-slate-500 mt-0.5">
                  {phase === 'amenities' && 'Using cache if available, else querying OpenStreetMap via OSMnx.'}
                  {phase === 'predicting' && 'Training Random Forest regressor on store performance attributes.'}
                </p>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
        disabled={busy} onClick={handleRunPipeline}
        className="btn-primary w-full flex items-center justify-center gap-2 py-3 text-base">
        <Play size={18} fill="currentColor" />
        {busy ? 'Running intelligence engine…' : 'Run Location Intelligence Pipeline'}
      </motion.button>
    </motion.div>
  );
}
