from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from typing import Any

import httpx


class GroundwireError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, body: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class GroundwireClient:
    """Thin HTTP client for the Groundwire control plane.

    Your agent framework plans; this client registers the contract, starts a
    durable run, and lets the signal box hold gated tool calls.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        token: str | None = None,
        *,
        client: httpx.Client | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._token = token
        self._owns_client = client is None
        self._http = client or httpx.Client(base_url=self.base_url, timeout=timeout)

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def __enter__(self) -> GroundwireClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def login_password(
        self,
        token_url: str,
        username: str,
        password: str,
        *,
        client_id: str = "groundwire-dashboard",
    ) -> None:
        response = httpx.post(
            token_url,
            data={
                "client_id": client_id,
                "grant_type": "password",
                "username": username,
                "password": password,
            },
            timeout=30.0,
        )
        if response.status_code >= 400:
            raise GroundwireError(
                "OIDC password grant failed",
                status_code=response.status_code,
                body=_safe_body(response),
            )
        token = response.json().get("access_token")
        if not token:
            raise GroundwireError("OIDC response did not include an access token")
        self._token = str(token)

    def me(self) -> dict:
        return self._request("GET", "/v1/me")

    def register_agent(
        self,
        name: str,
        allowed_tools: Sequence[str],
        approval_policy: Mapping[str, Any],
    ) -> dict:
        return self._request(
            "POST",
            "/v1/agents",
            json={
                "name": name,
                "allowed_tools": list(allowed_tools),
                "approval_policy": dict(approval_policy),
            },
        )

    def list_agents(self) -> list[dict]:
        return self._request("GET", "/v1/agents")

    def start_run(self, agent_id: str, payload: Mapping[str, Any]) -> dict:
        return self._request(
            "POST",
            "/v1/runs",
            json={"agent_id": agent_id, "payload": dict(payload)},
        )

    def get_run(self, run_id: str) -> dict:
        return self._request("GET", f"/v1/runs/{run_id}")

    def wait_for_status(
        self,
        run_id: str,
        statuses: Sequence[str],
        *,
        timeout: float = 30.0,
        interval: float = 0.4,
    ) -> dict:
        import time

        wanted = set(statuses)
        deadline = time.monotonic() + timeout
        latest: dict | None = None
        while time.monotonic() < deadline:
            latest = self.get_run(run_id)
            if latest.get("status") in wanted:
                return latest
            time.sleep(interval)
        raise GroundwireError(
            f"run {run_id} did not reach {sorted(wanted)}; last status={latest and latest.get('status')}"
        )

    def approve(
        self,
        run_id: str,
        decision: str = "approve",
        edited_params: Mapping[str, Any] | None = None,
    ) -> dict:
        body: dict[str, Any] = {"decision": decision}
        if edited_params is not None:
            body["edited_params"] = dict(edited_params)
        return self._request("POST", f"/v1/runs/{run_id}/approvals", json=body)

    def graph(self, run_id: str) -> dict:
        return self._request("GET", f"/v1/runs/{run_id}/graph")

    def audit(self, **params: Any) -> Any:
        return self._request("GET", "/v1/audit", params={k: v for k, v in params.items() if v is not None})

    def metrics(self) -> dict:
        return self._request("GET", "/v1/metrics")

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        headers = dict(kwargs.pop("headers", {}) or {})
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        response = self._http.request(method, path, headers=headers, **kwargs)
        if response.status_code >= 400:
            raise GroundwireError(
                f"{method} {path} failed with {response.status_code}",
                status_code=response.status_code,
                body=_safe_body(response),
            )
        if not response.content:
            return None
        return response.json()


def client_from_env() -> GroundwireClient:
    base_url = os.environ.get("GROUNDWIRE_API_URL", "http://localhost:8000")
    token = os.environ.get("GROUNDWIRE_TOKEN")
    client = GroundwireClient(base_url, token=token)
    if token:
        return client
    username = os.environ.get("GROUNDWIRE_USERNAME")
    password = os.environ.get("GROUNDWIRE_PASSWORD")
    if username and password:
        client.login_password(
            os.environ.get(
                "GROUNDWIRE_OIDC_TOKEN_URL",
                "http://localhost:8081/realms/groundwire/protocol/openid-connect/token",
            ),
            username,
            password,
            client_id=os.environ.get("GROUNDWIRE_OIDC_CLIENT_ID", "groundwire-dashboard"),
        )
    return client


def _safe_body(response: httpx.Response) -> Any:
    try:
        return response.json()
    except Exception:
        return response.text
