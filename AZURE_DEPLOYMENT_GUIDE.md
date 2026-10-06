# Deploying to Azure — step-by-step guide

This maps every piece of `production-travel-planner` to a specific Azure service and walks through creating each one with the Azure CLI. It assumes you'll run these commands yourself (Azure Portal or CLI) rather than using generated infrastructure-as-code files.

## Service mapping

| Component | Azure service | Why |
|---|---|---|
| React frontend | **Azure Static Web Apps** (Free tier) | Free, built for static SPAs, auto CI/CD from GitHub |
| FastAPI backend | **Azure Container Apps** | Serverless containers, scale-to-zero, built-in HTTPS |
| 5 MCP tool servers | **Azure Container Apps** (5 separate apps, internal-only ingress) | Each independently deployable/scalable, matching how they're built |
| Postgres | **Azure Database for PostgreSQL – Flexible Server** (Burstable B1ms) | Cheapest managed Postgres tier (~$12/mo compute) |
| Redis | **Azure Cache for Redis** (Basic C0) | Cheapest managed Redis tier |
| Qdrant | *Optional — skip to start* | RAG (Phase 6) is now actually built, so this note is updated from "not built yet" to "built, but still optional in production": `app/rag/retrieval.py` treats Qdrant as one of two independent retrieval signals (dense vs BM25) and degrades to BM25-only if Qdrant is unreachable — see the `RAG: Qdrant unavailable at startup ... continuing with BM25-only` warning already visible in local logs. For a class project, running without a managed Qdrant instance (BM25-only) is a legitimate way to avoid a 6th thing to pay for and operate. If you want the full hybrid dense+BM25 retrieval in production later, the free tier of [Qdrant Cloud](https://cloud.qdrant.io) (1GB, no card required) is the lowest-friction option — point `QDRANT_URL`/`QDRANT_API_KEY` at it, no separate Azure resource needed. |
| Secrets (API keys) | **Container Apps secrets** | Built into Container Apps; upgrade to Azure Key Vault later if this becomes a real production deployment |

**Cost tip:** sign up for [Azure for Students](https://azure.microsoft.com/en-us/free/students) first if eligible — $100 free credit, no credit card required, renewable yearly. More than enough to run this whole stack for a semester.

## 0. Prerequisites

```bash
# Install the Azure CLI, then:
az login
az account set --subscription "<your subscription name>"

# One resource group for everything - makes cleanup a single command later
az group create --name travel-planner-rg --location eastus
```

## 1. Postgres

```bash
az postgres flexible-server create \
  --resource-group travel-planner-rg \
  --name travel-planner-pg \
  --location eastus \
  --admin-user travel_admin \
  --admin-password "<strong-password>" \
  --sku-name Standard_B1ms \
  --tier Burstable \
  --storage-size 32 \
  --version 16 \
  --public-access 0.0.0.0-255.255.255.255   # tighten this to Container Apps' outbound IPs once you have them

az postgres flexible-server db create \
  --resource-group travel-planner-rg \
  --server-name travel-planner-pg \
  --database-name travel_planner
```

Run your Alembic migrations once against this server (from your machine, pointed at the new connection string):

```bash
# services/api/.env, temporarily:
# DATABASE_URL=postgresql+asyncpg://travel_admin:<password>@travel-planner-pg.postgres.database.azure.com:5432/travel_planner
python -m alembic upgrade head
```

## 2. Redis

```bash
az redis create \
  --resource-group travel-planner-rg \
  --name travel-planner-redis \
  --location eastus \
  --sku Basic \
  --vm-size c0
```

Grab the connection details afterward with `az redis show` and `az redis list-keys` — you'll need the hostname and primary key for `REDIS_URL`.

## 3. Container Apps environment

One shared environment hosts the API and all 5 MCP servers, so they can reach each other over an internal network without going through the public internet:

```bash
az extension add --name containerapp --upgrade
az provider register --namespace Microsoft.App

az containerapp env create \
  --resource-group travel-planner-rg \
  --name travel-planner-env \
  --location eastus
```

## 4. Deploy the 5 MCP servers

Each one gets `--ingress internal` — only reachable from inside the Container Apps environment, never from the public internet, since only the FastAPI backend needs to call them. `az containerapp up` builds straight from the Dockerfile in each service's folder (no separate registry step needed for a simple setup):

```bash
cd services/mcp-weather-server
az containerapp up \
  --resource-group travel-planner-rg \
  --name mcp-weather-server \
  --environment travel-planner-env \
  --source . \
  --target-port 8001 \
  --ingress internal \
  --env-vars OSM_USER_AGENT="production-travel-planner/1.0 (you@example.com)"
```

Repeat for `mcp-flights-server` (port 8002, env var `DUFFEL_API_KEY`), `mcp-hotels-server` (port 8003, env vars `GOOGLE_PLACES_API_KEY` + `OSM_USER_AGENT`), `mcp-attractions-server` (port 8004), and `mcp-transport-server` (port 8005).

After each deploy, `az containerapp show --name <name> --query properties.configuration.ingress.fqdn` gives you its internal hostname (looks like `mcp-weather-server.internal.<env-id>.eastus.azurecontainerapps.io`) — you'll need all 5 for the next step.

## 5. Deploy the FastAPI backend

This one gets `--ingress external` (the frontend needs to reach it publicly):

```bash
cd services/api
az containerapp up \
  --resource-group travel-planner-rg \
  --name travel-api \
  --environment travel-planner-env \
  --source . \
  --target-port 8000 \
  --ingress external \
  --env-vars \
    DATABASE_URL="postgresql+asyncpg://travel_admin:<password>@travel-planner-pg.postgres.database.azure.com:5432/travel_planner" \
    REDIS_URL="redis://:<redis-key>@travel-planner-redis.redis.cache.windows.net:6380/0?ssl_cert_reqs=none" \
    JWT_SECRET_KEY="<generate with: python -c \"import secrets; print(secrets.token_hex(32))\">" \
    MCP_WEATHER_SERVER_URL="http://mcp-weather-server.internal.<env-id>.eastus.azurecontainerapps.io/mcp" \
    MCP_FLIGHTS_SERVER_URL="http://mcp-flights-server.internal.<env-id>.eastus.azurecontainerapps.io/mcp" \
    MCP_HOTELS_SERVER_URL="http://mcp-hotels-server.internal.<env-id>.eastus.azurecontainerapps.io/mcp" \
    MCP_ATTRACTIONS_SERVER_URL="http://mcp-attractions-server.internal.<env-id>.eastus.azurecontainerapps.io/mcp" \
    MCP_TRANSPORT_SERVER_URL="http://mcp-transport-server.internal.<env-id>.eastus.azurecontainerapps.io/mcp" \
    GROQ_API_KEY="<your groq key>" \
    GROQ_MODEL="llama-3.3-70b-versatile"
```

For real secrets (not just config), prefer `az containerapp secret set` and reference them with `secretref:` instead of putting raw values in `--env-vars` — keeps them out of shell history and `az containerapp show` output.

Note the `Azure Cache for Redis` connection needs TLS (`rediss://` or the `?ssl_cert_reqs=none` query param depending on your Redis client version) — Azure's managed Redis only accepts TLS connections on port 6380, unlike the plain `redis://localhost:6380` used in local dev.

## 6. Deploy the frontend

```bash
cd frontend
# Update .env before building:
# VITE_API_BASE_URL=https://<travel-api's public FQDN from step 5>

az staticwebapp create \
  --resource-group travel-planner-rg \
  --name travel-planner-frontend \
  --location eastus2 \
  --sku Free \
  --source https://github.com/<your-username>/<your-repo> \
  --branch main \
  --app-location "/frontend" \
  --output-location "dist" \
  --login-with-github
```

This connects to a GitHub repo and sets up automatic CI/CD (every push to `main` rebuilds and redeploys) — you'll need your code pushed to GitHub first. If you'd rather not wire up GitHub, `swa deploy` (the Static Web Apps CLI) can push a local build directly.

**Update the backend's CORS setting** once you have the Static Web App's URL — `app/core/config.py`'s `CORS_ORIGINS` needs to include `https://<your-static-web-app>.azurestaticapps.net`, then redeploy the API container app.

## 7. Verify

- `https://<travel-api-fqdn>/health` → `{"status": "ok", ...}`
- `https://<travel-api-fqdn>/docs` → Swagger UI, run through signup/login/plan manually
- Frontend URL → full signup/login/plan flow through the UI

## 8. Cost control while this is a learning project

- Container Apps scale to zero when idle on the Consumption plan — you're not paying for compute between demos.
- Postgres and Redis do **not** scale to zero (they're always-on managed services) — this is where most of the cost sits. Stop/delete them between long gaps if budget matters.
- `az group delete --name travel-planner-rg --yes` tears down everything in the resource group in one command when you're done — the cleanest way to make sure nothing keeps billing.

## Portal-only path (no CLI)

Everything above can be done by clicking through [portal.azure.com](https://portal.azure.com) instead. The steps map 1:1 to the CLI commands, with two real differences worth knowing up front:

1. **`az containerapp up --source .` has no portal equivalent.** The CLI command builds your Dockerfile locally and pushes it for you in one step. The portal's container-app wizard only *runs* an existing image — it doesn't build one. The clean portal-native way around this is **Continuous deployment from GitHub**: push this repo to GitHub first, then Azure builds the image FOR you via an auto-generated GitHub Actions workflow every time you push. This also happens to double as your CI/CD.
2. **Migrations still need a terminal, no matter what.** Portal can create the Postgres server, but `alembic upgrade head` is code execution, not infrastructure — there's no portal button for "run my migration script". Run it once from your own machine, pointed at the Azure connection string.

### 1. Resource group

Portal → **Resource groups** → **+ Create** → name `travel-planner-rg`, region East US → **Review + create**.

### 2. Postgres

Search **Azure Database for PostgreSQL flexible servers** → **+ Create**.
- Resource group `travel-planner-rg`, server name `travel-planner-pg`, region East US
- Workload type: **Development** (this pre-selects Burstable compute) → under "Compute + storage" click **Configure server** and confirm **Burstable, B1ms**, 32 GiB storage
- Set an admin username/password
- **Networking** tab → Public access → add a firewall rule allowing Azure services (same caveat as the CLI version: this is wide-open, tighten later)
- **Review + create**

After it's created: open the resource → **Databases** → **+ Add** → name it `travel_planner`.

Then, from your own machine (not the portal): point `services/api/.env`'s `DATABASE_URL` at this server and run `python -m alembic upgrade head` once.

### 3. Redis

Search **Azure Cache for Redis** → **+ Create** → resource group, name `travel-planner-redis`, **Cache type: Basic C0** → **Review + create**. Afterward, open the resource → **Access keys** for the primary key, **Overview** for the hostname.

### 4-5. The API and the 5 MCP servers (Container Apps)

Push this whole repo to GitHub first — every container app below uses the same GitHub-connected flow.

For **each** of the 6 services (`services/api`, `services/mcp-weather-server`, `services/mcp-flights-server`, `services/mcp-hotels-server`, `services/mcp-attractions-server`, `services/mcp-transport-server`):

1. Search **Container Apps** → **+ Create**.
2. **Basics**: resource group `travel-planner-rg`, name it after the service (e.g. `mcp-weather-server`), region East US. **Container Apps Environment**: first time through, click **Create new** and name it `travel-planner-env`; every service after that, pick the existing one from the dropdown — this is what lets them all reach each other internally.
3. **Container** tab: for the very first save you need *some* image, so leave the default quickstart image checked — you'll swap it for your real code in step 5 below.
4. **Ingress** tab: enable ingress, target port matches the service (`8000` for the API, `8001`-`8005` for weather/flights/hotels/attractions/transport in that order). For the 5 MCP servers, set **Ingress traffic** to **Limited to Container Apps Environment** (this is the portal's internal-only option — never expose these publicly). For the API only, choose **Accepting traffic from anywhere**.
5. **Review + create**, then once it exists, open the app → left menu → **Continuous deployment** → **Get started** → connect your GitHub account → pick the repo/branch → **Dockerfile path**: point it at that service's `Dockerfile` (e.g. `services/mcp-weather-server/Dockerfile`) → confirm. Azure provisions a Container Registry for you and commits a GitHub Actions workflow to your repo — every future push rebuilds and redeploys this app automatically.
6. Open the app → **Environment variables** → add that service's variables (same list as the CLI section above — `OSM_USER_AGENT`, `DUFFEL_API_KEY`, etc. for the MCP servers; `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET_KEY`, the five `MCP_*_SERVER_URL`s, and `GROQ_API_KEY` for the API). Mark real secrets (passwords, keys) as **Secret** type — there's a toggle right next to the value field — rather than plain env vars.

Once all 5 MCP servers exist, copy each one's internal URL from its **Overview** page (**Application Url**, looks like `mcp-weather-server.internal.<suffix>.eastus.azurecontainerapps.io`) before filling in the API's environment variables in step 6.

### 6. Frontend

Search **Static Web Apps** → **+ Create** → resource group, name `travel-planner-frontend`, **Plan type: Free** → **Deployment details**: sign in with GitHub, pick this repo and branch → **Build Details**: preset **Vite** (or Custom), **App location** `/frontend`, **Output location** `dist` → **Review + create**. This also commits its own GitHub Actions workflow.

**Important Vite-specific gotcha**: `VITE_API_BASE_URL` gets baked into the JavaScript bundle at *build* time, not read at runtime like the Container Apps env vars above. So it has to be set as a committed `.env.production` file in the `frontend/` folder (containing the API's public URL) *before* pushing — changing it later means editing that file and pushing again, not a portal settings toggle.

### 7. CORS

`CORS_ORIGINS` in `app/core/config.py` is a plain Python list in the code, not read from the portal. Add your Static Web App's URL to that list in the source, commit, and push — the API's Continuous deployment workflow (set up in step 4-5) picks it up and redeploys automatically.

## What this guide deliberately leaves out

Production concerns like a custom domain + managed TLS cert, Azure Key Vault for secrets, VNet-restricted Postgres/Redis access, Application Insights / LangSmith observability (Phase 7, not built yet), and CI/CD for the backend containers (only the frontend gets automatic deploys above). Good next steps once the class has the basic deployment working end to end.
