# vLLM CPU Inference on Kubernetes

Deploy vLLM 0.28.0 with Qwen3-0.6B on Kubernetes using Minikube and Docker.

The project provides a CPU-only OpenAI-compatible inference API.

## Technology stack

- vLLM 0.28.0
- Qwen/Qwen3-0.6B
- Docker and Docker Desktop
- Kubernetes and Minikube
- Kustomize
- Hugging Face Hub
- Windows PowerShell 5.1

## Requirements

- Docker Desktop with Linux containers
- Minikube
- At least 6 CPU cores allocated to Minikube
- Approximately 12 GiB RAM allocated to Minikube
- Internet access for initial image and model downloads

## Architecture

1. Docker provides the custom vLLM CPU image.
2. Kubernetes Deployment runs vLLM as non-root UID 10001.
3. An initContainer verifies or downloads model weights.
4. PVC preserves the Hugging Face model cache.
5. ConfigMap stores inference configuration.
6. Kubernetes Secret stores the API key.
7. ClusterIP Service exposes the API inside Kubernetes.

## Deployment

Open PowerShell in the project directory.

First deployment:

```powershell
.\deploy.ps1
```

Reuse the existing local Minikube image:

```powershell
.\deploy.ps1 -SkipBuild
```

The script starts Minikube, prepares the API Secret,
applies Kustomize resources and checks deployment readiness.

## API access

Open a dedicated PowerShell window:

```powershell
minikube kubectl -- port-forward -n kaspersky-ml service/kaspersky-vllm-svc 8002:8000
```

The API is available locally at:

http://127.0.0.1:8002

## Automated smoke tests

In another PowerShell window:

```powershell
.\scripts\smoke-test.ps1
```

The smoke tests verify:

1. HTTP 401 without an API key.
2. Successful authenticated model discovery.
3. Successful text generation through the chat API.

## Security

- The container runs as non-root UID/GID 10001.
- Privilege escalation is disabled.
- Linux capabilities are dropped.
- The root filesystem is read-only.
- Writable cache directories use mounted volumes.
- The Service uses ClusterIP.
- The API key is stored in a Kubernetes Secret.
- Request and output logging are disabled in vLLM configuration.

The API key protects supported vLLM API routes, not necessarily
every HTTP endpoint. Do not expose the service publicly without
additional access controls.

Secrets and downloaded model weights must not be committed to Git.

## Model storage

The model is Qwen/Qwen3-0.6B.

The initContainer checks the model files and the weight SHA256
before starting vLLM. If validation fails, it attempts to download
the pinned model revision.

The model is persisted in PVC model-cache.

## Current validation status

Verified:
- Local CPU inference
- Rootless Docker execution
- Kubernetes Deployment readiness
- Model loading from an existing PVC
- Successful initContainer cache validation
- Bearer authentication on /v1/models
- Chat completion HTTP 200
- Kustomize deployment
- Automated deployment with -SkipBuild
- Automated smoke tests
- Absence of a test prompt marker in inspected logs

Still to validate:
- Fresh deployment using an empty PVC
- Full dependency pinning and build reproducibility
- Performance benchmarking
- Comprehensive logging and security audit

## Notes

This deployment is intended as a local Kubernetes demonstration
and is not a production-ready public inference service.

## CPU Performance Benchmark

Environment:
- Model: Qwen/Qwen3-0.6B
- Runtime: vLLM 0.28.0, CPU-only
- Platform: Kubernetes / Minikube
- Requests: 3 sequential streaming requests
- Output: 64 tokens per request

Results:

| Run | TTFT | Total latency | Decode speed |
|-----|------|---------------|--------------|
| 1 | 2433.4 ms | 12778.1 ms | 6.09 tok/s |
| 2 | 315.9 ms | 10830.0 ms | 5.99 tok/s |
| 3 | 302.3 ms | 11020.9 ms | 5.88 tok/s |

Average TTFT: 1017.2 ms
Average latency: 11543.0 ms
Average decode speed: 5.99 tok/s

The first request had noticeably higher TTFT.
These measurements represent sequential local CPU inference,
not maximum throughput under concurrent load.

Raw measurements: benchmarks/results.json

## Load Testing: Short vs Long Prompts

Run: python .\scripts\load-test.py --port 8003

| Prompt | Clients | Tokens | TTFT (ms) | Latency (ms) | Throughput (tok/s) |
|---|---:|---:|---:|---:|---:|
| Short | 1 | 21 | 4356.3 | 12095.4 | 3.97 |
| Short | 2 | 21 | 5981.4 | 13969.4 | 5.76 |
| Long | 1 | 319 | 906.7 | 9038.0 | 5.31 |
| Long | 2 | 319 | 6349.9 | 14304.6 | 5.61 |

### Performance Analysis
Many short requests: tune max-num-seqs and max-num-batched-tokens to improve batching and throughput.
Few long-context requests: evaluate max-model-len, KV-cache capacity and chunked prefill.
Two concurrent clients increased TTFT. Results may include warm-up effects.
These optimizations are proposed, not experimentally validated.
Raw data: benchmarks/load-results.json
