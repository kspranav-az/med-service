# Deployment Guide

This guide covers deploying MedService on a server that may already be running other projects. It assumes you want to **avoid reindexing** by copying your local Qdrant storage and entity data.

No application code changes are required. All configuration is done through environment variables, Docker Compose overrides, and systemd/Nginx files.

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

## Recommended alternate ports

| Service | Suggested alternate port |
|---|---|
| Qdrant HTTP | `7333` |
| Qdrant gRPC | `7334` |
| Redis | `7380` |
| RAG Chat Agent | `8002` |
| Semantic Autocomplete | `8003` |

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
ExecStart=/usr/local/bin/uv run uvicorn services.rag_chat_agent.api.main:app --host 127.0.0.1 --port 8002
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
ExecStart=/usr/local/bin/uv run uvicorn services.autocomplete.api.main:app --host 127.0.0.1 --port 8003
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
        proxy_pass http://127.0.0.1:8002;
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
        proxy_pass http://127.0.0.1:8003;
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
        proxy_pass http://127.0.0.1:8002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /autocomplete/ {
        rewrite ^/autocomplete/(.*)$ /$1 break;
        proxy_pass http://127.0.0.1:8003;
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
- Use a firewall to block external access to `7333`, `7334`, `7380`, `8002`, and `8003`.
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
curl http://localhost:8002/api/v1/health
curl http://localhost:8003/api/v1/health

# Autocomplete smoke test
curl -X POST http://localhost:8003/api/v1/autocomplete \
  -H 'Content-Type: application/json' \
  -d '{"query":"myo","limit":5}'
```

If all health checks pass and autocomplete returns results, the deployment is working.
