# mcp-flights-server

Phase 4/5. Standalone MCP server exposing `search_flights`, over
Streamable HTTP.

**Migrated to Duffel (19 Jul 2026).** Amadeus decommissioned its entire
self-service developer portal on 17 Jul 2026 - existing keys stopped
working and new signups were blocked. Duffel's free test mode is the
replacement: real API, real auth, real parsing - test mode just returns
offers from a fake "Duffel Airways" instead of real airline inventory,
so prices/schedules won't be realistic, but everything about how the
tool is called and how the response is shaped is genuine.

Get a free key: sign up at https://app.duffel.com/join (~1 minute, no
card required) -> Dashboard -> More -> Developers -> Access tokens ->
create a **test** token.

## Run
    pip install -r requirements.txt
    python server.py
Listens on `http://localhost:8002/mcp` by default.

## Docker
    docker build -t mcp-flights-server .
    docker run -p 8002:8002 --env-file .env mcp-flights-server

## Consumed by
`services/api/app/mcp_clients/flights_client.py` - unchanged by this
migration, since the tool's name and return shape didn't change, only
where the data comes from.
