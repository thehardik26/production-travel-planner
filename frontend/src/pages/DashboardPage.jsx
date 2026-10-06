import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Compass, LogOut, Sparkles, Radio } from 'lucide-react'
import { authApi, clearToken, tripsApi } from '../lib/api.js'
import TripForm from '../components/TripForm.jsx'
import TripHistorySidebar from '../components/TripHistorySidebar.jsx'
import TripResult from '../components/TripResult.jsx'

function normalizeTrip(raw) {
  if (!raw) return null
  const intent = raw.intent || {}
  const research = raw.research || {}
  return {
    query: raw.query,
    destination: raw.destination ?? intent.destination,
    start_date: raw.start_date ?? intent.start_date,
    end_date: raw.end_date ?? intent.end_date,
    travelers: raw.travelers ?? intent.travelers,
    budget_summary: raw.budget_summary,
    itinerary: raw.itinerary,
    weather: research.weather ?? null,
    flights: research.flights ?? [],
    hotels: research.hotels ?? [],
    destinationGuide: research.destination_guide ?? null,
    warnings: raw.warnings || [],
    errors: raw.errors || [],
  }
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const [user, setUser] = useState(null)
  const [trips, setTrips] = useState([])
  const [tripsLoading, setTripsLoading] = useState(true)
  const [selectedId, setSelectedId] = useState(null)
  const [selectedTrip, setSelectedTrip] = useState(null)
  const [planning, setPlanning] = useState(false)
  const [planError, setPlanError] = useState('')
  const latestRequestId = useRef(null)

  const loadTrips = useCallback(async () => {
    setTripsLoading(true)
    try {
      const list = await tripsApi.list()
      setTrips(list)
      if (list.length > 0 && selectedId === null) {
        setSelectedId(list[0].id)
        latestRequestId.current = list[0].id
        const full = await tripsApi.get(list[0].id)
        setSelectedTrip(normalizeTrip(full))
      }
    } catch {
      // Background load failures silently handled
    } finally {
      setTripsLoading(false)
    }
  }, [selectedId])

  useEffect(() => {
    let mounted = true
    authApi
      .me()
      .then((u) => {
        if (mounted) setUser(u)
      })
      .catch(() => {
        // me() failures redirect via unauthorized event
      })
    return () => {
      mounted = false
    }
  }, [])

  useEffect(() => {
    loadTrips()
  }, [loadTrips])

  async function handleSelectTrip(id) {
    if (id === selectedId && selectedTrip) return
    setSelectedId(id)
    latestRequestId.current = id
    try {
      const full = await tripsApi.get(id)
      if (latestRequestId.current === id) {
        setSelectedTrip(normalizeTrip(full))
      }
    } catch (err) {
      if (latestRequestId.current === id) {
        setPlanError(err.message)
      }
    }
  }

  async function handlePlan(query) {
    setPlanning(true)
    setPlanError('')
    try {
      const result = await tripsApi.plan(query)
      setSelectedId(result.trip_id)
      setSelectedTrip(normalizeTrip({ ...result, query }))
      loadTrips()
    } catch (err) {
      setPlanError(err.message)
    } finally {
      setPlanning(false)
    }
  }

  function handleLogout() {
    clearToken()
    navigate('/login', { replace: true })
  }

  const firstName = user?.email ? user.email.split('@')[0] : null
  const initial = user?.email ? user.email[0].toUpperCase() : '?'

  return (
    <div className="min-h-screen text-slate-800">
      {/* Floating Aesthetic White Navigation Header */}
      <header className="sticky top-0 z-30 border-b border-slate-200/80 bg-white/90 backdrop-blur-xl shadow-xs transition-all duration-300">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3.5">
          {/* Brand Identity */}
          <div className="flex items-center gap-3">
            <div className="relative flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-rose-500 via-orange-500 to-amber-400 text-white shadow-md shadow-rose-500/20">
              <Compass className="h-5 w-5 transition-transform duration-300 hover:rotate-45" />
              <div className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-white bg-emerald-500" />
            </div>
            <div className="flex flex-col">
              <div className="flex items-center gap-2">
                <span className="font-display text-xl font-bold tracking-tight text-slate-900">
                  Aura<span className="text-gradient-coral ml-1">Travel</span>
                </span>
                <span className="hidden rounded-full border border-rose-200 bg-rose-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-rose-700 md:inline-flex items-center gap-1">
                  <Sparkles className="h-2.5 w-2.5 text-amber-500" />
                  AI Concierge
                </span>
              </div>
            </div>
          </div>

          {/* Right Header Navigation & User Profile */}
          <div className="flex items-center gap-3.5">
            <div className="hidden lg:flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50/80 px-3 py-1 text-xs font-medium text-emerald-800">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-600" />
              </span>
              <span>5 Tool Agents Active</span>
            </div>

            {user?.email && (
              <span className="flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50/80 py-1 pl-1 pr-3.5 shadow-2xs">
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-tr from-rose-500 to-amber-500 text-xs font-bold text-white shadow-xs">
                  {initial}
                </span>
                <span className="text-xs font-semibold text-slate-700">{user.email}</span>
              </span>
            )}
            <button
              onClick={handleLogout}
              className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 py-1.5 text-xs font-semibold text-slate-600 shadow-2xs transition-all duration-200 hover:border-rose-200 hover:bg-rose-50 hover:text-rose-700"
            >
              <LogOut className="h-3.5 w-3.5 text-rose-500" />
              <span className="hidden sm:inline">Sign out</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="mx-auto max-w-7xl px-6 py-9">
        <div className="mb-8">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-rose-600">
            <Radio className="h-3.5 w-3.5 animate-pulse text-amber-500" />
            <span>Ambient Autonomous Travel Network</span>
          </div>
          <h1 className="font-display mt-2 text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
            {firstName ? (
              <>
                Where shall your aura wander,{' '}
                <span className="text-gradient-sunset">{firstName}</span>?
              </>
            ) : (
              <>
                Where would you like your aura to{' '}
                <span className="text-gradient-sunset">wander</span>?
              </>
            )}
          </h1>
          <p className="mt-2 text-sm text-slate-500 max-w-2xl leading-relaxed">
            Real-time airline routes, curated stays, live weather telemetry, and intelligent multi-agent itineraries — orchestrated in ambient harmony.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-7 lg:grid-cols-[380px_1fr] lg:items-start">
          <aside className="space-y-6 lg:sticky lg:top-24">
            <TripForm onSubmit={handlePlan} loading={planning} />
            <TripHistorySidebar
              trips={trips}
              loading={tripsLoading}
              selectedId={selectedId}
              onSelect={handleSelectTrip}
            />
          </aside>

          <section>
            {planError && (
              <div className="mb-5 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800 shadow-xs">
                <p className="font-semibold text-rose-900">Planning notice:</p>
                <p className="mt-1 text-rose-700">{planError}</p>
              </div>
            )}
            <TripResult trip={selectedTrip} loading={planning} />
          </section>
        </div>
      </main>
    </div>
  )
}
