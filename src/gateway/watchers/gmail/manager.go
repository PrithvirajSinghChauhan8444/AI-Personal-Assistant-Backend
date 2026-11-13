package gmail

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
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

	// 1. Discover from config/google_accounts.json
	accountsPath := filepath.Join(m.cfg.ConfigDir, "google_accounts.json")
	if data, err := os.ReadFile(accountsPath); err == nil {
		var mapped map[string]string
		if json.Unmarshal(data, &mapped) == nil {
			for alias, email := range mapped {
				if clean := strings.TrimSpace(email); clean != "" && !seen[alias] {
					seen[alias] = true
					results = append(results, WatchedAccount{Alias: alias, Email: clean})
				}
			}
		}
	}

	// 2. Discover from token_*.json files
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
