# mcp-transport-server

Phase 4. Standalone MCP server exposing `search_transport`
(OpenStreetMap Nominatim + Overpass API, free, no key), over Streamable
HTTP.

## Run
    pip install -r requirements.txt
    python server.py
Listens on `http://localhost:8005/mcp` by default.

## Docker
    docker build -t mcp-transport-server .
    docker run -p 8005:8005 mcp-transport-server

## Consumed by
`services/api/app/mcp_clients/transport_client.py`
