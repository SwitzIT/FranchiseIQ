import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Lock, Mail, ArrowRight, Building2 } from 'lucide-react';
import toast from 'react-hot-toast';
import { useAuth } from '../context/AuthContext';

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await login(email, password);
      toast.success('Welcome back!');
    } catch (err) {
      const detail = err?.response?.data?.detail || 'Incorrect email or password.';
      toast.error(detail);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-[#0a0a12] px-4">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-md rounded-2xl border border-white/10 bg-white/[0.02] p-8 shadow-xl"
      >
        <div className="flex items-center gap-2 mb-8">
          <div className="w-9 h-9 rounded-lg bg-purple/20 border border-purple/30 flex items-center justify-center">
            <Building2 className="w-5 h-5 text-purple-light" />
          </div>
          <div>
            <div className="text-white font-semibold leading-none">FranchiseIQ</div>
            <div className="text-[11px] text-slate-500">Location Intelligence Platform</div>
          </div>
        </div>

        <div className="mb-6">
          <div className="text-lg font-semibold text-white">Sign In</div>
          <div className="text-xs text-slate-500 mt-1">
            Access is by invitation only. Contact your admin if you need credentials.
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="relative">
            <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <input
              type="email"
              required
              placeholder="Email address"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full pl-10 pr-3 py-2.5 rounded-lg bg-white/[0.03] border border-white/10
                         text-sm text-white placeholder:text-slate-500 focus:outline-none focus:border-purple-light"
            />
          </div>
          <div className="relative">
            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <input
              type="password"
              required
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full pl-10 pr-3 py-2.5 rounded-lg bg-white/[0.03] border border-white/10
                         text-sm text-white placeholder:text-slate-500 focus:outline-none focus:border-purple-light"
            />
          </div>

          <button
            type="submit"
            disabled={busy}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg
                       bg-purple hover:bg-purple-light transition-colors text-white text-sm font-semibold
                       disabled:opacity-50"
          >
            {busy ? 'Signing in…' : 'Sign In'}
            {!busy && <ArrowRight className="w-4 h-4" />}
          </button>
        </form>

        <p className="text-[11px] text-slate-600 mt-6 text-center">
          West Bengal, India · Franchise Location Intelligence
        </p>
      </motion.div>
    </div>
  );
}
