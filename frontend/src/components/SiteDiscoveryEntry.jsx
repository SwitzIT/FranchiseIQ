import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Compass, MapPin, ChevronRight, Loader2, Building2 } from 'lucide-react';
import useAppStore from '../store/useAppStore';
import { getAvailableTerritories, analyseTerritory } from '../services/api';

/**
 * Site Discovery Entry
 * ────────────────────
 * Entry screen for the "I want to enter a new market" use case.
 * Tenant picks country + city/state from a dropdown — no upload required.
 *
 * Once a territory is selected and analysed, results flow into the same
 * dashboard, but with the layers adapted (no performance heatmap since
 * there are no existing stores; untapped demand + competitor density are
 * the headline layers).
 */
export default function SiteDiscoveryEntry() {
  const {
    sessionId, country,
    availableTerritories, setAvailableTerritories,
    selectedTerritory, setSelectedTerritory,
    setSiteDiscoveryResult, setMode, setStep,
  } = useAppStore();

  const [loadingTerritories, setLoadingTerritories] = useState(false);
  const [analysing, setAnalysing] = useState(false);
  const [error, setError] = useState(null);

  // Load territory list on mount
  useEffect(() => {
    let cancelled = false;
    setLoadingTerritories(true);
    getAvailableTerritories(country)
      .then((data) => { if (!cancelled) setAvailableTerritories(data); })
      .catch((e) => { if (!cancelled) setError(`Could not load territories: ${e.message}`); })
      .finally(() => { if (!cancelled) setLoadingTerritories(false); });
    return () => { cancelled = true; };
  }, [country, setAvailableTerritories]);

  const territoriesForCountry = country
    ? (availableTerritories[country] || [])
    : Object.entries(availableTerritories).flatMap(
        ([c, ts]) => ts.map(t => ({ country: c, name: t }))
      );

  const handleAnalyse = async () => {
    if (!sessionId || !country || !selectedTerritory) return;
    setError(null);
    setAnalysing(true);
    try {
      const result = await analyseTerritory(sessionId, country, selectedTerritory);
      setSiteDiscoveryResult(result);
      setMode('site_discovery');
      setStep('dashboard');
    } catch (e) {
      setError(`Analysis failed: ${e.message}`);
    } finally {
      setAnalysing(false);
    }
  };

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
            <Compass size={20} className="text-primary" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-ink">Site Discovery</h2>
            <p className="text-xs text-ink-muted">
              Analyse a new market before you enter — no sales data required
            </p>
          </div>
        </div>
      </div>

      {/* Body */}
      <div className="p-6 space-y-4">
        <div>
          <label className="block text-xs font-semibold text-ink-muted mb-2 uppercase tracking-wider">
            Territory
          </label>
          {loadingTerritories ? (
            <div className="flex items-center gap-2 text-sm text-ink-subtle">
              <Loader2 size={14} className="animate-spin" />
              Loading available territories…
            </div>
          ) : (
            <select
              value={selectedTerritory || ''}
              onChange={(e) => setSelectedTerritory(e.target.value || null)}
              className="w-full px-4 py-2.5 rounded-lg border border-border bg-surface text-sm text-ink focus:outline-none focus:border-primary/50 focus:ring-2 focus:ring-primary/15"
            >
              <option value="">— Select a city or state —</option>
              {country
                ? territoriesForCountry.map(t => (
                    <option key={t} value={t}>{t}</option>
                  ))
                : territoriesForCountry.map(({ country: c, name }) => (
                    <option key={`${c}:${name}`} value={name}>{c} · {name}</option>
                  ))
              }
            </select>
          )}
        </div>

        {/* What you'll get */}
        <div className="rounded-lg border border-border bg-app-bg/40 p-3 space-y-1.5">
          <div className="text-[10px] font-bold text-ink-subtle uppercase tracking-wider">
            Site Discovery delivers
          </div>
          <ul className="space-y-1 text-xs text-ink-muted">
            <li className="flex items-center gap-2">
              <MapPin size={11} className="text-primary shrink-0" />
              Untapped demand hexes (high population × low competition)
            </li>
            <li className="flex items-center gap-2">
              <Building2 size={11} className="text-primary shrink-0" />
              Competitor density across the territory
            </li>
            <li className="flex items-center gap-2">
              <Compass size={11} className="text-primary shrink-0" />
              Demographic context layer
            </li>
          </ul>
        </div>

        {error && (
          <div className="rounded-lg border border-danger/30 bg-danger/5 p-3 text-xs text-danger">
            {error}
          </div>
        )}

        <button
          onClick={handleAnalyse}
          disabled={!selectedTerritory || analysing || !sessionId}
          className={`
            w-full px-4 py-3 rounded-xl font-semibold text-sm
            flex items-center justify-center gap-2 transition-all
            ${(!selectedTerritory || analysing || !sessionId)
              ? 'bg-ink-faint/30 text-ink-subtle cursor-not-allowed'
              : 'bg-primary text-white hover:bg-primary-dark shadow-card'}
          `}
        >
          {analysing ? (
            <>
              <Loader2 size={15} className="animate-spin" />
              Analysing {selectedTerritory}…
            </>
          ) : (
            <>
              Analyse {selectedTerritory || 'territory'}
              <ChevronRight size={15} />
            </>
          )}
        </button>
      </div>
    </motion.div>
  );
}
