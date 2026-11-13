import logging

logger = logging.getLogger("vllm.inference_audit")

INFERENCE_ENDPOINTS = {
    "/v1/chat/completions",
    "/v1/completions",
    "/v1/responses",
    "/v1/messages",
    "/invocations",
    "/inference/v1/generate",
}


async def audit_inference(request, call_next):
    path = request.url.path

    if request.method != "POST" or path not in INFERENCE_ENDPOINTS:
        return await call_next(request)

    status = 500

    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        logger.info(
            "INFERENCE_REQUEST method=POST endpoint=%s status=%d",
            path,
            status,
        )
