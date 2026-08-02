# mcp-attractions-server

Phase 4. Standalone MCP server exposing `search_attractions`
(OpenStreetMap Nominatim + Overpass API, free, no key), over Streamable
HTTP.

## Run
    pip install -r requirements.txt
    python server.py
Listens on `http://localhost:8004/mcp` by default.

## Docker
    docker build -t mcp-attractions-server .
    docker run -p 8004:8004 mcp-attractions-server

## Consumed by
`services/api/app/mcp_clients/attractions_client.py`
