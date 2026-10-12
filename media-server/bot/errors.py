"""Safe error reporting.

Exceptions from httpx include the full request URL in their message, and some
services (TMDB) authenticate with an API key in the query string. So we never
show `str(exc)` to users and never log it for HTTP errors: we describe the
error from its parts (type, status, host, path) instead.
"""
import logging

import httpx

log = logging.getLogger("cinebot.errors")


def _safe_url(request: httpx.Request | None) -> str:
    if request is None:
        return "?"
    return f"{request.method} {request.url.host}{request.url.path}"


def _request_of(exc: httpx.HTTPError) -> httpx.Request | None:
    try:
        return exc.request
    except RuntimeError:  # request not attached
        return None


def describe(exc: BaseException) -> str:
    """One-line description that never contains query strings or credentials."""
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code} on {_safe_url(exc.request)}"
    if isinstance(exc, httpx.HTTPError):
        return f"{type(exc).__name__} on {_safe_url(_request_of(exc))}"
    return f"{type(exc).__name__}: {exc}"


def _reason(exc: BaseException) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return "el servicio tardó demasiado en responder"
    if isinstance(exc, httpx.ConnectError):
        return "el servicio no está disponible"
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code in (401, 403):
            return "el servicio rechazó la autenticación"
        if code == 404:
            return "no se encontró lo que buscabas"
        if code >= 500:
            return "el servicio tuvo un error interno"
        return "el servicio rechazó el pedido"
    return "ocurrió un error inesperado"


def report_error(action: str, exc: BaseException) -> str:
    """Log the error safely and return a user-facing message.

    `action` completes the sentence "No pude ..." (e.g. "buscar la película").
    """
    # Tracebacks only for non-HTTP errors (likely bugs): HTTP error tracebacks
    # end with str(exc), which contains the URL.
    log.error(
        "Failed to %s: %s", action, describe(exc),
        exc_info=None if isinstance(exc, httpx.HTTPError) else exc,
    )
    return f"❌ No pude {action}: {_reason(exc)}. Probá de nuevo en un rato."
