import React, { useCallback, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, FileSpreadsheet, X, CheckCircle, Sparkles } from 'lucide-react';
import toast from 'react-hot-toast';
import useAppStore from '../store/useAppStore';
import { loadData, fetchAmenities } from '../services/api';

export default function FileUpload() {
  const { sessionId, country, state, setDataStats, setAmenitiesInfo, setStep, setLoading } = useAppStore();
  const [storesFile, setStoresFile]   = useState(null);
  const [reqFile,    setReqFile]      = useState(null);
  const [busy,       setBusy]         = useState(false);
  const [phase,      setPhase]        = useState('idle'); // idle | uploading | amenities
  const storesRef = useRef();
  const reqRef    = useRef();

  const onDrop = useCallback((e, setter) => {
    e.preventDefault();
    const f = e.dataTransfer?.files?.[0] || e.target.files?.[0];
    if (f) setter(f);
  }, []);

  async function handleSubmit() {
    if (!storesFile) { toast.error('Please upload a Stores file'); return; }
    setBusy(true); setPhase('uploading');
    setLoading(true, 'Uploading and parsing data files…');
    try {
      const dataRes = await loadData(sessionId, storesFile, reqFile);
      setDataStats(dataRes);
      toast.success(`${dataRes.n_stores} stores loaded`);

      // Immediately check / fetch amenities
      setPhase('amenities');
      setLoading(true, 'Checking amenities cache for ' + state + '…');
      const amenRes = await fetchAmenities(sessionId);
      setAmenitiesInfo(amenRes);
      toast.success(
        amenRes.was_cached
          ? `Amenities loaded from cache (${amenRes.amenities_count.toLocaleString()} POIs)`
          : `Fetched ${amenRes.amenities_count.toLocaleString()} amenities via OSMnx`
      );
      setStep('bu_question');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Upload failed');
    } finally {
      setBusy(false); setPhase('idle'); setLoading(false);
    }
  }

  return (
    <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }} className="max-w-2xl mx-auto">

      <div className="text-center mb-8">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-semibold
                        bg-cyan/10 border border-cyan/30 text-cyan mb-4">
          <Sparkles size={12} /> Step 3 of 5 — Upload Data
        </div>
        <h2 className="text-3xl font-bold text-white mb-2">Upload Your Files</h2>
        <p className="text-slate-400 text-sm">
          Franchise stores are required. Request locations are optional but improve predictions.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <DropZone
          label="Franchise Stores"  required
          hint="Store ID, Name, Latitude, Longitude, Sales"
          file={storesFile} setFile={setStoresFile}
          inputRef={storesRef} onDrop={onDrop} color="purple"
        />
        <DropZone
          label="Franchise Requests" required={false}
          hint="Name, Latitude, Longitude"
          file={reqFile} setFile={setReqFile}
          inputRef={reqRef} onDrop={onDrop} color="cyan"
        />
      </div>

      {/* Phase indicator */}
      <AnimatePresence>
        {busy && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }} className="mb-5">
            <div className="glass-card p-4 flex items-center gap-3">
              <div className="w-8 h-8 rounded-full border-2 border-purple border-t-transparent animate-spin" />
              <div>
                <p className="text-sm font-medium text-white">
                  {phase === 'uploading' ? 'Processing data files…' : `Fetching amenities for ${state}…`}
                </p>
                <p className="text-xs text-slate-500 mt-0.5">
                  {phase === 'amenities' && 'This may take a moment if OSMnx fetch is needed.'}
                </p>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
        disabled={!storesFile || busy} onClick={handleSubmit}
        className="btn-primary w-full flex items-center justify-center gap-2 py-3 text-base">
        <Upload size={18} />
        {busy ? (phase === 'amenities' ? 'Fetching Amenities…' : 'Uploading…') : 'Process Data & Continue'}
      </motion.button>
    </motion.div>
  );
}

function DropZone({ label, required, hint, file, setFile, inputRef, onDrop, color }) {
  const [dragOver, setDragOver] = useState(false);
  const colorMap = {
    purple: 'border-purple/60 bg-purple/10',
    cyan:   'border-cyan/60 bg-cyan/10',
  };
  return (
    <div
      onDragOver={e => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={e => { setDragOver(false); onDrop(e, setFile); }}
      onClick={() => !file && inputRef.current?.click()}
      className={`relative rounded-xl border-2 border-dashed p-6 text-center cursor-pointer
                  transition-all duration-200 min-h-[160px] flex flex-col items-center justify-center
                  ${file ? colorMap[color] : dragOver
                    ? 'border-white/30 bg-white/5'
                    : 'border-white/10 bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.04]'
                  }`}
    >
      <input ref={inputRef} type="file" accept=".xlsx,.xls,.csv" className="hidden"
        onChange={e => setFile(e.target.files?.[0])} />

      {file ? (
        <>
          <CheckCircle size={32} className={color === 'purple' ? 'text-purple-light mb-2' : 'text-cyan mb-2'} />
          <p className="font-semibold text-sm text-white truncate max-w-full px-2">{file.name}</p>
          <p className="text-xs text-slate-500 mt-1">{(file.size / 1024).toFixed(1)} KB</p>
          <button onClick={e => { e.stopPropagation(); setFile(null); }}
            className="absolute top-2 right-2 p-1 rounded-full hover:bg-white/10 text-slate-500 hover:text-white transition-colors">
            <X size={14} />
          </button>
        </>
      ) : (
        <>
          <FileSpreadsheet size={32} className="text-slate-600 mb-3" />
          <p className="font-semibold text-sm text-white mb-1">
            {label} {required && <span className="text-rose text-xs">*</span>}
          </p>
          <p className="text-xs text-slate-500">{hint}</p>
          <p className="text-xs text-slate-600 mt-3">Drop file or click to browse</p>
        </>
      )}
    </div>
  );
}
