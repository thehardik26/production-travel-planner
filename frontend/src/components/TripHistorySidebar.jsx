import { MapPin } from 'lucide-react'
import { timeAgo } from '../lib/format.js'

export default function TripHistorySidebar({ trips, loading, selectedId, onSelect }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <h3 className="text-sm font-semibold text-slate-900">Recent trips</h3>

      {loading && <p className="mt-3 text-sm text-slate-400">Loading…</p>}

      {!loading && trips.length === 0 && (
        <p className="mt-3 text-sm text-slate-400">No trips planned yet — try the form above.</p>
      )}

      <ul className="mt-3 space-y-1">
        {trips.map((trip) => (
          <li key={trip.id}>
            <button
              onClick={() => onSelect(trip.id)}
              className={`w-full rounded-xl px-3 py-2.5 text-left transition ${
                selectedId === trip.id ? 'bg-indigo-50 ring-1 ring-indigo-200' : 'hover:bg-slate-50'
              }`}
            >
              <div className="flex items-center gap-1.5 text-sm font-medium text-slate-900">
                <MapPin className="h-3.5 w-3.5 shrink-0 text-indigo-500" />
                <span className="truncate">{trip.destination || 'Trip'}</span>
              </div>
              <p className="mt-0.5 truncate text-xs text-slate-500">{trip.query}</p>
              <p className="mt-0.5 text-[11px] text-slate-400">{timeAgo(trip.created_at)}</p>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
