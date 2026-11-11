package engine

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"sync"
)

// Recorder persists execution records to disk for auditability and replay.
type Recorder struct {
	mu       sync.RWMutex
	filePath string
}

// NewRecorder initializes a disk-backed flight recorder.
func NewRecorder(dirPath string) (*Recorder, error) {
	if err := os.MkdirAll(dirPath, 0755); err != nil {
		return nil, fmt.Errorf("failed to create recorder directory %q: %w", dirPath, err)
	}

	filePath := filepath.Join(dirPath, "history.jsonl")
	return &Recorder{
		filePath: filePath,
	}, nil
}

// Save appends an execution record to the JSONL history file.
func (r *Recorder) Save(rec *ExecutionRecord) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	data, err := json.Marshal(rec)
	if err != nil {
		return fmt.Errorf("failed to marshal execution record: %w", err)
	}

	f, err := os.OpenFile(r.filePath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
	if err != nil {
		return fmt.Errorf("failed to open history file: %w", err)
	}
	defer f.Close()

	if _, err := f.Write(append(data, '\n')); err != nil {
		return fmt.Errorf("failed to write record: %w", err)
	}

	return nil
}

// List returns the latest execution records up to the given limit, ordered newest first.
func (r *Recorder) List(limit int) ([]ExecutionRecord, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	if _, err := os.Stat(r.filePath); os.IsNotExist(err) {
		return []ExecutionRecord{}, nil
	}

	f, err := os.Open(r.filePath)
	if err != nil {
		return nil, fmt.Errorf("failed to read history file: %w", err)
	}
	defer f.Close()

	var records []ExecutionRecord
	scanner := bufio.NewScanner(f)
	// Allow large lines for heavy event stream payloads
	buf := make([]byte, 1024*1024)
	scanner.Buffer(buf, 10*1024*1024)

	for scanner.Scan() {
		line := scanner.Bytes()
		if len(line) == 0 {
			continue
		}
		var rec ExecutionRecord
		if err := json.Unmarshal(line, &rec); err == nil {
			records = append(records, rec)
		}
	}

	// Sort newest first
	sort.Slice(records, func(i, j int) bool {
		return records[i].StartedAt.After(records[j].StartedAt)
	})

	if limit > 0 && len(records) > limit {
		records = records[:limit]
	}

	return records, nil
}

// GetByID finds a single record by its execution UUID.
func (r *Recorder) GetByID(id string) (*ExecutionRecord, error) {
	records, err := r.List(0)
	if err != nil {
		return nil, err
	}

	for _, rec := range records {
		if rec.ID == id {
			return &rec, nil
		}
	}

	return nil, fmt.Errorf("record with id %q not found", id)
}
