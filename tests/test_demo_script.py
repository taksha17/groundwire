from groundwire.demo import demo_requests


def test_demo_request_sequence_covers_crash_and_approve():
    steps = demo_requests(base_url="http://localhost:8000")
    methods_paths = [(s.method, s.path) for s in steps]
    assert ("POST", "/v1/agents") in methods_paths
    assert ("POST", "/v1/runs") in methods_paths
    assert any(p.startswith("/v1/runs/") and m == "GET" for m, p in methods_paths)
    assert any(p.endswith("/approvals") for _, p in methods_paths)
