import { useState } from 'react'
import { Loader2, Send, Sparkles, Compass } from 'lucide-react'

const PLACEHOLDER = '5 day trip to Goa from Delhi starting 2026-09-10, budget 50000 INR, 2 travelers, love food and beaches'

const EXAMPLES = [
  { label: 'Goa Beaches & Food', text: '5 day trip to Goa from Delhi starting 2026-09-10, budget 50000 INR, 2 travelers, love food and beaches' },
  { label: 'Manali Alpine Retreat', text: '3 day trip to Manali from Chandigarh starting 2026-10-05, budget 20000 INR, 1 traveler, love mountains and adventure' },
  { label: 'Udaipur Royal Lakes', text: 'Weekend trip to Udaipur from Mumbai, budget 30000 INR, 2 travelers, love culture and lake views' },
]

export default function TripForm({ onSubmit, loading }) {
  const [query, setQuery] = useState('')

  function handleSubmit(e) {
    e.preventDefault()
    if (!query.trim() || loading) return
    onSubmit(query.trim())
  }

  return (
    <form onSubmit={handleSubmit} className="card p-6 relative overflow-hidden shadow-sm">
      {/* Top sunset accent stripe */}
      <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-rose-500 via-orange-500 to-amber-400" />

      <label htmlFor="trip-query" className="flex items-center gap-2.5 font-display text-lg font-bold text-slate-900">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-rose-500/10 to-amber-500/10 text-rose-600 ring-1 ring-rose-200/50">
          <Sparkles className="h-4 w-4 text-amber-500" />
        </span>
        Plan a bespoke trip
      </label>
      <p className="mt-1.5 text-xs leading-relaxed text-slate-500">
        Describe your vision in plain natural language — the AI agents orchestrate the itinerary.
      </p>

      <textarea
        id="trip-query"
        rows={4}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={PLACEHOLDER}
        className="mt-4 w-full resize-none rounded-xl border border-slate-200 bg-slate-50/70 p-3.5 text-sm leading-relaxed text-slate-900 placeholder:text-slate-400 outline-none transition focus:border-rose-400 focus:bg-white focus:ring-4 focus:ring-rose-500/10"
      />

      <div className="mt-3.5">
        <div className="mb-2 flex items-center justify-between text-[11px] font-semibold uppercase tracking-wider text-slate-400">
          <span>Inspiration Prompts</span>
          <Compass className="h-3 w-3 text-rose-500" />
        </div>
        <div className="flex flex-wrap gap-2">
          {EXAMPLES.map((ex) => (
            <button
              key={ex.label}
              type="button"
              onClick={() => setQuery(ex.text)}
              className="rounded-full border border-slate-200 bg-slate-50/60 px-3 py-1 text-xs font-medium text-slate-600 transition-all hover:border-rose-300 hover:bg-rose-50 hover:text-rose-700 hover:scale-[1.02] active:scale-[0.98]"
              title={ex.text}
            >
              {ex.label}
            </button>
          ))}
        </div>
      </div>

      <button
        type="submit"
        disabled={loading || !query.trim()}
        className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-sunset-glow-btn py-3 text-sm font-semibold text-white transition active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-50"
      >
        {loading ? <Loader2 className="h-4 w-4 animate-spin text-white" /> : <Send className="h-4 w-4" />}
        {loading ? 'Synthesizing live travel data…' : 'Generate Aura Itinerary'}
      </button>

      <p className="mt-3 text-[11px] leading-relaxed text-slate-400 text-center">
        Specify dates, origin, budget, and traveler count for precision pricing.
      </p>
    </form>
  )
}
