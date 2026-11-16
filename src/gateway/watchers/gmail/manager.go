package gmail

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"sync"

	"assistant/src/tools/workspace"
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

// discoverAccounts loads watched accounts exclusively from config/gmail_watcher.json.
// If the configuration file is missing, disabled, or contains no valid accounts,
// no watchers are started. No fallbacks to disk tokens, global memories, or legacy files are performed.
func (m *WatcherManager) discoverAccounts(ctx context.Context) []WatchedAccount {
	var results []WatchedAccount
	seen := make(map[string]bool)

	configPath := filepath.Join(m.cfg.ConfigDir, "gmail_watcher.json")
	data, err := os.ReadFile(configPath)
	if err != nil {
		return results
	}

	type AccountConfig struct {
		Alias   string `json:"alias"`
		Email   string `json:"email"`
		Enabled *bool  `json:"enabled"`
	}

	type WatcherConfigFile struct {
		Enabled  *bool           `json:"enabled"`
		Accounts []AccountConfig `json:"accounts"`
	}

	var parsed WatcherConfigFile
	if err := json.Unmarshal(data, &parsed); err == nil && parsed.Accounts != nil {
		if parsed.Enabled != nil && !*parsed.Enabled {
			return results
		}
		for _, acc := range parsed.Accounts {
			if acc.Enabled != nil && !*acc.Enabled {
				continue
			}
			alias := strings.ToLower(strings.TrimSpace(acc.Alias))
			email := strings.ToLower(strings.TrimSpace(acc.Email))
			if alias == "" && email != "" {
				alias = strings.Split(email, "@")[0]
			}
			if alias != "" && email != "" && !seen[alias] {
				seen[alias] = true
				results = append(results, WatchedAccount{Alias: alias, Email: email})
			}
		}
		return results
	}

	// Secondary support for flat map format in gmail_watcher.json: {"primary": "user@gmail.com"}
	var mapped map[string]string
	if err := json.Unmarshal(data, &mapped); err == nil && len(mapped) > 0 {
		for alias, email := range mapped {
			cleanAlias := strings.ToLower(strings.TrimSpace(alias))
			cleanEmail := strings.ToLower(strings.TrimSpace(email))
			if cleanAlias != "" && cleanEmail != "" && !seen[cleanAlias] {
				seen[cleanAlias] = true
				results = append(results, WatchedAccount{Alias: cleanAlias, Email: cleanEmail})
			}
		}
	}

	return results
}
