import asyncio
import base64
from abc import ABC, abstractmethod
from collections.abc import Mapping
from email.message import Message
from typing import Any
from urllib.parse import quote

import httpx

from .auth import AuthorizationContext, ServiceNowAuthenticator
from .config import ServiceNowKnowledgeConfig
from .errors import ErrorCode, KnowledgeMcpError
from .models import KnowledgeArticle, KnowledgeAttachment, KnowledgeSearchCandidate


class KnowledgeClient(ABC):
    @abstractmethod
    async def search(
        self,
        query: str,
        limit: int,
        knowledge_base: str | None,
        language: str | None,
        authorization: AuthorizationContext | None = None,
    ) -> list[KnowledgeSearchCandidate]: ...

    @abstractmethod
    async def get_article(
        self, article_id: str, authorization: AuthorizationContext | None = None
    ) -> KnowledgeArticle: ...

    @abstractmethod
    async def get_attachment(
        self,
        article_id: str,
        attachment_id: str,
        authorization: AuthorizationContext | None = None,
    ) -> KnowledgeAttachment: ...


class ServiceNowKnowledgeClient(KnowledgeClient):
    def __init__(
        self,
        config: ServiceNowKnowledgeConfig,
        authenticator: ServiceNowAuthenticator,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config
        self.authenticator = authenticator
        self._owns_client = http_client is None
        self.http_client = http_client or httpx.AsyncClient(
            base_url=config.servicenow_base_url, timeout=config.request_timeout_seconds
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self.http_client.aclose()

    def _headers(self, authorization: AuthorizationContext | None, accept: str) -> dict[str, str]:
        headers = {"Accept": accept, **self.authenticator.headers(authorization)}
        if self.config.servicenow_api_version:
            headers["Accept-Version"] = self.config.servicenow_api_version
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        authorization: AuthorizationContext | None,
        params: Mapping[str, str | int] | None = None,
        accept: str = "application/json",
    ) -> httpx.Response:
        attempts = self.config.transient_retry_attempts + 1
        for attempt in range(attempts):
            try:
                response = await self.http_client.request(
                    method,
                    path,
                    params=params,
                    headers=self._headers(authorization, accept),
                )
            except httpx.TimeoutException as exc:
                if attempt + 1 == attempts:
                    raise KnowledgeMcpError(
                        ErrorCode.UPSTREAM_TIMEOUT, "ServiceNow request timed out"
                    ) from exc
            except httpx.RequestError as exc:
                if attempt + 1 == attempts:
                    raise KnowledgeMcpError(
                        ErrorCode.UPSTREAM_UNAVAILABLE, "ServiceNow is unavailable"
                    ) from exc
            else:
                if response.status_code not in (429,) and response.status_code < 500:
                    return response
                if attempt + 1 == attempts:
                    return response
            await asyncio.sleep(self.config.retry_backoff_seconds * (2**attempt))
        raise AssertionError("request retry loop exited unexpectedly")

    @staticmethod
    def _raise_for_status(response: httpx.Response, resource: str) -> None:
        status = response.status_code
        if status == 404:
            raise KnowledgeMcpError(ErrorCode.NOT_FOUND, f"{resource} was not found", status=404)
        if status == 401:
            raise KnowledgeMcpError(
                ErrorCode.UNAUTHENTICATED, "ServiceNow authentication failed", status=401
            )
        if status == 403:
            raise KnowledgeMcpError(
                ErrorCode.FORBIDDEN, "ServiceNow access was forbidden", status=403
            )
        if status == 429:
            raise KnowledgeMcpError(
                ErrorCode.RATE_LIMITED, "ServiceNow rate limit was reached", status=429
            )
        if status >= 500:
            raise KnowledgeMcpError(
                ErrorCode.UPSTREAM_UNAVAILABLE, "ServiceNow is unavailable", status=status
            )
        if status >= 400:
            raise KnowledgeMcpError(
                ErrorCode.UPSTREAM_ERROR, "ServiceNow rejected the request", status=status
            )

    @staticmethod
    def _json_result(response: httpx.Response) -> Any:
        try:
            payload = response.json()
        except ValueError as exc:
            raise KnowledgeMcpError(
                ErrorCode.UPSTREAM_ERROR, "ServiceNow returned malformed JSON"
            ) from exc
        if not isinstance(payload, dict) or "result" not in payload:
            raise KnowledgeMcpError(
                ErrorCode.UPSTREAM_ERROR, "ServiceNow returned an unexpected response"
            )
        return payload["result"]

    async def search(
        self,
        query: str,
        limit: int,
        knowledge_base: str | None,
        language: str | None,
        authorization: AuthorizationContext | None = None,
    ) -> list[KnowledgeSearchCandidate]:
        params: dict[str, str | int] = {
            "query": query,
            "limit": limit,
            "fields": ",".join(self.config.search_fields),
        }
        if knowledge_base:
            params["knowledge_base"] = knowledge_base
        if language:
            params["language"] = language
        response = await self._request(
            "GET",
            self.config.servicenow_knowledge_api_path,
            params=params,
            authorization=authorization,
        )
        self._raise_for_status(response, "Knowledge search")
        result = self._json_result(response)
        if isinstance(result, dict):
            result = result.get("articles", result.get("items"))
        if not isinstance(result, list) or not all(isinstance(item, dict) for item in result):
            raise KnowledgeMcpError(
                ErrorCode.UPSTREAM_ERROR, "ServiceNow returned invalid search results"
            )
        return [self._map_candidate(item, rank) for rank, item in enumerate(result, start=1)]

    @staticmethod
    def _map_candidate(raw: Mapping[str, Any], rank: int) -> KnowledgeSearchCandidate:
        identifier = raw.get("sys_id") or raw.get("id")
        title = raw.get("short_description") or raw.get("title")
        if not identifier or not title:
            raise KnowledgeMcpError(
                ErrorCode.UPSTREAM_ERROR, "Search result omitted required fields"
            )
        score = raw.get("score") or raw.get("relevance")
        try:
            normalized_score = float(score) if score is not None else None
        except (TypeError, ValueError):
            normalized_score = None
        return KnowledgeSearchCandidate(
            id=str(identifier),
            number=_optional_string(raw.get("number")),
            title=str(title),
            snippet=_optional_string(raw.get("snippet") or raw.get("description")),
            score=normalized_score,
            rank=rank,
            link=_optional_string(raw.get("link") or raw.get("url")),
            knowledge_base=_display_value(
                raw.get("knowledge_base") or raw.get("kb_knowledge_base")
            ),
        )

    async def get_article(
        self, article_id: str, authorization: AuthorizationContext | None = None
    ) -> KnowledgeArticle:
        path = f"{self.config.servicenow_knowledge_api_path}/{quote(article_id, safe='')}"
        response = await self._request(
            "GET",
            path,
            params={"fields": ",".join(self.config.article_fields)},
            authorization=authorization,
        )
        self._raise_for_status(response, "Knowledge Article")
        result = self._json_result(response)
        if isinstance(result, dict) and isinstance(result.get("article"), dict):
            result = result["article"]
        if not isinstance(result, dict):
            raise KnowledgeMcpError(
                ErrorCode.UPSTREAM_ERROR, "ServiceNow returned an invalid article"
            )
        return self._map_article(result)

    def _map_article(self, raw: Mapping[str, Any]) -> KnowledgeArticle:
        identifier = raw.get("sys_id") or raw.get("id")
        title = raw.get("short_description") or raw.get("title")
        if not identifier or not title:
            raise KnowledgeMcpError(ErrorCode.UPSTREAM_ERROR, "Article omitted required fields")
        content = next(
            (
                raw.get(field)
                for field in ("content", "text", "article_body", "wiki_text")
                if raw.get(field) is not None
            ),
            "",
        )
        return KnowledgeArticle(
            id=str(identifier),
            number=_optional_string(raw.get("number")),
            title=str(title),
            content=str(content)[: self.config.max_article_content_chars],
            knowledge_base=_display_value(
                raw.get("knowledge_base") or raw.get("kb_knowledge_base")
            ),
            category=_display_value(raw.get("category") or raw.get("kb_category")),
            workflow_state=_optional_string(raw.get("workflow_state")),
            published=_optional_string(raw.get("published")),
            valid_to=_optional_string(raw.get("valid_to")),
            updated_on=_optional_string(raw.get("updated_on") or raw.get("sys_updated_on")),
            link=_optional_string(raw.get("link") or raw.get("url")),
        )

    async def get_attachment(
        self,
        article_id: str,
        attachment_id: str,
        authorization: AuthorizationContext | None = None,
    ) -> KnowledgeAttachment:
        path = (
            f"{self.config.servicenow_knowledge_api_path}/{quote(article_id, safe='')}"
            f"/attachments/{quote(attachment_id, safe='')}"
        )
        attempts = self.config.transient_retry_attempts + 1
        for attempt in range(attempts):
            try:
                async with self.http_client.stream(
                    "GET", path, headers=self._headers(authorization, "*/*")
                ) as response:
                    if (
                        response.status_code == 429 or response.status_code >= 500
                    ) and attempt + 1 < attempts:
                        await response.aread()
                        await asyncio.sleep(self.config.retry_backoff_seconds * (2**attempt))
                        continue
                    self._raise_for_status(response, "Knowledge attachment")
                    declared_size = response.headers.get("Content-Length")
                    if declared_size and int(declared_size) > self.config.max_attachment_bytes:
                        raise KnowledgeMcpError(
                            ErrorCode.PAYLOAD_TOO_LARGE,
                            "Attachment exceeds the configured size limit",
                        )
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > self.config.max_attachment_bytes:
                            raise KnowledgeMcpError(
                                ErrorCode.PAYLOAD_TOO_LARGE,
                                "Attachment exceeds the configured size limit",
                            )
                    return KnowledgeAttachment(
                        article_id=article_id,
                        attachment_id=attachment_id,
                        filename=_filename(response.headers.get("Content-Disposition")),
                        content_type=response.headers.get(
                            "Content-Type", "application/octet-stream"
                        ).split(";", 1)[0],
                        size_bytes=len(data),
                        content_base64=base64.b64encode(data).decode("ascii"),
                    )
            except KnowledgeMcpError:
                raise
            except httpx.TimeoutException as exc:
                if attempt + 1 == attempts:
                    raise KnowledgeMcpError(
                        ErrorCode.UPSTREAM_TIMEOUT, "ServiceNow request timed out"
                    ) from exc
            except httpx.RequestError as exc:
                if attempt + 1 == attempts:
                    raise KnowledgeMcpError(
                        ErrorCode.UPSTREAM_UNAVAILABLE, "ServiceNow is unavailable"
                    ) from exc
            await asyncio.sleep(self.config.retry_backoff_seconds * (2**attempt))
        raise AssertionError("attachment retry loop exited unexpectedly")


def _optional_string(value: Any) -> str | None:
    return None if value is None else str(value)


def _display_value(value: Any) -> str | None:
    if isinstance(value, dict):
        return _optional_string(value.get("display_value") or value.get("value"))
    return _optional_string(value)


def _filename(content_disposition: str | None) -> str | None:
    if not content_disposition:
        return None
    message = Message()
    message["content-disposition"] = content_disposition
    filename = message.get_filename()
    return filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1] if filename else None
