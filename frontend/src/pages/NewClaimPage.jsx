import React, { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Car, Laptop, Package, Upload, Video, Copy, Check, Loader2, ArrowRight, Clock, Zap } from 'lucide-react'
import { createClaim, uploadEvidence, verifyClaim, healthCheck } from '../lib/api.js'

const OBJECT_TYPES = [
  { value: 'car', label: 'Car', icon: Car },
  { value: 'laptop', label: 'Laptop', icon: Laptop },
  { value: 'package', label: 'Package', icon: Package },
]

const STEPS = ['Claim details', 'Evidence', 'Verification']

export default function NewClaimPage({ navigate }) {
  const [step, setStep] = useState(0)
  const [claimObject, setClaimObject] = useState('laptop')
  const [userId, setUserId] = useState('user_demo')
  const [userClaim, setUserClaim] = useState('')
  const [model, setModel] = useState('')
  const [serial, setSerial] = useState('')
  const [plate, setPlate] = useState('')
  const [vin, setVin] = useState('')
  const [policyStartDate, setPolicyStartDate] = useState('')
  const [region, setRegion] = useState('')
  const [ollamaInfo, setOllamaInfo] = useState(null)

  useEffect(() => {
    healthCheck().then(setOllamaInfo).catch(() => setOllamaInfo({ ollama_available: false, fast_mode: false }))
  }, [])

  const [claimId, setClaimId] = useState(null)
  const [challengeCode, setChallengeCode] = useState(null)
  const [images, setImages] = useState([])
  const [video, setVideo] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [verifying, setVerifying] = useState(false)
  const [error, setError] = useState(null)
  const [codeCopied, setCodeCopied] = useState(false)

  const fileInputRef = useRef(null)
  const videoInputRef = useRef(null)

  const handleCreateClaim = async () => {
    setSubmitting(true)
    setError(null)
    try {
      const res = await createClaim({
        user_id: userId,
        claim_object: claimObject,
        user_claim: userClaim,
        user_provided_model: model || null,
        user_provided_serial: serial || null,
        user_provided_plate: plate || null,
        user_provided_vin: vin || null,
        policy_start_date: policyStartDate || null,
        registered_region: region || null,
      })
      setClaimId(res.claim_id)
      setChallengeCode(res.challenge_code)
      setStep(1)
    } catch (e) {
      setError(e?.response?.data?.detail || 'Could not create claim. Is the backend running?')
    } finally {
      setSubmitting(false)
    }
  }

  const handleUploadAndVerify = async () => {
    if (images.length === 0) {
      setError('Please add at least one evidence photo.')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      await uploadEvidence(claimId, images, video)
      setStep(2)
      setVerifying(true)
      await verifyClaim(claimId)
      setVerifying(false)
      navigate('detail', claimId)
    } catch (e) {
      setVerifying(false)
      setStep(1)  // go back to a screen where the error is actually visible
      const detail = e?.response?.data?.detail
      setError(
        detail
          ? `Verification failed: ${detail}`
          : e?.message?.includes('Network')
            ? 'Could not reach the backend. Is it still running on port 8000?'
            : 'Verification failed unexpectedly. Check your backend terminal for the error and try again.'
      )
    } finally {
      setSubmitting(false)
    }
  }

  const copyCode = () => {
    navigator.clipboard.writeText(challengeCode)
    setCodeCopied(true)
    setTimeout(() => setCodeCopied(false), 1500)
  }

  return (
    <div className="pt-8 sm:pt-10 max-w-2xl mx-auto">
      <p className="font-mono text-[11px] tracking-widest text-amber-400/90 uppercase mb-2">New investigation</p>
      <h1 className="font-display text-[26px] sm:text-[32px] leading-tight mb-8">File a claim</h1>

      <StepIndicator step={step} />

      <AnimatePresence mode="wait">
        {step === 0 && (
          <motion.div key="s0" initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -12 }} transition={{ duration: 0.2 }}>
            <Section title="What was damaged?">
              <div className="grid grid-cols-3 gap-2 sm:gap-3">
                {OBJECT_TYPES.map(({ value, label, icon: Icon }) => (
                  <button
                    key={value}
                    onClick={() => setClaimObject(value)}
                    className={`flex flex-col items-center gap-2 py-5 rounded-lg border transition-all ${
                      claimObject === value
                        ? 'border-amber-400/60 bg-amber-400/10 text-amber-400'
                        : 'border-ink-700 text-ink-500 hover:border-ink-600 hover:text-paper-200'
                    }`}
                  >
                    <Icon size={22} strokeWidth={1.5} />
                    <span className="text-[13px]">{label}</span>
                  </button>
                ))}
              </div>
            </Section>

            <Section title="Tell us what happened">
              <textarea
                value={userClaim}
                onChange={(e) => setUserClaim(e.target.value)}
                placeholder="e.g. My laptop screen cracked after it fell off my desk while I was moving it."
                rows={4}
                className="w-full bg-ink-800/60 border border-ink-700 rounded-lg px-4 py-3 text-[14px] placeholder:text-ink-600 focus:border-amber-400/50 transition-colors resize-none"
              />
            </Section>

            <Section title="Identifying details (optional, but speeds up ownership verification)">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <Input label="Model" value={model} onChange={setModel} placeholder="Dell Inspiron 15" />
                <Input label="Serial number" value={serial} onChange={setSerial} placeholder="SN7X9K2L" />
                {claimObject === 'car' && <Input label="Number plate" value={plate} onChange={setPlate} placeholder="MH12AB1234" />}
                {claimObject === 'car' && <Input label="VIN" value={vin} onChange={setVin} placeholder="17-character VIN" />}
                <Input label="Policy start date" value={policyStartDate} onChange={setPolicyStartDate} placeholder="2025-01-15" />
                <Input label="Registered region" value={region} onChange={setRegion} placeholder="Pune" />
              </div>
            </Section>

            {error && <ErrorBanner message={error} />}

            <PrimaryButton onClick={handleCreateClaim} disabled={!userClaim || submitting} loading={submitting}>
              Create claim
            </PrimaryButton>
          </motion.div>
        )}

        {step === 1 && (
          <motion.div key="s1" initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -12 }} transition={{ duration: 0.2 }}>
            <ChallengeCodeCard code={challengeCode} copied={codeCopied} onCopy={copyCode} />

            <Section title="Upload evidence photos">
              <UploadDropzone
                accept="image/*"
                multiple
                files={images}
                onFiles={(files) => setImages([...images, ...files])}
                onRemove={(i) => setImages(images.filter((_, idx) => idx !== i))}
                icon={Upload}
                label="Drop photos here, or click to browse"
              />
            </Section>

            <Section title="Verification video (optional — recommended for higher trust scores)">
              <UploadDropzone
                accept="video/*"
                files={video ? [video] : []}
                onFiles={(files) => setVideo(files[0])}
                onRemove={() => setVideo(null)}
                icon={Video}
                label="Drop a short video of you with the object and code, or click to browse"
              />
            </Section>

            {error && <ErrorBanner message={error} />}

            <PrimaryButton onClick={handleUploadAndVerify} disabled={submitting} loading={submitting}>
              Submit evidence & run investigation
            </PrimaryButton>
          </motion.div>
        )}

        {step === 2 && (
          <motion.div key="s2" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="py-12 sm:py-16 flex flex-col items-center text-center">
            <ProcessingPanel ollamaInfo={ollamaInfo} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function StepIndicator({ step }) {
  return (
    <div className="flex items-center gap-2 mb-10">
      {STEPS.map((label, i) => (
        <React.Fragment key={label}>
          <div className="flex items-center gap-2">
            <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-mono transition-colors ${
              i < step ? 'bg-verdict-supported text-ink-950' : i === step ? 'bg-amber-400 text-ink-950' : 'bg-ink-800 text-ink-600'
            }`}>
              {i < step ? <Check size={12} /> : i + 1}
            </div>
            <span className={`text-[12px] ${i === step ? 'text-paper-100' : 'text-ink-600'}`}>{label}</span>
          </div>
          {i < STEPS.length - 1 && <div className="flex-1 h-px bg-ink-700" />}
        </React.Fragment>
      ))}
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div className="mb-7">
      <p className="text-[12px] text-ink-500 mb-3">{title}</p>
      {children}
    </div>
  )
}

function Input({ label, value, onChange, placeholder }) {
  return (
    <div>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-ink-800/60 border border-ink-700 rounded-lg px-3.5 py-2.5 text-[13px] placeholder:text-ink-600 focus:border-amber-400/50 transition-colors"
      />
    </div>
  )
}

function PrimaryButton({ onClick, disabled, loading, children }) {
  return (
    <motion.button
      whileHover={!disabled ? { y: -1 } : {}}
      whileTap={!disabled ? { scale: 0.98 } : {}}
      onClick={onClick}
      disabled={disabled}
      className="w-full flex items-center justify-center gap-2 py-3 rounded-lg bg-amber-400 text-ink-950 font-medium text-[14px] disabled:opacity-40 disabled:cursor-not-allowed hover:bg-amber-500 transition-colors"
    >
      {loading ? <Loader2 size={16} className="animate-spin" /> : null}
      {children}
      {!loading && <ArrowRight size={15} />}
    </motion.button>
  )
}

function ErrorBanner({ message }) {
  return (
    <div className="mb-5 text-[13px] text-verdict-contradicted border border-verdict-contradicted/30 bg-verdict-contradicted/5 rounded-lg px-4 py-3">
      {message}
    </div>
  )
}

function ChallengeCodeCard({ code, copied, onCopy }) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      className="mb-7 rounded-xl border border-amber-400/30 bg-amber-400/5 p-5"
    >
      <p className="text-[12px] text-ink-500 mb-2">
        Write this code on paper and place it next to the object in your photos/video. This proves you currently possess it.
      </p>
      <div className="flex items-center justify-between">
        <span className="font-mono text-2xl tracking-wider text-amber-400">{code}</span>
        <button onClick={onCopy} className="flex items-center gap-1.5 text-[12px] text-ink-500 hover:text-paper-100 transition-colors px-3 py-1.5 rounded-md border border-ink-700">
          {copied ? <Check size={13} /> : <Copy size={13} />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
    </motion.div>
  )
}

function UploadDropzone({ accept, multiple, files, onFiles, onRemove, icon: Icon, label }) {
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)

  const handleDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    onFiles(Array.from(e.dataTransfer.files))
  }

  return (
    <div>
      <div
        onClick={() => inputRef.current.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={`cursor-pointer rounded-lg border-2 border-dashed transition-colors px-5 py-8 flex flex-col items-center text-center ${
          dragging ? 'border-amber-400/60 bg-amber-400/5' : 'border-ink-700 hover:border-ink-600'
        }`}
      >
        <Icon size={20} className="text-ink-500 mb-2.5" strokeWidth={1.5} />
        <p className="text-[13px] text-ink-500">{label}</p>
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          multiple={multiple}
          className="hidden"
          onChange={(e) => onFiles(Array.from(e.target.files))}
        />
      </div>

      {files.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-3">
          {files.map((f, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              className="flex items-center gap-2 bg-ink-800 border border-ink-700 rounded-md px-3 py-1.5 text-[12px]"
            >
              <span className="truncate max-w-[140px]">{f.name}</span>
              <button onClick={() => onRemove(i)} className="text-ink-500 hover:text-verdict-contradicted">×</button>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  )
}

const PIPELINE_STAGES = [
  { label: 'Evidence authenticity (EXIF, ELA, AI-detection)', seconds: 2 },
  { label: 'Ownership & possession verification (OCR)', seconds: 3 },
  { label: 'Damage liveness & evidence sufficiency', seconds: 2 },
  { label: 'Vision-language analysis', seconds: 25 },
  { label: 'Claim understanding & story consistency', seconds: 15 },
  { label: 'Physics-based damage validation', seconds: 2 },
  { label: 'Risk scoring & fraud network check', seconds: 2 },
  { label: 'Multi-agent investigation & final verdict', seconds: 10 },
]

function ProcessingPanel({ ollamaInfo }) {
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    const start = Date.now()
    const interval = setInterval(() => setElapsed((Date.now() - start) / 1000), 200)
    return () => clearInterval(interval)
  }, [])

  // Stage estimates scale up a lot when Ollama is doing real LLM/VLM
  // inference vs. fast CV/regex fallbacks — reflect that honestly rather
  // than showing a generic spinner with no sense of expected duration.
  const usingLLM = ollamaInfo?.ollama_available && !ollamaInfo?.fast_mode
  const stages = PIPELINE_STAGES.map(s => ({
    ...s,
    seconds: usingLLM ? s.seconds : Math.min(s.seconds, 2),
  }))
  const totalEstimate = stages.reduce((sum, s) => sum + s.seconds, 0)
  let cumulative = 0
  const stageBoundaries = stages.map(s => {
    cumulative += s.seconds
    return cumulative
  })
  const activeIdx = stageBoundaries.findIndex(b => elapsed < b)
  const currentStage = activeIdx === -1 ? stages.length - 1 : activeIdx

  const minutes = Math.floor(elapsed / 60)
  const seconds = Math.floor(elapsed % 60)
  const overEstimate = elapsed > totalEstimate * 1.3

  return (
    <div className="w-full max-w-md">
      <div className="relative w-16 h-16 mx-auto mb-5">
        <div className="absolute inset-0 rounded-full border-2 border-ink-700" />
        <motion.div
          className="absolute inset-0 rounded-full border-2 border-amber-400 border-t-transparent"
          animate={{ rotate: 360 }}
          transition={{ duration: 1.1, repeat: Infinity, ease: 'linear' }}
        />
      </div>

      <h3 className="font-display text-xl mb-1">Running the investigation pipeline</h3>

      <div className="flex items-center justify-center gap-2 mb-1.5">
        <Clock size={14} className="text-ink-500" />
        <span className="font-mono text-lg tabular text-amber-400">
          {minutes > 0 ? `${minutes}m ` : ''}{seconds}s
        </span>
        <span className="text-ink-600 text-[12px]">elapsed</span>
      </div>

      <p className="text-[12px] text-ink-500 mb-6">
        {usingLLM ? (
          <span className="flex items-center justify-center gap-1.5">
            <Zap size={12} /> Using Ollama (llava + llama3) — typically {Math.round(totalEstimate)}s–{Math.round(totalEstimate * 2)}s on CPU
          </span>
        ) : (
          <span className="flex items-center justify-center gap-1.5">
            <Zap size={12} /> Fast mode (classical CV/OCR only) — typically under {Math.round(totalEstimate) + 5}s
          </span>
        )}
      </p>

      <div className="space-y-2.5 text-left">
        {stages.map((s, i) => {
          const done = i < currentStage
          const active = i === currentStage
          return (
            <motion.div
              key={s.label}
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: done || active ? 1 : 0.35, x: 0 }}
              className="flex items-center gap-2.5"
            >
              <span className={`w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0 ${
                done ? 'bg-verdict-supported' : active ? 'bg-amber-400' : 'bg-ink-700'
              }`}>
                {done && <Check size={10} className="text-ink-950" />}
                {active && <motion.span animate={{ scale: [1, 1.3, 1] }} transition={{ duration: 1, repeat: Infinity }} className="w-1.5 h-1.5 rounded-full bg-ink-950" />}
              </span>
              <span className={`text-[12.5px] ${active ? 'text-paper-100' : done ? 'text-ink-400' : 'text-ink-600'}`}>
                {s.label}
              </span>
            </motion.div>
          )
        })}
      </div>

      {overEstimate && (
        <motion.p
          initial={{ opacity: 0 }} animate={{ opacity: 1 }}
          className="mt-6 text-[12px] text-amber-400 bg-amber-400/10 border border-amber-400/20 rounded-lg px-3.5 py-2.5"
        >
          This is taking longer than usual. If Ollama is running on CPU without a GPU,
          vision-language analysis can take a while per image — it will finish, but if
          it's been several minutes, check your backend terminal for errors or consider
          setting <code className="font-mono">INSUREVERIFY_FAST_MODE=1</code> for instant
          classical-CV results.
        </motion.p>
      )}
    </div>
  )
}
