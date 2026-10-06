import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Compass, Eye, EyeOff, Loader2, Lock, Mail, MapPin, Plane, Sparkles, ShieldCheck } from 'lucide-react'
import { authApi, setToken } from '../lib/api.js'

const HIGHLIGHTS = [
  { icon: MapPin, text: 'Curated boutique hotels, attractions, & transport for every destination' },
  { icon: Plane, text: 'Live airline search powered by real global aviation telemetry' },
  { icon: Sparkles, text: 'Day-by-day itineraries orchestrated by autonomous AI agents' },
]

export default function AuthPage({ mode }) {
  const isLogin = mode === 'login'
  const navigate = useNavigate()
  const location = useLocation()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [info, setInfo] = useState(location.state?.info || '')

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setInfo('')

    if (!isLogin && password !== confirmPassword) {
      setError("Passwords don't match")
      return
    }
    if (!isLogin && password.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }

    setLoading(true)
    let signupSucceeded = false
    try {
      if (!isLogin) {
        await authApi.signup(email, password)
        signupSucceeded = true
      }
      const { access_token } = await authApi.login(email, password)
      setToken(access_token)
      navigate('/dashboard', { replace: true })
    } catch (err) {
      if (signupSucceeded) {
        navigate('/login', {
          replace: true,
          state: { info: 'Your account was created. Please sign in below to access Aura Travel.' },
        })
      } else {
        setError(err.message)
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen w-full flex bg-[#faf9f6] text-slate-800">
      {/* Left editorial brand hero panel */}
      <div className="hidden lg:flex lg:w-1/2 relative overflow-hidden bg-gradient-to-br from-rose-50/80 via-amber-50/50 to-orange-50/60 border-r border-rose-100/80">
        <div className="absolute inset-0 text-slate-300/40 bg-map-dots" />
        <div className="absolute -left-20 top-1/4 h-80 w-80 rounded-full bg-rose-400/15 blur-3xl animate-[floatSlow_9s_ease-in-out_infinite]" />
        <div className="absolute right-10 top-10 h-72 w-72 rounded-full bg-amber-400/15 blur-3xl animate-[floatSlow_12s_ease-in-out_infinite]" />

        <div className="relative z-10 flex flex-col justify-between p-14 text-slate-800 w-full">
          {/* Top Logo */}
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-rose-500 via-orange-500 to-amber-400 text-white shadow-md shadow-rose-500/20">
              <Compass className="h-5 w-5" />
            </div>
            <span className="font-display text-2xl font-bold tracking-tight text-slate-900">
              Aura<span className="text-gradient-coral ml-1">Travel</span>
            </span>
          </div>

          {/* Hero Typography & Value Prop */}
          <div className="max-w-lg">
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-rose-200 bg-white/90 px-3 py-1 text-xs font-semibold tracking-wider text-rose-700 shadow-2xs">
              <Sparkles className="h-3.5 w-3.5 text-amber-500" />
              <span>THE NEXT-GEN AGENTIC TRAVEL COMPANION</span>
            </div>
            <h1 className="font-display text-5xl font-extrabold leading-[1.12] tracking-tight text-slate-900">
              The world, orchestrated in{' '}
              <span className="text-gradient-sunset">ambient luxury.</span>
            </h1>
            <p className="mt-5 text-slate-600 text-base leading-relaxed">
              Describe where and when you wish to wander. Five autonomous tool agents research real flights, hand-picked boutique hotels, and hyper-local activities in seconds.
            </p>

            <div className="mt-8 space-y-3.5">
              {HIGHLIGHTS.map(({ icon: Icon, text }) => (
                <div key={text} className="flex items-center gap-3.5 rounded-2xl border border-rose-100/80 bg-white/80 p-3.5 shadow-2xs backdrop-blur-sm transition-all hover:bg-white hover:shadow-xs">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-rose-500/10 to-amber-500/10 text-rose-600 ring-1 ring-rose-200/60">
                    <Icon className="h-4 w-4" />
                  </div>
                  <span className="text-xs sm:text-sm font-semibold text-slate-700">{text}</span>
                </div>
              ))}
            </div>

            <div className="mt-8 flex items-center gap-2.5 text-xs font-medium text-slate-500">
              <ShieldCheck className="h-4 w-4 text-emerald-600" />
              <span>Zero subscription friction • Instant agentic planning</span>
            </div>
          </div>

          <p className="text-xs text-slate-400">© {new Date().getFullYear()} Aura Travel Inc. All rights reserved.</p>
        </div>
      </div>

      {/* Right form panel */}
      <div className="flex flex-1 items-center justify-center px-6 py-12 sm:px-12 relative">
        <div className="w-full max-w-md animate-[fadeIn_.4s_ease-out]">
          {/* Mobile Logo Header */}
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-rose-500 to-amber-400 text-white shadow-md">
              <Compass className="h-5 w-5" />
            </div>
            <span className="font-display text-2xl font-bold tracking-tight text-slate-900">
              Aura<span className="text-gradient-coral ml-1">Travel</span>
            </span>
          </div>

          {/* Form Card Container */}
          <div className="card p-8 sm:p-9 shadow-lg shadow-slate-200/50">
            <h2 className="font-display text-3xl font-extrabold tracking-tight text-slate-900">
              {isLogin ? 'Welcome back' : 'Begin your journey'}
            </h2>
            <p className="mt-2 text-sm text-slate-500">
              {isLogin
                ? 'Sign in to access your curated itineraries.'
                : 'Create an account to begin planning your bespoke trips.'}
            </p>

            {info && !error && (
              <div className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs text-emerald-800">
                {info}
              </div>
            )}

            {error && (
              <div className="mt-5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs text-rose-800">
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="mt-6 space-y-4">
              <div>
                <label htmlFor="email" className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-700">
                  Email Address
                </label>
                <div className="relative">
                  <Mail className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                  <input
                    id="email"
                    type="email"
                    required
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="traveler@auratravel.com"
                    className="w-full rounded-xl border border-slate-200 bg-slate-50/60 py-2.5 pl-10 pr-3 text-sm text-slate-900 placeholder:text-slate-400 outline-none transition focus:border-rose-500 focus:bg-white focus:ring-4 focus:ring-rose-500/10"
                  />
                </div>
              </div>

              <div>
                <label htmlFor="password" className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-700">
                  Password
                </label>
                <div className="relative">
                  <Lock className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                  <input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    required
                    minLength={isLogin ? undefined : 8}
                    autoComplete={isLogin ? 'current-password' : 'new-password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full rounded-xl border border-slate-200 bg-slate-50/60 py-2.5 pl-10 pr-10 text-sm text-slate-900 placeholder:text-slate-400 outline-none transition focus:border-rose-500 focus:bg-white focus:ring-4 focus:ring-rose-500/10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 transition hover:text-slate-700"
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                {!isLogin && (
                  <p className="mt-1 text-[11px] text-slate-500">Must be at least 8 characters.</p>
                )}
              </div>

              {!isLogin && (
                <div>
                  <label htmlFor="confirm-password" className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-700">
                    Confirm Password
                  </label>
                  <div className="relative">
                    <Lock className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                    <input
                      id="confirm-password"
                      type={showPassword ? 'text' : 'password'}
                      required
                      autoComplete="new-password"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="••••••••"
                      className="w-full rounded-xl border border-slate-200 bg-slate-50/60 py-2.5 pl-10 pr-3 text-sm text-slate-900 placeholder:text-slate-400 outline-none transition focus:border-rose-500 focus:bg-white focus:ring-4 focus:ring-rose-500/10"
                    />
                  </div>
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl bg-sunset-glow-btn py-3 text-sm font-semibold text-white transition active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading && <Loader2 className="h-4 w-4 animate-spin" />}
                {loading ? 'Authenticating…' : isLogin ? 'Sign In to Aura Travel' : 'Create Free Account'}
              </button>
            </form>

            <div className="mt-6 border-t border-slate-100 pt-5 text-center text-xs text-slate-500">
              {isLogin ? (
                <>
                  New to Aura Travel?{' '}
                  <button
                    onClick={() => navigate('/signup')}
                    className="font-bold text-rose-600 transition hover:text-rose-700"
                  >
                    Create an account
                  </button>
                </>
              ) : (
                <>
                  Already registered?{' '}
                  <button
                    onClick={() => navigate('/login')}
                    className="font-bold text-rose-600 transition hover:text-rose-700"
                  >
                    Sign in here
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
