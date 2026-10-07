from dataclasses import dataclass


@dataclass(frozen=True)
class DemoRequest:
    method: str
    path: str


def demo_requests(base_url: str = "http://localhost:8000") -> list[DemoRequest]:
    """Ordered HTTP calls for the v0.1 crash-and-approve demo."""
    _ = base_url
    return [
        DemoRequest("POST", "/v1/agents"),
        DemoRequest("POST", "/v1/runs"),
        DemoRequest("GET", "/v1/runs/{id}"),
        DemoRequest("POST", "/v1/runs/{id}/approvals"),
    ]
