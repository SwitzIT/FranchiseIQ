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
  const isDashboard = step === 'dashboard';

  return (
    <>
      <AnimatePresence>
        <LoadingOverlay key="loading" />
      </AnimatePresence>
      {isDashboard ? <DashboardPage /> : <HomePage />}
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
