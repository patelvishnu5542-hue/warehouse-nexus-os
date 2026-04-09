---
title: Warehouse Nexus OS
sdk: docker
app_port: 7860
---

# Warehouse Nexus OS (OpenEnv Submission)

## Links
- GitHub: `https://github.com/patelvishnu5542-hue/warehouse-nexus-os`
- HF Space: `https://huggingface.co/spaces/Vishnupatel/warehouse-nexus-os`
- Runtime URL: `https://vishnupatel-warehouse-nexus-os.hf.space`

## Required Space Variables/Secrets
- `API_BASE_URL` (recommended): `https://router.huggingface.co/v1`
- `MODEL_NAME` (example): `Qwen/Qwen2.5-72B-Instruct`
- `HF_TOKEN` (secret)

## Local (Docker)
```bash
docker build -t warehouse-openenv .
docker run --rm -p 7860:7860 -e PORT=7860 warehouse-openenv
```

## Runtime Endpoints
- UI: `GET /ui`
- Health: `GET /health` (expects `{"status":"healthy"}`)
- Reset: `POST /reset` (expects HTTP 200)

## Validation (same as judges)
```bash
bash scripts/validate-submission.sh https://vishnupatel-warehouse-nexus-os.hf.space .
```

