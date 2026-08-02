# mcp-hotels-server

Phase 4/5. Standalone MCP server exposing `search_hotels`, over
Streamable HTTP.

**Migrated to Google Places API (19 Jul 2026).** Amadeus decommissioned
its self-service portal on 17 Jul 2026. Duffel Stays (Duffel's hotel
equivalent) requires requesting access and manual approval - not
instant self-serve - so it wasn't usable right away. Google Places API
(Nearby Search, `type=lodging`) gives real hotel names/addresses/ratings
with only a Google Cloud signup (free monthly credit covers dev/demo
usage, though a billing account with a card is required to enable the
API at all).

**Known limitation, stated honestly rather than faked:** Google Places
has no live room-pricing data. `price` / `price_per_night` in this
tool's results are always `None` - same pattern already used for
attraction pricing and transport fares (OSM has neither). Phase 5's
BudgetAgent already handles a missing hotel price gracefully (see its
`missing_estimates` field).

Get a free key: https://console.cloud.google.com -> create/select a
project -> enable "Places API (New)" -> enable billing -> APIs &
Services -> Credentials -> create an API key.

## Run
    pip install -r requirements.txt
    python server.py
Listens on `http://localhost:8003/mcp` by default.

## Docker
    docker build -t mcp-hotels-server .
    docker run -p 8003:8003 --env-file .env mcp-hotels-server

## Consumed by
`services/api/app/mcp_clients/hotels_client.py` - unchanged by this
migration, since the tool's name and return shape didn't change, only
where the data comes from (and that price is now honestly None).
