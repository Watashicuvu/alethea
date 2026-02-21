FROM ghcr.io/ggml-org/llama.cpp:server

ENV MODEL_PATH="/models/model.gguf"
ENV MODEL_URL=""
ENV GPU_LAYERS="99"

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000 8080
ENTRYPOINT ["/entrypoint.sh"]