package tools_test

import (
	"context"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"assistant/src/tools/tools/net"
)

func TestNetFetchTool(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("X-Custom-Header") != "CustomValue" {
			http.Error(w, "missing header", http.StatusBadRequest)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"ok","message":"pong"}`))
	}))
	defer ts.Close()

	tool := net.NewNetFetchTool()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	args := fmt.Sprintf(`{"url":"%s","method":"GET","headers":{"X-Custom-Header":"CustomValue"}}`, ts.URL)
	res, err := tool.Execute(ctx, args)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if res.IsError || res.ExitCode != 0 {
		t.Fatalf("net_fetch failed: %s", res.Stderr)
	}

	if !strings.Contains(res.Stdout, "HTTP 200") || !strings.Contains(res.Stdout, `"status":"ok"`) {
		t.Fatalf("unexpected net_fetch output: %s", res.Stdout)
	}
}

func TestNetFetchToolNotFound(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Error(w, "not found", http.StatusNotFound)
	}))
	defer ts.Close()

	tool := net.NewNetFetchTool()
	ctx := context.Background()

	args := fmt.Sprintf(`{"url":"%s/missing"}`, ts.URL)
	res, err := tool.Execute(ctx, args)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if !res.IsError || res.ExitCode != 1 {
		t.Fatalf("expected 404 to be marked as error")
	}
	if !strings.Contains(res.Stdout, "HTTP 404") {
		t.Fatalf("expected HTTP 404 status in output: %s", res.Stdout)
	}
}
