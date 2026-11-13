import logging
import time

logger = logging.getLogger("monitor")


class RequestTimingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = time.perf_counter()
        response = self.get_response(request)
        duration_ms = (time.perf_counter() - started) * 1000
        response["X-Request-Duration-Ms"] = f"{duration_ms:.2f}"
        logger.info("%s %s %s %.2fms", request.method, request.path, response.status_code, duration_ms)
        return response
