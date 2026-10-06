import {
  Banknote,
  BedDouble,
  BookOpen,
  CalendarDays,
  Camera,
  Car,
  Cloud,
  CloudFog,
  CloudLightning,
  CloudRain,
  CloudSun,
  Coffee,
  Compass,
  Droplets,
  ExternalLink,
  FlaskConical,
  Info,
  Landmark,
  MapPin,
  Mountain,
  Plane,
  ShoppingBag,
  Snowflake,
  Sparkles,
  Star,
  Sun,
  Thermometer,
  UtensilsCrossed,
  Users,
  Waves,
  Wind,
} from 'lucide-react'
import { formatDateRange, formatDateShort, formatMoney } from '../lib/format.js'
import { activityIcon, destinationGradient, flightSearchUrl, hotelSearchUrl, weatherVisual } from '../lib/visuals.js'

const WEATHER_ICONS = { Sun, Cloud, CloudFog, CloudRain, Snowflake, CloudLightning, Wind, CloudSun }
const ACTIVITY_ICONS = {
  Coffee, UtensilsCrossed, BedDouble, Plane, Car, Waves, Mountain, Landmark,
  ShoppingBag, Sparkles, Camera, MapPin,
}

function SectionHeading({ icon: Icon, children, trailing }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <h3 className="flex items-center gap-2.5 font-display text-base font-bold text-slate-900">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-rose-500/10 to-amber-500/10 text-rose-600 ring-1 ring-rose-200/50">
          <Icon className="h-4 w-4" />
        </span>
        {children}
      </h3>
      {trailing}
    </div>
  )
}

function LoadingState() {
  return (
    <div className="space-y-4">
      <div className="card animate-pulse p-6">
        <div className="flex items-center gap-4">
          <div className="h-16 w-16 rounded-2xl bg-slate-200" />
          <div className="flex-1 space-y-2.5">
            <div className="h-6 w-48 rounded-lg bg-slate-200" />
            <div className="h-4 w-64 rounded-lg bg-slate-100" />
          </div>
        </div>
      </div>
      <div className="flex items-center justify-center gap-3 rounded-2xl border border-dashed border-rose-300 bg-rose-50/50 py-10 text-rose-800">
        <span className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-tr from-rose-500 to-amber-500 text-white shadow-md shadow-rose-500/20">
          <Compass className="h-5 w-5 animate-spin" />
        </span>
        <div>
          <p className="text-sm font-bold text-slate-900">
            Autonomous agent network is researching your journey…
          </p>
          <p className="text-xs text-rose-700">
            Querying flights, boutique hotels, weather telemetry, and local guides.
          </p>
        </div>
      </div>
      {[0, 1].map((i) => (
        <div key={i} className="card animate-pulse p-6">
          <div className="h-4 w-32 rounded bg-slate-200" />
          <div className="mt-3 h-3 w-full rounded bg-slate-100" />
          <div className="mt-2 h-3 w-3/4 rounded bg-slate-100" />
        </div>
      ))}
    </div>
  )
}

function EmptyState() {
  return (
    <div className="relative flex h-full min-h-[440px] flex-col items-center justify-center overflow-hidden rounded-3xl border border-dashed border-slate-300 bg-white/80 p-8 text-center shadow-xs">
      <div className="absolute inset-0 text-slate-200/50 bg-map-dots" />
      <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-rose-500 via-orange-500 to-amber-400 text-white shadow-lg shadow-rose-500/20">
        <Compass className="h-8 w-8 transition-transform duration-500 hover:rotate-90" />
      </div>
      <p className="relative mt-5 font-display text-2xl font-bold text-slate-900 tracking-tight">No journey selected yet</p>
      <p className="relative mt-2 max-w-sm text-sm leading-relaxed text-slate-500">
        Describe a dream getaway on the left and click "Generate Aura Itinerary", or select a past journey from your saved expeditions.
      </p>
    </div>
  )
}

export default function TripResult({ trip, loading }) {
  if (loading) return <LoadingState />
  if (!trip) return <EmptyState />

  const { destination, start_date, end_date, travelers, budget_summary, itinerary, weather, flights, hotels, destinationGuide, warnings, errors } = trip
  const days = itinerary?.days || []
  const gradient = destinationGradient(destination)

  const currenciesDiffer =
    budget_summary?.budget_currency &&
    budget_summary?.estimated_total_currency &&
    budget_summary.budget_currency !== budget_summary.estimated_total_currency
  const compareTotal = currenciesDiffer
    ? budget_summary?.estimated_total_converted
    : budget_summary?.estimated_total
  const currencyMismatch = currenciesDiffer && budget_summary?.over_budget == null
  const budgetPct =
    budget_summary?.budget && compareTotal != null
      ? Math.min(100, Math.round((compareTotal / budget_summary.budget) * 100))
      : null

  return (
    <div className="space-y-6">
      {/* Hero Header */}
      <div className="card overflow-hidden shadow-sm relative">
        <div className="relative h-36 text-white" style={gradient.style}>
          <div className="absolute inset-0 bg-map-dots text-white/20" />
          <div className="absolute inset-0 bg-gradient-to-t from-black/20 via-transparent to-transparent" />
        </div>
        <div className="relative flex flex-wrap items-start justify-between gap-4 px-7 pb-6 pt-0">
          <div className="-mt-12 flex items-end gap-5">
            <div
              className="flex h-20 w-20 shrink-0 items-center justify-center rounded-2xl text-white shadow-xl ring-4 ring-white"
              style={gradient.style}
            >
              <MapPin className="h-10 w-10 drop-shadow-sm" />
            </div>
            <div className="pb-1">
              <h2 className="font-display text-3xl font-extrabold leading-tight tracking-tight text-slate-900 sm:text-4xl">
                {destination || 'Your Expedition'}
              </h2>
              {start_date && end_date && (
                <p className="mt-1.5 flex items-center gap-2 text-sm font-semibold text-slate-600">
                  <CalendarDays className="h-4 w-4 text-rose-500" />
                  {formatDateRange(start_date, end_date)}
                </p>
              )}
            </div>
          </div>
          {travelers ? (
            <span className="mt-2 flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-4 py-1.5 text-xs font-bold text-slate-700 shadow-2xs">
              <Users className="h-4 w-4 text-rose-500" />
              {travelers} traveler{travelers > 1 ? 's' : ''}
            </span>
          ) : null}
        </div>
      </div>

      {/* Advisory Notices */}
      {(warnings?.length > 0 || errors?.length > 0) && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-amber-800">
            <Info className="h-4 w-4 text-amber-600" />
            Advisory Telemetry
          </div>
          <ul className="mt-2.5 space-y-1.5">
            {[...warnings, ...errors].map((msg, i) => (
              <li key={i} className="flex items-start gap-2.5 text-xs leading-relaxed text-amber-900">
                <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500" />
                <span>{msg}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Weather + Budget Matrix */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
        {weather && (
          <div className="card p-6 shadow-sm">
            {(() => {
              const { icon } = weatherVisual(weather.condition)
              const Icon = WEATHER_ICONS[icon] || CloudSun
              return <SectionHeading icon={Icon}>Atmospheric Forecast</SectionHeading>
            })()}
            <div className="mt-5 flex items-center gap-4">
              <p className="flex items-baseline gap-1.5 font-display text-4xl font-extrabold text-slate-900">
                {Math.round(weather.temp_high_c)}°
                <span className="text-lg font-normal text-slate-400">/ {Math.round(weather.temp_low_c)}°C</span>
              </p>
              <div className="rounded-xl border border-slate-100 bg-slate-50 p-2 text-rose-500">
                <Thermometer className="h-5 w-5" />
              </div>
            </div>
            <div className="mt-3 flex items-center gap-3.5 text-xs font-medium text-slate-600">
              <span className="capitalize text-slate-800 font-semibold">{weatherVisual(weather.condition).label}</span>
              {weather.precipitation_chance != null && (
                <span className="flex items-center gap-1.5 rounded-full border border-sky-200 bg-sky-50 px-2.5 py-0.5 text-sky-700 font-semibold">
                  <Droplets className="h-3 w-3" />
                  {weather.precipitation_chance}% precipitation
                </span>
              )}
            </div>
          </div>
        )}

        {budget_summary && (
          <div className="card p-6 shadow-sm">
            <SectionHeading icon={Banknote}>Budget Overview</SectionHeading>
            <div className="mt-5 flex items-end justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Your Target</p>
                <p className="mt-1 text-xl font-bold text-slate-900">
                  {budget_summary.budget != null
                    ? formatMoney(budget_summary.budget, budget_summary.budget_currency)
                    : '—'}
                </p>
              </div>
              <div className="text-right">
                <p className="flex items-center justify-end gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Estimated Total
                  {budget_summary.estimated_total != null && (
                    <span className="flex items-center gap-1 rounded-full border border-rose-200 bg-rose-50 px-2 py-0.5 text-[10px] font-bold text-rose-700">
                      <FlaskConical className="h-2.5 w-2.5" />
                      Live
                    </span>
                  )}
                </p>
                <p className="mt-1 text-xl font-bold text-slate-900">
                  {budget_summary.estimated_total != null
                    ? formatMoney(budget_summary.estimated_total, budget_summary.estimated_total_currency)
                    : 'Not available'}
                </p>
                {currenciesDiffer && budget_summary.estimated_total_converted != null && (
                  <p className="mt-1 text-xs text-slate-500">
                    ≈ {formatMoney(budget_summary.estimated_total_converted, budget_summary.budget_currency)}{' '}
                    (converted)
                  </p>
                )}
              </div>
            </div>

            {budgetPct != null && (
              <div className="mt-4">
                <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-100 ring-1 ring-slate-200">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      budget_summary.over_budget
                        ? 'bg-rose-500'
                        : 'bg-gradient-to-r from-emerald-500 via-amber-500 to-rose-500'
                    }`}
                    style={{ width: `${budgetPct}%` }}
                  />
                </div>
                {budget_summary.over_budget && (
                  <span className="mt-2 inline-block rounded-full border border-rose-200 bg-rose-50 px-3 py-0.5 text-xs font-bold text-rose-700">
                    Projected Over Budget
                  </span>
                )}
              </div>
            )}

            {currencyMismatch && (
              <p className="mt-3.5 flex items-start gap-2 text-xs text-slate-500">
                <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-500" />
                Estimate is in {budget_summary.estimated_total_currency}; budget is in{' '}
                {budget_summary.budget_currency}.
              </p>
            )}

            {budget_summary.missing_estimates?.length > 0 && (
              <p className="mt-3.5 flex items-start gap-2 text-xs text-slate-500">
                <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-500" />
                Missing price points: {budget_summary.missing_estimates.join(', ')}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Flights + Hotels */}
      {(flights?.length > 0 || hotels?.length > 0) && (
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
          {flights?.length > 0 && (
            <div className="card p-6 shadow-sm">
              <SectionHeading icon={Plane}>Aviation Options</SectionHeading>
              <ul className="mt-4 space-y-2.5">
                {flights.slice(0, 3).map((f, i) => (
                  <li key={i}>
                    <a
                      href={flightSearchUrl(f, destination, formatDateShort(start_date))}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="group flex items-center justify-between gap-3 rounded-xl border border-slate-100 bg-slate-50/60 p-3 text-sm transition-all hover:border-rose-200 hover:bg-rose-50/60 hover:shadow-xs"
                    >
                      <div className="min-w-0">
                        <p className="flex items-center gap-1.5 truncate font-semibold text-slate-900 group-hover:text-rose-700">
                          {f.airline || 'Commercial Airline'}
                          <ExternalLink className="h-3 w-3 shrink-0 text-slate-400 opacity-60 transition-opacity group-hover:opacity-100 group-hover:text-rose-600" />
                        </p>
                        <p className="mt-0.5 text-xs text-slate-500">
                          {f.origin} <span className="text-rose-500">→</span> {f.destination}
                          {f.stops === 0 ? ' · Nonstop' : f.stops ? ` · ${f.stops} stop${f.stops > 1 ? 's' : ''}` : ''}
                          {f.duration_minutes ? ` · ${Math.floor(f.duration_minutes / 60)}h ${f.duration_minutes % 60}m` : ''}
                        </p>
                      </div>
                      {f.price != null && (
                        <span className="shrink-0 font-bold tabular-nums text-slate-900 text-sm">
                          {formatMoney(f.price, f.currency)}
                        </span>
                      )}
                    </a>
                  </li>
                ))}
              </ul>
              <p className="mt-3 flex items-start gap-2 text-xs text-slate-400">
                <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
                Direct routes verified via live aviation search telemetry.
              </p>
            </div>
          )}

          {hotels?.length > 0 && (
            <div className="card p-6 shadow-sm">
              <SectionHeading icon={BedDouble}>Boutique Stays</SectionHeading>
              <ul className="mt-4 space-y-2.5">
                {hotels.slice(0, 4).map((h, i) => (
                  <li key={i}>
                    <a
                      href={hotelSearchUrl(h.name, destination)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="group flex items-center justify-between gap-3 rounded-xl border border-slate-100 bg-slate-50/60 p-3 text-sm transition-all hover:border-rose-200 hover:bg-rose-50/60 hover:shadow-xs"
                    >
                      <p className="flex min-w-0 items-center gap-1.5 truncate font-semibold text-slate-900 group-hover:text-rose-700">
                        <span className="truncate">{h.name}</span>
                        <ExternalLink className="h-3 w-3 shrink-0 text-slate-400 opacity-60 transition-opacity group-hover:opacity-100 group-hover:text-rose-600" />
                      </p>
                      {h.rating != null ? (
                        <span className="flex shrink-0 items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-0.5 text-xs font-bold text-amber-700">
                          <Star className="h-3 w-3 fill-amber-400 text-amber-400" />
                          {h.rating}
                        </span>
                      ) : null}
                    </a>
                  </li>
                ))}
              </ul>
              {hotels.every((h) => h.price == null) && (
                <p className="mt-3 flex items-start gap-2 text-xs text-slate-400">
                  <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
                  Curated accommodation ratings powered by Places intelligence.
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {/* Local Insights */}
      {destinationGuide?.passages?.length > 0 && (
        <div className="card relative overflow-hidden border-rose-100 bg-gradient-to-br from-rose-50/50 via-white to-white p-6 shadow-sm">
          <BookOpen className="pointer-events-none absolute -bottom-4 -right-4 h-28 w-28 text-rose-500/[0.05]" />
          <SectionHeading icon={BookOpen}>Local Insights & Culture</SectionHeading>
          <div className="relative mt-4 space-y-3.5">
            {destinationGuide.passages.slice(0, 2).map((p, i) => (
              <blockquote key={i} className="border-l-2 border-rose-400 pl-4 text-sm leading-relaxed text-slate-700">
                {p.content.split('\n\n')[0]}
                {p.title && <cite className="mt-1.5 block text-xs font-semibold not-italic text-rose-600">— {p.title}</cite>}
              </blockquote>
            ))}
          </div>
        </div>
      )}

      {/* Day-by-day Itinerary */}
      {days.length > 0 && (
        <div className="card p-6 sm:p-8 shadow-sm">
          <div className="flex items-center justify-between border-b border-slate-100 pb-4">
            <div>
              <h3 className="font-display text-2xl font-extrabold tracking-tight text-slate-900">Day-by-Day Itinerary</h3>
              <p className="mt-1 text-xs text-slate-500">Optimized scheduling sequenced by AI orchestration</p>
            </div>
            <span className="rounded-full border border-rose-200 bg-rose-50 px-3 py-1 text-xs font-bold text-rose-700">
              {days.length} Day{days.length > 1 ? 's' : ''}
            </span>
          </div>

          <ol className="mt-7 space-y-8">
            {days.map((day, i) => (
              <li key={day.date || i} className="relative pl-10">
                {/* Number indicator */}
                <span
                  className="absolute left-0 top-0.5 flex h-7 w-7 items-center justify-center rounded-full text-xs font-extrabold text-white shadow-sm ring-4 ring-white"
                  style={gradient.style}
                >
                  {i + 1}
                </span>
                {i < days.length - 1 && (
                  <span className="absolute left-[13px] top-8 h-[calc(100%-8px)] w-0.5 bg-slate-200" />
                )}

                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-rose-600">
                    {formatDateShort(day.date)}
                  </span>
                </div>
                <h4 className="mt-1 font-display text-lg font-bold text-slate-900 tracking-tight">{day.summary}</h4>

                {day.activities?.length > 0 && (
                  <ul className="mt-3.5 space-y-2.5">
                    {day.activities.map((a, ai) => {
                      const timed = a && typeof a === 'object' && 'activity' in a
                      const time = timed ? a.time : null
                      const text = timed ? a.activity : a
                      const Icon = ACTIVITY_ICONS[activityIcon(text)] || MapPin
                      return (
                        <li key={ai} className="flex items-start gap-3 rounded-xl border border-slate-100 bg-slate-50/70 p-2.5 text-sm text-slate-700 transition-all hover:bg-slate-100/70">
                          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-white text-rose-600 ring-1 ring-slate-200/80 shadow-2xs">
                            <Icon className="h-3.5 w-3.5" />
                          </span>
                          {time && (
                            <span className="mt-1 w-12 shrink-0 font-mono text-xs font-bold text-rose-600">
                              {time}
                            </span>
                          )}
                          <span className="mt-0.5 leading-relaxed">{text}</span>
                        </li>
                      )
                    })}
                  </ul>
                )}
              </li>
            ))}
          </ol>

          {itinerary?.notes && (
            <div className="mt-7 flex items-start gap-2.5 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-xs leading-relaxed text-slate-600">
              <Info className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
              <span>{itinerary.notes}</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
