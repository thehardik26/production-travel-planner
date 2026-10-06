import { Compass, MapPin, Sparkles } from 'lucide-react'
import { timeAgo } from '../lib/format.js'
import { destinationGradient } from '../lib/visuals.js'

export default function TripHistorySidebar({ trips, loading, selectedId, onSelect }) {
  return (
    <div className="card p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <h3 className="flex items-center gap-2 font-display text-base font-bold text-slate-900">
          <Sparkles className="h-4 w-4 text-amber-500" />
          Saved Expeditions
        </h3>
        {trips.length > 0 && (
          <span className="rounded-full border border-rose-200 bg-rose-50 px-2.5 py-0.5 text-xs font-semibold text-rose-700">
            {trips.length}
          </span>
        )}
      </div>

      {loading && (
        <div className="mt-4 space-y-2.5">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-16 animate-pulse rounded-2xl bg-slate-100" />
          ))}
        </div>
      )}

      {!loading && trips.length === 0 && (
        <div className="mt-4 flex flex-col items-center rounded-2xl border border-dashed border-slate-200 bg-slate-50/50 py-8 text-center">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-slate-400">
            <Compass className="h-5 w-5" />
          </div>
          <p className="mt-3 text-xs font-medium text-slate-600">No journeys planned yet.</p>
          <p className="mt-1 text-[11px] text-slate-400">Your planned itineraries will appear here.</p>
        </div>
      )}

      <ul className="mt-3.5 max-h-[28rem] space-y-1.5 overflow-y-auto pr-1">
        {trips.map((trip) => {
          const gradient = destinationGradient(trip.destination || trip.query)
          const selected = selectedId === trip.id
          return (
            <li key={trip.id}>
              <button
                onClick={() => onSelect(trip.id)}
                className={`flex w-full items-center gap-3 rounded-2xl p-2.5 text-left transition-all duration-200 ${
                  selected
                    ? 'border border-rose-300 bg-rose-50/70 shadow-xs ring-1 ring-rose-200'
                    : 'border border-transparent bg-slate-50/60 hover:border-slate-200 hover:bg-slate-100/70'
                }`}
              >
                <div
                  className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-white shadow-xs"
                  style={gradient.style}
                >
                  <MapPin className="h-5 w-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-slate-900">
                    {trip.destination || 'Uncharted Trip'}
                  </p>
                  <p className="truncate text-xs text-slate-500">{trip.query}</p>
                  <p className="mt-0.5 text-[11px] font-medium text-rose-600">{timeAgo(trip.created_at)}</p>
                </div>
                {selected && (
                  <span className="relative flex h-2 w-2 shrink-0">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-rose-400 opacity-75" />
                    <span className="relative inline-flex h-2 w-2 rounded-full bg-rose-500" />
                  </span>
                )}
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
