/**
 * Small presentation helpers shared by the trip-history cards and the
 * trip-result hero: a destination doesn't have a real photo (this app
 * never fetches one, and pulling in a stock-photo API is its own can of
 * worms - licensing, another API key, another point of failure), so a
 * deterministic gradient keyed off the destination name stands in for
 * one. "Deterministic" matters here specifically: the same destination
 * should always render the same color across the history sidebar and
 * the result header, so a user's Goa trip HB-1 and Goa trip #2 look
 * visually related rather than randomly different every render.
 */

// Curated so every pair reads as "place", not "random gradient" - each
// is loosely inspired by a real travel palette (ocean, sunset, desert,
// forest, dusk) rather than picked for contrast alone.
const DESTINATION_PALETTES = [
  ['#f43f5e', '#fb923c'], // sunset coral -> radiant amber
  ['#e11d48', '#9333ea'], // radiant rose -> twilight purple
  ['#f97316', '#eab308'], // tangerine glow -> golden horizon
  ['#8b5cf6', '#ec4899'], // dusk violet -> magenta
  ['#0ea5e9', '#6366f1'], // twilight azure -> deep indigo
  ['#10b981', '#06b6d4'], // emerald lagoon -> cyan
  ['#ea580c', '#be123c'], // terracotta embers -> ruby
  ['#d97706', '#f43f5e'], // amber spice -> sunset rose
]

function hashString(str) {
  let h = 0
  for (let i = 0; i < str.length; i++) {
    h = (h << 5) - h + str.charCodeAt(i)
    h |= 0
  }
  return Math.abs(h)
}

export function destinationGradient(destination) {
  const key = destination || 'trip'
  const [from, to] = DESTINATION_PALETTES[hashString(key) % DESTINATION_PALETTES.length]
  return { from, to, style: { backgroundImage: `linear-gradient(135deg, ${from}, ${to})` } }
}

// Open-Meteo condition strings (see mcp-weather-server/server.py's
// _weathercode_to_text) mapped to a lucide-react icon name + short
// human label. Kept as a name->name map (not importing icon components
// here) so this file has zero React/lucide dependency - callers map
// the name to a component themselves.
const WEATHER_CONDITIONS = {
  clear: { icon: 'Sun', label: 'Clear' },
  cloudy: { icon: 'Cloud', label: 'Cloudy' },
  foggy: { icon: 'CloudFog', label: 'Foggy' },
  rainy: { icon: 'CloudRain', label: 'Rainy' },
  snowy: { icon: 'Snowflake', label: 'Snowy' },
  stormy: { icon: 'CloudLightning', label: 'Stormy' },
  windy: { icon: 'Wind', label: 'Windy' },
}

export function weatherVisual(condition) {
  return WEATHER_CONDITIONS[condition] || { icon: 'CloudSun', label: condition || 'Unknown' }
}

// NOTE (21 Aug 2026): added alongside the "itinerary feels naive" fixes
// (see mcp-attractions-server and scheduling_agent.py's same-dated
// notes) - the itinerary card itself was a wall of identical grey
// bullet dots, which reads as unfinished/generic regardless of how good
// the underlying activity text is. Keyword-matching the activity text
// against a short, ordered list of (pattern, icon) pairs - first match
// wins - gives each row a purpose-built icon without needing the
// backend to classify activities itself. Ordered so specific meal words
// are checked before the generic "visit" catch-all.
const ACTIVITY_ICON_RULES = [
  [/breakfast/i, 'Coffee'],
  [/lunch/i, 'UtensilsCrossed'],
  [/dinner/i, 'UtensilsCrossed'],
  [/\b(check.?in|check.?out|hotel|pack)\b/i, 'BedDouble'],
  [/\b(flight|airport|depart)\b/i, 'Plane'],
  [/\b(transport|taxi|cab|train|bus|ferry|drive)\b/i, 'Car'],
  [/\b(beach|coast|lagoon)\b/i, 'Waves'],
  [/\b(waterfall|trek|hike|viewpoint|hill|mountain|nature)\b/i, 'Mountain'],
  [/\b(museum|temple|church|basilica|monument|fort|palace|ashram|heritage)\b/i, 'Landmark'],
  [/\b(market|shopping|bazaar|souvenir)\b/i, 'ShoppingBag'],
  [/\b(free time|leisure|relax|explore)\b/i, 'Sparkles'],
  [/\b(photo|sunset|sunrise)\b/i, 'Camera'],
]

export function activityIcon(text) {
  if (!text) return 'MapPin'
  for (const [pattern, icon] of ACTIVITY_ICON_RULES) {
    if (pattern.test(text)) return icon
  }
  return 'MapPin'
}

// NOTE (21 Aug 2026): found via a real user question ("should these
// have real links?"). Flight/hotel rows used to be plain text with
// nothing to click - a real product wouldn't leave a result dead-ended
// like that. A genuine BOOKING link (with an affiliate/partner ID,
// commission tracking) is exactly the Travelpayouts integration this
// project deliberately leaves for students to build - adding one here
// ourselves would just be doing that exercise for them. What's fair
// game, and genuinely useful on its own, is a plain external search
// link with no account, no API key, and nothing to configure: a plain
// google.com/search URL, built entirely from data already in hand. When
// a real booking link (Travelpayouts or otherwise) is wired up later,
// it's a straight swap of the `href` this returns - the UI doesn't
// change.
export function flightSearchUrl(flight, destinationCity, dateLabel) {
  const parts = [
    flight?.airline,
    'flight',
    flight?.origin && flight?.destination ? `${flight.origin} to ${flight.destination}` : destinationCity,
    dateLabel,
  ].filter(Boolean)
  return `https://www.google.com/search?q=${encodeURIComponent(parts.join(' '))}`
}

export function hotelSearchUrl(hotelName, city) {
  const parts = [hotelName, 'hotel', city].filter(Boolean)
  return `https://www.google.com/search?q=${encodeURIComponent(parts.join(' '))}`
}
