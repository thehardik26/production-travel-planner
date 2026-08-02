import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Compass, LogOut } from 'lucide-react'
import { authApi, clearToken, tripsApi } from '../lib/api.js'
import TripForm from '../components/TripForm.jsx'
import TripHistorySidebar from '../components/TripHistorySidebar.jsx'
import TripResult from '../components/TripResult.jsx'

/**
 * The two backend shapes we render here aren't identical:
 * POST /api/trips/plan returns destination/start_date/end_date etc. at
 * the top level, while GET /api/trips/{id} nests the same fields under
 * "intent" (see app/api/routes/trips.py - `stored_itinerary`). Rather
 * than branching in every component, normalize once here so TripResult
 * only ever has to know one shape.
 */
function normalizeTrip(raw) {
  if (!raw) return null
  const intent = raw.intent || {}
  return {
    query: raw.query,
    destination: raw.destination ?? intent.destination,
    start_date: raw.start_date ?? intent.start_date,
    end_date: raw.end_date ?? intent.end_date,
    travelers: raw.travelers ?? intent.travelers,
    budget_summary: raw.budget_summary,
    itinerary: raw.itinerary,
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

  const loadTrips = useCallback(async () => {
    setTripsLoading(true)
    try {
      const list = await tripsApi.list()
      setTrips(list)
    } catch {
      // History is a nice-to-have, not the core flow - a failed refresh
      // here shouldn't block planning a new trip.
    } finally {
      setTripsLoading(false)
    }
  }, [])

  useEffect(() => {
    authApi
      .me()
      .then(setUser)
      .catch(() => {
        clearToken()
        navigate('/login', { replace: true })
      })
    loadTrips()
  }, [navigate, loadTrips])

  async function handleSelectTrip(tripId) {
    setSelectedId(tripId)
    setPlanError('')
    try {
      const data = await tripsApi.get(tripId)
      setSelectedTrip(normalizeTrip(data))
    } catch (err) {
      setPlanError(err.message)
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

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-4">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-white">
            <Compass className="h-4 w-4" />
          </div>
          <span className="font-semibold tracking-tight text-slate-900">Wanderplan</span>
        </div>
        <div className="flex items-center gap-3">
          {user?.email && <span className="hidden text-sm text-slate-500 sm:inline">{user.email}</span>}
          <button
            onClick={handleLogout}
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium text-slate-600 transition hover:bg-slate-100"
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </button>
        </div>
      </header>

      <main className="mx-auto grid max-w-6xl grid-cols-1 gap-6 px-6 py-8 lg:grid-cols-[320px_1fr]">
        <aside className="space-y-4">
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
            <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {planError}
            </div>
          )}
          <TripResult trip={selectedTrip} />
        </section>
      </main>
    </div>
  )
}
