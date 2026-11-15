package gmail

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"sync"

	"assistant/src/tools/tools/workspace"
)

// ManagerConfig holds runtime options for WatcherManager.
type ManagerConfig struct {
	ConfigDir    string
	Gateway      TurnDispatcher
	GoogleClient *workspace.GoogleClient
	WatcherCfg   WatcherConfig
}

// WatcherManager coordinates background email watchers across all configured Google accounts.
type WatcherManager struct {
	mu         sync.RWMutex
	cfg        ManagerConfig
	classifier *EmailClassifier
	watchers   map[string]*AccountWatcher
	running    bool
	sessionID  string
}

// NewWatcherManager initializes a WatcherManager with system dependencies.
func NewWatcherManager(cfg ManagerConfig) *WatcherManager {
	if cfg.ConfigDir == "" {
		cfg.ConfigDir = "config"
	}
	return &WatcherManager{
		cfg:        cfg,
		classifier: NewEmailClassifier(nil),
		watchers:   make(map[string]*AccountWatcher),
	}
}

// SetSessionID sets the active session ID across all account watchers.
func (m *WatcherManager) SetSessionID(sessionID string) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.sessionID = sessionID
	for _, w := range m.watchers {
		w.SetSessionID(sessionID)
	}
}

// GetSessionID retrieves the currently bound active session ID.
func (m *WatcherManager) GetSessionID() string {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.sessionID
}

// Start discovers configured accounts and starts watchers in background goroutines.
func (m *WatcherManager) Start(ctx context.Context) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	if m.running {
		return nil
	}

	accounts := m.discoverAccounts(ctx)
	if len(accounts) == 0 {
		return nil
	}

	// Register all discovered user emails to ensure accurate self-mail classification
	for _, acc := range accounts {
		if acc.Email != "" {
			m.classifier.RegisterEmail(acc.Email)
		}
	}

	fetcher := NewGoogleMailFetcher(m.cfg.GoogleClient)

	for _, acc := range accounts {
		deps := Dependencies{
			Tokens:     m.cfg.GoogleClient,
			Fetcher:    fetcher,
			Classifier: m.classifier,
			Gateway:    m.cfg.Gateway,
		}
		watcher := NewAccountWatcher(acc, m.cfg.WatcherCfg, deps)
		if m.sessionID != "" {
			watcher.SetSessionID(m.sessionID)
		}
		if err := watcher.Start(ctx); err == nil {
			m.watchers[acc.Alias] = watcher
		}
	}

	m.running = true
	return nil
}

// Stop cleanly terminates all running account watchers.
func (m *WatcherManager) Stop() error {
	m.mu.Lock()
	defer m.mu.Unlock()

	var firstErr error
	for _, watcher := range m.watchers {
		if err := watcher.Stop(); err != nil && firstErr == nil {
			firstErr = err
		}
	}

	m.watchers = make(map[string]*AccountWatcher)
	m.running = false
	return firstErr
}

// Status returns a snapshot of each account watcher's operational status.
func (m *WatcherManager) Status() map[string]WatcherStatus {
	m.mu.RLock()
	defer m.mu.RUnlock()

	res := make(map[string]WatcherStatus, len(m.watchers))
	for alias, watcher := range m.watchers {
		res[alias] = watcher.Status()
	}
	return res
}

// Running reports whether the manager is actively supervising watchers.
func (m *WatcherManager) Running() bool {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.running
}

func (m *WatcherManager) discoverAccounts(ctx context.Context) []WatchedAccount {
	var results []WatchedAccount
	seen := make(map[string]bool)

	parseMD := func(path string) bool {
		data, err := os.ReadFile(path)
		if err != nil {
			return false
		}
		reBracket := regexp.MustCompile(`^\[([a-zA-Z0-9_\-\.]+)\]\s*([^\s\(]+)`)
		scanner := bufio.NewScanner(bytes.NewReader(data))
		found := false
		for scanner.Scan() {
			line := strings.TrimSpace(scanner.Text())
			if !strings.HasPrefix(line, "- ") && !strings.HasPrefix(line, "* ") {
				continue
			}
			item := strings.TrimSpace(line[2:])
			if match := reBracket.FindStringSubmatch(item); len(match) > 2 {
				alias := strings.ToLower(strings.TrimSpace(match[1]))
				email := strings.ToLower(strings.TrimSpace(match[2]))
				if strings.Contains(email, "@") && !seen[alias] {
					seen[alias] = true
					results = append(results, WatchedAccount{Alias: alias, Email: email})
					found = true
				}
			} else if strings.Contains(item, ":") {
				parts := strings.SplitN(item, ":", 2)
				alias := strings.ToLower(strings.TrimSpace(parts[0]))
				email := strings.ToLower(strings.TrimSpace(parts[1]))
				if strings.Contains(email, "@") && !seen[alias] {
					seen[alias] = true
					results = append(results, WatchedAccount{Alias: alias, Email: email})
					found = true
				}
			}
		}
		return found
	}

	// 1. Check local config dir first (accounts.md or google_accounts.json)
	localMD := filepath.Join(m.cfg.ConfigDir, "accounts.md")
	hasLocalMD := parseMD(localMD)

	if !hasLocalMD {
		localJSON := filepath.Join(m.cfg.ConfigDir, "google_accounts.json")
		if data, err := os.ReadFile(localJSON); err == nil {
			var mapped map[string]string
			if json.Unmarshal(data, &mapped) == nil && len(mapped) > 0 {
				for alias, email := range mapped {
					if clean := strings.TrimSpace(email); clean != "" && !seen[alias] {
						seen[alias] = true
						results = append(results, WatchedAccount{Alias: alias, Email: clean})
					}
				}
			}
		}
	}

	// 2. If nothing configured in local config dir, search global memory paths
	if len(results) == 0 {
		globalCandidates := []string{}
		if dir := os.Getenv("AI_ASSISTANT_MEMORY_DIR"); dir != "" {
			globalCandidates = append(globalCandidates, filepath.Join(dir, "accounts.md"))
		}
		if home, err := os.UserHomeDir(); err == nil {
			globalCandidates = append(globalCandidates, filepath.Join(home, ".config", "ai-assistant", "memory", "accounts.md"))
		}
		globalCandidates = append(globalCandidates,
			"workspace/Memory/accounts.md",
			"Memory/accounts.md",
		)

		for _, cand := range globalCandidates {
			if parseMD(cand) {
				break
			}
		}
	}

	// 3. Discover from token_*.json files in ConfigDir
	files, err := os.ReadDir(m.cfg.ConfigDir)
	if err == nil {
		for _, file := range files {
			name := file.Name()
			if strings.HasPrefix(name, "token_") && strings.HasSuffix(name, ".json") {
				alias := strings.TrimSuffix(strings.TrimPrefix(name, "token_"), ".json")
				if alias != "" && !seen[alias] {
					seen[alias] = true
					results = append(results, WatchedAccount{Alias: alias, Email: ""})
				}
			}
		}
	}

	return results
}
