import React, { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ArrowLeft, CheckCircle2, AlertTriangle, HelpCircle, Flag, Link2,
  Eye, ShieldQuestion, FileSearch2, Bug, History, KeyRound, X, ImageIcon, Network,
} from 'lucide-react'
import { getClaim, getNetworkClaim } from '../lib/api.js'

const STATUS_CONFIG = {
  supported: { icon: CheckCircle2, color: 'text-verdict-supported', bg: 'bg-verdict-supported/10', border: 'border-verdict-supported/30', label: 'Supported' },
  contradicted: { icon: AlertTriangle, color: 'text-verdict-contradicted', bg: 'bg-verdict-contradicted/10', border: 'border-verdict-contradicted/30', label: 'Contradicted' },
  not_enough_information: { icon: HelpCircle, color: 'text-amber-400', bg: 'bg-amber-400/10', border: 'border-amber-400/30', label: 'Not enough information' },
}

const AGENT_ICONS = {
  'Vision Expert': Eye,
  'Authenticity Expert': ShieldQuestion,
  'Evidence Expert': FileSearch2,
  'Fraud Expert': Bug,
  'History Expert': History,
  'Ownership Expert': KeyRound,
}

const SCORE_FIELDS = [
  { key: 'authenticity_score', label: 'Authenticity' },
  { key: 'ownership_score', label: 'Ownership' },
  { key: 'possession_score', label: 'Possession' },
  { key: 'damage_liveness_score', label: 'Liveness' },
  { key: 'evidence_coverage_score', label: 'Coverage' },
  { key: 'fraud_probability', label: 'Fraud risk', invert: true },
]

export default function ClaimDetailPage({ claimId, navigate }) {
  const [claim, setClaim] = useState(null)
  const [error, setError] = useState(null)
  const [activeImage, setActiveImage] = useState(null)
  const [networkClaimId, setNetworkClaimId] = useState(null)

  useEffect(() => {
    getClaim(claimId).then(setClaim).catch(e => setError(e.message))
  }, [claimId])

  if (error) return <div className="pt-10 text-verdict-contradicted">Could not load claim: {error}</div>
  if (!claim) return <PageSkeleton navigate={navigate} />

  const verdict = claim.verdict
  if (!verdict) {
    return (
      <div className="pt-10">
        <BackButton navigate={navigate} />
        <p className="text-ink-500 mt-6">This claim has not been verified yet. Status: {claim.status}</p>
      </div>
    )
  }

  const statusConfig = STATUS_CONFIG[verdict.claim_status] || STATUS_CONFIG.not_enough_information
  const StatusIcon = statusConfig.icon
  const networkFlagged = [
    ...(verdict.fraud_network_duplicate_claim_ids || []),
    ...(verdict.fraud_network_shared_identifier_claim_ids || []),
  ]
  const uniqueNetworkClaims = [...new Set(networkFlagged)]

  return (
    <div className="pt-8 sm:pt-10">
      <BackButton navigate={navigate} />

      {/* Verdict header */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mt-6 mb-8">
        <p className="font-mono text-[11px] tracking-widest text-ink-500 uppercase mb-2 truncate">{claim.claim_id}</p>
        <div className="flex items-center gap-3 flex-wrap">
          <div className={`flex items-center gap-2 px-3.5 py-1.5 rounded-full border ${statusConfig.border} ${statusConfig.bg}`}>
            <StatusIcon size={15} className={statusConfig.color} />
            <span className={`text-[13px] font-medium ${statusConfig.color}`}>{statusConfig.label}</span>
          </div>
          {verdict.requires_manual_review && (
            <motion.div
              animate={{ opacity: [0.7, 1, 0.7] }}
              transition={{ duration: 2, repeat: Infinity }}
              className="flex items-center gap-2 px-3.5 py-1.5 rounded-full border border-amber-400/30 bg-amber-400/10"
            >
              <Flag size={13} className="text-amber-400" />
              <span className="text-[13px] text-amber-400">Flagged for manual review</span>
            </motion.div>
          )}
          <div className="text-[13px] text-ink-500">
            Severity: <span className="text-paper-100 capitalize">{verdict.severity}</span>
          </div>
        </div>
      </motion.div>

      <TrustScoreHero score={verdict.overall_claim_trust_score} />

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-10">
        {SCORE_FIELDS.map((f, i) => (
          <ScoreTile key={f.key} label={f.label} value={verdict[f.key]} invert={f.invert} index={i} />
        ))}
      </div>

      {uniqueNetworkClaims.length > 0 && (
        <Section title="Fraud network matches">
          <div className="rounded-xl border border-verdict-contradicted/30 bg-verdict-contradicted/5 p-4 sm:p-5">
            <div className="flex items-start gap-3 mb-3">
              <Network size={18} className="text-verdict-contradicted flex-shrink-0 mt-0.5" />
              <p className="text-[13px] text-paper-200 leading-relaxed">
                This claim shares evidence or identifiers with {uniqueNetworkClaims.length} other claim
                {uniqueNetworkClaims.length > 1 ? 's' : ''} in the system. Review the comparison before approving.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {uniqueNetworkClaims.map((id) => (
                <button
                  key={id}
                  onClick={() => setNetworkClaimId(id)}
                  className="font-mono text-[12px] px-3 py-1.5 rounded-md bg-ink-900/60 border border-verdict-contradicted/30 text-verdict-contradicted hover:bg-verdict-contradicted/10 transition-colors"
                >
                  Compare with {id}
                </button>
              ))}
            </div>
          </div>
        </Section>
      )}

      {verdict.risk_flags.length > 0 && (
        <Section title="Risk flags raised">
          <div className="flex flex-wrap gap-2">
            {verdict.risk_flags.map((flag) => (
              <span key={flag} className="font-mono text-[11px] px-2.5 py-1 rounded-md bg-verdict-contradicted/10 text-verdict-contradicted border border-verdict-contradicted/20">
                {flag}
              </span>
            ))}
          </div>
        </Section>
      )}

      <InlineFraudSummary perImageSummary={verdict.per_image_summary} />

      <Section title="Final justification">
        <p className="text-[14px] leading-relaxed text-paper-200 bg-ink-900/50 border border-ink-700 rounded-xl p-4 sm:p-5">
          {verdict.final_justification}
        </p>
      </Section>

      {claim.image_paths?.length > 0 && (
        <Section title="Evidence images — forensic drill-down">
          <EvidenceGrid
            imagePaths={claim.image_paths}
            perImageSummary={verdict.per_image_summary}
            onSelect={setActiveImage}
          />
        </Section>
      )}

      <Section title="Chain of evidence">
        <ChainOfEvidence items={verdict.chain_of_evidence} />
      </Section>

      <Section title="Investigation team verdicts">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {verdict.agent_verdicts.map((agent, i) => (
            <AgentCard key={agent.agent_name} agent={agent} index={i} />
          ))}
        </div>
      </Section>

      <AnimatePresence>
        {activeImage && <ImageDetailModal item={activeImage} onClose={() => setActiveImage(null)} />}
      </AnimatePresence>

      <AnimatePresence>
        {networkClaimId && (
          <NetworkComparisonModal
            claimId={claimId}
            otherClaimId={networkClaimId}
            currentImagePaths={claim.image_paths}
            onClose={() => setNetworkClaimId(null)}
          />
        )}
      </AnimatePresence>
    </div>
  )
}

function BackButton({ navigate }) {
  return (
    <button onClick={() => navigate('dashboard')} className="flex items-center gap-1.5 text-[12px] text-ink-500 hover:text-paper-100 transition-colors font-mono">
      <ArrowLeft size={13} /> Case board
    </button>
  )
}

function Section({ title, children }) {
  return (
    <div className="mb-10">
      <p className="font-mono text-[11px] tracking-widest text-ink-500 uppercase mb-4">{title}</p>
      {children}
    </div>
  )
}

function TrustScoreHero({ score }) {
  const pct = Math.round(score * 100)
  const color = pct >= 65 ? '#4DD0A7' : pct >= 40 ? '#E8A23D' : '#E85D5D'
  const circumference = 2 * Math.PI * 54

  return (
    <div className="flex flex-col sm:flex-row items-center gap-6 sm:gap-8 mb-10 p-5 sm:p-6 rounded-2xl border border-ink-700 bg-ink-900/40">
      <div className="relative w-28 h-28 sm:w-32 sm:h-32 flex-shrink-0">
        <svg viewBox="0 0 120 120" className="w-full h-full -rotate-90">
          <circle cx="60" cy="60" r="54" fill="none" stroke="#1E2530" strokeWidth="8" />
          <motion.circle
            cx="60" cy="60" r="54" fill="none" stroke={color} strokeWidth="8" strokeLinecap="round"
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: circumference - (pct / 100) * circumference }}
            transition={{ duration: 1.2, ease: 'easeOut' }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-display text-2xl sm:text-3xl tabular">{pct}</span>
          <span className="text-[10px] text-ink-500 font-mono">TRUST</span>
        </div>
      </div>
      <div className="text-center sm:text-left">
        <p className="font-display text-xl mb-1">Overall claim trust score</p>
        <p className="text-[13px] text-ink-500 max-w-md">
          Weighted across evidence authenticity, ownership, possession, evidence coverage,
          story consistency, damage physics, and claimant history — with hard penalties applied
          for fraud-network matches or policy-timing contradictions.
        </p>
      </div>
    </div>
  )
}

function InlineFraudSummary({ perImageSummary }) {
  if (!perImageSummary?.length) return null

  const flaggedImages = perImageSummary.filter(p => p.fraud_verdict !== 'clean')
  if (flaggedImages.length === 0) return null

  const worst = flaggedImages.find(p => p.fraud_verdict === 'likely_manipulated') || flaggedImages[0]
  const style = FRAUD_VERDICT_BANNER[worst.fraud_verdict] || FRAUD_VERDICT_BANNER.suspicious
  const Icon = style.icon
  const topEvidence = worst.fraud_evidence?.[0]

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
      className={`mb-10 rounded-xl border p-4 sm:p-5 ${style.bg} ${style.border}`}
    >
      <div className="flex items-start gap-3">
        <Icon size={18} className={`${style.text} flex-shrink-0 mt-0.5`} />
        <div className="flex-1">
          <p className={`text-[13px] font-medium mb-1 ${style.text}`}>
            {flaggedImages.length} of {perImageSummary.length} image(s) raised forensic concerns
          </p>
          <p className="text-[12.5px] text-paper-200 leading-relaxed">
            {worst.fraud_headline}
            {topEvidence && <span className="text-ink-400"> — {topEvidence.check}: {topEvidence.measurement}</span>}
          </p>
          <p className="text-[11px] text-ink-500 mt-2 font-mono">See "Evidence images" below for the full breakdown per image →</p>
        </div>
      </div>
    </motion.div>
  )
}

function ScoreTile({ label, value, invert, index }) {
  const pct = Math.round((value ?? 0) * 100)
  const good = invert ? pct < 35 : pct >= 60
  const warn = invert ? pct >= 35 && pct < 60 : pct >= 35 && pct < 60
  const color = good ? 'text-verdict-supported' : warn ? 'text-amber-400' : 'text-verdict-contradicted'

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04 }}
      whileHover={{ y: -2 }}
      className="rounded-lg border border-ink-700 bg-ink-900/40 p-3 sm:p-3.5 transition-transform"
    >
      <p className="text-[10.5px] sm:text-[11px] text-ink-500 mb-1.5">{label}</p>
      <p className={`font-mono text-lg sm:text-xl tabular ${color}`}>{pct}%</p>
    </motion.div>
  )
}

function ChainOfEvidence({ items }) {
  return (
    <div className="relative pl-6">
      <motion.div
        initial={{ scaleY: 0 }}
        animate={{ scaleY: 1 }}
        transition={{ duration: 0.6, ease: 'easeOut' }}
        style={{ transformOrigin: 'top' }}
        className="absolute left-[7px] top-2 bottom-2 w-px bg-ink-700"
      />
      <div className="space-y-5">
        {items.map((item, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.15 + i * 0.08 }}
            className="relative"
          >
            <span className="absolute -left-6 top-1 w-3 h-3 rounded-full bg-amber-400 ring-4 ring-ink-950" />
            <p className="font-mono text-[11px] text-amber-400/90 uppercase tracking-wide mb-1">{item.source}</p>
            <p className="text-[13px] text-paper-200 leading-relaxed">{item.observation}</p>
          </motion.div>
        ))}
      </div>
    </div>
  )
}

function AgentCard({ agent, index }) {
  const Icon = AGENT_ICONS[agent.agent_name] || Link2
  const pct = Math.round(agent.score * 100)

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06 }}
      whileHover={{ y: -2, borderColor: 'rgba(232,162,61,0.3)' }}
      className="rounded-xl border border-ink-700 bg-ink-900/40 p-4 transition-colors"
    >
      <div className="flex items-center justify-between mb-2.5">
        <div className="flex items-center gap-2">
          <Icon size={15} className="text-ink-400" strokeWidth={1.75} />
          <span className="text-[13px] font-medium">{agent.agent_name}</span>
        </div>
        <span className="font-mono text-[12px] tabular text-ink-400">{pct}</span>
      </div>
      <p className="text-[12.5px] text-ink-500 leading-relaxed">{agent.summary}</p>
      {agent.flags?.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-2.5">
          {agent.flags.map(f => (
            <span key={f} className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-verdict-contradicted/10 text-verdict-contradicted">{f}</span>
          ))}
        </div>
      )}
    </motion.div>
  )
}

const FRAUD_VERDICT_STYLE = {
  clean: { label: 'Clean', bg: 'bg-verdict-supported/85', text: 'text-ink-950' },
  suspicious: { label: 'Suspicious', bg: 'bg-amber-400/90', text: 'text-ink-950' },
  likely_manipulated: { label: 'Flagged', bg: 'bg-verdict-contradicted/90', text: 'text-paper-100' },
}

function EvidenceGrid({ imagePaths, perImageSummary, onSelect }) {
  const summaryByPath = {}
  for (const s of perImageSummary || []) summaryByPath[s.image_path] = s

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
      {imagePaths.map((path, i) => {
        const summary = summaryByPath[path]
        const verdictStyle = summary ? FRAUD_VERDICT_STYLE[summary.fraud_verdict] || FRAUD_VERDICT_STYLE.clean : null
        return (
          <motion.button
            key={path}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: i * 0.05 }}
            whileHover={{ y: -3 }}
            onClick={() => onSelect(summary || { image_path: path })}
            className="relative rounded-lg overflow-hidden border border-ink-700 group aspect-square bg-ink-900"
          >
            <img src={path} alt={`evidence ${i + 1}`} className="w-full h-full object-cover transition-transform group-hover:scale-105" />
            <div className="absolute inset-0 bg-gradient-to-t from-ink-950/90 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex items-end p-2">
              <span className="text-[11px] text-paper-200 flex items-center gap-1">
                <ImageIcon size={11} /> View forensics
              </span>
            </div>
            {verdictStyle && (
              <span className={`absolute top-1.5 right-1.5 font-mono text-[10px] px-1.5 py-0.5 rounded ${verdictStyle.bg} ${verdictStyle.text}`}>
                {verdictStyle.label}
              </span>
            )}
          </motion.button>
        )
      })}
    </div>
  )
}

const EVIDENCE_SEVERITY_STYLE = {
  high: { border: 'border-verdict-contradicted/40', bg: 'bg-verdict-contradicted/5', text: 'text-verdict-contradicted', icon: AlertTriangle },
  caution: { border: 'border-amber-400/40', bg: 'bg-amber-400/5', text: 'text-amber-400', icon: HelpCircle },
  info: { border: 'border-ink-700', bg: 'bg-ink-800/40', text: 'text-ink-400', icon: CheckCircle2 },
}

const FRAUD_VERDICT_BANNER = {
  clean: { bg: 'bg-verdict-supported/10', border: 'border-verdict-supported/30', text: 'text-verdict-supported', icon: CheckCircle2 },
  suspicious: { bg: 'bg-amber-400/10', border: 'border-amber-400/30', text: 'text-amber-400', icon: HelpCircle },
  likely_manipulated: { bg: 'bg-verdict-contradicted/10', border: 'border-verdict-contradicted/30', text: 'text-verdict-contradicted', icon: AlertTriangle },
}

function ImageDetailModal({ item, onClose }) {
  const hasFraudData = item.fraud_verdict !== undefined
  const banner = hasFraudData ? (FRAUD_VERDICT_BANNER[item.fraud_verdict] || FRAUD_VERDICT_BANNER.clean) : null
  const BannerIcon = banner?.icon

  return (
    <motion.div
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      onClick={onClose}
      className="fixed inset-0 bg-ink-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4"
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 10 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.95 }}
        onClick={(e) => e.stopPropagation()}
        className="bg-ink-900 border border-ink-700 rounded-xl max-w-2xl w-full max-h-[85vh] overflow-y-auto"
      >
        <div className="flex items-center justify-between p-4 border-b border-ink-700">
          <span className="font-mono text-[12px] text-ink-500">Forensic detail</span>
          <button onClick={onClose} className="text-ink-500 hover:text-paper-100"><X size={18} /></button>
        </div>
        <div className="p-4 sm:p-5">
          <img src={item.image_path} alt="evidence" className="w-full rounded-lg mb-4 border border-ink-700" />

          {hasFraudData ? (
            <div className="space-y-4">
              <div className={`flex items-start gap-2.5 p-3.5 rounded-lg border ${banner.bg} ${banner.border}`}>
                {BannerIcon && <BannerIcon size={16} className={`${banner.text} flex-shrink-0 mt-0.5`} />}
                <p className={`text-[13px] ${banner.text}`}>{item.fraud_headline}</p>
              </div>

              {item.fraud_evidence?.length > 0 && (
                <div className="space-y-2.5">
                  <p className="text-[11px] text-ink-500 font-mono uppercase tracking-wide">What we analyzed and why</p>
                  {item.fraud_evidence.map((ev, idx) => {
                    const style = EVIDENCE_SEVERITY_STYLE[ev.severity] || EVIDENCE_SEVERITY_STYLE.info
                    const EvIcon = style.icon
                    return (
                      <motion.div
                        key={idx}
                        initial={{ opacity: 0, x: -6 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: idx * 0.08 }}
                        className={`rounded-lg border p-3.5 ${style.border} ${style.bg}`}
                      >
                        <div className="flex items-center gap-2 mb-1.5">
                          <EvIcon size={13} className={style.text} />
                          <span className={`text-[12.5px] font-medium ${style.text}`}>{ev.check}</span>
                        </div>
                        <p className="font-mono text-[11px] text-ink-400 mb-1.5">{ev.measurement}</p>
                        <p className="text-[12.5px] text-paper-200 leading-relaxed">{ev.interpretation}</p>
                      </motion.div>
                    )
                  })}
                </div>
              )}

              <div className="grid grid-cols-2 gap-2.5 pt-2 border-t border-ink-700">
                <DetailRow label="Overall authenticity" value={`${Math.round(item.image_authenticity_score * 100)}%`} />
                <DetailRow label="ELA score" value={`${Math.round(item.ela_manipulation_score * 100)}%`} />
                <DetailRow label="AI-generation probability" value={`${Math.round(item.ai_generation_probability * 100)}%`} />
                <DetailRow label="Lighting consistency" value={`${Math.round(item.lighting_consistency_score * 100)}%`} />
              </div>
            </div>
          ) : (
            <p className="text-ink-500 text-sm">No detailed forensic data available for this image.</p>
          )}
        </div>
      </motion.div>
    </motion.div>
  )
}

function DetailRow({ label, value }) {
  return (
    <div className="flex items-center justify-between text-[13px]">
      <span className="text-ink-500">{label}</span>
      <span className="font-mono text-paper-200">{value}</span>
    </div>
  )
}

function NetworkComparisonModal({ claimId, otherClaimId, currentImagePaths, onClose }) {
  const [other, setOther] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    getNetworkClaim(claimId, otherClaimId).then(setOther).catch(e => setError(e.message))
  }, [claimId, otherClaimId])

  return (
    <motion.div
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      onClick={onClose}
      className="fixed inset-0 bg-ink-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4"
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 10 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.95 }}
        onClick={(e) => e.stopPropagation()}
        className="bg-ink-900 border border-verdict-contradicted/30 rounded-xl max-w-3xl w-full max-h-[85vh] overflow-y-auto"
      >
        <div className="flex items-center justify-between p-4 border-b border-ink-700">
          <span className="font-mono text-[12px] text-verdict-contradicted flex items-center gap-1.5"><Network size={13} /> Network comparison</span>
          <button onClick={onClose} className="text-ink-500 hover:text-paper-100"><X size={18} /></button>
        </div>
        <div className="p-4 sm:p-5">
          {error && <p className="text-verdict-contradicted text-sm">Could not load comparison claim: {error}</p>}
          {!other && !error && <p className="text-ink-500 text-sm">Loading comparison…</p>}
          {other && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              <div>
                <p className="font-mono text-[11px] text-ink-500 mb-2">THIS CLAIM — {claimId}</p>
                <div className="grid grid-cols-2 gap-2">
                  {currentImagePaths.slice(0, 4).map((p, i) => (
                    <img key={i} src={p} className="rounded-lg border border-ink-700 aspect-square object-cover" />
                  ))}
                </div>
              </div>
              <div>
                <p className="font-mono text-[11px] text-verdict-contradicted mb-2">MATCHED CLAIM — {other.claim_id}</p>
                <p className="text-[12px] text-ink-500 mb-2">Filed by {other.user_id} · {other.claim_object}</p>
                <div className="grid grid-cols-2 gap-2">
                  {other.image_paths.slice(0, 4).map((p, i) => (
                    <img key={i} src={p} className="rounded-lg border border-verdict-contradicted/30 aspect-square object-cover" />
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </motion.div>
    </motion.div>
  )
}

function PageSkeleton({ navigate }) {
  return (
    <div className="pt-8 sm:pt-10">
      <BackButton navigate={navigate} />
      <div className="mt-6 space-y-4">
        <div className="h-7 w-48 bg-ink-800/60 rounded animate-pulse" />
        <div className="h-32 bg-ink-800/60 rounded-2xl animate-pulse" />
        <div className="grid grid-cols-2 sm:grid-cols-6 gap-3">
          {[...Array(6)].map((_, i) => <div key={i} className="h-16 bg-ink-800/60 rounded-lg animate-pulse" />)}
        </div>
      </div>
    </div>
  )
}
