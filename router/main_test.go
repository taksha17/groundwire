package main

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestRoutePrefersSmallModelForShortEmail(t *testing.T) {
	got := route(routeRequest{Task: "send_email", Prompt: "Notify ops of the outage"})
	if got.Model != "groundwire-small" {
		t.Fatalf("model=%s want groundwire-small", got.Model)
	}
	if !got.Routed {
		t.Fatal("expected routed")
	}
	if got.EstimatedCostUSD <= 0 {
		t.Fatalf("cost should be > 0, got %v", got.EstimatedCostUSD)
	}
}

func TestRouteDoesNotTreatPlannedAsHeavy(t *testing.T) {
	got := route(routeRequest{
		Task:   "send_email",
		Prompt: "Notify the recipient using the planned email",
	})
	if got.Model != "groundwire-small" {
		t.Fatalf("model=%s want groundwire-small", got.Model)
	}
}

func TestRoutePrefersLargeModelForReasoning(t *testing.T) {
	got := route(routeRequest{
		Task:   "write_brief",
		Prompt: "Analyze the incident and reason about which on-call rotation should be paged.",
	})
	if got.Model != "groundwire-large" {
		t.Fatalf("model=%s want groundwire-large", got.Model)
	}
}

func TestHTTPRouteEndpoint(t *testing.T) {
	body, _ := json.Marshal(routeRequest{Task: "send_email", Prompt: "hi"})
	req := httptest.NewRequest(http.MethodPost, "/v1/route", bytes.NewReader(body))
	rec := httptest.NewRecorder()
	handleRoute(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("status=%d", rec.Code)
	}
	var got routeResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatal(err)
	}
	if got.Model != "groundwire-small" {
		t.Fatalf("model=%s", got.Model)
	}
}
