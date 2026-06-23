# Phase 6: Production Hardening & Deployment

## Goal
Deploy the system to a cloud VPS with HIPAA-aligned security, monitoring, and reliability.

## Status

⏳ Not started. Depends on Phase 4 (or Phase 5 if UMLS is required before production) and provisioned infrastructure.

## Duration
Weeks 8–10

## Prerequisites
- Phase 3 (RAG enhancements) completed
- Phase 4 or Phase 5 (autocomplete) completed
- VPS provisioned (recommended: Hetzner CPX41)
- Domain + TLS certificate ready
- LLM API keys and BAAs in place

## Tasks

### 1. Production Docker Compose
- Multi-service compose:
  - FastAPI (4+ Uvicorn workers)
  - Qdrant
  - Redis
  - Nginx reverse proxy
  - Optional: Langfuse self-hosted
- Environment-specific config
- Secrets management (Docker secrets or env files)

### 2. Security & Compliance
- TLS 1.2+ via Nginx / Let's Encrypt
- AES-256 encryption at rest for volumes
- RBAC and API key authentication
- Audit logging for all queries and data changes
- 6+ year log retention plan
- BAAs documented for all third-party APIs

### 3. Backup & Recovery
- Scheduled Qdrant snapshots
- Redis persistence (RDB + AOF)
- Offsite backup strategy
- Documented recovery runbook

### 4. Monitoring & Alerting
- Structured logging aggregation
- Latency histograms (P50, P95, P99)
- Error rate thresholds
- LLM API cost tracking
- Cache hit rate metrics
- Alert on:
  - Error rate >1%
  - P95 latency >3s for RAG, >50ms for autocomplete
  - Qdrant/Redis down
  - LLM API errors or quota exhaustion

### 5. Admin Dashboard
- Source/index status
- Query volume and cost trends
- Evaluation metrics over time
- Feedback review interface
- Manual cache invalidation controls

### 6. Load Testing
- Simulate 5–20 concurrent users
- Measure P95 latency under load
- Verify rate limiting holds
- Test failover behavior

### 7. CI/CD
- GitHub/GitLab Actions:
  - Lint and test on PR
  - Build Docker images
  - Deploy to staging then production

### 8. Documentation
- Deployment runbook
- Incident response guide
- On-call checklist
- Data handling and privacy policy

## Key Considerations

- **Do not send PHI to LLM APIs** unless a BAA is in place and explicitly configured.
- **Self-host Qdrant and Redis** for data residency.
- **Use separate staging and production environments.**
- **Keep logs free of PHI** where possible; redact if necessary.
- **FDA consideration:** If the system suggests diagnoses/treatments, it may be regulated as SaMD.

## Verification Checklist

- [ ] Production deployment is live and reachable via HTTPS
- [ ] `/health` endpoint returns OK
- [ ] `/chat` works end-to-end with citations
- [ ] `/autocomplete` works with rate limiting
- [ ] TLS certificate is valid
- [ ] Qdrant and Redis volumes are encrypted
- [ ] Audit logs capture all requests
- [ ] Alerts fire on simulated failure
- [ ] Load test passes with target concurrency
- [ ] CI/CD pipeline deploys successfully
- [ ] Disaster recovery runbook tested

## Outputs / Deliverables

1. `docker-compose.prod.yml`
2. Nginx configuration
3. Terraform/infra scripts (optional)
4. CI/CD pipeline
5. Admin dashboard
6. Monitoring dashboards and alerts
7. Security/compliance documentation
8. Deployment and incident runbooks
