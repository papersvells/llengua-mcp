"""Client HTTP cortès: rate limit per host, cache i tolerància a EOF de TLS."""

from __future__ import annotations

import asyncio
import hashlib
import json
import random
import ssl
import time
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

import httpx

from llengua_mcp.cache import TTLCache
from llengua_mcp.config import Settings
from llengua_mcp.errors import UnexpectedResponseError, UpstreamError

_TRANSIENT = (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout)


@dataclass
class HttpResult:
    text: str
    status: int
    url: str
    warnings: list[str] = field(default_factory=list)
    from_cache: bool = False
    bytes_received: int = 0
    _cacheable: bool = field(default=False, repr=False, compare=False)
    _cache_token: object | None = field(default=None, repr=False, compare=False)


@dataclass
class RequestMeter:
    """Compta el cost real d'una crida a una eina.

    `upstream_requests` inclou cada intent de xarxa, també els reintents;
    `cache_hits` compta les respostes servides des de la memòria cau HTTP.
    """

    started_at: float = field(default_factory=time.monotonic)
    upstream_requests: int = 0
    cache_hits: int = 0

    def payload(self) -> dict[str, Any]:
        return {
            "elapsed_ms": round((time.monotonic() - self.started_at) * 1000),
            "upstream_requests": self.upstream_requests,
            "cache_hits": self.cache_hits,
            "from_cache": self.upstream_requests == 0 and self.cache_hits > 0,
        }


_METER: ContextVar[RequestMeter | None] = ContextVar("llengua_meter", default=None)


def start_meter() -> RequestMeter:
    """Obre un comptador per a la crida actual i el deixa al context."""

    meter = RequestMeter()
    _METER.set(meter)
    return meter


def current_meter() -> RequestMeter | None:
    return _METER.get()


def reset_meter(_meter: RequestMeter | None = None) -> None:
    _METER.set(None)


def _count(*, upstream: bool) -> None:
    meter = _METER.get()
    if meter is None:
        return
    if upstream:
        meter.upstream_requests += 1
    else:
        meter.cache_hits += 1


def is_cacheable(headers: dict[str, str]) -> bool:
    """No cachegem respostes que la font marca com a no-store."""

    for key, value in headers.items():
        if key.lower() == "cache-control" and "no-store" in value.lower():
            return False
    return True


class RateLimiter:
    """Espaiat mínim entre peticions al mateix host (no paral·lelisme)."""

    def __init__(self, rate_per_second: float) -> None:
        self.interval = 1.0 / max(rate_per_second, 0.01)
        self._next_allowed: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def wait(self, host: str) -> None:
        lock = self._locks.setdefault(host, asyncio.Lock())
        async with lock:
            now = time.monotonic()
            delay = self._next_allowed.get(host, 0.0) - now
            if delay > 0:
                await asyncio.sleep(delay + random.uniform(0.0, 0.15))
            self._next_allowed[host] = time.monotonic() + self.interval


class HttpClient:
    def __init__(
        self,
        settings: Settings,
        *,
        verify: ssl.SSLContext | bool = True,
        follow_redirects: bool = True,
    ) -> None:
        self.settings = settings
        self.cache = TTLCache(default_ttl=settings.cache_ttl_seconds)
        self.limiter = RateLimiter(settings.rate_per_second)
        self._cache_locks: dict[str, tuple[asyncio.Lock, int]] = {}
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.timeout_seconds),
            follow_redirects=follow_redirects,
            verify=verify,
            headers={
                "User-Agent": settings.user_agent,
                "Accept-Language": "ca",
                "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            },
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _cache_key(
        method: str, url: str, body: str | None, headers: dict[str, str] | None = None
    ) -> str:
        normalized_headers = sorted(httpx.Headers(headers).multi_items())
        payload = json.dumps([method, url, body, normalized_headers], ensure_ascii=False).encode()
        return hashlib.sha256(payload).hexdigest()

    @asynccontextmanager
    async def _cache_lock(self, key: str):
        """Serialitza una mateixa clau i allibera el pany quan ja no té usuaris."""

        lock, users = self._cache_locks.get(key, (asyncio.Lock(), 0))
        self._cache_locks[key] = (lock, users + 1)
        try:
            async with lock:
                yield
        finally:
            _, users = self._cache_locks[key]
            if users == 1:
                del self._cache_locks[key]
            else:
                self._cache_locks[key] = (lock, users - 1)

    def _cached_result(self, key: str, url: str) -> HttpResult | None:
        cached = self.cache.get(key)
        if cached is None:
            return None
        _count(upstream=False)
        text, status, token = cached
        return HttpResult(
            text=text,
            status=status,
            url=url,
            from_cache=True,
            bytes_received=len(text.encode("utf-8")),
            _cache_token=token,
        )

    async def get_text(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        cache_ttl: int | None = None,
        use_cache: bool = True,
    ) -> HttpResult:
        if params:
            request = httpx.Request("GET", url, params=params)
            url = str(request.url)
        return await self._request(
            "GET",
            url,
            body=None,
            headers=headers,
            cache_ttl=cache_ttl,
            use_cache=use_cache,
        )

    async def post_text(
        self,
        url: str,
        body: str,
        *,
        headers: dict[str, str] | None = None,
        cache_ttl: int | None = None,
        use_cache: bool = True,
    ) -> HttpResult:
        merged = {"Content-Type": "application/x-www-form-urlencoded"}
        if headers:
            merged.update(headers)
        return await self._request(
            "POST",
            url,
            body=body,
            headers=merged,
            cache_ttl=cache_ttl,
            use_cache=use_cache,
        )

    async def post_json(
        self,
        url: str,
        body: str,
        *,
        headers: dict[str, str] | None = None,
        cache_ttl: int | None = None,
    ) -> tuple[dict[str, Any], HttpResult]:
        merged = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
        }
        if headers:
            merged.update(headers)
        # Separa els POST de text cru dels POST amb JSON validat.
        key = self._cache_key("POST JSON", url, body, merged)
        result = self._cached_result(key, url)
        if result is not None:
            return self._parse_json(result, url), result
        async with self._cache_lock(key):
            result = self._cached_result(key, url)
            if result is None:
                result = await self.post_text(url, body, headers=merged, use_cache=False)
            payload = self._parse_json(result, url)
            if result._cacheable:
                result._cache_token = object()
                self.cache.set(
                    key, (result.text, result.status, result._cache_token), ttl=cache_ttl
                )
            return payload, result

    @staticmethod
    def _parse_json(result: HttpResult, url: str) -> dict[str, Any]:
        try:
            payload = json.loads(result.text)
        except json.JSONDecodeError as exc:
            raise UnexpectedResponseError(
                "La resposta no és JSON vàlid.",
                hint="El servei pot haver canviat de format o haver retornat una pàgina d'error.",
                source=url,
            ) from exc
        if not isinstance(payload, dict):
            raise UnexpectedResponseError(
                "La resposta JSON no té el format esperat.",
                hint="Cal revisar el parser del servei.",
                source=url,
            )
        return payload

    async def _request(
        self,
        method: str,
        url: str,
        *,
        body: str | None,
        headers: dict[str, str] | None,
        cache_ttl: int | None,
        use_cache: bool,
    ) -> HttpResult:
        key = self._cache_key(method, url, body, headers)
        if use_cache:
            cached = self._cached_result(key, url)
            if cached is not None:
                return cached
            async with self._cache_lock(key):
                cached = self._cached_result(key, url)
                if cached is not None:
                    return cached
                return await self._request_network(
                    method, url, body=body, headers=headers, cache_ttl=cache_ttl, key=key
                )
        return await self._request_network(
            method, url, body=body, headers=headers, cache_ttl=cache_ttl, key=None
        )

    async def _request_network(
        self,
        method: str,
        url: str,
        *,
        body: str | None,
        headers: dict[str, str] | None,
        cache_ttl: int | None,
        key: str | None,
    ) -> HttpResult:
        host = urlsplit(url).netloc
        last_error: Exception | None = None

        for attempt in range(3):
            await self.limiter.wait(host)
            _count(upstream=True)
            try:
                text, status, warnings, size, response_headers = await self._one_request(
                    method, url, body=body, headers=headers
                )
            except _TRANSIENT as exc:
                last_error = exc
                if attempt < 2:
                    await asyncio.sleep(1.5 * (attempt + 1) + random.uniform(0, 0.4))
                    continue
                raise UpstreamError(
                    f"No s'ha pogut connectar amb {host}.",
                    hint="Comprova la connexió i torna-ho a provar més tard.",
                    source=url,
                ) from exc

            if status >= 500:
                raise UpstreamError(
                    f"El servei ha retornat HTTP {status}.",
                    hint=(
                        "El CTILC retorna 500 per consultes no vàlides o per errors interns. "
                        "No es reintenta automàticament; revisa la consulta abans de repetir-la."
                    ),
                    source=url,
                )
            if status == 404:
                raise UpstreamError(
                    "El recurs no existeix (HTTP 404).",
                    hint="L'URL pot haver canviat; cal revisar el protocol del servei.",
                    source=url,
                )
            if status >= 400:
                raise UpstreamError(
                    f"El servei ha retornat HTTP {status}.",
                    hint="La consulta o l'accés poden haver canviat.",
                    source=url,
                )

            result = HttpResult(
                text=text,
                status=status,
                url=url,
                warnings=warnings,
                bytes_received=size,
                _cacheable=not warnings and is_cacheable(response_headers),
            )
            # No cachegem respostes amb transport incomplet.
            if key is not None and result._cacheable:
                result._cache_token = object()
                self.cache.set(key, (text, status, result._cache_token), ttl=cache_ttl)
            return result

        raise UpstreamError(
            "No s'ha pogut completar la petició.",
            hint=str(last_error) if last_error else "Error de transport desconegut.",
            source=url,
        )

    async def _one_request(
        self,
        method: str,
        url: str,
        *,
        body: str | None,
        headers: dict[str, str] | None,
    ) -> tuple[str, int, list[str], int, dict[str, str]]:
        warnings: list[str] = []
        buffer = bytearray()
        truncated = False
        response_headers: dict[str, str] = {}
        try:
            async with self._client.stream(
                method,
                url,
                content=body.encode("utf-8") if body is not None else None,
                headers=headers,
            ) as response:
                status = response.status_code
                response_headers = dict(response.headers)
                try:
                    async for chunk in response.aiter_bytes():
                        buffer.extend(chunk)
                        if len(buffer) > self.settings.max_response_bytes:
                            raise UpstreamError(
                                "La resposta supera el límit de mida configurat.",
                                hint="Redueix el nombre de files o augmenta LLENGUA_MAX_BYTES.",
                                source=url,
                            )
                except (httpx.RemoteProtocolError, httpx.ReadError) as exc:
                    truncated = True
                    if len(buffer) < 200:
                        raise UpstreamError(
                            "La connexió s'ha tallat abans de rebre dades.",
                            hint=str(exc),
                            source=url,
                        ) from exc
        except _TRANSIENT as exc:
            # Si ja hem rebut dades, no reintentem a cegues: podríem duplicar
            # una consulta o barrejar una resposta parcial.
            if buffer:
                raise UpstreamError(
                    "La connexió s'ha tallat després de rebre dades.",
                    hint=str(exc),
                    source=url,
                ) from exc
            raise
        except httpx.HTTPError as exc:
            raise UpstreamError(
                "Error de transport en la petició HTTP.",
                hint=str(exc),
                source=url,
            ) from exc

        text = buffer.decode("utf-8", errors="replace").lstrip("\ufeff")
        if truncated:
            complete_html = text.rstrip().lower().endswith("</html>")
            complete_json = text.rstrip().endswith("}")
            if not (complete_html or complete_json):
                raise UpstreamError(
                    "La resposta s'ha rebut incompleta.",
                    hint="No es presenta com un resultat vàlid; torna-ho a provar més tard.",
                    source=url,
                )
            warnings.append("transport_eof")
        return text, status, warnings, len(buffer), response_headers
