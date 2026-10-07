package main

import (
	"encoding/json"
	"log"
	"net/http"
	"os"
	"regexp"
	"strings"
	"unicode/utf8"
)

type routeRequest struct {
	Task    string            `json:"task"`
	Prompt  string            `json:"prompt"`
	Profile map[string]string `json:"profile"`
}

type routeResponse struct {
	Model            string  `json:"model"`
	Provider         string  `json:"provider"`
	Reason           string  `json:"reason"`
	EstimatedCostUSD float64 `json:"estimated_cost_usd"`
	InputTokens      int     `json:"input_tokens"`
	OutputTokens     int     `json:"output_tokens"`
	Routed           bool    `json:"routed"`
}

var heavy = []string{"analyze", "reason", "plan", "summarize", "rag", "research", "write a long"}

func estimateTokens(prompt string) int {
	n := utf8.RuneCountInString(prompt)
	if n < 1 {
		return 32
	}
	tokens := n / 4
	if tokens < 32 {
		return 32
	}
	return tokens
}

func route(req routeRequest) routeResponse {
	blob := strings.ToLower(req.Task + " " + req.Prompt)
	if req.Profile != nil {
		blob += " " + strings.ToLower(req.Profile["complexity"])
	}
	tokens := estimateTokens(req.Prompt)
	large := tokens > 400 || hasHeavy(blob)
	if req.Profile["complexity"] == "high" {
		large = true
	}
	if req.Profile["complexity"] == "low" {
		large = false
	}

	outTokens := tokens / 2
	if outTokens > 200 {
		outTokens = 200
	}
	if large {
		cost := (float64(tokens)*2.50 + float64(outTokens)*10.0) / 1_000_000
		return routeResponse{
			Model:            "groundwire-large",
			Provider:         "groundwire",
			Reason:           "long or reasoning-shaped prompt; send it to the larger model",
			EstimatedCostUSD: round6(cost),
			InputTokens:      tokens,
			OutputTokens:     outTokens,
			Routed:           true,
		}
	}
	cost := (float64(tokens)*0.15 + float64(outTokens)*0.60) / 1_000_000
	return routeResponse{
		Model:            "groundwire-small",
		Provider:         "groundwire",
		Reason:           "short deterministic tool call; keep it on the small model",
		EstimatedCostUSD: round6(cost),
		InputTokens:      tokens,
		OutputTokens:     outTokens,
		Routed:           true,
	}
}

func hasHeavy(blob string) bool {
	for _, word := range heavy {
		re := regexp.MustCompile(`\b` + regexp.QuoteMeta(word) + `\b`)
		if re.MatchString(blob) {
			return true
		}
	}
	return false
}

func round6(v float64) float64 {
	return float64(int(v*1_000_000+0.5)) / 1_000_000
}

func handleRoute(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req routeRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "invalid json", http.StatusBadRequest)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(route(req))
}

func handleHealth(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	_, _ = w.Write([]byte(`{"status":"ok"}`))
}

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", handleHealth)
	mux.HandleFunc("POST /v1/route", handleRoute)
	addr := os.Getenv("ROUTER_ADDR")
	if addr == "" {
		addr = ":8090"
	}
	log.Printf("groundwire router listening on %s", addr)
	log.Fatal(http.ListenAndServe(addr, mux))
}
