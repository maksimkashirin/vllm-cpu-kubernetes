import argparse
import base64
import json
import statistics
import subprocess
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--port", type=int, default=8003)
args = p.parse_args()

encoded = subprocess.check_output([
    "minikube", "kubectl", "--", "get", "secret",
    "kaspersky-vllm-auth", "-n", "kaspersky-ml",
    "-o", "jsonpath={.data.VLLM_API_KEY}"
])
api_key = base64.b64decode(encoded.strip()).decode()

url = f"http://127.0.0.1:{args.port}/v1/chat/completions"

short_prompt = "Write 12 short facts about computers."

paragraph = (
    "An industrial site operates PLC controllers, pumps, valves and "
    "physical sensors. Network events and equipment alarms should be "
    "correlated to detect incidents while reducing false positives. "
)

long_prompt = paragraph * 10 + "Summarize the monitoring approach."

def measure(prompt):
    payload = {
        "model": "Qwen/Qwen3-0.6B",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 48,
        "temperature": 0,
        "stream": True,
        "stream_options": {"include_usage": True},
        "chat_template_kwargs": {"enable_thinking": False},
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    start = time.perf_counter()
    ttft = None
    usage = None

    with urllib.request.urlopen(req, timeout=240) as response:
        for line in response:
            if not line.startswith(b"data:"):
                continue

            data = line[5:].strip()

            if not data or data == b"[DONE]":
                continue

            event = json.loads(data)

            if event.get("usage"):
                usage = event["usage"]

            for choice in event.get("choices", []):
                delta = choice.get("delta") or {}

                if delta.get("content") and ttft is None:
                    ttft = time.perf_counter() - start

    latency = time.perf_counter() - start

    if ttft is None or usage is None:
        raise RuntimeError("Missing TTFT or token usage")

    return {
        "ttft_ms": round(ttft * 1000, 1),
        "latency_ms": round(latency * 1000, 1),
        "prompt_tokens": usage["prompt_tokens"],
        "completion_tokens": usage["completion_tokens"],
    }

results = []

for name, prompt in [
    ("short", short_prompt),
    ("long", long_prompt),
]:
    for concurrency in [1, 2]:
        started = time.perf_counter()

        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            samples = list(pool.map(measure, [prompt] * 3))

        elapsed = time.perf_counter() - started
        output_tokens = sum(x["completion_tokens"] for x in samples)

        result = {
            "scenario": name,
            "concurrency": concurrency,
            "requests": 3,
            "prompt_tokens": samples[0]["prompt_tokens"],
            "avg_ttft_ms": round(statistics.mean(
                x["ttft_ms"] for x in samples
            ), 1),
            "avg_latency_ms": round(statistics.mean(
                x["latency_ms"] for x in samples
            ), 1),
            "output_throughput_tok_s": round(
                output_tokens / elapsed, 2
            ),
            "requests_per_second": round(3 / elapsed, 3),
            "samples": samples,
        }

        results.append(result)

        print(
            f"{name.upper()} | clients={concurrency} | "
            f"prompt={result['prompt_tokens']} tokens | "
            f"TTFT={result['avg_ttft_ms']} ms | "
            f"Latency={result['avg_latency_ms']} ms | "
            f"Throughput={result['output_throughput_tok_s']} tok/s",
            flush=True,
        )

out = Path(__file__).resolve().parent.parent / "benchmarks" / "load-results.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(results, indent=2), encoding="utf-8")

print("LOAD TEST COMPLETED")
print(f"Results: {out}")
