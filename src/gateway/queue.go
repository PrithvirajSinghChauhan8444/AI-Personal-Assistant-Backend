package gateway

import (
	"context"
	"fmt"
	"sync"
	"time"
)

// TurnPriority defines scheduling precedence for turn execution.
type TurnPriority int

const (
	// PriorityInteractive is reserved for human user turns (CLI, Web, Telegram).
	PriorityInteractive TurnPriority = 1
	// PriorityAutonomous is for background daemons (Gmail watcher, cron).
	PriorityAutonomous TurnPriority = 2
)

// QueuedTurn represents an inbound turn request awaiting or undergoing execution.
type QueuedTurn struct {
	ID         string
	Priority   TurnPriority
	Request    InboundTurnRequest
	EventCh    chan OutboundEvent
	DoneCh     chan struct{}
	EnqueuedAt time.Time
	Ctx        context.Context
}

// AutonomousConsumerFunc handles streaming events for autonomous turns in client adapters.
type AutonomousConsumerFunc func(req InboundTurnRequest, eventCh <-chan OutboundEvent)

// PriorityTurnQueue provides serialized, priority-ordered turn execution to prevent
// race conditions, message loss, and visual interleaving across concurrent turns.
type PriorityTurnQueue struct {
	mu           sync.Mutex
	cond         *sync.Cond
	interactive  []*QueuedTurn
	autonomous   []*QueuedTurn
	activeTurn   *QueuedTurn
	running      bool
	closed       bool
	turnExecutor func(ctx context.Context, req InboundTurnRequest, clientEventCh chan OutboundEvent)

	consumerMu sync.RWMutex
	consumers  map[string]AutonomousConsumerFunc
}

// NewPriorityTurnQueue initializes a PriorityTurnQueue with a downstream turn executor.
func NewPriorityTurnQueue(executor func(ctx context.Context, req InboundTurnRequest, clientEventCh chan OutboundEvent)) *PriorityTurnQueue {
	pq := &PriorityTurnQueue{
		turnExecutor: executor,
		consumers:    make(map[string]AutonomousConsumerFunc),
	}
	pq.cond = sync.NewCond(&pq.mu)
	return pq
}

// Start spawns the background queue worker.
func (pq *PriorityTurnQueue) Start(ctx context.Context) {
	pq.mu.Lock()
	if pq.running {
		pq.mu.Unlock()
		return
	}
	pq.running = true
	pq.closed = false
	pq.mu.Unlock()

	go pq.workerLoop(ctx)
}

// Stop cleanly terminates the queue worker and cancels pending items.
func (pq *PriorityTurnQueue) Stop() {
	pq.mu.Lock()
	if !pq.running || pq.closed {
		pq.mu.Unlock()
		return
	}
	pq.closed = true
	pq.running = false
	pq.cond.Broadcast()
	pq.mu.Unlock()
}

// Enqueue inserts a turn request into the queue according to priority.
func (pq *PriorityTurnQueue) Enqueue(ctx context.Context, req InboundTurnRequest, priority TurnPriority) (<-chan OutboundEvent, error) {
	pq.mu.Lock()
	defer pq.mu.Unlock()

	if pq.closed {
		return nil, fmt.Errorf("turn queue is closed")
	}

	eventCh := make(chan OutboundEvent, 64)
	doneCh := make(chan struct{})

	qt := &QueuedTurn{
		ID:         req.TraceID,
		Priority:   priority,
		Request:    req,
		EventCh:    eventCh,
		DoneCh:     doneCh,
		EnqueuedAt: time.Now().UTC(),
		Ctx:        ctx,
	}

	if priority == PriorityInteractive {
		pq.interactive = append(pq.interactive, qt)
	} else {
		pq.autonomous = append(pq.autonomous, qt)
	}

	pq.cond.Signal()
	return eventCh, nil
}

// RegisterAutonomousConsumer registers a callback to receive autonomous turns for a session.
func (pq *PriorityTurnQueue) RegisterAutonomousConsumer(sessionID string, consumer AutonomousConsumerFunc) {
	pq.consumerMu.Lock()
	defer pq.consumerMu.Unlock()
	pq.consumers[sessionID] = consumer
}

// UnregisterAutonomousConsumer removes the registered autonomous consumer for a session.
func (pq *PriorityTurnQueue) UnregisterAutonomousConsumer(sessionID string) {
	pq.consumerMu.Lock()
	defer pq.consumerMu.Unlock()
	delete(pq.consumers, sessionID)
}

// IsBusy reports whether a turn is currently in-flight.
func (pq *PriorityTurnQueue) IsBusy() bool {
	pq.mu.Lock()
	defer pq.mu.Unlock()
	return pq.activeTurn != nil
}

// PendingCount returns the number of waiting interactive and autonomous turns.
func (pq *PriorityTurnQueue) PendingCount() (interactive int, autonomous int) {
	pq.mu.Lock()
	defer pq.mu.Unlock()
	return len(pq.interactive), len(pq.autonomous)
}

func (pq *PriorityTurnQueue) workerLoop(ctx context.Context) {
	for {
		pq.mu.Lock()
		for len(pq.interactive) == 0 && len(pq.autonomous) == 0 && !pq.closed && ctx.Err() == nil {
			pq.cond.Wait()
		}

		if pq.closed || ctx.Err() != nil {
			pq.mu.Unlock()
			return
		}

		var next *QueuedTurn
		if len(pq.interactive) > 0 {
			next = pq.interactive[0]
			pq.interactive = pq.interactive[1:]
		} else if len(pq.autonomous) > 0 {
			next = pq.autonomous[0]
			pq.autonomous = pq.autonomous[1:]
		}

		pq.activeTurn = next
		pq.mu.Unlock()

		if next == nil {
			continue
		}

		pq.executeTurn(next)

		pq.mu.Lock()
		pq.activeTurn = nil
		close(next.DoneCh)
		pq.mu.Unlock()
	}
}

func (pq *PriorityTurnQueue) executeTurn(turn *QueuedTurn) {
	var consumerChan chan OutboundEvent
	if turn.Priority == PriorityAutonomous {
		pq.consumerMu.RLock()
		var consumer AutonomousConsumerFunc
		if c, ok := pq.consumers[turn.Request.SessionID]; ok {
			consumer = c
		} else if c, ok := pq.consumers["*"]; ok {
			consumer = c
		} else {
			// Single-session default
			for _, c := range pq.consumers {
				consumer = c
				break
			}
		}
		pq.consumerMu.RUnlock()

		if consumer != nil {
			consumerChan = make(chan OutboundEvent, 64)
			go consumer(turn.Request, consumerChan)
		}
	}

	execCh := make(chan OutboundEvent, 64)
	go func() {
		defer close(execCh)
		pq.turnExecutor(turn.Ctx, turn.Request, execCh)
	}()

	for ev := range execCh {
		turn.EventCh <- ev
		if consumerChan != nil {
			consumerChan <- ev
		}
	}
	close(turn.EventCh)
	if consumerChan != nil {
		close(consumerChan)
	}
}
