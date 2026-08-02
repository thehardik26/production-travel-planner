import { AlertTriangle, Banknote, CalendarDays, FlaskConical, Info, MapPin, Users } from 'lucide-react'
import { formatDateRange, formatDateShort, formatMoney } from '../lib/format.js'

export default function TripResult({ trip }) {
  if (!trip) {
    return (
      <div className="flex h-full min-h-[400px] flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-white text-center">
        <MapPin className="h-8 w-8 text-slate-300" />
        <p className="mt-3 text-sm font-medium text-slate-500">No trip selected yet</p>
        <p className="mt-1 max-w-xs text-xs text-slate-400">
          Describe a trip on the left and hit &quot;Plan trip&quot;, or pick a past trip from your history.
        </p>
      </div>
    )
  }

  const { destination, start_date, end_date, travelers, budget_summary, itinerary, warnings, errors } = trip
  const days = itinerary?.days || []

  return (
    <div className="space-y-4">
      {/* Header card */}
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="flex items-center gap-1.5 text-xl font-bold text-slate-900">
              <MapPin className="h-5 w-5 text-indigo-600" />
              {destination || 'Your trip'}
            </h2>
            {start_date && end_date && (
              <p className="mt-1 flex items-center gap-1.5 text-sm text-slate-500">
                <CalendarDays className="h-4 w-4" />
                {formatDateRange(start_date, end_date)}
              </p>
            )}
          </div>
          {travelers ? (
            <span className="flex items-center gap-1.5 rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
              <Users className="h-3.5 w-3.5" />
              {travelers} traveler{travelers > 1 ? 's' : ''}
            </span>
          ) : null}
        </div>
      </div>

      {/* Warnings / errors - surfaced, not hidden, so a degraded plan is visible not silent */}
      {(warnings?.length > 0 || errors?.length > 0) && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
          <div className="flex items-center gap-1.5 text-sm font-semibold text-amber-800">
            <AlertTriangle className="h-4 w-4" />
            Some data was incomplete
          </div>
          <ul className="mt-2 space-y-1 text-xs text-amber-700">
            {warnings.map((w, i) => (
              <li key={`w-${i}`}>• {w}</li>
            ))}
            {errors.map((e, i) => (
              <li key={`e-${i}`}>• {e}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Budget summary */}
      {budget_summary && (
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="flex items-center gap-1.5 text-sm font-semibold text-slate-900">
            <Banknote className="h-4 w-4 text-indigo-600" />
            Budget
          </h3>
          <div className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-3">
            <div>
              <p className="text-xs text-slate-400">Your budget</p>
              <p className="mt-0.5 text-lg font-semibold text-slate-900">
                {budget_summary.budget != null
                  ? formatMoney(budget_summary.budget, budget_summary.budget_currency)
                  : '—'}
              </p>
            </div>
            <div>
              <p className="flex items-center gap-1.5 text-xs text-slate-400">
                Estimated cost
                {budget_summary.estimated_total != null && (
                  <span className="flex items-center gap-1 rounded-full bg-orange-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-orange-700">
                    <FlaskConical className="h-2.5 w-2.5" />
                    Test data
                  </span>
                )}
              </p>
              <p className="mt-0.5 text-lg font-semibold text-slate-900">
                {budget_summary.estimated_total != null
                  ? formatMoney(budget_summary.estimated_total, budget_summary.estimated_total_currency)
                  : 'Not available'}
              </p>
            </div>
            {budget_summary.over_budget && (
              <div className="flex items-center">
                <span className="rounded-full bg-red-100 px-2.5 py-1 text-xs font-medium text-red-700">
                  Over budget
                </span>
              </div>
            )}
          </div>
          {budget_summary.estimated_total != null && (
            <p className="mt-3 flex items-start gap-1.5 text-xs text-orange-600">
              <FlaskConical className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              Flight prices come from Duffel&apos;s test mode (simulated airline data) - not real
              market prices. Hotel prices aren&apos;t available at all yet (see below).
            </p>
          )}
          {budget_summary.missing_estimates?.length > 0 && (
            <p className="mt-3 flex items-start gap-1.5 text-xs text-slate-400">
              <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              No live pricing available for: {budget_summary.missing_estimates.join(', ')}
            </p>
          )}
        </div>
      )}

      {/* Itinerary */}
      {days.length > 0 && (
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-slate-900">Day-by-day itinerary</h3>
          <ol className="mt-4 space-y-4">
            {days.map((day, i) => (
              <li key={day.date || i} className="relative pl-6">
                <span className="absolute left-0 top-1 flex h-4 w-4 items-center justify-center rounded-full bg-indigo-600 text-[10px] font-bold text-white">
                  {i + 1}
                </span>
                {i < days.length - 1 && (
                  <span className="absolute left-[7px] top-5 h-[calc(100%-4px)] w-px bg-slate-200" />
                )}
                <p className="text-xs font-medium uppercase tracking-wide text-indigo-600">
                  {formatDateShort(day.date)}
                </p>
                <p className="mt-0.5 text-sm font-semibold text-slate-900">{day.summary}</p>
                {day.activities?.length > 0 && (
                  <ul className="mt-1.5 space-y-1">
                    {day.activities.map((a, ai) => (
                      <li key={ai} className="text-sm text-slate-600">
                        • {a}
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ol>
          {itinerary?.notes && (
            <p className="mt-4 rounded-xl bg-slate-50 p-3 text-xs text-slate-500">{itinerary.notes}</p>
          )}
        </div>
      )}
    </div>
  )
}
