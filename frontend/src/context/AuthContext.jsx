import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import { fetchMe, login as apiLogin, logout as apiLogout, getToken } from '../services/authApi';
import toast from 'react-hot-toast';
import { selectCountry, selectState } from '../services/api';
import { runFullPipeline } from '../services/pipeline';
import useAppStore from '../store/useAppStore';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  // True if auto-selecting the user's country failed — then the normal
  // Country picker is shown as a fallback.
  const [autoSelectFailed, setAutoSelectFailed] = useState(false);

  const refresh = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    const me = await fetchMe();
    setUser(me);
    setLoading(false);
  }, []);

  useEffect(() => {
    refresh();
    // Auto-logout if any API call comes back 401 (see services/api.js interceptor)
    const onUnauthorized = () => setUser(null);
    window.addEventListener('franchiseiq:unauthorized', onUnauthorized);
    return () => window.removeEventListener('franchiseiq:unauthorized', onUnauthorized);
  }, [refresh]);

  // v9.2 — if this user has a `country` assigned in users.json, skip the
  // manual Country/State picker and Configure screens and land straight on
  // the dashboard. Triggered by the effect further down whenever
  // the app is on the Country step (login, reload, Start New Analysis).
  const autoSelectMarket = async (me) => {
    if (!me?.country) return;
    const store = useAppStore.getState();
    try {
      store.setLoading(true, 'Setting up your workspace…');
      const countryData = await selectCountry(me.country);
      store.setSessionId(countryData.session_id);
      store.setCountry(me.country, countryData.states, countryData.currency_symbol, countryData.currency_code);

      const usableStates = (countryData.states || []).filter((s) => s.has_data);
      if (usableStates.length === 1) {
        const stateName = usableStates[0].name;
        const stateData = await selectState(countryData.session_id, stateName);
        store.setState(stateName, stateData);
        // Skip the "Verify Datasets / Configure & Run" screen: run the
        // analysis with the default 10 picks and open the dashboard. If it
        // fails, fall back to that screen so the user can retry.
        try {
          await runFullPipeline(countryData.session_id, stateName);
        } catch (err) {
          console.error('Automatic analysis failed:', err);
          toast.error(err?.response?.data?.detail || 'Could not run the analysis automatically — please run it manually.');
          store.setStep('configure');
        }
      } else {
        // Multiple (or zero) usable states — country is pre-selected but
        // we can't safely guess which state, so let the user pick.
        store.setStep('state');
      }
    } catch (e) {
      // Non-fatal: if auto-selection fails for any reason, the user just
      // sees the normal Country picker instead of a broken screen.
      console.error('Auto country/state selection failed:', e);
      setAutoSelectFailed(true);
    } finally {
      store.setLoading(false);
    }
  };

  const login = async (email, password) => {
    await apiLogin({ email, password });
    const me = await fetchMe();
    setUser(me);
    setLoading(false);
    // autoSelectMarket runs from the effect below once `user` is set.
  };

  // Whenever the app is on the Country step and the logged-in user has a
  // country in users.json, pick it automatically. This covers a fresh
  // login, a page reload with a saved token, and "Start New Analysis"
  // (which resets the app back to the Country step).
  const step = useAppStore((s) => s.step);
  const autoSelecting = useRef(false);
  useEffect(() => {
    if (!user?.country || step !== 'country' || autoSelectFailed || autoSelecting.current) return;
    autoSelecting.current = true;
    autoSelectMarket(user).finally(() => { autoSelecting.current = false; });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, step, autoSelectFailed]);

  const logout = () => {
    apiLogout();
    setUser(null);
    setAutoSelectFailed(false);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, autoSelectFailed, isAuthenticated: !!user }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
}
