FROM vllm/vllm-openai-cpu:v0.28.0@sha256:197354e6475e638eb5ccca09beb078488046a82de0e204e7429bf1a804df9647

USER root

RUN groupadd --gid 10001 app && \
    useradd --uid 10001 --gid 10001 \
        --home-dir /home/app --create-home \
        --shell /bin/sh app && \
    mkdir -p /home/app/.cache/huggingface \
             /home/app/.cache/vllm && \
    chown -R 10001:10001 /home/app

ENV HOME=/home/app \
    HF_HOME=/home/app/.cache/huggingface \
    XDG_CACHE_HOME=/home/app/.cache \
    VLLM_CPU_KVCACHE_SPACE=1

COPY --chown=10001:10001 requirements.txt /home/app/requirements.lock

WORKDIR /home/app

USER 10001:10001

EXPOSE 8000

ENTRYPOINT ["vllm"]

CMD ["serve", "Qwen/Qwen3-0.6B", \
     "--dtype", "float32", \
     "--max-model-len", "512", \
     "--max-num-seqs", "1", \
     "--enforce-eager", \
     "--no-enable-log-requests"]
