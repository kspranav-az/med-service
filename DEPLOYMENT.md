# Deployment Guide

This guide covers deploying MedService on a server that may already be running other projects. It assumes you want to **avoid reindexing** by copying your local Qdrant storage and entity data.

No application code changes are required. All configuration is done through environment variables, Docker Compose overrides, and systemd/Nginx files.

---

## Deploying on the Prime World CRM VPS (recommended)

The current server already runs Prime World CRM and Nori-Tura, both routed through the same Traefik reverse proxy on the Docker network `prime-world-crm_prime-network`. MedService can be added to this same server with **no port conflicts** and **no extra reverse proxy** by connecting its container to that network and letting Traefik terminate HTTPS.

### Architecture

- **Dedicated Qdrant + Redis inside MedService's own compose stack.** They have no published host ports, so they cannot conflict with Prime World CRM's Redis/Qdrant.
- **Single MedService inference container** hosting both RAG chat (internal port `8100`) and autocomplete (internal port `8101`). This keeps memory and CPU overhead low on a 4-core VPS and avoids port `8000`, which is already used by Nori-Tura's API container.
- **Traefik routes by hostname** (or hostname+path) to the appropriate internal port.
- **Data is mounted from the host** — `data/` (read-only) and `qdrant_storage/` — so no reindexing is needed.

### Routing options

| Approach | Example URL for chat | Example URL for autocomplete | Recommendation |
|---|---|---|---|
| **Separate subdomains** | `https://med.primeworld.tech/api/v1/chat` | `https://med-api.primeworld.tech/api/v1/autocomplete` | **Recommended** — clean, no path rewriting, easy CORS |
| Single subdomain + path prefixes | `https://med.primeworld.tech/chat/api/v1/chat` | `https://med.primeworld.tech/autocomplete/api/v1/autocomplete` | Possible, but frontend URLs must include the prefix |

The default `docker-compose.med-service.deploy.yml` uses **separate subdomains**.

### DNS records required

For the default subdomain option, add these A records pointing to the server IP:

```
med.primeworld.tech     A <server-ip>
med-api.primeworld.tech A <server-ip>
```

Traefik will automatically request Let's Encrypt certificates for both.

### Compose file

Use `docker-compose.med-service.deploy.yml` (in this repo). It:

- Defines `med-qdrant` and `med-redis` with **no host ports**.
- Builds/runs the single `med-service` container.
- Attaches `med-service` to the external `prime-world-crm_prime-network` so Traefik can reach it.
- Adds Traefik labels for HTTPS routing.
- Sets CPU/memory limits suitable for a 4-core VPS:
  - `med-qdrant`: 0.6 CPU / 1 GB
  - `med-redis`: 0.2 CPU / 256 MB
  - `med-service`: 1.5 CPU / 4 GB
  - **Total MedService limit: ~2.3 CPU / ~5.25 GB**

> **Memory note:** `med-service` needs 4 GB because both uvicorn processes run in one container and the autocomplete process loads the large SciSpaCy `en_core_sci_lg` model. If you see `SIGKILL` in the logs, the container is OOMing — do not lower this limit.

### Steps

1. **Copy data to the server** (from your local machine):

   ```bash
   # Stop local Qdrant first so the storage files are consistent.
   docker compose stop qdrant

   rsync -avz --delete qdrant_storage/ \
     kavi@srv1496320:~/client_projects/med-service/qdrant_storage/

   rsync -avz --progress \
     data/processed/entities/scispacy_entities.json \
     kavi@srv1496320:~/client_projects/med-service/data/processed/entities/

   docker compose start qdrant
   ```

2. **Create the production `.env`** on the server:

   ```bash
   ssh kavi@srv1496320
   cd ~/client_projects/med-service
   cp .env.example .env
   # edit .env
   ```

   Required values:

   ```bash
   ENVIRONMENT=production
   LOG_LEVEL=INFO

   # Internal compose service names (already set in docker-compose.med-service.deploy.yml)
   QDRANT_URL=http://med-qdrant:6333
   REDIS_URL=redis://med-redis:6379/0

   # Allowed frontend origins — set to the deployed frontend domain(s)
   CORS_ORIGINS=https://med.primeworld.tech,https://med-api.primeworld.tech

   # LLM provider for Kimi Code
   ANTHROPIC_API_KEY=sk-...
   ANTHROPIC_BASE_URL=https://api.kimi.com/coding/
   DEFAULT_LLM_MODEL=claude-sonnet-4-20250514
   ```

3. **Start the stack**:

   ```bash
   docker compose -f docker-compose.med-service.deploy.yml up -d --build
   ```

4. **Verify**:

   ```bash
   # Inside the Traefik network
   curl https://med.primeworld.tech/api/v1/health
   curl -X POST https://med-api.primeworld.tech/api/v1/autocomplete \
     -H 'Content-Type: application/json' \
     -d '{"query":"myo","limit":5}'
   ```

### Why not piggyback on Prime World's Redis/Qdrant?

You could, but it is **not recommended**:

- Prime World's Redis requires password authentication (`redis_pass`). MedService currently uses an unauthenticated Redis URL format.
- Prime World's Qdrant would need a separate collection namespace to avoid collisions.
- Running dedicated containers isolates MedService failures and makes the stack portable.

The resource overhead of a dedicated Qdrant + Redis is small compared to the MedService container itself.

### Why a separate subdomain is better than a path under `primeworld.tech`

- Traefik can route by hostname to the correct internal port without any URL rewriting.
- The FastAPI services see their real root path (`/`), so generated docs, OpenAPI schemas, and CORS `Origin` headers stay simple.
- You can later move MedService to its own server by just updating DNS, without touching Prime World's routing.

---

## Shared-server considerations

The default ports used by this project are common defaults that may conflict with another project on the same server:

| Service | Default port | Why it can conflict |
|---|---|---|
| Qdrant HTTP | `6333` | Another Qdrant or service may use it |
| Qdrant gRPC | `6334` | Same as above |
| Redis | `6379` | Default Redis port |
| RAG Chat Agent | `8000` | Very common API port |
| Semantic Autocomplete | `8001` | Very common API port |

To deploy alongside another project, move these to unused ports and isolate the Docker stack.

---

## Co-existing with Prime World CRM on the same server

The other project already binds several ports. The conflict analysis against MedService defaults is:

| Other project port | Used by | MedService default | Conflict? | MedService solution |
|---|---|---|---|---|
| `80` / `443` | Traefik / Nginx public entrypoint | none | **Yes — cannot run a second reverse proxy** | Route through existing Traefik |
| `8080` | Traefik dashboard | none | No | Avoid `8080` |
| `5432` | PostgreSQL | none | No | — |
| `6379` | Redis | `6379` | **Yes if published** | Do not publish MedService Redis |
| `9000` / `9001` | MinIO | none | No | — |
| `3000` | NestJS API | none | No | — |
| `3001` | NestJS worker | none | No | — |
| `6333` / `6334` | — | Qdrant | No if not published | Do not publish MedService Qdrant |
| `8000` | Nori-Tura API | Chat API (was `8000`) | **Yes — Nori-Tura uses `8000` internally** | Container now uses `8100` internally |
| `8001` | — | Autocomplete API (was `8001`) | No if not published | Container now uses `8101` internally |

**Key point:** because `80` and `443` are already occupied, you cannot run another Nginx/Traefik for MedService on the same IP. You must route MedService through the **existing** reverse proxy.

The recommended approach is `docker-compose.med-service.deploy.yml`, which keeps all MedService ports internal and exposes only via Traefik labels. This avoids every conflict above without needing alternate host ports.

### Option 1: the other project uses Traefik (`docker-compose.yml`)

Put MedService services on the same Docker network as Traefik and add Traefik labels. No host port mapping is needed for the backend or frontend.

Example `docker-compose.med-service.yml`:

```yaml
services:
  med-chat:
    build: .
    command: uv run uvicorn services.rag_chat_agent.api.main:app --host 0.0.0.0 --port 8100
    env_file: .env
    networks:
      - prime-network
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.med-chat.rule=Host(`chat-api.yourdomain.com`)"
      - "traefik.http.services.med-chat.loadbalancer.server.port=8100"

  med-autocomplete:
    build: .
    command: uv run uvicorn services.autocomplete.api.main:app --host 0.0.0.0 --port 8101
    env_file: .env
    networks:
      - prime-network
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.med-autocomplete.rule=Host(`autocomplete-api.yourdomain.com`)"
      - "traefik.http.services.med-autocomplete.loadbalancer.server.port=8101"

  med-console:
    build: ./frontend
    networks:
      - prime-network
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.med-console.rule=Host(`console.yourdomain.com`)"
      - "traefik.http.services.med-console.loadbalancer.server.port=80"

networks:
  prime-network:
    external: true
```

> Replace `prime-network` with the actual external network name used by the other project’s Traefik stack.

In this setup:
- Qdrant and Redis still run from `docker-compose.override.yml` on alternate host ports (`7333`, `7380`).
- The FastAPI services reach them via `QDRANT_URL=http://host.docker.internal:7333` and `REDIS_URL=redis://host.docker.internal:7380/0` (or put Qdrant/Redis on the same Docker network and use service names).
- Traefik terminates HTTPS and routes by hostname.

### Option 2: the other project uses production Nginx (`docker-compose.prod.yml`)

Run MedService on alternate host ports as shown in the systemd examples below, then add upstreams and server blocks to the existing Nginx container. The example server blocks in [Step 6](#step-6-nginx-reverse-proxy) work exactly the same way; you just mount them into the other project’s `nginx` service instead of running a separate Nginx.

For example, add a volume to the other project’s `nginx` service:

```yaml
services:
  nginx:
    volumes:
      - ./med-service/nginx-med-service.conf:/etc/nginx/conf.d/med-service.conf:ro
      - /opt/med-service/frontend/dist:/opt/med-service/frontend/dist:ro
```

### Option 3: alternate host ports with any reverse proxy

If you prefer to keep MedService services on the host (no containers), use the alternate ports below and point the existing reverse proxy to `127.0.0.1:8002` and `127.0.0.1:8003`.

---

## Dockerized inference + Nori-Tura submodule

If you want MedService to live inside the Nori-Tura repo, the cleanest approach is:

1. Add MedService as a **git submodule**.
2. Build a Docker image for MedService inference only.
3. Run MedService containers from Nori-Tura’s Docker Compose.
4. Point Nori-Tura’s existing `RAG_DIAGNOSIS_URL` / `RAG_CONSENT_URL` at the MedService containers.

### Why a submodule + Docker works

- **No Python version conflict.** The MedService image uses Python 3.12; Nori-Tura stays on 3.11.
- **No dependency conflict.** Heavy ML/vector libraries live only inside the MedService image.
- **No code merge.** MedService remains a standalone repo; Nori-Tura only adds a submodule reference and a few Compose service definitions.
- **Endpoint-only integration.** Nori-Tura’s existing RAG config fields are designed exactly for this.

### Add MedService as a submodule in Nori-Tura

```bash
cd Nori-Tura
git submodule add https://github.com/your-org/med-service.git med-service
git submodule update --init
```

This creates `.gitmodules` and pins MedService to a specific commit. To update later:

```bash
cd med-service
git pull origin main
cd ..
git add med-service
git commit -m "update med-service submodule"
```

### MedService Docker files

MedService now includes a **single-container, CPU-only inference image**:

- `Dockerfile` — one container running both chat and autocomplete via `supervisord`.
- `supervisord.conf` — keeps both uvicorn processes alive.
- `docker-compose.med-service.yml` — Qdrant + Redis + one MedService container.
- `.dockerignore` — excludes data, frontend build, caches, secrets.

`pyproject.toml` pins `torch` to the CPU-only wheel on Linux, so the Docker image does not pull in CUDA libraries.

Build it standalone:

```bash
cd med-service
docker build -t med-service-inference .
```

Expected image size after CPU-only torch: **~1.2–1.8 GB** (down from 3–4 GB).

### Why a single container on one 4-core server

For a single small server, one container is more resource-efficient than two because:

- The embedding model and PyTorch libraries are loaded **once**, not twice.
- Shared memory usage is lower.
- A 4-core CPU is enough for occasional concurrent chat/autocomplete requests.

The trade-off is less isolation between the two services.

### Run from Nori-Tura’s compose

Add this to `Nori-Tura/backend/docker-compose.yml` (or a separate `docker-compose.med-service.yml` in Nori-Tura):

```yaml
services:
  med-qdrant:
    image: qdrant/qdrant:v1.18.0
    container_name: med-service-qdrant
    volumes:
      - ./med-service/qdrant_storage:/qdrant/storage

  med-redis:
    image: redis:7-alpine
    container_name: med-service-redis

  med-service:
    build: ./med-service
    container_name: med-service
    env_file: ./med-service/.env
    environment:
      QDRANT_URL: http://med-qdrant:6333
      REDIS_URL: redis://med-redis:6379/0
    volumes:
      - ./med-service/data:/app/data:ro
      - med-cache:/app/.cache
    depends_on:
      - med-qdrant
      - med-redis
    ports:
      - "127.0.0.1:8100:8100"
      - "127.0.0.1:8101:8101"

volumes:
  med-cache:
```

Then in `Nori-Tura/backend/.env`:

```bash
RAG_DIAGNOSIS_URL=http://med-service:8100/api/v1/chat
RAG_CONSENT_URL=http://med-service:8100/api/v1/chat
RAG_API_KEY=your-shared-secret
```

And in `med-service/.env`:

```bash
CORS_ORIGINS=http://localhost:3000,http://localhost:8080
# plus LLM keys, Qdrant/Redis URLs, etc.
```

> **Response-shape mismatch:** MedService `/chat` returns `answer`, `citations`, `confidence`, etc. Nori-Tura’s `rag_service.py` expects `context` for diagnosis and specific consent keys. You will need a small adapter — either a thin wrapper endpoint in MedService or a parser update in Nori-Tura.

### Important notes

- `data/` and `qdrant_storage/` are **not** in the submodule. You must copy them onto the server and mount them as volumes.
- Do not commit secrets. Both `.env` files should be in `.gitignore`.
- The submodule approach is only convenient if MedService is actively maintained as a separate repo. If you plan to heavily customize it for Nori-Tura, forking or copying the code may be simpler long-term.

---

## Recommended alternate ports

| Service | Suggested alternate port |
|---|---|
| Qdrant HTTP | `7333` |
| Qdrant gRPC | `7334` |
| Redis | `7380` |
| RAG Chat Agent | `8100` |
| Semantic Autocomplete | `8101` |

You can choose any free ports. The examples below use the values above.

---

## Step 1: Docker Compose override

Copy the provided example override file and adjust ports if needed:

```bash
cp docker-compose.override.yml.example docker-compose.override.yml
```

This override maps Qdrant and Redis to alternate host ports while keeping their internal container ports unchanged. It also avoids container-name conflicts by using the `med-service` project name.

Start the infrastructure:

```bash
docker compose -p med-service up -d
```

The `-p med-service` flag isolates this stack (networks, container names) from any other Docker Compose project on the server.

---

## Step 2: Environment variables

Create a `.env` file (do not commit it):

```bash
cp .env.example .env
```

Set at least these values for a shared server:

```bash
ENVIRONMENT=production
LOG_LEVEL=INFO

# Use the alternate ports from the override file
QDRANT_URL=http://localhost:7333
REDIS_URL=redis://localhost:7380/0

# CORS: set to your deployed frontend origin(s)
CORS_ORIGINS=https://console.yourdomain.com

# LLM provider (set at least one)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-...
KIMI_API_KEY=...
```

If the other project already uses Redis database `0`, you can also change the database index in `REDIS_URL`, for example `redis://localhost:7380/1`.

---

## Step 3: Copy data without reindexing

Stop your local Qdrant before copying its files:

```bash
docker compose stop qdrant

rsync -avz --delete qdrant_storage/ user@server:/opt/med-service/qdrant_storage/
rsync -avz --progress \
  data/processed/entities/scispacy_entities.json \
  user@server:/opt/med-service/data/processed/entities/

docker compose start qdrant
```

On the server:

```bash
cd /opt/med-service
docker compose -p med-service up -d
```

`redis_data/` does not need to be copied — Redis cache contents are regenerated at runtime.

---

## Step 4: Run the backend services

### systemd example

Create `/etc/systemd/system/med-service-chat.service`:

```ini
[Unit]
Description=MedService RAG Chat Agent
After=network.target docker.service

[Service]
Type=simple
User=medservice
WorkingDirectory=/opt/med-service
ExecStart=/usr/local/bin/uv run uvicorn services.rag_chat_agent.api.main:app --host 127.0.0.1 --port 8100
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/med-service-autocomplete.service`:

```ini
[Unit]
Description=MedService Semantic Autocomplete
After=network.target docker.service

[Service]
Type=simple
User=medservice
WorkingDirectory=/opt/med-service
ExecStart=/usr/local/bin/uv run uvicorn services.autocomplete.api.main:app --host 127.0.0.1 --port 8101
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now med-service-chat med-service-autocomplete
```

---

## Step 5: Build and serve the frontend

Set production API URLs that match your Nginx routing:

```bash
cd frontend
cat > .env.production <<EOF
VITE_CHAT_API_URL=https://chat-api.yourdomain.com
VITE_AUTOCOMPLETE_API_URL=https://autocomplete-api.yourdomain.com
EOF

npm install
npm run build
```

Serve `frontend/dist/` with Nginx (see example below).

---

## Step 6: Nginx reverse proxy

If another project already uses Nginx on the same server, add these server blocks to it.

### Option A: separate subdomains

```nginx
server {
    listen 443 ssl http2;
    server_name console.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/console.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/console.yourdomain.com/privkey.pem;

    root /opt/med-service/frontend/dist;
    index index.html;

    location / {
        try_files $uri /index.html;
    }

    gzip on;
    gzip_types text/css application/javascript application/json;
}

server {
    listen 443 ssl http2;
    server_name chat-api.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/chat-api.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/chat-api.yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8100;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 443 ssl http2;
    server_name autocomplete-api.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/autocomplete-api.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/autocomplete-api.yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8101;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Option B: single domain with path prefixes

If you prefer one domain, use Nginx to strip the path prefix before proxying:

```nginx
server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    ssl_certificate ...;
    ssl_certificate_key ...;

    location /chat/ {
        rewrite ^/chat/(.*)$ /$1 break;
        proxy_pass http://127.0.0.1:8100;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /autocomplete/ {
        rewrite ^/autocomplete/(.*)$ /$1 break;
        proxy_pass http://127.0.0.1:8101;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

In this case your frontend `.env.production` would be:

```bash
VITE_CHAT_API_URL=https://api.yourdomain.com/chat
VITE_AUTOCOMPLETE_API_URL=https://api.yourdomain.com/autocomplete
```

---

## Security notes for shared servers

- Do not expose Qdrant or Redis ports to the public internet. They should only listen on `localhost` or inside the Docker network.
- Use a firewall to block external access to `7333`, `7334`, `7380`, `8100`, and `8101`.
- Keep `.env` permissions strict: `chmod 600 .env`.
- Use HTTPS for the frontend and API subdomains.
- Set `CORS_ORIGINS` to exactly your frontend domain. Do not use a wildcard with credentials enabled.

---

## Verifying the deployment

```bash
# Infrastructure health
curl http://localhost:7333/collections
curl http://localhost:7380 ping

# Service health
curl http://localhost:8100/api/v1/health
curl http://localhost:8101/api/v1/health

# Autocomplete smoke test
curl -X POST http://localhost:8101/api/v1/autocomplete \
  -H 'Content-Type: application/json' \
  -d '{"query":"myo","limit":5}'
```

If all health checks pass and autocomplete returns results, the deployment is working.
