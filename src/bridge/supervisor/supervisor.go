package supervisor

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"sync"
	"time"

	"assistant/src/bridge/protocol"
	"assistant/src/tools"
)

var (
	ErrSupervisorNotStarted = errors.New("supervisor is not started")
	ErrReadyHandshakeTimedOut = errors.New("timed out waiting for ready handshake from python daemon")
	ErrTurnNotFound         = errors.New("turn handle not found")
)

// ToolExecutor executes native tools on behalf of the supervisor.
type ToolExecutor interface {
	ExecuteWithContext(ctx context.Context, sessionID, turnID, callID, toolName, argsJSON string) (*tools.ToolResult, error)
}

// AutonomousEventHandler receives proactive background events from Python.
type AutonomousEventHandler func(evt *protocol.AutonomousEventPayload)

// Config holds options for the Go supervisor.
type Config struct {
	ProcessConfig          ProcessConfig
	ToolExecutor           ToolExecutor
	AutonomousEventHandler AutonomousEventHandler
	ReadyTimeout           time.Duration
	GracePeriod            time.Duration
	StderrLogger           *log.Logger
}

// Supervisor coordinates the Python resident daemon and multiplexes IPC frames.
type Supervisor struct {
	cfg         Config
	processMgr  *ProcessManager
	multiplexer *Multiplexer
	activeTurns map[string]*TurnHandle
	turnsMu     sync.RWMutex
	readyCh     chan struct{}
	readyOnce   sync.Once
	started     bool
	startMu     sync.Mutex
}

// NewSupervisor constructs a Supervisor instance with the specified configuration.
func NewSupervisor(cfg Config) *Supervisor {
	if cfg.ReadyTimeout == 0 {
		cfg.ReadyTimeout = 10 * time.Second
	}
	if cfg.GracePeriod == 0 {
		cfg.GracePeriod = 3 * time.Second
	}
	return &Supervisor{
		cfg:         cfg,
		processMgr:  NewProcessManager(cfg.ProcessConfig),
		activeTurns: make(map[string]*TurnHandle),
		readyCh:     make(chan struct{}),
	}
}

// Start launches the daemon process, attaches streams, and awaits the ready handshake.
func (s *Supervisor) Start(ctx context.Context) error {
	s.startMu.Lock()
	defer s.startMu.Unlock()

	if s.started {
		return nil
	}

	if err := s.processMgr.Start(ctx); err != nil {
		return fmt.Errorf("supervisor failed to start process: %w", err)
	}

	s.pipeStderr(s.processMgr.Stderr())

	s.multiplexer = NewMultiplexer(s.processMgr.Stdout(), s.processMgr.Stdin())
	s.registerFrameHandlers()

	s.multiplexer.StartReadLoop(ctx, s.handleDisconnect)

	select {
	case <-s.readyCh:
		s.started = true
		return nil
	case <-time.After(s.cfg.ReadyTimeout):
		_ = s.processMgr.Stop(s.cfg.GracePeriod)
		return ErrReadyHandshakeTimedOut
	case <-ctx.Done():
		_ = s.processMgr.Stop(s.cfg.GracePeriod)
		return ctx.Err()
	}
}

// Stop cleanly shuts down the child daemon and closes all active turn streams.
func (s *Supervisor) Stop() error {
	s.startMu.Lock()
	defer s.startMu.Unlock()

	if !s.started {
		return nil
	}

	s.failAllActiveTurns(errors.New("supervisor stopped"))

	if s.multiplexer != nil {
		s.multiplexer.Close()
	}

	err := s.processMgr.Stop(s.cfg.GracePeriod)
	s.started = false
	return err
}

// StartTurn initiates a reasoning turn in the Python cognitive daemon.
func (s *Supervisor) StartTurn(ctx context.Context, sessionID, turnID string, payload *protocol.StartTurnPayload) (*TurnHandle, error) {
	if !s.IsRunning() {
		return nil, ErrSupervisorNotStarted
	}

	handle := NewTurnHandle(sessionID, turnID)
	s.registerTurn(turnID, handle)

	frame, err := protocol.NewMasterFrame(sessionID, turnID, protocol.FrameTypeStartTurn, payload)
	if err != nil {
		s.removeTurn(turnID)
		return nil, fmt.Errorf("failed to create start_turn frame: %w", err)
	}

	if err := s.multiplexer.SendFrame(frame); err != nil {
		s.removeTurn(turnID)
		return nil, fmt.Errorf("failed to send start_turn frame: %w", err)
	}

	go s.watchTurnCancellation(ctx, sessionID, turnID)

	return handle, nil
}

// IsRunning reports whether the supervised daemon is running and ready.
func (s *Supervisor) IsRunning() bool {
	s.startMu.Lock()
	defer s.startMu.Unlock()
	return s.started && s.processMgr.IsRunning()
}

func (s *Supervisor) registerFrameHandlers() {
	s.multiplexer.On(protocol.FrameTypeReady, s.handleReadyFrame)
	s.multiplexer.On(protocol.FrameTypeToken, s.handleTokenFrame)
	s.multiplexer.On(protocol.FrameTypeAgentThought, s.handleThoughtFrame)
	s.multiplexer.On(protocol.FrameTypeToolCall, s.handleToolCallFrame)
	s.multiplexer.On(protocol.FrameTypeTurnComplete, s.handleTurnCompleteFrame)
	s.multiplexer.On(protocol.FrameTypeAutonomousEvent, s.handleAutonomousEventFrame)
	s.multiplexer.On(protocol.FrameTypeError, s.handleErrorFrame)
}

func (s *Supervisor) handleReadyFrame(_ *protocol.MasterFrame) {
	s.readyOnce.Do(func() {
		close(s.readyCh)
	})
}

func (s *Supervisor) handleTokenFrame(frame *protocol.MasterFrame) {
	var payload protocol.TokenPayload
	if err := frame.UnmarshalPayload(&payload); err != nil {
		return
	}
	if handle := s.getTurn(frame.TurnID); handle != nil {
		handle.PushToken(payload.Delta)
	}
}

func (s *Supervisor) handleThoughtFrame(frame *protocol.MasterFrame) {
	var payload protocol.AgentThoughtPayload
	if err := frame.UnmarshalPayload(&payload); err != nil {
		return
	}
	if handle := s.getTurn(frame.TurnID); handle != nil {
		handle.PushThought(payload.Thought)
	}
}

func (s *Supervisor) handleToolCallFrame(frame *protocol.MasterFrame) {
	var payload protocol.ToolCallPayload
	if err := frame.UnmarshalPayload(&payload); err != nil {
		return
	}

	go s.executeToolCallConcurrently(frame.SessionID, frame.TurnID, payload)
}

func (s *Supervisor) executeToolCallConcurrently(sessionID, turnID string, call protocol.ToolCallPayload) {
	if s.cfg.ToolExecutor == nil {
		s.sendToolResult(sessionID, turnID, protocol.ToolResultPayload{
			CallID:   call.CallID,
			ExitCode: 1,
			Output:   "error: tool executor not configured in supervisor",
			IsError:  true,
		})
		return
	}

	argsBytes, _ := json.Marshal(call.Arguments)
	argsJSON := string(argsBytes)

	startTime := time.Now()
	res, err := s.cfg.ToolExecutor.ExecuteWithContext(
		context.Background(),
		sessionID,
		turnID,
		call.CallID,
		call.ToolName,
		argsJSON,
	)
	duration := time.Since(startTime).Milliseconds()

	resultPayload := protocol.ToolResultPayload{
		CallID:     call.CallID,
		DurationMs: duration,
	}

	if err != nil {
		resultPayload.IsError = true
		resultPayload.ExitCode = 1
		resultPayload.Output = err.Error()
	} else if res != nil {
		resultPayload.ExitCode = res.ExitCode
		resultPayload.Output = res.Stdout
		if res.Stderr != "" && res.Stdout == "" {
			resultPayload.Output = res.Stderr
		}
		resultPayload.ArtifactPath = res.ArtifactPath
		resultPayload.IsError = res.IsError
	}

	s.sendToolResult(sessionID, turnID, resultPayload)
}

func (s *Supervisor) sendToolResult(sessionID, turnID string, res protocol.ToolResultPayload) {
	frame, err := protocol.NewMasterFrame(sessionID, turnID, protocol.FrameTypeToolResult, res)
	if err != nil {
		return
	}
	_ = s.multiplexer.SendFrame(frame)
}

func (s *Supervisor) handleTurnCompleteFrame(frame *protocol.MasterFrame) {
	var payload protocol.TurnCompletePayload
	if err := frame.UnmarshalPayload(&payload); err != nil {
		return
	}
	if handle := s.getTurn(frame.TurnID); handle != nil {
		handle.Finish(&payload)
		s.removeTurn(frame.TurnID)
	}
}

func (s *Supervisor) handleErrorFrame(frame *protocol.MasterFrame) {
	var payload protocol.ErrorPayload
	if err := frame.UnmarshalPayload(&payload); err != nil {
		return
	}
	if handle := s.getTurn(frame.TurnID); handle != nil {
		handle.Fail(fmt.Errorf("[%s] %s", payload.Code, payload.Message))
		s.removeTurn(frame.TurnID)
	}
}

func (s *Supervisor) handleAutonomousEventFrame(frame *protocol.MasterFrame) {
	if s.cfg.AutonomousEventHandler == nil {
		return
	}
	var payload protocol.AutonomousEventPayload
	if err := frame.UnmarshalPayload(&payload); err == nil {
		s.cfg.AutonomousEventHandler(&payload)
	}
}

func (s *Supervisor) watchTurnCancellation(ctx context.Context, sessionID, turnID string) {
	<-ctx.Done()
	if handle := s.getTurn(turnID); handle != nil {
		cancelPayload := protocol.CancelTurnPayload{Reason: "context_cancelled"}
		frame, err := protocol.NewMasterFrame(sessionID, turnID, protocol.FrameTypeCancelTurn, cancelPayload)
		if err == nil {
			_ = s.multiplexer.SendFrame(frame)
		}
		handle.Fail(ctx.Err())
		s.removeTurn(turnID)
	}
}

func (s *Supervisor) handleDisconnect(err error) {
	errMsg := "bridge disconnected"
	if err != nil {
		errMsg = fmt.Sprintf("bridge disconnected: %v", err)
	}
	s.failAllActiveTurns(errors.New(errMsg))
}

func (s *Supervisor) pipeStderr(r io.Reader) {
	if r == nil {
		return
	}
	go func() {
		scanner := bufio.NewScanner(r)
		for scanner.Scan() {
			line := scanner.Text()
			if s.cfg.StderrLogger != nil {
				s.cfg.StderrLogger.Println(line)
			}
		}
	}()
}

func (s *Supervisor) registerTurn(turnID string, handle *TurnHandle) {
	s.turnsMu.Lock()
	defer s.turnsMu.Unlock()
	s.activeTurns[turnID] = handle
}

func (s *Supervisor) getTurn(turnID string) *TurnHandle {
	s.turnsMu.RLock()
	defer s.turnsMu.RUnlock()
	return s.activeTurns[turnID]
}

func (s *Supervisor) removeTurn(turnID string) {
	s.turnsMu.Lock()
	defer s.turnsMu.Unlock()
	delete(s.activeTurns, turnID)
}

func (s *Supervisor) failAllActiveTurns(err error) {
	s.turnsMu.Lock()
	defer s.turnsMu.Unlock()
	for id, handle := range s.activeTurns {
		handle.Fail(err)
		delete(s.activeTurns, id)
	}
}
