import argparse
import base64
import json
import statistics
import subprocess
import time
import urllib.request
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=8002)
parser.add_argument("--runs", type=int, default=3)
args = parser.parse_args()

secret = subprocess.run(
    [
        "minikube", "kubectl", "--", "get", "secret",
        "kaspersky-vllm-auth", "-n", "kaspersky-ml",
        "-o", "jsonpath={.data.VLLM_API_KEY}",
    ],
    capture_output=True,
    text=True,
    check=True,
)

key = base64.b64decode(secret.stdout.strip()).decode("utf-8")
url = f"http://127.0.0.1:{args.port}/v1/chat/completions"

payload = {
    "model": "Qwen/Qwen3-0.6B",
    "messages": [
        {
            "role": "user",
            "content": "Write 12 short facts about computers.",
        }
    ],
    "temperature": 0,
    "max_tokens": 64,
    "stream": True,
    "stream_options": {"include_usage": True},
    "chat_template_kwargs": {"enable_thinking": False},
}

measurements = []

for number in range(1, args.runs + 1):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    started = time.perf_counter()
    ttft = None
    tokens = None

    with urllib.request.urlopen(request, timeout=180) as response:
        for line in response:
            if not line.startswith(b"data:"):
                continue

            content = line[5:].strip()

            if not content or content == b"[DONE]":
                continue

            event = json.loads(content)

            usage = event.get("usage")
            if usage:
                tokens = usage.get("completion_tokens")

            for choice in event.get("choices", []):
                delta = choice.get("delta") or {}
                if delta.get("content") and ttft is None:
                    ttft = time.perf_counter() - started

    total = time.perf_counter() - started

    if ttft is None or tokens is None:
        raise RuntimeError("Missing streamed token or usage data")

    decode_seconds = max(total - ttft, 0.001)
    decode_rate = max(tokens - 1, 0) / decode_seconds

    sample = {
        "run": number,
        "ttft_ms": round(ttft * 1000, 1),
        "latency_ms": round(total * 1000, 1),
        "output_tokens": tokens,
        "decode_tokens_per_second": round(decode_rate, 2),
    }

    measurements.append(sample)

    print(
        f"RUN {number}: "
        f"TTFT={sample['ttft_ms']} ms | "
        f"Latency={sample['latency_ms']} ms | "
        f"Tokens={tokens} | "
        f"Decode={sample['decode_tokens_per_second']} tok/s",
        flush=True,
    )

summary = {
    "model": payload["model"],
    "runs": args.runs,
    "average_ttft_ms": round(statistics.mean(
        x["ttft_ms"] for x in measurements
    ), 1),
    "average_latency_ms": round(statistics.mean(
        x["latency_ms"] for x in measurements
    ), 1),
    "average_decode_tokens_per_second": round(statistics.mean(
        x["decode_tokens_per_second"] for x in measurements
    ), 2),
    "measurements": measurements,
}

output = Path(__file__).resolve().parent.parent / "benchmarks" / "results.json"
output.parent.mkdir(exist_ok=True)
output.write_text(json.dumps(summary, indent=2), encoding="utf-8")

print("\n=== BENCHMARK COMPLETED ===")
print(json.dumps(summary, indent=2))
print(f"Results saved to {output}")
