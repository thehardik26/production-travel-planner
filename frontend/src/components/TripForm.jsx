import { useState } from 'react'
import { Loader2, Send, Sparkles } from 'lucide-react'

const EXAMPLE = '5 day trip to Goa from Delhi starting 2026-09-10, budget 50000 INR, 2 travelers, love food and beaches'

export default function TripForm({ onSubmit, loading }) {
  const [query, setQuery] = useState('')

  function handleSubmit(e) {
    e.preventDefault()
    if (!query.trim() || loading) return
    onSubmit(query.trim())
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <label htmlFor="trip-query" className="flex items-center gap-1.5 text-sm font-semibold text-slate-900">
        <Sparkles className="h-4 w-4 text-indigo-600" />
        Plan a new trip
      </label>
      <textarea
        id="trip-query"
        rows={4}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={EXAMPLE}
        className="mt-2 w-full resize-none rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 outline-none transition focus:border-indigo-500 focus:bg-white focus:ring-4 focus:ring-indigo-500/10"
      />
      <button
        type="submit"
        disabled={loading || !query.trim()}
        className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-blue-600 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-600/20 transition hover:from-indigo-500 hover:to-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
        {loading ? 'Planning your trip…' : 'Plan trip'}
      </button>
      <p className="mt-2 text-xs text-slate-400">
        Mention destination, dates, budget, travelers and what you like — the more detail, the better the plan.
      </p>
    </form>
  )
}
