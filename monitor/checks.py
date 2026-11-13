import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .models import CheckRecord


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def check_service(service):
    """Probe once, then persist the result even for network failures."""
    url = service.base_url.rstrip("/") + service.health_path
    started = time.perf_counter()
    status_code = None
    error_message = ""
    success = False

    request = Request(url, headers={"Authorization": f"Bearer {service.get_token()}"})
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request, timeout=5) as response:
            status_code = response.status
        success = 200 <= status_code < 300
    except HTTPError as exc:
        status_code = exc.code
        error_message = f"HTTP {exc.code}"
    except (URLError, TimeoutError, OSError) as exc:
        error_message = str(exc)[:500]

    duration_ms = max(0, round((time.perf_counter() - started) * 1000))
    return CheckRecord.objects.create(
        service=service,
        success=success,
        status_code=status_code,
        duration_ms=duration_ms,
        error_message=error_message,
    )
