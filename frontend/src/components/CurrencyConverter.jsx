import React, { useEffect, useRef, useState } from 'react';
import { ArrowLeftRight, RefreshCw, X, Check, RotateCcw } from 'lucide-react';
import useAppStore from '../store/useAppStore';

// Live USD rates, fetched in the browser. Tried in order; if every source
// fails the user can type a rate by hand.
const RATE_SOURCES = [
  {
    url: 'https://open.er-api.com/v6/latest/USD',
    parse: (j, code) => ({
      rate: j?.rates?.[code],
      date: j?.time_last_update_utc ? new Date(j.time_last_update_utc) : null,
    }),
  },
  {
    url: 'https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json',
    parse: (j, code) => ({
      rate: j?.usd?.[code.toLowerCase()],
      date: j?.date ? new Date(j.date) : null,
    }),
  },
];

const CACHE_KEY = 'franchiseiq_usd_rates';
const CACHE_TTL_MS = 6 * 60 * 60 * 1000; // 6 hours

function readCache(code) {
  try {
    const all = JSON.parse(sessionStorage.getItem(CACHE_KEY) || '{}');
    const hit = all[code];
    if (hit && Date.now() - hit.fetchedAt < CACHE_TTL_MS) {
      return { rate: hit.rate, date: hit.date ? new Date(hit.date) : null };
    }
  } catch { /* storage unavailable */ }
  return null;
}

function writeCache(code, rate, date) {
  try {
    const all = JSON.parse(sessionStorage.getItem(CACHE_KEY) || '{}');
    all[code] = { rate, date: date ? date.toISOString() : null, fetchedAt: Date.now() };
    sessionStorage.setItem(CACHE_KEY, JSON.stringify(all));
  } catch { /* storage unavailable */ }
}

async function fetchUsdRate(code) {
  for (const src of RATE_SOURCES) {
    try {
      const res = await fetch(src.url);
      if (!res.ok) continue;
      const { rate, date } = src.parse(await res.json(), code);
      if (Number.isFinite(rate) && rate > 0) return { rate, date };
    } catch { /* try next source */ }
  }
  throw new Error('No exchange-rate source reachable');
}

// Keep up to 2 decimals, drop trailing zeros; empty stays empty.
const round2 = (n) => (Number.isFinite(n) ? String(Math.round(n * 100) / 100) : '');

export default function CurrencyConverter() {
  const { currencyCode, currencySymbol, country, displayCurrency, usdRate, setDisplayCurrency } = useAppStore();
  const showingUsd = displayCurrency === 'USD' && usdRate > 0;
  const code = (currencyCode || '').toUpperCase();

  const [open, setOpen] = useState(false);
  const [rate, setRate] = useState(null);        // local units per 1 USD
  const [rateDate, setRateDate] = useState(null);
  const [status, setStatus] = useState('idle');  // idle | loading | ok | error
  const [manualRate, setManualRate] = useState('');
  const [usd, setUsd] = useState('1');
  const [local, setLocal] = useState('');
  const wrapRef = useRef(null);

  const effectiveRate = parseFloat(manualRate) > 0 ? parseFloat(manualRate) : rate;

  const loadRate = async (force = false) => {
    if (!code) return;
    const cached = !force && readCache(code);
    if (cached) {
      setRate(cached.rate); setRateDate(cached.date); setStatus('ok');
      return;
    }
    setStatus('loading');
    try {
      const { rate: r, date } = await fetchUsdRate(code);
      setRate(r); setRateDate(date); setStatus('ok');
      writeCache(code, r, date);
    } catch {
      setStatus('error');
    }
  };

  // New country → forget the old rate and inputs.
  useEffect(() => {
    setRate(null); setRateDate(null); setStatus('idle');
    setManualRate(''); setUsd('1'); setLocal('');
  }, [code]);

  // Fetch when the popover first opens or the country changes.
  useEffect(() => {
    if (open && code && rate == null && status === 'idle') loadRate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, code, rate, status]);

  // Recompute the local amount whenever the rate changes.
  useEffect(() => {
    if (effectiveRate && usd !== '') setLocal(round2(parseFloat(usd) * effectiveRate));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effectiveRate]);

  // Close on outside click.
  useEffect(() => {
    const onDown = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, []);

  // Nothing to convert until a non-USD country is selected.
  if (!code || code === 'USD') return null;

  const onUsdChange = (v) => {
    setUsd(v);
    const n = parseFloat(v);
    setLocal(effectiveRate && Number.isFinite(n) ? round2(n * effectiveRate) : '');
  };

  const onLocalChange = (v) => {
    setLocal(v);
    const n = parseFloat(v);
    setUsd(effectiveRate && Number.isFinite(n) ? round2(n / effectiveRate) : '');
  };

  const inputCls = 'w-full text-sm font-semibold tabular-nums px-3 py-2 rounded-lg border border-border bg-white ' +
    'focus:outline-none focus:border-primary/50 focus:ring-2 focus:ring-primary/10';

  return (
    <div ref={wrapRef} className="relative shrink-0">
      <button
        onClick={() => setOpen(v => !v)}
        className={`filter-pill ${open ? 'active' : ''}`}
        title={`Convert USD to ${code}`}
      >
        <ArrowLeftRight size={13} />
        <span>{showingUsd ? `Showing USD · 1$ = ${round2(usdRate)} ${code}` : `USD ⇄ ${code}`}</span>
      </button>

      {open && (
        <div
          className="absolute right-0 mt-2 rounded-xl shadow-card-lg border border-border bg-white p-4 text-xs"
          style={{ zIndex: 99999, width: 280, maxWidth: 'calc(100vw - 32px)' }}
        >
          <div className="flex items-center justify-between mb-3">
            <span className="text-[10px] font-bold text-ink-subtle uppercase tracking-wider">
              Currency converter
            </span>
            <button onClick={() => setOpen(false)} className="p-0.5 rounded hover:bg-app-bg" aria-label="Close">
              <X size={12} className="text-ink-subtle" />
            </button>
          </div>

          <label className="block text-[11px] font-medium text-ink-muted mb-1">US Dollar (USD)</label>
          <div className="relative mb-2">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-subtle text-sm">$</span>
            <input
              type="number" inputMode="decimal" min="0" value={usd}
              onChange={(e) => onUsdChange(e.target.value)}
              className={`${inputCls} pl-7`}
            />
          </div>

          <label className="block text-[11px] font-medium text-ink-muted mb-1">
            {country ? `${country} ` : ''}({code})
          </label>
          <div className="relative mb-3">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-subtle text-sm">{currencySymbol}</span>
            <input
              type="number" inputMode="decimal" min="0" value={local}
              onChange={(e) => onLocalChange(e.target.value)}
              disabled={!effectiveRate}
              placeholder={effectiveRate ? '' : 'Rate needed'}
              className={`${inputCls} pl-9 disabled:bg-app-bg`}
            />
          </div>

          <div className="pt-3 border-t border-border space-y-2">
            <div className="flex items-center justify-between gap-2 text-ink-muted">
              <span className="tabular-nums">
                {status === 'loading' && 'Loading live rate…'}
                {status === 'error' && 'Live rate unavailable'}
                {status === 'ok' && rate && `1 USD = ${round2(rate)} ${code}`}
              </span>
              <button
                onClick={() => loadRate(true)}
                disabled={status === 'loading'}
                className="p-1 rounded hover:bg-app-bg disabled:opacity-50"
                title="Refresh rate"
              >
                <RefreshCw size={12} className={status === 'loading' ? 'animate-spin' : ''} />
              </button>
            </div>
            {status === 'ok' && rateDate && !Number.isNaN(rateDate.getTime()) && (
              <div className="text-[10px] text-ink-subtle">
                Rate as of {rateDate.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })}
              </div>
            )}

            <div>
              <label className="block text-[10px] text-ink-subtle mb-1">
                Custom rate (optional, {code} per 1 USD)
              </label>
              <input
                type="number" inputMode="decimal" min="0" value={manualRate}
                onChange={(e) => setManualRate(e.target.value)}
                placeholder={rate ? round2(rate) : 'e.g. 88.5'}
                className="w-full text-xs tabular-nums px-2.5 py-1.5 rounded-md border border-border bg-white
                           focus:outline-none focus:border-primary/50"
              />
            </div>

            {/* Apply: show every amount on the dashboard in USD at this rate */}
            <div className="pt-2 space-y-1.5">
              {(!showingUsd || (effectiveRate && Math.abs(effectiveRate - usdRate) > 1e-9)) && (
                <button
                  onClick={() => { setDisplayCurrency('USD', effectiveRate); setOpen(false); }}
                  disabled={!effectiveRate}
                  className="btn-primary w-full text-xs py-2 disabled:opacity-50"
                >
                  <Check size={13} />
                  {showingUsd ? `Update dashboard to 1 USD = ${round2(effectiveRate)} ${code}` : 'Apply — show dashboard in USD'}
                </button>
              )}
              {showingUsd && (
                <button
                  onClick={() => { setDisplayCurrency('local'); setOpen(false); }}
                  className="btn-secondary w-full text-xs py-2"
                >
                  <RotateCcw size={12} />
                  Back to {code}
                </button>
              )}
              {!effectiveRate && (
                <div className="text-[10px] text-ink-subtle text-center">Enter a custom rate to apply.</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
