import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { fetchMe, login as apiLogin, logout as apiLogout, getToken } from '../services/authApi';

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

  const login = async (email, password) => {
    await apiLogin({ email, password });
    await refresh();
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
