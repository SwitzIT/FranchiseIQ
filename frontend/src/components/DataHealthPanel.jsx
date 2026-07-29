import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ShieldCheck, ShieldAlert, ShieldX, AlertTriangle,
  ChevronDown, ChevronUp, X, CheckCircle2, CircleAlert
} from 'lucide-react';
import useAppStore from '../store/useAppStore';

/**
 * Data Health Panel
 * ─────────────────
 * Renders the data-validation report (from POST /api/validate-stores or
 * GET /api/validate-session). Three visual zones:
 *
 *   1. Health score badge (0-100) with severity-coloured ring
 *   2. Hard errors list (if any) — blocks ingestion, must be fixed
 *   3. Soft warnings list (collapsible)
 *
 * The panel is dismissable but auto-shows when validation runs.
 */
export default function DataHealthPanel({ floating = false }) {
  const {
    validationReport: report,
    showValidationPanel, setShowValidationPanel,
  } = useAppStore();

  const [warningsOpen, setWarningsOpen] = useState(false);
  const [coverageOpen, setCoverageOpen] = useState(false);

  if (!report || !showValidationPanel) return null;

  const score = report.health_score ?? 0;
  const passed = report.passed;
  const errorCount = report.errors?.length || 0;
  const warningCount = report.warnings?.length || 0;

  // Health colour: red < 60, amber 60-85, green > 85
  const healthColor =
    score >= 85 ? '#22C55E' :
    score >= 60 ? '#F59E0B' :
    '#EF4444';

  const HealthIcon = passed && score >= 85 ? ShieldCheck :
                     passed ? ShieldAlert : ShieldX;

  // Container varies between floating modal-style and inline panel
  const containerClass = floating
    ? "fixed top-20 right-5 z-[2000] w-96 max-w-[95vw] bg-white rounded-2xl shadow-card-lg border border-border overflow-hidden"
    : "w-full bg-white rounded-2xl shadow-card border border-border overflow-hidden";

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -8 }}
        className={containerClass}
      >
        {/* Header */}
        <div className="flex items-center gap-3 p-4 border-b border-border">
          <div
            className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0"
            style={{ backgroundColor: healthColor + '18', color: healthColor }}
          >
            <HealthIcon size={22} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-baseline gap-2">
              <span className="text-xl font-bold tabular-nums" style={{ color: healthColor }}>
                {score.toFixed(0)}
              </span>
              <span className="text-[10px] font-semibold text-ink-subtle uppercase tracking-widest">
                Data Health
              </span>
            </div>
            <p className="text-xs text-ink-muted mt-0.5 truncate">{report.summary}</p>
          </div>
          <button
            onClick={() => setShowValidationPanel(false)}
            className="p-1 rounded hover:bg-app-bg transition-colors shrink-0"
          >
            <X size={14} className="text-ink-subtle" />
          </button>
        </div>

        {/* Body */}
        <div className="p-3 space-y-2 max-h-[60vh] overflow-y-auto">

          {/* Hard errors — always shown if present */}
          {errorCount > 0 && (
            <div className="rounded-lg border border-danger/30 bg-danger/5 p-3">
              <div className="flex items-center gap-2 mb-1.5">
                <ShieldX size={14} className="text-danger" />
                <span className="text-xs font-bold text-danger">
                  {errorCount} hard error{errorCount !== 1 ? 's' : ''} — fix before proceeding
                </span>
              </div>
              <ul className="space-y-1 mt-1.5">
                {report.errors.slice(0, 10).map((e, i) => (
                  <li key={i} className="text-[11px] text-ink-muted flex gap-2">
                    <span className="font-mono text-ink-subtle shrink-0">[{e.id}]</span>
                    <span>{e.issue}</span>
                  </li>
                ))}
                {errorCount > 10 && (
                  <li className="text-[10px] text-ink-subtle italic">…and {errorCount - 10} more</li>
                )}
              </ul>
            </div>
          )}

          {/* Soft warnings — collapsible */}
          {warningCount > 0 && (
            <div className="rounded-lg border border-warning/30 bg-warning/5 p-3">
              <button
                onClick={() => setWarningsOpen(v => !v)}
                className="w-full flex items-center justify-between gap-2 text-left"
              >
                <span className="flex items-center gap-2 text-xs font-bold text-warning">
                  <AlertTriangle size={14} />
                  {warningCount} warning{warningCount !== 1 ? 's' : ''} (proceed with notice)
                </span>
                {warningsOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </button>
              {warningsOpen && (
                <ul className="space-y-1 mt-2">
                  {report.warnings.slice(0, 20).map((w, i) => (
                    <li key={i} className="text-[11px] text-ink-muted flex gap-2">
                      <span className={`shrink-0 mt-0.5 ${
                        w.severity === 'high' ? 'text-danger' :
                        w.severity === 'medium' ? 'text-warning' :
                        'text-ink-subtle'
                      }`}>
                        ●
                      </span>
                      <span className="font-mono text-ink-subtle shrink-0">[{w.id}]</span>
                      <span>{w.issue}</span>
                    </li>
                  ))}
                  {warningCount > 20 && (
                    <li className="text-[10px] text-ink-subtle italic">
                      …and {warningCount - 20} more
                    </li>
                  )}
                </ul>
              )}
            </div>
          )}

          {/* All good */}
          {errorCount === 0 && warningCount === 0 && (
            <div className="rounded-lg border border-success/30 bg-success/5 p-3 flex items-center gap-2">
              <CheckCircle2 size={16} className="text-success" />
              <span className="text-xs font-medium text-success">
                All {report.row_count} rows passed validation cleanly.
              </span>
            </div>
          )}

          {/* Field coverage */}
          {report.field_coverage && Object.keys(report.field_coverage).length > 0 && (
            <div className="rounded-lg border border-border bg-app-bg/40 p-3">
              <button
                onClick={() => setCoverageOpen(v => !v)}
                className="w-full flex items-center justify-between gap-2"
              >
                <span className="flex items-center gap-2 text-[10px] font-bold text-ink-subtle uppercase tracking-wider">
                  Field coverage
                </span>
                {coverageOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              </button>
              {coverageOpen && (
                <div className="space-y-1 mt-2">
                  {Object.entries(report.field_coverage).map(([field, pct]) => (
                    <div key={field} className="flex items-center gap-2">
                      <span className="text-[11px] text-ink-muted w-20 truncate">{field}</span>
                      <div className="flex-1 h-1.5 bg-ink-faint/30 rounded-full overflow-hidden">
                        <div className="h-full rounded-full"
                             style={{
                               width: `${pct}%`,
                               backgroundColor:
                                 pct >= 80 ? '#22C55E' :
                                 pct >= 50 ? '#F59E0B' :
                                 '#EF4444',
                             }} />
                      </div>
                      <span className="text-[10px] font-mono text-ink-subtle w-10 text-right tabular-nums">
                        {pct.toFixed(0)}%
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Footer summary */}
          <div className="text-[10px] text-ink-subtle text-center pt-1">
            {report.row_count} rows · {report.valid_count} valid · score {score.toFixed(1)}/100
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
