"""Tests for the LLM analysis service."""

import asyncio
from typing import Any

import httpx2 as httpx
import pytest
from app.config.settings import LLMConfig
from app.services import llm_analysis_service as service
from app.services.llm_analysis_service import (
    LLMNotConfiguredError,
    build_endpoint_url,
)


def _make_llm(**kwargs: Any) -> LLMConfig:
    """Build an enabled LLMConfig with test-friendly defaults."""
    defaults: dict[str, Any] = {
        "enabled": True,
        "base_url": "http://localhost",
        "api_path": "/v1/chat/completions",
        "model": "test-model",
    }
    defaults.update(kwargs)
    return LLMConfig(**defaults)


class FakeResponse:
    """Minimal stand-in for an httpx2 response."""

    def __init__(self, status_code: int, body: Any = None, json_error: bool = False, text: str = "") -> None:
        self.status_code = status_code
        self._body = body
        self._json_error = json_error
        self._text = text

    @property
    def text(self) -> str:
        return self._text

    def json(self) -> Any:
        if self._json_error:
            raise ValueError("invalid json")
        return self._body


class FakeClient:
    """Minimal async client stand-in that records the request it is given."""

    def __init__(self, response: FakeResponse | None = None, exc: Exception | None = None) -> None:
        self._response = response
        self._exc = exc
        self.calls: list[tuple[str, dict[str, Any] | None, dict[str, str] | None]] = []
        self.timeout: Any = None

    async def __aenter__(self) -> "FakeClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def post(self, url: str, json: dict[str, Any] | None = None,
                   headers: dict[str, str] | None = None) -> FakeResponse:
        self.calls.append((url, json, headers))
        if self._exc is not None:
            raise self._exc
        assert self._response is not None
        return self._response


def _patch_client(monkeypatch: Any, client: FakeClient) -> None:
    """Replace the service's httpx AsyncClient with a factory returning client."""
    def _factory(timeout: Any = None) -> FakeClient:
        client.timeout = timeout
        return client

    monkeypatch.setattr(service.httpx, "AsyncClient", _factory)


class TestBuildEndpointUrl:
    """Tests for build_endpoint_url."""

    def test_https_default_port_omitted(self) -> None:
        """Test that the default https port is omitted."""
        llm = _make_llm(base_url="https://api.openai.com")
        assert build_endpoint_url(llm) == "https://api.openai.com/v1/chat/completions"

    def test_http_default_port_omitted(self) -> None:
        """Test that the default http port is omitted."""
        llm = _make_llm(port=80)
        assert build_endpoint_url(llm) == "http://localhost/v1/chat/completions"

    def test_explicit_url_port_wins_over_configured(self) -> None:
        """Test that a port in the base URL beats the configured port."""
        llm = _make_llm(base_url="http://localhost:9999", port=8000)
        assert build_endpoint_url(llm) == "http://localhost:9999/v1/chat/completions"

    def test_configured_port_used(self) -> None:
        """Test that the configured port is used when the URL has none."""
        llm = _make_llm(port=8000)
        assert build_endpoint_url(llm) == "http://localhost:8000/v1/chat/completions"

    def test_trailing_slashes_normalized(self) -> None:
        """Test that base URL trailing slashes and a slash-less api_path normalize."""
        llm = _make_llm(base_url="http://host:1234///", api_path="v1/completions")
        assert build_endpoint_url(llm) == "http://host:1234/v1/completions"

    def test_ipv6_host_wrapped_in_brackets(self) -> None:
        """Test that IPv6 hosts are wrapped in brackets."""
        llm = _make_llm(base_url="http://[::1]:9000")
        assert build_endpoint_url(llm) == "http://[::1]:9000/v1/chat/completions"

    @pytest.mark.parametrize(
        "llm",
        [
            pytest.param(_make_llm(enabled=False), id="disabled"),
            pytest.param(_make_llm(base_url="   "), id="whitespace"),
            pytest.param(_make_llm(base_url="ftp://example.com"), id="bad-scheme"),
            pytest.param(_make_llm(base_url="https://"), id="no-hostname"),
            pytest.param(_make_llm(base_url="https://api.openai.com:notaport"), id="bad-port"),
        ],
    )
    def test_invalid_config_raises(self, llm: LLMConfig) -> None:
        """Test that invalid configurations raise LLMNotConfiguredError."""
        with pytest.raises(LLMNotConfiguredError):
            build_endpoint_url(llm)


class TestTestLLMConnection:
    """Tests for test_llm_connection."""

    async def test_success(self, monkeypatch: Any) -> None:
        """Test a successful connection returns ok with model and timing."""
        client = FakeClient(response=FakeResponse(200, {"model": "gpt-4o-mini", "choices": [{"message": {"content": "ok"}}]}))
        _patch_client(monkeypatch, client)
        llm = _make_llm(api_key="sk-123")

        result = await service.test_llm_connection(llm)

        assert result.ok is True
        assert result.model == "gpt-4o-mini"
        assert result.elapsed_ms >= 0
        url, payload, headers = client.calls[0]
        assert url == "http://localhost/v1/chat/completions"
        assert payload is not None
        assert payload["model"] == "test-model"
        assert headers is not None
        assert headers["Authorization"] == "Bearer sk-123"
        assert "max_tokens" not in payload
        assert client.timeout == llm.timeout_seconds

    async def test_model_fallback_to_configured(self, monkeypatch: Any) -> None:
        """Test that the configured model is reported when the body lacks one."""
        client = FakeClient(response=FakeResponse(200, {"choices": [{"message": {"content": "ok"}}]}))
        _patch_client(monkeypatch, client)

        result = await service.test_llm_connection(_make_llm())

        assert result.ok is True
        assert result.model == "test-model"

    async def test_timeout(self, monkeypatch: Any) -> None:
        """Test that a timeout produces a friendly error."""
        client = FakeClient(exc=httpx.TimeoutException("timed out"))
        _patch_client(monkeypatch, client)
        llm = _make_llm(timeout_seconds=5)

        result = await service.test_llm_connection(llm)

        assert result.ok is False
        assert result.error == "Request timed out after 5s"

    async def test_connect_error(self, monkeypatch: Any) -> None:
        """Test that a connection error names the exception type."""
        client = FakeClient(exc=httpx.ConnectError("boom"))
        _patch_client(monkeypatch, client)

        result = await service.test_llm_connection(_make_llm())

        assert result.ok is False
        assert result.error == "Could not reach endpoint: ConnectError"

    async def test_http_error_status(self, monkeypatch: Any) -> None:
        """Test that a non-200 status includes the status and a body snippet."""
        client = FakeClient(response=FakeResponse(500, text="Internal Server Error"))
        _patch_client(monkeypatch, client)

        result = await service.test_llm_connection(_make_llm())

        assert result.ok is False
        assert result.error.startswith("HTTP 500:")
        assert "Internal Server Error" in result.error

    async def test_invalid_json(self, monkeypatch: Any) -> None:
        """Test that invalid JSON is reported as a format error."""
        client = FakeClient(response=FakeResponse(200, json_error=True))
        _patch_client(monkeypatch, client)

        result = await service.test_llm_connection(_make_llm())

        assert result.ok is False
        assert "Unexpected response format" in result.error

    async def test_missing_choices(self, monkeypatch: Any) -> None:
        """Test that a body without choices is reported as a format error."""
        client = FakeClient(response=FakeResponse(200, {"error": "nope"}))
        _patch_client(monkeypatch, client)

        result = await service.test_llm_connection(_make_llm())

        assert result.ok is False
        assert "Unexpected response format" in result.error

    async def test_empty_choices(self, monkeypatch: Any) -> None:
        """Test that an empty choices list is reported as a format error."""
        client = FakeClient(response=FakeResponse(200, {"choices": []}))
        _patch_client(monkeypatch, client)

        result = await service.test_llm_connection(_make_llm())

        assert result.ok is False
        assert "Unexpected response format" in result.error

    async def test_blank_content(self, monkeypatch: Any) -> None:
        """Test that blank content is rejected."""
        client = FakeClient(response=FakeResponse(200, {"choices": [{"message": {"content": "   "}}]}))
        _patch_client(monkeypatch, client)

        result = await service.test_llm_connection(_make_llm())

        assert result.ok is False
        assert result.error == "Endpoint returned empty content"

    async def test_no_api_key_omits_authorization(self, monkeypatch: Any) -> None:
        """Test that no Authorization header is sent without an api_key."""
        client = FakeClient(response=FakeResponse(200, {"choices": [{"message": {"content": "ok"}}]}))
        _patch_client(monkeypatch, client)

        await service.test_llm_connection(_make_llm(api_key=""))

        _, _, headers = client.calls[0]
        assert headers is not None
        assert "Authorization" not in headers

    async def test_max_tokens_included_when_set(self, monkeypatch: Any) -> None:
        """Test that max_tokens is sent when configured."""
        client = FakeClient(response=FakeResponse(200, {"choices": [{"message": {"content": "ok"}}]}))
        _patch_client(monkeypatch, client)

        await service.test_llm_connection(_make_llm(max_tokens=256))

        _, payload, _ = client.calls[0]
        assert payload is not None
        assert payload["max_tokens"] == 256

    async def test_disabled_raises(self) -> None:
        """Test that a disabled config raises before any request."""
        with pytest.raises(LLMNotConfiguredError):
            await service.test_llm_connection(_make_llm(enabled=False))


OK_BODY: dict[str, Any] = {
    "model": "test-model-echo",
    "choices": [{"message": {"content": "## Analysis\nLooks risky."}}],
}


class TestBuildPrompt:
    """Tests for build_prompt."""

    def _full_finding(self) -> dict[str, Any]:
        return {
            "function_name": "strcpy",
            "containing_function": "parse_packet",
            "entrypoint": "0x401000",
            "category": "memory",
            "severity": "high",
            "cwe": "CWE-120",
            "description": "Copies a string without bounds checking.",
            "safe_alternative": "strncpy or memcpy with an explicit length",
            "usage_context": ["strcpy(dst, src);", "strcpy(dst2, src);"],
            "containing_function_code": "void parse_packet(char *dst) { strcpy(dst, buf); }",
        }

    def test_includes_all_fields(self) -> None:
        """Test that every populated finding field appears in the prompt."""
        prompt = service.build_prompt(self._full_finding())
        for expected in (
            "Dangerous function: strcpy",
            "Containing function: parse_packet",
            "Entrypoint: 0x401000",
            "Category: memory",
            "Severity: high",
            "CWE: CWE-120",
            "Catalog description: Copies a string without bounds checking.",
            "Recommended safe alternative: strncpy or memcpy with an explicit length",
            "  strcpy(dst, src);",
            "  strcpy(dst2, src);",
            "void parse_packet(char *dst) { strcpy(dst, buf); }",
        ):
            assert expected in prompt

    def test_omits_empty_optional_fields(self) -> None:
        """Test that empty optional fields are left out of the prompt."""
        prompt = service.build_prompt(
            {
                "function_name": "system",
                "containing_function": "main",
                "entrypoint": "0x400000",
                "category": "os",
                "severity": "critical",
                "cwe": "CWE-78",
                "description": "",
                "safe_alternative": "",
                "usage_context": [],
                "containing_function_code": "",
            }
        )
        assert "Catalog description:" not in prompt
        assert "Recommended safe alternative:" not in prompt
        assert "Call-site context" not in prompt
        assert "Decompiled code" not in prompt

    def test_handles_missing_keys(self) -> None:
        """Test that missing keys fall back to 'unknown'."""
        prompt = service.build_prompt({})
        assert "Dangerous function: unknown" in prompt
        assert "Containing function: unknown" in prompt
        assert "CWE: unknown" in prompt


class TestAnalyzeFinding:
    """Tests for analyze_finding."""

    def _finding(self) -> dict[str, Any]:
        return {
            "function_name": "strcpy",
            "containing_function": "parse_packet",
            "entrypoint": "0x401000",
            "category": "memory",
            "severity": "high",
            "cwe": "CWE-120",
            "description": "Copies a string without bounds checking.",
            "safe_alternative": "strncpy",
            "usage_context": ["strcpy(dst, src);"],
            "containing_function_code": "void parse_packet(char *dst) { strcpy(dst, buf); }",
        }

    async def test_success(self, monkeypatch: Any) -> None:
        """Test a successful analysis returns the model content and request shape."""
        client = FakeClient(response=FakeResponse(200, OK_BODY))
        _patch_client(monkeypatch, client)

        result = await service.analyze_finding(_make_llm(api_key="sk-abc"), self._finding())

        assert result.status == "success"
        assert result.analysis == "## Analysis\nLooks risky."
        assert result.model == "test-model-echo"
        assert result.error == ""
        assert result.elapsed_ms >= 0
        url, payload, headers = client.calls[0]
        assert url == "http://localhost/v1/chat/completions"
        assert payload is not None
        assert payload["model"] == "test-model"
        assert payload["temperature"] == 0.1
        messages = payload["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert "security engineer" in messages[0]["content"]
        assert messages[1]["role"] == "user"
        assert "strcpy" in messages[1]["content"]
        assert "CWE-120" in messages[1]["content"]
        assert "strcpy(dst, src);" in messages[1]["content"]
        assert headers is not None
        assert headers["Authorization"] == "Bearer sk-abc"
        assert client.timeout == 120.0

    async def test_model_fallback_to_configured(self, monkeypatch: Any) -> None:
        """Test that the configured model is reported when the body lacks one."""
        client = FakeClient(response=FakeResponse(200, {"choices": [{"message": {"content": "ok"}}]}))
        _patch_client(monkeypatch, client)

        result = await service.analyze_finding(_make_llm(), self._finding())

        assert result.status == "success"
        assert result.model == "test-model"

    async def test_timeout(self, monkeypatch: Any) -> None:
        """Test that a timeout produces an error result, not an exception."""
        client = FakeClient(exc=httpx.TimeoutException("timed out"))
        _patch_client(monkeypatch, client)

        result = await service.analyze_finding(_make_llm(timeout_seconds=5), self._finding())

        assert result.status == "error"
        assert result.error == "Request timed out after 5s"
        assert result.analysis == ""

    async def test_connect_error(self, monkeypatch: Any) -> None:
        """Test that a connection error names the exception type."""
        client = FakeClient(exc=httpx.ConnectError("boom"))
        _patch_client(monkeypatch, client)

        result = await service.analyze_finding(_make_llm(), self._finding())

        assert result.status == "error"
        assert result.error == "Could not reach endpoint: ConnectError"

    async def test_http_error_status(self, monkeypatch: Any) -> None:
        """Test that a non-200 status includes the status and a body snippet."""
        client = FakeClient(response=FakeResponse(401, text="invalid api key"))
        _patch_client(monkeypatch, client)

        result = await service.analyze_finding(_make_llm(api_key="sk-bad"), self._finding())

        assert result.status == "error"
        assert result.error.startswith("HTTP 401:")
        assert "invalid api key" in result.error

    async def test_invalid_json(self, monkeypatch: Any) -> None:
        """Test that invalid JSON is reported as a format error."""
        client = FakeClient(response=FakeResponse(200, json_error=True))
        _patch_client(monkeypatch, client)

        result = await service.analyze_finding(_make_llm(), self._finding())

        assert result.status == "error"
        assert "Unexpected response format" in result.error

    async def test_missing_choices(self, monkeypatch: Any) -> None:
        """Test that a body without choices is reported as a format error."""
        client = FakeClient(response=FakeResponse(200, {"error": "nope"}))
        _patch_client(monkeypatch, client)

        result = await service.analyze_finding(_make_llm(), self._finding())

        assert result.status == "error"
        assert "Unexpected response format" in result.error

    async def test_blank_content(self, monkeypatch: Any) -> None:
        """Test that blank content is treated as an error."""
        client = FakeClient(response=FakeResponse(200, {"choices": [{"message": {"content": "   "}}]}))
        _patch_client(monkeypatch, client)

        result = await service.analyze_finding(_make_llm(), self._finding())

        assert result.status == "error"
        assert result.error == "Endpoint returned empty content"

    async def test_no_api_key_omits_authorization(self, monkeypatch: Any) -> None:
        """Test that no Authorization header is sent without an api_key."""
        client = FakeClient(response=FakeResponse(200, OK_BODY))
        _patch_client(monkeypatch, client)

        await service.analyze_finding(_make_llm(api_key=""), self._finding())

        _, _, headers = client.calls[0]
        assert headers is not None
        assert "Authorization" not in headers

    async def test_max_tokens_included_when_set(self, monkeypatch: Any) -> None:
        """Test that max_tokens is sent when configured."""
        client = FakeClient(response=FakeResponse(200, OK_BODY))
        _patch_client(monkeypatch, client)

        await service.analyze_finding(_make_llm(max_tokens=512), self._finding())

        _, payload, _ = client.calls[0]
        assert payload is not None
        assert payload["max_tokens"] == 512

    async def test_disabled_raises(self) -> None:
        """Test that a disabled config raises before any request."""
        with pytest.raises(LLMNotConfiguredError):
            await service.analyze_finding(_make_llm(enabled=False), self._finding())


class TestAnalyzeFindings:
    """Tests for analyze_findings."""

    def _findings(self, count: int) -> list[dict[str, Any]]:
        return [
            {
                "function_name": f"fn{i}",
                "containing_function": "main",
                "entrypoint": "0x400000",
                "category": "memory",
                "severity": "high",
                "cwe": "CWE-120",
                "description": "",
                "safe_alternative": "",
                "usage_context": [],
                "containing_function_code": "",
            }
            for i in range(count)
        ]

    async def test_returns_one_result_per_finding_in_order(self, monkeypatch: Any) -> None:
        """Test that results match the input order, one per finding."""
        client = FakeClient(response=FakeResponse(200, OK_BODY))
        _patch_client(monkeypatch, client)

        results = await service.analyze_findings(_make_llm(), self._findings(4))

        assert len(results) == 4
        assert all(r.status == "success" for r in results)
        assert len(client.calls) == 4
        for i, (_, payload, _) in enumerate(client.calls):
            assert payload is not None
            assert f"fn{i}" in str(payload["messages"][1]["content"])

    async def test_empty_list_returns_empty(self, monkeypatch: Any) -> None:
        """Test that an empty input returns an empty result without any request."""
        client = FakeClient(response=FakeResponse(200, OK_BODY))
        _patch_client(monkeypatch, client)

        results = await service.analyze_findings(_make_llm(), [])

        assert results == []
        assert client.calls == []

    async def test_disabled_raises(self) -> None:
        """Test that a disabled config raises before any request is scheduled."""
        with pytest.raises(LLMNotConfiguredError):
            await service.analyze_findings(_make_llm(enabled=False), self._findings(1))

    async def test_failure_does_not_abort_batch(self, monkeypatch: Any) -> None:
        """Test that one failing finding yields an error result without aborting the batch."""

        class FlakyClient(FakeClient):
            """Client that fails the request for fn0 with a connection error."""

            async def post(self, url: str, json: dict[str, Any] | None = None,
                           headers: dict[str, str] | None = None) -> FakeResponse:
                self.calls.append((url, json, headers))
                if json is not None and "fn0" in str(json["messages"][1]["content"]):
                    raise httpx.ConnectError("boom")
                return FakeResponse(200, OK_BODY)

        client = FlakyClient()
        _patch_client(monkeypatch, client)

        results = await service.analyze_findings(_make_llm(), self._findings(3))

        assert [r.status for r in results] == ["error", "success", "success"]
        assert "ConnectError" in results[0].error

    async def test_concurrency_limited(self, monkeypatch: Any) -> None:
        """Test that in-flight requests never exceed max_concurrent."""

        class TimingClient(FakeClient):
            """Client that records the peak number of in-flight posts."""

            def __init__(self, response: FakeResponse | None = None,
                         exc: Exception | None = None) -> None:
                super().__init__(response=response, exc=exc)
                self.in_flight = 0
                self.max_in_flight = 0

            async def post(self, url: str, json: dict[str, Any] | None = None,
                           headers: dict[str, str] | None = None) -> FakeResponse:
                self.calls.append((url, json, headers))
                self.in_flight += 1
                self.max_in_flight = max(self.max_in_flight, self.in_flight)
                await asyncio.sleep(0.02)
                self.in_flight -= 1
                assert self._response is not None
                return self._response

        client = TimingClient(response=FakeResponse(200, OK_BODY))
        _patch_client(monkeypatch, client)

        results = await service.analyze_findings(_make_llm(max_concurrent=2), self._findings(6))

        assert len(results) == 6
        assert all(r.status == "success" for r in results)
        assert client.max_in_flight == 2
