# mcp-weather-server

Phase 4. Standalone MCP server exposing the `get_weather` tool
(Open-Meteo-backed, keyless), running over **Streamable HTTP** transport
instead of the demo projects' stdio subprocess model.

## Why HTTP instead of stdio

stdio MCP (used in `mcp-travel-planner/` and `mcptoolcalling/`) means the
server is a child process piped to exactly one client - fine for a local
demo, unusable in production where many API instances (and many end
users, concurrently) need to call the same tool server. Streamable HTTP
is a normal HTTP endpoint: any number of clients can call it at once,
it can run behind a load balancer, and it can be scaled to multiple
replicas independently of every other service.

## Run directly

    pip install -r requirements.txt
    python server.py

Server listens on `http://localhost:8001/mcp` by default (see
`.env.example` to change host/port).

## Run via Docker

    docker build -t mcp-weather-server .
    docker run -p 8001:8001 mcp-weather-server

## Consumed by

`services/api/app/mcp_clients/weather_client.py`, which wraps calls to
this server with a Redis cache (see that file's docstring for the
caching/multi-user design).
