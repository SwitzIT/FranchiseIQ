import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { fetchMe, login as apiLogin, logout as apiLogout, getToken } from '../services/authApi';
import { selectCountry, selectState } from '../services/api';
import useAppStore from '../store/useAppStore';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

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
  // manual Country/State picker screens and land straight on the
  // Configure & Run step. Only runs right after an explicit login (not on
  // every page refresh/token check via `refresh()` above), so reloading
  // an in-progress session doesn't reset it back to a fresh pipeline run.
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
        const stateData = await selectState(countryData.session_id, usableStates[0].name);
        store.setState(usableStates[0].name, stateData);
        store.setStep('configure');
      } else {
        // Multiple (or zero) usable states — country is pre-selected but
        // we can't safely guess which state, so let the user pick.
        store.setStep('state');
      }
    } catch (e) {
      // Non-fatal: if auto-selection fails for any reason, the user just
      // sees the normal Country picker instead of a broken screen.
      console.error('Auto country/state selection failed:', e);
    } finally {
      store.setLoading(false);
    }
  };

  const login = async (email, password) => {
    await apiLogin({ email, password });
    const me = await fetchMe();
    setUser(me);
    setLoading(false);
    await autoSelectMarket(me);
  };

  const logout = () => {
    apiLogout();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, isAuthenticated: !!user }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
}
