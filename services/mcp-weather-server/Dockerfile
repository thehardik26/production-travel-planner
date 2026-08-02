# Standalone image for this ONE MCP server - deployed, scaled, and
# restarted independently of the API service and the other MCP servers.
# A traffic spike or crash in weather lookups never touches flights or
# hotels because they are not the same process, container, or pod.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

EXPOSE 8001

CMD ["python", "server.py"]
