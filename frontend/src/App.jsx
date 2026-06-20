import React, { useState, useEffect } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ShieldCheck, LayoutGrid, FilePlus2, LogOut, Loader2 } from 'lucide-react'
import NewClaimPage from './pages/NewClaimPage.jsx'
import DashboardPage from './pages/DashboardPage.jsx'
import ClaimDetailPage from './pages/ClaimDetailPage.jsx'
import LandingPage from './pages/LandingPage.jsx'
import LoginPage from './pages/LoginPage.jsx'
import { healthCheck } from './lib/api.js'
import { useAuth } from './lib/AuthContext.jsx'

export default function App() {
  const { user, loading, signOut, firebaseConfigured } = useAuth()
  const [entryState, setEntryState] = useState('landing') // 'landing' | 'login' | 'app'
  const [view, setView] = useState({ name: 'dashboard', claimId: null })
  const [ollamaStatus, setOllamaStatus] = useState(null)

  useEffect(() => {
    healthCheck().then(d => setOllamaStatus(d.ollama_available)).catch(() => setOllamaStatus(false))
  }, [])

  // If Firebase auth is configured and a session already exists (e.g. on
  // reload), skip straight past landing/login into the app.
  useEffect(() => {
    if (firebaseConfigured && user) setEntryState('app')
  }, [user, firebaseConfigured])

  const navigate = (name, claimId = null) => setView({ name, claimId })

  if (firebaseConfigured && loading) {
    return (
      <div className="min-h-screen bg-ink-950 flex items-center justify-center">
        <Loader2 size={22} className="text-amber-400 animate-spin" />
      </div>
    )
  }

  if (entryState === 'landing') {
    return <LandingPage onGetStarted={() => setEntryState(firebaseConfigured ? 'login' : 'app')} />
  }

  if (entryState === 'login' && firebaseConfigured && !user) {
    return <LoginPage />
  }

  return (
    <div className="min-h-screen bg-ink-950 bg-grain text-paper-100 font-sans selection:bg-amber-500/30 relative overflow-x-hidden">
      <div className="pointer-events-none fixed inset-0 z-0 opacity-[0.05]">
        <div className="absolute inset-0 bg-gradient-to-b from-amber-400/20 via-transparent to-transparent animate-scanline" />
      </div>
      <div className="relative z-10">
        <Header view={view} navigate={navigate} ollamaStatus={ollamaStatus} user={user} onSignOut={signOut} firebaseConfigured={firebaseConfigured} />
        <main className="max-w-6xl mx-auto px-4 sm:px-6 pb-24">
          <AnimatePresence mode="wait">
            {view.name === 'dashboard' && (
              <motion.div key="dashboard" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.25 }}>
                <DashboardPage navigate={navigate} />
              </motion.div>
            )}
            {view.name === 'new' && (
              <motion.div key="new" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.25 }}>
                <NewClaimPage navigate={navigate} />
              </motion.div>
            )}
            {view.name === 'detail' && (
              <motion.div key="detail" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.25 }}>
                <ClaimDetailPage claimId={view.claimId} navigate={navigate} />
              </motion.div>
            )}
          </AnimatePresence>
        </main>
      </div>
    </div>
  )
}

function Header({ view, navigate, ollamaStatus, user, onSignOut, firebaseConfigured }) {
  return (
    <header className="border-b border-ink-700/80 sticky top-0 z-30 backdrop-blur-md bg-ink-950/85">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-3">
        <button onClick={() => navigate('dashboard')} className="flex items-center gap-2 sm:gap-2.5 group flex-shrink-0">
          <ShieldCheck size={22} className="text-amber-400" strokeWidth={1.75} />
          <span className="font-display text-[15px] sm:text-[17px] tracking-tight whitespace-nowrap">
            Insure<span className="text-amber-400">Verify</span>
          </span>
        </button>

        <nav className="flex items-center gap-1">
          <NavButton active={view.name === 'dashboard'} onClick={() => navigate('dashboard')} icon={LayoutGrid} label="Case board" />
          <NavButton active={view.name === 'new'} onClick={() => navigate('new')} icon={FilePlus2} label="New claim" />
        </nav>

        <div className="flex items-center gap-3 flex-shrink-0">
          <div className="hidden sm:flex items-center gap-2 text-[11px] font-mono text-ink-500">
            <span className={`inline-block w-1.5 h-1.5 rounded-full ${ollamaStatus ? 'bg-verdict-supported' : 'bg-amber-400'}`} />
            {ollamaStatus === null ? 'checking…' : ollamaStatus ? 'llm online' : 'cv-only mode'}
          </div>
          {firebaseConfigured && user && (
            <button
              onClick={onSignOut}
              title={user.email || 'Sign out'}
              className="flex items-center gap-1.5 text-[11px] text-ink-500 hover:text-paper-100 transition-colors"
            >
              <LogOut size={13} />
              <span className="hidden sm:inline">Sign out</span>
            </button>
          )}
        </div>
      </div>
    </header>
  )
}

function NavButton({ active, onClick, icon: Icon, label }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 px-2.5 sm:px-3.5 py-1.5 rounded-md text-[12px] sm:text-[13px] transition-colors ${
        active ? 'bg-ink-700 text-paper-100' : 'text-ink-500 hover:text-paper-200 hover:bg-ink-800'
      }`}
    >
      <Icon size={14} strokeWidth={1.75} />
      <span className="hidden sm:inline">{label}</span>
    </button>
  )
}
