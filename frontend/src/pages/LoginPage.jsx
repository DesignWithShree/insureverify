import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ShieldCheck, Mail, Lock, Loader2, AlertTriangle } from 'lucide-react'
import { useAuth } from '../lib/AuthContext.jsx'

export default function LoginPage() {
  const { signInWithEmail, signUpWithEmail, signInWithGoogle, error, clearError, firebaseConfigured } = useAuth()
  const [mode, setMode] = useState('signin') // 'signin' | 'signup'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    try {
      if (mode === 'signin') await signInWithEmail(email, password)
      else await signUpWithEmail(email, password)
    } catch {
      // error is already set in context
    } finally {
      setSubmitting(false)
    }
  }

  const handleGoogle = async () => {
    setSubmitting(true)
    try {
      await signInWithGoogle()
    } catch {
      // error already set in context
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-ink-950 bg-grain flex items-center justify-center px-4">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="w-full max-w-sm"
      >
        <div className="flex items-center justify-center gap-2 mb-8">
          <ShieldCheck size={26} className="text-amber-400" strokeWidth={1.75} />
          <span className="font-display text-xl text-paper-100 tracking-tight">
            Insure<span className="text-amber-400">Verify</span>
          </span>
        </div>

        {!firebaseConfigured && (
          <div className="mb-6 rounded-lg border border-amber-400/30 bg-amber-400/10 p-4 text-[12.5px] text-amber-400 leading-relaxed">
            Firebase isn't configured yet. Add your project's credentials to{' '}
            <code className="font-mono">frontend/.env</code> (see{' '}
            <code className="font-mono">.env.example</code>) to enable real sign-in.
          </div>
        )}

        <div className="bg-ink-900/60 border border-ink-700 rounded-2xl p-6 sm:p-7">
          <div className="flex mb-6 rounded-lg bg-ink-800/60 p-1">
            <ModeTab active={mode === 'signin'} onClick={() => { setMode('signin'); clearError() }}>Sign in</ModeTab>
            <ModeTab active={mode === 'signup'} onClick={() => { setMode('signup'); clearError() }}>Create account</ModeTab>
          </div>

          <form onSubmit={handleSubmit} className="space-y-3.5">
            <FieldWithIcon icon={Mail}>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                disabled={!firebaseConfigured}
                className="w-full bg-transparent text-[13.5px] placeholder:text-ink-600 focus:outline-none disabled:opacity-50"
              />
            </FieldWithIcon>
            <FieldWithIcon icon={Lock}>
              <input
                type="password"
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Password"
                disabled={!firebaseConfigured}
                className="w-full bg-transparent text-[13.5px] placeholder:text-ink-600 focus:outline-none disabled:opacity-50"
              />
            </FieldWithIcon>

            <AnimatePresence>
              {error && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}
                  className="flex items-start gap-2 text-[12px] text-verdict-contradicted bg-verdict-contradicted/5 border border-verdict-contradicted/20 rounded-lg p-3"
                >
                  <AlertTriangle size={13} className="flex-shrink-0 mt-0.5" />
                  {error}
                </motion.div>
              )}
            </AnimatePresence>

            <motion.button
              type="submit"
              whileHover={firebaseConfigured ? { y: -1 } : {}}
              whileTap={firebaseConfigured ? { scale: 0.98 } : {}}
              disabled={!firebaseConfigured || submitting}
              className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-amber-400 text-ink-950 font-medium text-[13.5px] disabled:opacity-40 disabled:cursor-not-allowed hover:bg-amber-500 transition-colors"
            >
              {submitting && <Loader2 size={14} className="animate-spin" />}
              {mode === 'signin' ? 'Sign in' : 'Create account'}
            </motion.button>
          </form>

          <div className="flex items-center gap-3 my-5">
            <div className="flex-1 h-px bg-ink-700" />
            <span className="text-[11px] text-ink-600 font-mono">OR</span>
            <div className="flex-1 h-px bg-ink-700" />
          </div>

          <button
            onClick={handleGoogle}
            disabled={!firebaseConfigured || submitting}
            className="w-full flex items-center justify-center gap-2.5 py-2.5 rounded-lg border border-ink-700 text-[13.5px] text-paper-200 hover:bg-ink-800 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <GoogleIcon />
            Continue with Google
          </button>
        </div>

        <p className="text-center text-[11.5px] text-ink-600 mt-5">
          Your investigation history is tied to your account and private to you.
        </p>
      </motion.div>
    </div>
  )
}

function ModeTab({ active, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex-1 py-2 rounded-md text-[12.5px] font-medium transition-colors ${
        active ? 'bg-ink-700 text-paper-100' : 'text-ink-500 hover:text-paper-200'
      }`}
    >
      {children}
    </button>
  )
}

function FieldWithIcon({ icon: Icon, children }) {
  return (
    <div className="flex items-center gap-2.5 bg-ink-800/60 border border-ink-700 rounded-lg px-3.5 py-2.5 focus-within:border-amber-400/50 transition-colors">
      <Icon size={15} className="text-ink-500 flex-shrink-0" />
      {children}
    </div>
  )
}

function GoogleIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24">
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.99.69-2.26 1.1-3.71 1.1-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
      <path fill="#FBBC05" d="M5.84 14.14c-.22-.69-.35-1.42-.35-2.14s.13-1.45.35-2.14V7.02H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.98l3.66-2.84z"/>
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.02l3.66 2.84c.87-2.6 3.3-4.48 6.16-4.48z"/>
    </svg>
  )
}
