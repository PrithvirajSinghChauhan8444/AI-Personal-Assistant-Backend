package sys

import (
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"regexp"
	"strings"
	"sync"
	"time"
)

// RiskTier represents the security level of a terminal command.
type RiskTier string

const (
	RiskTierSafe        RiskTier = "LOW"
	RiskTierStandard    RiskTier = "MEDIUM"
	RiskTierDestructive RiskTier = "HIGH"
)

// RiskAssessment holds the safety evaluation result for a shell command.
type RiskAssessment struct {
	Tier            RiskTier `json:"tier"`
	IsDestructive   bool     `json:"is_destructive"`
	Reason          string   `json:"reason,omitempty"`
	ConfirmationID  string   `json:"confirmation_id,omitempty"`
}

// confirmationStore tracks pending confirmation IDs with expiration.
type confirmationStore struct {
	mu     sync.RWMutex
	tokens map[string]time.Time
}

var activeConfirmations = &confirmationStore{
	tokens: make(map[string]time.Time),
}

var destructivePatterns = []*regexp.Regexp{
	regexp.MustCompile(`\brm\s+-[a-zA-Z]*r[a-zA-Z]*f?\b`),       // rm -r, rm -rf, rm -fr
	regexp.MustCompile(`\brm\s+--recursive\b`),                 // rm --recursive
	regexp.MustCompile(`\bunlink\s+`),                          // unlink
	regexp.MustCompile(`\bmkfs(\.[a-z0-9]+)?\b`),               // mkfs, mkfs.ext4
	regexp.MustCompile(`\bdd\s+if=`),                           // dd writes
	regexp.MustCompile(`\bfdisk\b`),                            // disk partition
	regexp.MustCompile(`\bgit\s+reset\s+--hard\b`),             // git reset --hard
	regexp.MustCompile(`\bgit\s+clean\s+-[a-zA-Z]*f\b`),        // git clean -f
	regexp.MustCompile(`\bgit\s+push\s+.*--force\b`),           // git push --force
	regexp.MustCompile(`\b(sudo|su)\b`),                        // privilege escalation
	regexp.MustCompile(`\bchmod\s+-[a-zA-Z]*R\s+777\s+/`),      // recursive root chmod
}

// EvaluateCommandSafety classifies the risk tier of a shell command.
func EvaluateCommandSafety(command string) RiskAssessment {
	trimmed := strings.TrimSpace(command)
	if trimmed == "" {
		return RiskAssessment{Tier: RiskTierSafe, IsDestructive: false}
	}

	for _, pattern := range destructivePatterns {
		if pattern.MatchString(trimmed) {
			token := generateConfirmationToken()
			activeConfirmations.store(token, 5*time.Minute)
			return RiskAssessment{
				Tier:           RiskTierDestructive,
				IsDestructive:  true,
				Reason:         fmt.Sprintf("Command matches dangerous/destructive pattern: %s", pattern.String()),
				ConfirmationID: token,
			}
		}
	}

	return RiskAssessment{
		Tier:          RiskTierStandard,
		IsDestructive: false,
	}
}

// ValidateConfirmation checks and consumes a confirmation token.
func ValidateConfirmation(token string) bool {
	if token == "" {
		return false
	}
	return activeConfirmations.consume(token)
}

func (s *confirmationStore) store(token string, ttl time.Duration) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.tokens[token] = time.Now().Add(ttl)
}

func (s *confirmationStore) consume(token string) bool {
	s.mu.Lock()
	defer s.mu.Unlock()

	expiry, exists := s.tokens[token]
	if !exists {
		return false
	}

	delete(s.tokens, token)
	return time.Now().Before(expiry)
}

func generateConfirmationToken() string {
	bytes := make([]byte, 8)
	_, _ = rand.Read(bytes)
	return "conf_" + hex.EncodeToString(bytes)
}
