import React, { useEffect, useState, useMemo } from 'react'
import { motion } from 'framer-motion'
import { ArrowRight, FileSearch, AlertTriangle, CheckCircle2, HelpCircle, Clock, Search, X, Download } from 'lucide-react'
import { listClaims, exportCsv, downloadCsvUrl } from '../lib/api.js'

const STATUS_CONFIG = {
  supported: { icon: CheckCircle2, color: 'text-verdict-supported', bg: 'bg-verdict-supported/10', label: 'Supported' },
  contradicted: { icon: AlertTriangle, color: 'text-verdict-contradicted', bg: 'bg-verdict-contradicted/10', label: 'Contradicted' },
  not_enough_information: { icon: HelpCircle, color: 'text-amber-400', bg: 'bg-amber-400/10', label: 'Needs more info' },
}

const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'supported', label: 'Supported' },
  { key: 'contradicted', label: 'Contradicted' },
  { key: 'not_enough_information', label: 'Needs info' },
  { key: 'review', label: 'Manual review' },
]

export default function DashboardPage({ navigate }) {
  const [claims, setClaims] = useState(null)
  const [error, setError] = useState(null)
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState('all')

  const [exporting, setExporting] = useState(false)

  useEffect(() => {
    listClaims().then(d => setClaims(d.claims)).catch((e) => setError(e.message))
  }, [])

  const handleExport = async () => {
    setExporting(true)
    try {
      await exportCsv()
      window.location.href = downloadCsvUrl
    } finally {
      setExporting(false)
    }
  }

  const filtered = useMemo(() => {
    if (!claims) return null
    return claims.filter((c) => {
      const matchesQuery = !query || c.claim_id.toLowerCase().includes(query.toLowerCase())
        || c.user_id.toLowerCase().includes(query.toLowerCase())
        || c.claim_object.toLowerCase().includes(query.toLowerCase())
      const matchesFilter =
        filter === 'all' ? true :
        filter === 'review' ? c.requires_manual_review :
        c.claim_status === filter
      return matchesQuery && matchesFilter
    })
  }, [claims, query, filter])

  return (
    <div className="pt-8 sm:pt-10">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-6">
        <div>
          <p className="font-mono text-[11px] tracking-widest text-amber-400/90 uppercase mb-2">Active investigations</p>
          <h1 className="font-display text-[26px] sm:text-[32px] leading-tight">Case board</h1>
        </div>
        <div className="flex items-center gap-4 self-start sm:self-auto">
          {claims && claims.length > 0 && (
            <button
              onClick={handleExport}
              disabled={exporting}
              className="flex items-center gap-1.5 text-[13px] text-ink-500 hover:text-paper-100 transition-colors font-mono disabled:opacity-50"
            >
              <Download size={13} /> {exporting ? 'Exporting…' : 'Export output.csv'}
            </button>
          )}
          <motion.button
            whileHover={{ x: 2 }}
            onClick={() => navigate('new')}
            className="flex items-center gap-1.5 text-[13px] text-ink-500 hover:text-amber-400 transition-colors font-mono"
          >
            File a new claim <ArrowRight size={14} />
          </motion.button>
        </div>
      </div>

      {claims && claims.length > 0 && (
        <div className="flex flex-col sm:flex-row gap-3 mb-7">
          <div className="relative flex-1">
            <Search size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-600" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by claim ID, user, or object type…"
              className="w-full bg-ink-900/60 border border-ink-700 rounded-lg pl-10 pr-9 py-2.5 text-[13px] placeholder:text-ink-600 focus:border-amber-400/50 transition-colors"
            />
            {query && (
              <button onClick={() => setQuery('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-600 hover:text-paper-200">
                <X size={14} />
              </button>
            )}
          </div>
          <div className="flex gap-1.5 overflow-x-auto pb-1 sm:pb-0 -mx-1 px-1 sm:mx-0 sm:px-0">
            {FILTERS.map((f) => (
              <button
                key={f.key}
                onClick={() => setFilter(f.key)}
                className={`whitespace-nowrap px-3 py-1.5 rounded-md text-[12px] font-mono transition-colors flex-shrink-0 ${
                  filter === f.key ? 'bg-amber-400 text-ink-950' : 'bg-ink-900/60 text-ink-500 border border-ink-700 hover:text-paper-200'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {error && (
        <div className="text-verdict-contradicted text-sm border border-verdict-contradicted/30 bg-verdict-contradicted/5 rounded-lg p-4">
          Could not reach the backend at /api — is the FastAPI server running on port 8000?
        </div>
      )}

      {claims === null && !error && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[0, 1, 2].map(i => (
            <div key={i} className="h-40 rounded-xl bg-ink-800/60 animate-pulse" />
          ))}
        </div>
      )}

      {claims && claims.length === 0 && <EmptyState navigate={navigate} />}

      {filtered && filtered.length === 0 && claims.length > 0 && (
        <div className="py-16 text-center text-ink-500 text-sm">No claims match your search or filter.</div>
      )}

      {filtered && filtered.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((c, i) => (
            <ClaimCard key={c.claim_id} claim={c} index={i} onClick={() => navigate('detail', c.claim_id)} />
          ))}
        </div>
      )}
    </div>
  )
}

function ClaimCard({ claim, index, onClick }) {
  const isPending = claim.status !== 'completed'
  const config = claim.claim_status ? STATUS_CONFIG[claim.claim_status] : null
  const Icon = config ? config.icon : Clock

  return (
    <motion.button
      onClick={onClick}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index * 0.04, 0.4), duration: 0.3 }}
      whileHover={{ y: -4, borderColor: 'rgba(232,162,61,0.45)', boxShadow: '0 8px 24px -8px rgba(0,0,0,0.5)' }}
      whileTap={{ scale: 0.99 }}
      className="text-left rounded-xl border border-ink-700 bg-ink-900/60 p-5 transition-all group relative overflow-hidden"
    >
      {claim.requires_manual_review && (
        <motion.div
          animate={{ opacity: [0.6, 1, 0.6] }}
          transition={{ duration: 2, repeat: Infinity }}
          className="absolute top-0 right-0 px-2.5 py-1 bg-amber-400/15 text-amber-400 text-[10px] font-mono tracking-wide rounded-bl-lg"
        >
          MANUAL REVIEW
        </motion.div>
      )}
      <div className="flex items-center gap-2 mb-3">
        <div className={`w-7 h-7 rounded-full flex items-center justify-center ${config ? config.bg : 'bg-ink-700'} transition-transform group-hover:scale-110`}>
          <Icon size={14} className={config ? config.color : 'text-ink-500'} />
        </div>
        <span className="font-mono text-[11px] text-ink-500 tracking-wide truncate">{claim.claim_id}</span>
      </div>

      <h3 className="font-display text-lg mb-1 capitalize">{claim.claim_object} claim</h3>
      <p className="text-[12px] text-ink-500 mb-4 truncate">Filed by {claim.user_id}</p>

      <div className="flex items-center justify-between pt-3 border-t border-ink-700/70">
        <span className={`text-[12px] font-mono ${config ? config.color : 'text-ink-500'}`}>
          {isPending ? 'Processing…' : config?.label || claim.status}
        </span>
        {claim.overall_claim_trust_score !== null && (
          <span className="font-mono text-[12px] tabular text-paper-200">
            trust {Math.round(claim.overall_claim_trust_score * 100)}%
          </span>
        )}
      </div>
    </motion.button>
  )
}

function EmptyState({ navigate }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="border border-dashed border-ink-700 rounded-xl py-16 sm:py-20 flex flex-col items-center text-center px-4"
    >
      <FileSearch size={32} className="text-ink-600 mb-4" strokeWidth={1.5} />
      <h3 className="font-display text-xl mb-2">No cases open yet</h3>
      <p className="text-ink-500 text-sm mb-6 max-w-sm">
        File a claim to start the investigation pipeline — evidence authenticity, ownership,
        possession, and damage analysis all run automatically.
      </p>
      <button
        onClick={() => navigate('new')}
        className="px-4 py-2 rounded-md bg-amber-400 text-ink-950 text-sm font-medium hover:bg-amber-500 transition-colors"
      >
        File your first claim
      </button>
    </motion.div>
  )
}
