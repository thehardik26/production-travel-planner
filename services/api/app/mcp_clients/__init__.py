# Phase 4 - one MCP client wrapper per MCP server: weather_client,
# flights_client, hotels_client, attractions_client, transport_client.
# Each is a thin typed wrapper around base.call_cached_tool() - see
# base.py's docstring for the caching/multi-user design shared by all
# five. Unlike the demo projects' stdio subprocess model, these connect
# over Streamable HTTP to independently deployed MCP server services
# (see services/mcp-*-server/).
