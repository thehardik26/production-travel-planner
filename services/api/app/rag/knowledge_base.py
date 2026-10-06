"""
Seed destination-guide corpus for the RAG knowledge base (Phase 6).

WHAT THIS IS: a starter set of hand-written guide entries covering most
of the cities IntentAgent's heuristic fallback already recognizes (see
app/agents/intent_agent.py's `known_cities`), so RAG has something real
to retrieve for the destinations this app already plans trips to.

WHAT THIS ISN'T: a live, continuously-updated content pipeline. Prices,
hours and events below are illustrative and WILL drift out of date -
treat this the same as the MCP tools' own "what's real data" honesty
table in PROJECT_FLOW_EXPLAINED.md. Before relying on this for real
users, either (a) have someone who knows these places review/correct
each entry, or (b) replace `SEED_KNOWLEDGE` with a real ingestion
source (a CMS, a scraped-and-reviewed content set, a licensed guide
dataset) - `ingest.py` doesn't care where the (title, content,
metadata) tuples come from, only that they exist.

Each entry's `content` is written as prose paragraphs (not bullet
fragments) specifically so semantic_chunk's paragraph-boundary
splitting in chunking.py has real boundaries to split on.
"""
from __future__ import annotations

SEED_KNOWLEDGE: list[dict] = [
    {
        "title": "Goa Travel Guide",
        "content": """
Goa is India's smallest state by area, on the west coast between the Arabian Sea and the
Western Ghats. It splits into North Goa (Baga, Calangute, Anjuna, Vagator - livelier,
younger, more nightlife) and South Goa (Palolem, Agonda, Colva - quieter, more resort-y).

Best time to visit: November to February, when temperatures sit around 20-32C and
humidity is manageable. The monsoon (June-September) closes most beach shacks and
water sports, though it draws a different crowd for the lush, quiet landscape.

Getting there: Goa's Manohar International Airport (GOI, Mopa, North Goa) and Dabolim
Airport (GOX, South Goa) both have frequent domestic connections from Mumbai, Delhi,
Bangalore and Hyderabad. The Konkan Railway route from Mumbai is a scenic overnight
option.

Budget guide: hostel dorm beds run roughly Rs 400-900/night; a double room in a
budget guesthouse Rs 1200-2500/night; a full seafood thali at a beach shack Rs
250-450; scooter rental Rs 300-500/day (an international driving permit or valid
Indian license is technically required, and helmet laws are enforced in parts of
North Goa).

Food specialties: Goan fish curry rice, prawn balchao, bebinca (layered dessert),
feni (cashew or coconut spirit, worth trying once, strong).

Cultural notes: Goa's Portuguese colonial history (until 1961) shows in its
churches (Basilica of Bom Jesus, a UNESCO site, holds the remains of St. Francis
Xavier), its cuisine, and its more relaxed attitude to alcohol compared to most of
India. Swimwear is fine on the beach itself but cover up when walking through
villages or visiting churches/temples.
""",
        "metadata": {"destination": "Goa", "content_type": "destination_guide"},
    },
    {
        "title": "Lonavala & Khandala Weekend Guide",
        "content": """
Lonavala and its twin hill town Khandala sit in the Sahyadri (Western Ghats) range,
roughly 65km from Pune and 100km from Mumbai - the single most popular weekend hill
escape for both cities precisely because of that distance.

Best time to visit: monsoon season (June-September) is when Lonavala is genuinely
famous - waterfalls, mist over the valley, everything green. Winter (October-February)
is drier and cooler, better for the forts and caves. Summers are hot and comparatively
unremarkable for a hill-station trip.

Getting there: no airport of its own - the nearest is Pune (PNQ) or Mumbai (BOM),
both roughly 2 hours by road/rail onward. Lonavala railway station sits on the
Mumbai-Pune main line, served by frequent locals and express trains, which is
usually the easiest way in without a car.

Key sights: Bhushi Dam (crowded but classic monsoon spot, sit on the overflow
steps), Tiger's Point and Lion's Point for valley viewpoints, Karla and Bhaja
Caves (2nd-century BCE Buddhist rock-cut caves, genuinely significant
archaeologically and far less crowded than the dam), Rajmachi Fort for a
half-day trek.

Budget guide: a day-trip from Pune/Mumbai costs little beyond transport; an
overnight stay in a mid-range hotel runs Rs 2000-5000; Lonavala's chikki
(a jaggery-nut brittle) is the classic souvenir/snack, sold all along the main
market road for Rs 150-400/kg depending on the nut mix.

Practical note: this is a short-trip, activity-light destination - well suited to
a 1-2 night visit built around one or two viewpoints/caves and food, not a
full multi-day itinerary of distinct daily activities.
""",
        "metadata": {"destination": "Lonavala", "content_type": "destination_guide"},
    },
    {
        "title": "Manali Travel Guide",
        "content": """
Manali sits in Himachal Pradesh's Kullu Valley on the Beas River, and is the usual
gateway for onward trips into Ladakh via the Manali-Leh highway (open roughly
May/June to October, weather permitting).

Best time to visit: March-June for pleasant weather and flowers; September-January
for snow (Manali gets real winter snowfall, unlike most of hill-station India) - the
old town (Manali proper vs. the newer Mall Road area) is at its most atmospheric
under snow, but road conditions can be unpredictable in peak winter.

Getting there: nearest airport is Bhuntar (KUU), about 50km away, with limited
seasonal flights mostly from Delhi. Most travelers arrive by overnight Volvo bus
or car from Delhi/Chandigarh (roughly 12-14 hours by road).

Key sights: Solang Valley (paragliding, and skiing in winter), Rohtang Pass
(permit required, often closed by snow outside a summer window - check before
planning a day around it), Hadimba Temple (a wooden cave temple in a cedar
forest, unlike the marble/stone temples typical elsewhere in India), Old Manali
(cafes, guesthouses, a very different pace from the touristy Mall Road).

Budget guide: guesthouse doubles Rs 800-2500/night depending on season; momos
and thukpa (Tibetan-influenced food, common given the large Tibetan community)
Rs 100-250/plate; paragliding at Solang roughly Rs 2000-3500 for a tandem flight.

Practical note: altitude and mountain roads mean travel times here are often
longer than map distance suggests - build slack into any multi-stop itinerary
rather than assuming plains-style driving speeds.
""",
        "metadata": {"destination": "Manali", "content_type": "destination_guide"},
    },
    {
        "title": "Rajasthan Travel Guide",
        "content": """
Rajasthan, the Land of Kings, is India's largest state by area and one of its most
vibrant cultural destinations, famous for its palaces, forts, and colourful festivals.

Best time to visit: October to March. Summers (April-June) get extremely hot,
with desert-region temperatures reaching 45C.

Key cities: Jaipur (Pink City), Jodhpur (Blue City), Jaisalmer (Golden City),
Udaipur (City of Lakes), Bikaner, Pushkar.

Transportation: state buses connect all major cities, the train network is
extensive, and taxis/hired cars are popular for multi-city itineraries. Jaipur
has an operational metro for getting around the city itself.

Budget tips: street food in Jaipur's markets runs Rs 50-200/meal; auto-rickshaws
should be negotiated before boarding, expect Rs 30-80 for short city hops;
heritage walking tours run Rs 500-2000/person; Amber Fort entry is Rs 550
(foreign visitors) / Rs 100 (Indian citizens).

Food specialties: Dal Baati Churma, Laal Maas, Gatte ki Sabzi, Ker Sangri,
a full Rajasthani Thali (Rs 200-500), Pyaaz Kachori, Mawa Kachori.

Cultural notes: dress modestly at temples and religious sites. The Pushkar
Fair (Kartik month, roughly October/November) is a world-famous camel fair.
Holi and Diwali are both celebrated with exceptional fervour here.
""",
        "metadata": {"destination": "Rajasthan", "content_type": "destination_guide"},
    },
    {
        "title": "Jaipur Attractions Guide",
        "content": """
Jaipur, the Pink City and capital of Rajasthan, offers a dense concentration of
historical and cultural attractions within the old walled city and just outside it.

Amber Fort (Amer Fort): open 8:00 AM-5:30 PM daily, entry Rs 550 (Indians: Rs
100), 2-3 hours recommended. Highlights include the Sheesh Mahal (Hall of
Mirrors) and Ganesh Pol; elephant rides up to the fort run in the early morning
only. It sits 11km from the Jaipur city centre.

City Palace: open 9:30 AM-5:00 PM, entry Rs 700 including camera, 1.5-2.5
hours. Multiple courtyards, museums, and the Mubarak Mahal.

Hawa Mahal (Palace of Winds): open 9:00 AM-4:30 PM, entry Rs 50 (Indians) / Rs
200 (foreigners), 45 minutes to an hour. 953 small latticed windows; best
photographed from outside, at sunrise, when the facade catches the light.

Jantar Mantar (UNESCO World Heritage Site): open 9:00 AM-4:30 PM, entry Rs 50
(Indians), about an hour. The world's largest stone sundial, with 19 separate
astronomical instruments.

Nahargarh Fort: open 10:00 AM-5:30 PM, entry Rs 50. Panoramic city views,
especially good at sunset, with a reasonably priced restaurant on the premises.

Johri Bazaar: best for jewellery, gemstones, traditional bangles and tie-dye
Bandhani textiles. Bargaining is expected - aim to negotiate to 60-70% of the
initial quoted price.
""",
        "metadata": {"destination": "Jaipur", "parent_destination": "Rajasthan", "content_type": "attractions_guide"},
    },
    {
        "title": "Jaisalmer Desert Experience",
        "content": """
Jaisalmer, the Golden City, is known for its desert landscape, its living fort, and
its traditional havelis (ornately carved mansions).

Jaisalmer Fort (Sonar Quila) is one of the world's few living forts - thousands
of people still live inside it. The fort area itself is free to enter; the
museum charges apply separately. Don't miss the Raj Mahal and the Jain temples,
known for extraordinarily detailed marble carving. Early morning or sunset gives
the best golden-light photography.

Sam Sand Dunes, 40km from Jaisalmer, are the classic desert-safari destination:
camel safaris run Rs 300-500/hour, with sunset safaris the most popular slot;
desert camping ranges Rs 1500-8000/night depending on luxury level, and most
camping packages include a folk music/dance evening and a bonfire. Best
experienced October through February.

Patwon Ki Haveli (open 9:00 AM-6:00 PM, entry Rs 100) is five interconnected
havelis with intricate stone carving, dating to roughly 1800 CE.

Gadisar Lake is free to enter, with boating available at Rs 100-200/hour; go at
sunrise for migratory birds, best November-February.

Budget guide: Dal Baati at a local dhaba runs Rs 120-180; a full Rajasthani
Thali Rs 250-400; all-inclusive camping packages Rs 2000-5000/person; a full day
of sightseeing by auto-rickshaw Rs 500-800.
""",
        "metadata": {"destination": "Jaisalmer", "parent_destination": "Rajasthan", "content_type": "destination_guide"},
    },
    {
        "title": "Udaipur Travel Guide",
        "content": """
Udaipur, the City of Lakes, is built around Lake Pichola and is often called the
most romantic city in Rajasthan for its lakeside palaces and whitewashed old town.

Best time to visit: September to March, when temperatures are comfortable for
walking the old city and taking boat rides.

Key sights: City Palace (a sprawling complex on the lake's east bank, entry
roughly Rs 300-700 depending on which sections/museums are included), Lake
Pichola boat rides (sunset boat rides, roughly Rs 400-700/person, are the
single most-recommended activity), Jagdish Temple (a large Indo-Aryan temple a
short walk from the City Palace), Saheliyon Ki Bari (a garden with fountains,
modest entry fee), and Monsoon Palace (Sajjangarh) on a hilltop above the city
for panoramic sunset views.

Food and stay: the old city around Jagdish Chowk has the highest concentration
of rooftop restaurants with lake views - useful for a memorable dinner but
generally pricier than street-level options a few lanes back. Budget
guesthouse doubles run roughly Rs 1000-3000/night depending on lake-view
proximity.

Practical note: Udaipur's old-city lanes are narrow and largely walkable; a car
isn't especially useful within the city itself, though useful for day trips to
Kumbhalgarh Fort (about 2 hours away).
""",
        "metadata": {"destination": "Udaipur", "parent_destination": "Rajasthan", "content_type": "destination_guide"},
    },
    {
        "title": "Kerala & Munnar Travel Guide",
        "content": """
Kerala, on India's southwest coast, is known for backwaters, tea-plantation hill
country, and Ayurvedic wellness tourism. Munnar, in the Western Ghats, is its
best-known hill station.

Best time to visit: September to March for most of Kerala (post-monsoon,
comfortable temperatures); Munnar specifically is pleasant nearly year-round
given its elevation, though it can be crowded and chilly December-January.

Munnar highlights: rolling tea estates (several offer plantation tours and
tastings, typically Rs 150-400), Eravikulam National Park (home to the
Nilgiri Tahr, entry roughly Rs 125 plus a mandatory shuttle fee, best visited
early to avoid the daily visitor cap), and Top Station viewpoint near the
Tamil Nadu border for valley views.

Alappuzha (Alleppey) backwaters: houseboat stays are the signature Kerala
experience - a shared/standard houseboat overnight runs roughly Rs 6000-12000
for a couple including meals, private/luxury boats considerably more. Day
cruises are a cheaper alternative at Rs 500-1500/person if an overnight isn't
in budget.

Food specialties: Kerala sadya (a large vegetarian thali served on a banana
leaf, especially around Onam), appam with stew, Malabar biryani, fresh
seafood along the coast.

Practical note: Kerala combines two very different trip types - hill-country
(Munnar) and backwater/coastal (Alleppey, Kochi) - well in a single itinerary,
but they're 4-5 hours apart by road, so a short trip usually has to pick one
rather than both.
""",
        "metadata": {"destination": "Munnar", "parent_destination": "Kerala", "content_type": "destination_guide"},
    },
    {
        "title": "Rishikesh Travel Guide",
        "content": """
Rishikesh, on the Ganges in Uttarakhand at the foothills of the Himalayas, is
India's best-known centre for yoga, meditation and whitewater rafting - often
combined into one trip.

Best time to visit: February-April and September-November for the best
weather; rafting season on the Ganges typically runs September-June (closed
during peak monsoon for safety).

Key activities: whitewater rafting (multiple stretches/grades available,
roughly Rs 500-1500/person depending on distance and rapid grade), the Beatles
Ashram (Chaurasi Kutia, where the band studied Transcendental Meditation in
1968, now a low-key, graffiti-covered ruin open to visitors for a small
entry fee), Laxman Jhula and Ram Jhula (the two suspension bridges that
anchor the town's geography and evening Ganga Aarti ceremony), and short-term
yoga/meditation courses (widely available, from single drop-in classes to
week-long residential programs).

Food and stay: Rishikesh is officially vegetarian and alcohol-free within
municipal limits (it's a pilgrimage town) - German Bakery-style cafes serving
health food are the dominant restaurant style rather than typical Indian
non-veg fare. Budget guesthouse doubles run Rs 600-2000/night; ashram stays
(often including meals and yoga sessions) are a distinct, usually cheaper,
alternative to hotels.

Practical note: this is a wellness/adventure hybrid destination rather than a
sightseeing-checklist one - itineraries here work best built around one or two
anchor activities (a rafting trip, a multi-day yoga program) plus riverside
time, not a long list of discrete attractions.
""",
        "metadata": {"destination": "Rishikesh", "content_type": "destination_guide"},
    },
    {
        "title": "Pondicherry (Puducherry) Travel Guide",
        "content": """
Pondicherry (officially Puducherry), on Tamil Nadu's coast, was a French colonial
territory until 1954 and still shows it strongly in its architecture, food and
street names - a distinctly different flavour from the rest of South India.

Best time to visit: October to March; summers are hot and humid like most of
coastal Tamil Nadu.

Key sights: the French Quarter (White Town) - mustard-yellow colonial villas,
bougainvillea-lined streets, cafes with a genuinely French-influenced menu;
Auroville (an experimental "universal township" about 10km away, its golden
Matrimandir dome is the well-known photo spot, though entry inside the dome
itself requires advance booking); Promenade Beach (a rocky, walk-focused
beach - not a swimming beach, but the town's social hub at dawn and dusk);
Sri Aurobindo Ashram, a major draw for spiritually-oriented visitors.

Food specialties: this is one of the few places in India with genuine
French-Tamil fusion food - expect both authentic French bakery items
(croissants, baguettes) and Tamil staples side by side, plus Franco-Creole
dishes found nowhere else in the country.

Budget guide: French Quarter heritage-hotel stays run noticeably higher (Rs
3000-8000+/night) than equivalent quality elsewhere in Tamil Nadu, given the
colonial-property premium; budget guesthouses outside White Town run Rs
800-2000/night. Renting a bicycle or scooter is the easiest way to cover both
the French Quarter and Auroville in a short trip.
""",
        "metadata": {"destination": "Pondicherry", "content_type": "destination_guide"},
    },
]
