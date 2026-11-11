package bridge_test

import (
	"context"
	"errors"
	"testing"
	"time"

	"assistant/src/bridge/protocol"
	"assistant/src/bridge/supervisor"
)

func TestTurnHandleStreamingAndFinish(t *testing.T) {
	t.Parallel()

	handle := supervisor.NewTurnHandle("sess_100", "turn_200")
	if handle.SessionID() != "sess_100" {
		t.Errorf("expected session_id sess_100, got %s", handle.SessionID())
	}
	if handle.TurnID() != "turn_200" {
		t.Errorf("expected turn_id turn_200, got %s", handle.TurnID())
	}

	handle.PushThought("Considering solution")
	handle.PushToken("Result:")
	handle.PushToken(" 42")

	handle.Finish(&protocol.TurnCompletePayload{
		Status: "success",
		Usage: protocol.TokenUsage{
			PromptTokens:     10,
			CompletionTokens: 5,
			TotalTokens:      15,
		},
	})

	// Read thought
	select {
	case thought := <-handle.Thoughts():
		if thought != "Considering solution" {
			t.Errorf("unexpected thought: %s", thought)
		}
	default:
		t.Fatal("expected thought to be available")
	}

	// Read tokens
	var tokens string
	for tok := range handle.Tokens() {
		tokens += tok
	}
	if tokens != "Result: 42" {
		t.Errorf("expected 'Result: 42', got %q", tokens)
	}

	// Read completion
	select {
	case comp := <-handle.Complete():
		if comp == nil || comp.Status != "success" {
			t.Errorf("expected success completion, got %v", comp)
		}
		if comp.Usage.TotalTokens != 15 {
			t.Errorf("expected 15 total tokens, got %d", comp.Usage.TotalTokens)
		}
	default:
		t.Fatal("expected completion payload")
	}
}

func TestTurnHandleFail(t *testing.T) {
	t.Parallel()

	handle := supervisor.NewTurnHandle("sess_err", "turn_err")
	expectedErr := errors.New("simulated network failure")

	handle.Fail(expectedErr)

	select {
	case err := <-handle.Errors():
		if err == nil || err.Error() != expectedErr.Error() {
			t.Fatalf("expected error %v, got %v", expectedErr, err)
		}
	case <-time.After(time.Second):
		t.Fatal("timed out waiting for error")
	}

	// Channels must be closed
	_, ok := <-handle.Tokens()
	if ok {
		t.Fatal("expected tokens channel to be closed")
	}
}

func TestSupervisorNotStartedError(t *testing.T) {
	t.Parallel()

	sup := supervisor.NewSupervisor(supervisor.Config{})
	_, err := sup.StartTurn(context.Background(), "s", "t", &protocol.StartTurnPayload{})
	if err != supervisor.ErrSupervisorNotStarted {
		t.Fatalf("expected ErrSupervisorNotStarted, got %v", err)
	}
}
