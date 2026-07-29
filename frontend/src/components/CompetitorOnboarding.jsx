import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  Target, Check, X, Plus, Loader2, AlertCircle, RefreshCw
} from 'lucide-react';
import useAppStore from '../store/useAppStore';
import {
  getSuggestedCompetitors, initializeCompetitors,
  refreshCompetitorLocations,
} from '../services/api';

/**
 * Competitor Onboarding (option c flow)
 * ─────────────────────────────────────
 * After country/state/category selection, this lets the tenant:
 *   1. See the platform's pre-filled competitor suggestions for their
 *      (country, category) combination
 *   2. Toggle suggestions off (uncheck a brand they don't consider a rival)
 *   3. Add custom competitors not in the template
 *   4. Save the final list to the session
 *   5. Optionally trigger an immediate Places API fetch for locations
 *      (the monthly cron also does this in background)
 */
export default function CompetitorOnboarding({ onComplete }) {
  const {
    sessionId, country, category,
    competitors, setCompetitors,
    setCompetitorRefreshLoading, competitorRefreshLoading,
  } = useAppStore();

  const [suggestions, setSuggestions] = useState([]);  // [string]
  const [selectedSet, setSelectedSet] = useState(new Set()); // Set<string>
  const [customAdds, setCustomAdds] = useState([]);    // [string]
  const [customInput, setCustomInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  // Load suggested competitors for (country, category)
  useEffect(() => {
    if (!country || !category) return;
    let cancelled = false;
    setLoading(true);

    getSuggestedCompetitors(country, category)
      .then((data) => {
        if (cancelled) return;
        setSuggestions(data.suggestions || []);
        // Start with all suggestions selected (option c default)
        setSelectedSet(new Set(data.suggestions || []));
      })
      .catch((e) => { if (!cancelled) setError(`Could not load suggestions: ${e.message}`); })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [country, category]);

  const toggleSuggestion = (name) => {
    const next = new Set(selectedSet);
    if (next.has(name)) next.delete(name);
    else next.add(name);
    setSelectedSet(next);
  };

  const addCustom = () => {
    const trimmed = customInput.trim();
    if (!trimmed) return;
    if (customAdds.includes(trimmed) || suggestions.includes(trimmed)) {
      setCustomInput('');
      return;
    }
    setCustomAdds([...customAdds, trimmed]);
    setSelectedSet(new Set([...selectedSet, trimmed]));
    setCustomInput('');
  };

  const removeCustom = (name) => {
    setCustomAdds(customAdds.filter(c => c !== name));
    const next = new Set(selectedSet);
    next.delete(name);
    setSelectedSet(next);
  };

  const handleSave = async (alsoFetchLocations = false) => {
    if (!sessionId) return;
    setSaving(true);
    setError(null);
    try {
      // Combine suggestions + customs, but only those checked
      const customsToSend = customAdds.filter(c => selectedSet.has(c));
      const result = await initializeCompetitors(
        sessionId, country, category, customsToSend,
      );
      // Apply selection state on top of returned brand list
      const branded = result.brands.map(b => ({
        ...b, selected: selectedSet.has(b.name),
      }));
      setCompetitors(branded);

      if (alsoFetchLocations) {
        setCompetitorRefreshLoading(true);
        try {
          const refreshed = await refreshCompetitorLocations(sessionId);
          setCompetitors(refreshed.brands);
        } catch (e) {
          console.warn('Location refresh failed (will retry on next cron):', e);
        } finally {
          setCompetitorRefreshLoading(false);
        }
      }

      if (onComplete) onComplete();
    } catch (e) {
      setError(`Save failed: ${e.message}`);
    } finally {
      setSaving(false);
    }
  };

  const totalSelected = selectedSet.size;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white rounded-2xl shadow-card border border-border overflow-hidden max-w-2xl w-full"
    >
      {/* Header */}
      <div className="p-6 border-b border-border bg-gradient-to-br from-primary/5 to-transparent">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-xl bg-primary/15 flex items-center justify-center">
            <Target size={20} className="text-primary" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-ink">Configure Competitors</h2>
            <p className="text-xs text-ink-muted">
              {country} · {category} — pick the brands you consider competitive threats
            </p>
          </div>
        </div>
      </div>

      <div className="p-6 space-y-4 max-h-[60vh] overflow-y-auto">

        {/* Suggested brands */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-bold text-ink-subtle uppercase tracking-wider">
              Suggested ({suggestions.length})
            </span>
            <span className="text-[10px] text-ink-subtle">
              {totalSelected} selected
            </span>
          </div>
          {loading ? (
            <div className="flex items-center gap-2 text-sm text-ink-subtle">
              <Loader2 size={14} className="animate-spin" />
              Loading suggested brands…
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-2">
              {suggestions.map(name => {
                const on = selectedSet.has(name);
                return (
                  <button
                    key={name}
                    onClick={() => toggleSuggestion(name)}
                    className={`
                      px-3 py-2 rounded-lg border text-left text-xs flex items-center gap-2
                      transition-all
                      ${on
                        ? 'bg-primary/8 border-primary/40 text-ink'
                        : 'bg-app-bg/40 border-border text-ink-subtle hover:border-ink-faint'}
                    `}
                  >
                    <span className={`w-4 h-4 rounded border flex items-center justify-center shrink-0
                      ${on ? 'bg-primary border-primary' : 'border-ink-faint bg-white'}`}>
                      {on && <Check size={11} className="text-white" />}
                    </span>
                    <span className="truncate">{name}</span>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Custom adds */}
        <div>
          <div className="text-[10px] font-bold text-ink-subtle uppercase tracking-wider mb-2">
            Add a brand not in the list
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              value={customInput}
              onChange={(e) => setCustomInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') addCustom(); }}
              placeholder="e.g. local bakery brand name"
              className="flex-1 px-3 py-2 rounded-lg border border-border bg-surface text-xs focus:outline-none focus:border-primary/50"
            />
            <button
              onClick={addCustom}
              disabled={!customInput.trim()}
              className="px-3 py-2 rounded-lg bg-primary text-white text-xs font-semibold flex items-center gap-1 hover:bg-primary-dark disabled:bg-ink-faint/30 disabled:cursor-not-allowed"
            >
              <Plus size={13} />
              Add
            </button>
          </div>
          {customAdds.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {customAdds.map(name => (
                <span
                  key={name}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-primary/10 text-primary text-[11px] font-medium"
                >
                  {name}
                  <button onClick={() => removeCustom(name)}
                          className="hover:bg-primary/15 rounded-full p-0.5">
                    <X size={10} />
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>

        {error && (
          <div className="rounded-lg border border-danger/30 bg-danger/5 p-3 flex items-start gap-2 text-xs text-danger">
            <AlertCircle size={14} className="shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <div className="rounded-lg border border-border bg-app-bg/40 p-3 text-[11px] text-ink-muted">
          <strong className="text-ink">Heads up:</strong> the platform fetches each
          brand's store locations via Google Places. This runs in the background and
          updates monthly. You can refresh on demand later from the Layers panel.
        </div>
      </div>

      {/* Footer actions */}
      <div className="p-4 border-t border-border bg-app-bg/30 flex gap-2 justify-end">
        <button
          onClick={() => handleSave(false)}
          disabled={saving || totalSelected === 0}
          className="px-4 py-2 rounded-lg border border-border bg-white text-xs font-semibold text-ink hover:border-primary/30 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {saving ? 'Saving…' : 'Save & continue'}
        </button>
        <button
          onClick={() => handleSave(true)}
          disabled={saving || competitorRefreshLoading || totalSelected === 0}
          className="px-4 py-2 rounded-lg bg-primary text-white text-xs font-semibold flex items-center gap-1.5 hover:bg-primary-dark disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {(saving || competitorRefreshLoading) ? (
            <>
              <Loader2 size={13} className="animate-spin" />
              {competitorRefreshLoading ? 'Fetching locations…' : 'Saving…'}
            </>
          ) : (
            <>
              <RefreshCw size={13} />
              Save & fetch locations now
            </>
          )}
        </button>
      </div>
    </motion.div>
  );
}
