package telegram

import (
	"fmt"
	"sync"

	"github.com/google/uuid"
)

// SessionManager manages per-chat sessions, HITL pending states, and authorization whitelisting.
type SessionManager struct {
	mu           sync.RWMutex
	allowedUsers map[int64]bool
	sessions     map[int64]string
	pendingHITL  map[int64]string
}

// NewSessionManager initializes a thread-safe SessionManager.
func NewSessionManager(allowedIDs []int64) *SessionManager {
	whitelist := make(map[int64]bool, len(allowedIDs))
	for _, id := range allowedIDs {
		whitelist[id] = true
	}
	return &SessionManager{
		allowedUsers: whitelist,
		sessions:     make(map[int64]string),
		pendingHITL:  make(map[int64]string),
	}
}

// IsAuthorized verifies if the user is in the configured authorization whitelist.
// If the whitelist is completely empty, all users are denied for security.
func (sm *SessionManager) IsAuthorized(userID int64) bool {
	sm.mu.RLock()
	defer sm.mu.RUnlock()

	if len(sm.allowedUsers) == 0 {
		return false
	}
	return sm.allowedUsers[userID]
}

// GetOrCreateSession retrieves the active session ID for a chat, generating a deterministic one if missing.
func (sm *SessionManager) GetOrCreateSession(chatID int64) string {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	sessID, exists := sm.sessions[chatID]
	if !exists || sessID == "" {
		sessID = fmt.Sprintf("tg_chat_%d", chatID)
		sm.sessions[chatID] = sessID
	}
	return sessID
}

// ResetSession generates and binds a fresh session ID for the given chat ID.
func (sm *SessionManager) ResetSession(chatID int64) string {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	newSessID := fmt.Sprintf("tg_chat_%d_%s", chatID, uuid.NewString()[:8])
	sm.sessions[chatID] = newSessID
	delete(sm.pendingHITL, chatID)
	return newSessID
}

// SetPendingHITL binds an in-flight HITL request ID to a chat ID.
func (sm *SessionManager) SetPendingHITL(chatID int64, requestID string) {
	sm.mu.Lock()
	defer sm.mu.Unlock()
	sm.pendingHITL[chatID] = requestID
}

// GetPendingHITL returns the in-flight HITL request ID for a chat ID, if one exists.
func (sm *SessionManager) GetPendingHITL(chatID int64) (string, bool) {
	sm.mu.RLock()
	defer sm.mu.RUnlock()
	reqID, ok := sm.pendingHITL[chatID]
	return reqID, ok
}

// ClearPendingHITL removes the pending HITL state for a chat.
func (sm *SessionManager) ClearPendingHITL(chatID int64) {
	sm.mu.Lock()
	defer sm.mu.Unlock()
	delete(sm.pendingHITL, chatID)
}
