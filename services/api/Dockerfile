# Standalone image for the FastAPI backend - deployed, scaled, and
# restarted independently of the 5 MCP tool servers (see each
# mcp-*-server/Dockerfile). This is the ONLY service the frontend talks
# to directly; it talks onward to Postgres, Redis, and each MCP server
# over the network - their URLs come from env vars (see .env.example),
# never baked into this image, so the same image works in dev and prod.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .

EXPOSE 8000

# No --reload here (that's a dev-only uvicorn flag that watches the
# filesystem for changes - pointless and wasteful in a built image).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
