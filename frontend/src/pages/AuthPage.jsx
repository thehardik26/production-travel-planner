import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Compass, Eye, EyeOff, Loader2, Lock, Mail, MapPin, Plane } from 'lucide-react'
import { authApi, setToken } from '../lib/api.js'

const HIGHLIGHTS = [
  { icon: MapPin, text: 'Real hotels, attractions and transport for every destination' },
  { icon: Plane, text: 'Live flight search, powered by real airline data' },
  { icon: Compass, text: 'A full day-by-day itinerary, built for you in seconds' },
]

export default function AuthPage({ mode }) {
  const isLogin = mode === 'login'
  const navigate = useNavigate()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')

    if (!isLogin && password !== confirmPassword) {
      setError("Passwords don't match")
      return
    }
    if (!isLogin && password.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }

    setLoading(true)
    try {
      if (!isLogin) {
        await authApi.signup(email, password)
      }
      const { access_token } = await authApi.login(email, password)
      setToken(access_token)
      navigate('/dashboard', { replace: true })
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen w-full flex bg-slate-50">
      {/* Left brand panel - hidden on small screens */}
      <div className="hidden lg:flex lg:w-1/2 relative overflow-hidden bg-gradient-to-br from-indigo-600 via-blue-600 to-teal-500">
        <div className="absolute inset-0 opacity-20 [background-image:radial-gradient(circle_at_20%_20%,white,transparent_35%),radial-gradient(circle_at_80%_60%,white,transparent_30%)]" />
        <div className="relative z-10 flex flex-col justify-between p-12 text-white w-full">
          <div className="flex items-center gap-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/15 backdrop-blur">
              <Compass className="h-5 w-5" />
            </div>
            <span className="text-lg font-semibold tracking-tight">Wanderplan</span>
          </div>

          <div className="max-w-md">
            <h1 className="text-4xl font-bold leading-tight tracking-tight">
              Plan your next trip in one sentence.
            </h1>
            <p className="mt-4 text-blue-100 text-lg leading-relaxed">
              Tell us where and when — real flights, hotels, weather and a
              day-by-day itinerary, assembled for you automatically.
            </p>

            <div className="mt-10 space-y-4">
              {HIGHLIGHTS.map(({ icon: Icon, text }) => (
                <div key={text} className="flex items-center gap-3">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/15 backdrop-blur">
                    <Icon className="h-4 w-4" />
                  </div>
                  <span className="text-sm text-blue-50">{text}</span>
                </div>
              ))}
            </div>
          </div>

          <p className="text-xs text-blue-200">© {new Date().getFullYear()} Wanderplan</p>
        </div>
      </div>

      {/* Right form panel */}
      <div className="flex flex-1 items-center justify-center px-6 py-12 sm:px-10">
        <div className="w-full max-w-sm animate-[fadeIn_.4s_ease-out]">
          <div className="mb-8 flex items-center gap-2 lg:hidden">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-600 text-white">
              <Compass className="h-5 w-5" />
            </div>
            <span className="text-lg font-semibold tracking-tight text-slate-900">Wanderplan</span>
          </div>

          <h2 className="text-2xl font-bold tracking-tight text-slate-900">
            {isLogin ? 'Welcome back' : 'Create your account'}
          </h2>
          <p className="mt-1.5 text-sm text-slate-500">
            {isLogin
              ? 'Sign in to keep planning your trips.'
              : 'Start planning trips with real, live travel data.'}
          </p>

          {error && (
            <div className="mt-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            <div>
              <label htmlFor="email" className="mb-1.5 block text-sm font-medium text-slate-700">
                Email
              </label>
              <div className="relative">
                <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  id="email"
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-10 pr-3 text-sm text-slate-900 placeholder:text-slate-400 shadow-sm outline-none transition focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/10"
                />
              </div>
            </div>

            <div>
              <label htmlFor="password" className="mb-1.5 block text-sm font-medium text-slate-700">
                Password
              </label>
              <div className="relative">
                <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  required
                  minLength={isLogin ? undefined : 8}
                  autoComplete={isLogin ? 'current-password' : 'new-password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-10 pr-10 text-sm text-slate-900 placeholder:text-slate-400 shadow-sm outline-none transition focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 transition hover:text-slate-600"
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {!isLogin && (
                <p className="mt-1.5 text-xs text-slate-400">Must be at least 8 characters.</p>
              )}
            </div>

            {!isLogin && (
              <div>
                <label htmlFor="confirm-password" className="mb-1.5 block text-sm font-medium text-slate-700">
                  Confirm password
                </label>
                <div className="relative">
                  <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                  <input
                    id="confirm-password"
                    type={showPassword ? 'text' : 'password'}
                    required
                    autoComplete="new-password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-10 pr-3 text-sm text-slate-900 placeholder:text-slate-400 shadow-sm outline-none transition focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/10"
                  />
                </div>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-blue-600 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-600/20 transition hover:from-indigo-500 hover:to-blue-500 disabled:cursor-not-allowed disabled:opacity-70"
            >
              {loading && <Loader2 className="h-4 w-4 animate-spin" />}
              {loading ? 'Please wait…' : isLogin ? 'Sign in' : 'Create account'}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-slate-500">
            {isLogin ? (
              <>
                Don't have an account?{' '}
                <button
                  onClick={() => navigate('/signup')}
                  className="font-semibold text-indigo-600 transition hover:text-indigo-500"
                >
                  Sign up
                </button>
              </>
            ) : (
              <>
                Already have an account?{' '}
                <button
                  onClick={() => navigate('/login')}
                  className="font-semibold text-indigo-600 transition hover:text-indigo-500"
                >
                  Sign in
                </button>
              </>
            )}
          </p>
        </div>
      </div>
    </div>
  )
}
