import hashlib
from pathlib import Path
from huggingface_hub import snapshot_download

REPO = "Qwen/Qwen3-0.6B"
REV = "c1899de289a04d12100db370d81485cdf75e47ca"
HASH = "f47f71177f32bcd101b7573ec9171e6a57f4f4d31148d38e382306f42996874b"

base = Path("/models/hub/models--Qwen--Qwen3-0.6B")
snapshot = base / "snapshots" / REV
weights = base / "blobs" / HASH

required = [
    "config.json",
    "generation_config.json",
    "merges.txt",
    "model.safetensors",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.json",
]

def valid_cache():
    if not all((snapshot / name).is_file() for name in required):
        return False

    if not weights.is_file():
        return False

    with weights.open("rb") as f:
        digest = hashlib.file_digest(f, "sha256").hexdigest()

    return digest == HASH

if not valid_cache():
    print("MODEL_CACHE_MISSING_OR_CORRUPT", flush=True)
    snapshot_download(
        repo_id=REPO,
        revision=REV,
        cache_dir="/models/hub",
        allow_patterns=["*.json", "*.txt", "*.safetensors"],
        force_download=True,
    )
else:
    print("MODEL_CACHE_VERIFIED", flush=True)

refs = base / "refs"
refs.mkdir(parents=True, exist_ok=True)
(refs / "main").write_text(REV)

if not valid_cache():
    raise RuntimeError("Model cache validation failed")

print("MODEL_READY", flush=True)
