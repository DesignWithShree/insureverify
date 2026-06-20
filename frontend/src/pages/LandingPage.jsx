import React from 'react'
import { motion } from 'framer-motion'
import {
  ShieldCheck, ScanSearch, KeyRound, Video, Layers, Network,
  ArrowRight, FileSearch2, Eye, Bug, History,
} from 'lucide-react'

const STAGES = [
  { icon: ScanSearch, title: 'Evidence authenticity', desc: 'EXIF forensics, Error Level Analysis, AI-generation detection, and localized anomaly scanning — before any damage is even assessed.' },
  { icon: KeyRound, title: 'Ownership & possession', desc: 'OCR cross-checks serials, VINs, and plates against your claim, plus a unique challenge code to prove you currently have the object.' },
  { icon: Video, title: 'Damage liveness', desc: 'Real handheld video vs. a looped photo — verified with motion analysis and frame-to-frame object tracking.' },
  { icon: Layers, title: 'Story consistency', desc: 'What you said happened is checked against what a vision model independently observed — without ever showing it your claim text.' },
  { icon: Network, title: 'Fraud network detection', desc: 'Every new claim is checked against every past claim for reused photos or shared identifiers across "unrelated" accounts.' },
]

const AGENTS = [
  { icon: Eye, name: 'Vision Expert' },
  { icon: ShieldCheck, name: 'Authenticity Expert' },
  { icon: FileSearch2, name: 'Evidence Expert' },
  { icon: Bug, name: 'Fraud Expert' },
  { icon: History, name: 'History Expert' },
  { icon: KeyRound, name: 'Ownership Expert' },
]

export default function LandingPage({ onGetStarted }) {
  return (
    <div className="bg-ink-950 bg-grain text-paper-100 font-sans overflow-x-hidden">
      <Hero onGetStarted={onGetStarted} />
      <HowItWorks />
      <AgentsSection />
      <ClosingCTA onGetStarted={onGetStarted} />
    </div>
  )
}

function Hero({ onGetStarted }) {
  return (
    <section className="relative min-h-screen flex flex-col items-center justify-center px-6 text-center">
      <div className="pointer-events-none absolute inset-0 opacity-[0.06]">
        <div className="absolute inset-0 bg-gradient-to-b from-amber-400/30 via-transparent to-transparent animate-scanline" />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}
        className="flex items-center gap-2.5 mb-7"
      >
        <ShieldCheck size={28} className="text-amber-400" strokeWidth={1.75} />
        <span className="font-display text-2xl tracking-tight">
          Insure<span className="text-amber-400">Verify</span>
        </span>
      </motion.div>

      <motion.h1
        initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.1 }}
        className="font-display text-[34px] sm:text-[52px] leading-[1.1] max-w-3xl mb-5"
      >
        Most AI tools ask "is there damage?"<br/>
        <span className="text-amber-400">This one asks "can I trust this claim?"</span>
      </motion.h1>

      <motion.p
        initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.2 }}
        className="text-ink-400 text-[15px] sm:text-[17px] max-w-xl mb-9 leading-relaxed"
      >
        An 11-stage AI investigation pipeline that verifies evidence authenticity, ownership,
        possession, and story consistency — the way a real insurance investigator would,
        not just a damage classifier.
      </motion.p>

      <motion.button
        initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.3 }}
        whileHover={{ y: -2 }}
        whileTap={{ scale: 0.97 }}
        onClick={onGetStarted}
        className="flex items-center gap-2 px-6 py-3.5 rounded-lg bg-amber-400 text-ink-950 font-medium text-[15px] hover:bg-amber-500 transition-colors"
      >
        Get started <ArrowRight size={16} />
      </motion.button>

      <motion.div
        animate={{ y: [0, 8, 0] }}
        transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
        className="absolute bottom-10 text-ink-600 text-[11px] font-mono tracking-widest"
      >
        SCROLL TO EXPLORE
      </motion.div>
    </section>
  )
}

function HowItWorks() {
  return (
    <section className="py-24 sm:py-32 px-6 max-w-4xl mx-auto">
      <ScrollReveal>
        <p className="font-mono text-[11px] tracking-widest text-amber-400/90 uppercase mb-3 text-center">How it works</p>
        <h2 className="font-display text-[28px] sm:text-[36px] text-center mb-16 sm:mb-20">
          Eleven stages. One verdict you can actually audit.
        </h2>
      </ScrollReveal>

      <div className="space-y-16 sm:space-y-24">
        {STAGES.map((stage, i) => (
          <StageRow key={stage.title} stage={stage} index={i} />
        ))}
      </div>
    </section>
  )
}

function StageRow({ stage, index }) {
  const Icon = stage.icon
  const reversed = index % 2 === 1
  return (
    <ScrollReveal>
      <div className={`flex flex-col sm:flex-row items-center gap-6 sm:gap-10 ${reversed ? 'sm:flex-row-reverse' : ''}`}>
        <div className="w-20 h-20 sm:w-24 sm:h-24 rounded-2xl bg-amber-400/10 border border-amber-400/20 flex items-center justify-center flex-shrink-0">
          <Icon size={32} className="text-amber-400" strokeWidth={1.5} />
        </div>
        <div className="text-center sm:text-left">
          <span className="font-mono text-[11px] text-ink-600">STAGE {index + 1}</span>
          <h3 className="font-display text-xl sm:text-2xl mt-1 mb-2">{stage.title}</h3>
          <p className="text-ink-400 text-[14px] sm:text-[15px] leading-relaxed max-w-md">{stage.desc}</p>
        </div>
      </div>
    </ScrollReveal>
  )
}

function AgentsSection() {
  return (
    <section className="py-24 sm:py-32 px-6 bg-ink-900/30 border-y border-ink-700/60">
      <div className="max-w-4xl mx-auto">
        <ScrollReveal>
          <p className="font-mono text-[11px] tracking-widest text-amber-400/90 uppercase mb-3 text-center">The investigation team</p>
          <h2 className="font-display text-[28px] sm:text-[36px] text-center mb-4">
            Six specialist agents. One judge.
          </h2>
          <p className="text-ink-400 text-center max-w-lg mx-auto mb-14 sm:mb-16 text-[15px] leading-relaxed">
            Every claim is reviewed from six different angles before a Judge Agent combines
            them into a final, explainable verdict — with a literal chain of evidence behind it.
          </p>
        </ScrollReveal>

        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
          {AGENTS.map((agent, i) => (
            <ScrollReveal key={agent.name} delay={i * 0.05}>
              <div className="flex flex-col items-center gap-3 p-6 rounded-xl border border-ink-700 bg-ink-900/50 hover:border-amber-400/30 transition-colors">
                <agent.icon size={22} className="text-amber-400" strokeWidth={1.5} />
                <span className="text-[13px] text-paper-200 text-center">{agent.name}</span>
              </div>
            </ScrollReveal>
          ))}
        </div>
      </div>
    </section>
  )
}

function ClosingCTA({ onGetStarted }) {
  return (
    <section className="py-28 sm:py-36 px-6 text-center">
      <ScrollReveal>
        <h2 className="font-display text-[28px] sm:text-[40px] mb-6 max-w-xl mx-auto leading-tight">
          Ready to see the chain of evidence behind every claim?
        </h2>
        <motion.button
          whileHover={{ y: -2 }}
          whileTap={{ scale: 0.97 }}
          onClick={onGetStarted}
          className="inline-flex items-center gap-2 px-6 py-3.5 rounded-lg bg-amber-400 text-ink-950 font-medium text-[15px] hover:bg-amber-500 transition-colors"
        >
          Get started <ArrowRight size={16} />
        </motion.button>
      </ScrollReveal>
    </section>
  )
}

function ScrollReveal({ children, delay = 0 }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-80px' }}
      transition={{ duration: 0.55, delay, ease: 'easeOut' }}
    >
      {children}
    </motion.div>
  )
}
