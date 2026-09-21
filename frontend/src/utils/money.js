import useAppStore from '../store/useAppStore';

/**
 * Formats a money amount for display.
 *
 * Amounts from the backend are always in the country's local currency
 * (INR / LKR). When the user has chosen "Show dashboard in USD" in the
 * currency converter, they are divided by the USD rate (local units per
 * 1 USD) and shown as $ with K / M suffixes.
 */
export function formatMoney(val, { country, currencySymbol, displayCurrency, usdRate } = {}, { tight = false } = {}) {
  if (val == null || !Number.isFinite(Number(val))) return '—';
  let n = Number(val);
  const sp = tight ? '' : ' ';
  const inUsd = displayCurrency === 'USD' && usdRate > 0;
  const sym = inUsd ? '$' : (currencySymbol || '');
  if (inUsd) n = n / usdRate;

  if (!inUsd && country === 'India') {
    if (Math.abs(n) >= 1e7) return `${sym}${(n / 1e7).toFixed(2)}${sp}Cr`;
    if (Math.abs(n) >= 1e5) return `${sym}${(n / 1e5).toFixed(1)}${sp}L`;
    return `${sym}${n.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
  }
  if (Math.abs(n) >= 1e6) return `${sym}${(n / 1e6).toFixed(2)}${sp}M`;
  if (Math.abs(n) >= 1e3) return `${sym}${(n / 1e3).toFixed(1)}${sp}K`;
  return `${sym}${n.toLocaleString('en-US', { maximumFractionDigits: inUsd && Math.abs(n) < 100 ? 2 : 0 })}`;
}

/** React hook: returns a formatter bound to the current country / display currency. */
export function useMoney(opts) {
  const country = useAppStore((s) => s.country);
  const currencySymbol = useAppStore((s) => s.currencySymbol);
  const displayCurrency = useAppStore((s) => s.displayCurrency);
  const usdRate = useAppStore((s) => s.usdRate);
  return (val) => formatMoney(val, { country, currencySymbol, displayCurrency, usdRate }, opts);
}
