import React from 'react';
import { AnimatePresence } from 'framer-motion';
import useAppStore from './store/useAppStore';
import HomePage from './pages/HomePage';
import DashboardPage from './pages/DashboardPage';
import LoginPage from './pages/LoginPage';
import LoadingOverlay from './components/LoadingOverlay';
import { AuthProvider, useAuth } from './context/AuthContext';

function AuthenticatedApp() {
  const step = useAppStore(s => s.step);
  const { user, autoSelectFailed } = useAuth();
  const isDashboard = step === 'dashboard';
  // Users with an assigned country never see the Country picker: while
  // their market is being selected, show only the loading overlay.
  const autoSelectingCountry = step === 'country' && !!user?.country && !autoSelectFailed;

  return (
    <>
      <AnimatePresence>
        <LoadingOverlay key="loading" />
      </AnimatePresence>
      {isDashboard ? <DashboardPage /> : autoSelectingCountry ? <div className="min-h-screen w-full" /> : <HomePage />}
    </>
  );
}

function Gate() {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return <div className="min-h-screen w-full bg-[#0a0a12]" />; // avoid a flash of the login screen
  }
  return isAuthenticated ? <AuthenticatedApp /> : <LoginPage />;
}

export default function App() {
  return (
    <AuthProvider>
      <Gate />
    </AuthProvider>
  );
}
