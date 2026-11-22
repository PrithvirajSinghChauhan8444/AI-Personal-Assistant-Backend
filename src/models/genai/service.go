package genai

import (
	"bufio"
	"context"
	"fmt"
	"os"
	"sort"
	"strings"
	"sync"
	"time"

	genaisdk "google.golang.org/genai"
)

// ModelInfo captures metadata about an available Google GenAI model.
type ModelInfo struct {
	Name             string   `json:"name"`
	DisplayName      string   `json:"display_name"`
	Description      string   `json:"description"`
	InputTokenLimit  int32    `json:"input_token_limit"`
	OutputTokenLimit int32    `json:"output_token_limit"`
	Thinking         bool     `json:"thinking"`
	SupportedActions []string `json:"supported_actions"`
}

// ModelService provides access to discover and inspect Google GenAI models.
type ModelService struct {
	apiKey       string
	client       *genaisdk.Client
	cachedModels []ModelInfo
	lastFetched  time.Time
	cacheTTL     time.Duration
	mu           sync.RWMutex
}

// NewModelService creates an initialized ModelService discovering the Gemini API key if omitted.
func NewModelService(apiKey string) *ModelService {
	if apiKey == "" {
		apiKey = resolveAPIKey()
	}
	return &ModelService{
		apiKey:   apiKey,
		cacheTTL: 5 * time.Minute,
	}
}

// resolveAPIKey searches environment variables and .env files for GEMINI_API_KEY or GOOGLE_API_KEY.
func resolveAPIKey() string {
	if key := os.Getenv("GEMINI_API_KEY"); key != "" {
		return key
	}
	if key := os.Getenv("GOOGLE_API_KEY"); key != "" {
		return key
	}

	// Try reading config/.env or .env across directory candidates
	candidates := []string{
		"config/.env",
		".env",
		"../config/.env",
		"../.env",
		"../../config/.env",
		"../../.env",
		"../../../config/.env",
		"../../../.env",
	}

	for _, envPath := range candidates {
		if f, err := os.Open(envPath); err == nil {
			scanner := bufio.NewScanner(f)
			for scanner.Scan() {
				line := strings.TrimSpace(scanner.Text())
				if strings.HasPrefix(line, "#") || !strings.Contains(line, "=") {
					continue
				}
				parts := strings.SplitN(line, "=", 2)
				k := strings.TrimSpace(parts[0])
				v := strings.Trim(strings.TrimSpace(parts[1]), "\"'")
				if (k == "GEMINI_API_KEY" || k == "GOOGLE_API_KEY") && v != "" {
					_ = f.Close()
					return v
				}
			}
			_ = f.Close()
		}
	}
	return ""
}

// SetAPIKey updates the active API key and clears any cached client.
func (s *ModelService) SetAPIKey(key string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.apiKey = key
	s.client = nil
	s.cachedModels = nil
}

func (s *ModelService) getClient(ctx context.Context) (*genaisdk.Client, error) {
	if s.client != nil {
		return s.client, nil
	}
	if s.apiKey == "" {
		s.apiKey = resolveAPIKey()
	}
	if s.apiKey == "" {
		return nil, fmt.Errorf("GEMINI_API_KEY is not configured in environment or config/.env")
	}

	client, err := genaisdk.NewClient(ctx, &genaisdk.ClientConfig{
		APIKey: s.apiKey,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to initialize GenAI client: %w", err)
	}
	s.client = client
	return s.client, nil
}

// ListModels queries Google GenAI via google.golang.org/genai and returns available models.
func (s *ModelService) ListModels(ctx context.Context, forceRefresh bool) ([]ModelInfo, error) {
	s.mu.RLock()
	if !forceRefresh && len(s.cachedModels) > 0 && time.Since(s.lastFetched) < s.cacheTTL {
		cached := make([]ModelInfo, len(s.cachedModels))
		copy(cached, s.cachedModels)
		s.mu.RUnlock()
		return cached, nil
	}
	s.mu.RUnlock()

	s.mu.Lock()
	defer s.mu.Unlock()

	// Double check cache under lock
	if !forceRefresh && len(s.cachedModels) > 0 && time.Since(s.lastFetched) < s.cacheTTL {
		cached := make([]ModelInfo, len(s.cachedModels))
		copy(cached, s.cachedModels)
		return cached, nil
	}

	client, err := s.getClient(ctx)
	if err != nil {
		return nil, err
	}

	var models []ModelInfo
	for m, err := range client.Models.All(ctx) {
		if err != nil {
			return nil, fmt.Errorf("error enumerating genai models: %w", err)
		}
		cleanName := strings.TrimPrefix(m.Name, "models/")
		info := ModelInfo{
			Name:             cleanName,
			DisplayName:      m.DisplayName,
			Description:      m.Description,
			InputTokenLimit:  m.InputTokenLimit,
			OutputTokenLimit: m.OutputTokenLimit,
			Thinking:         m.Thinking,
			SupportedActions: m.SupportedActions,
		}
		models = append(models, info)
	}

	// Sort models logically: gemini models first, then gemma, then others
	sort.Slice(models, func(i, j int) bool {
		m1 := models[i].Name
		m2 := models[j].Name
		isGem1 := strings.HasPrefix(m1, "gemini")
		isGem2 := strings.HasPrefix(m2, "gemini")
		if isGem1 && !isGem2 {
			return true
		}
		if !isGem1 && isGem2 {
			return false
		}
		return m1 < m2
	})

	s.cachedModels = models
	s.lastFetched = time.Now()

	result := make([]ModelInfo, len(models))
	copy(result, models)
	return result, nil
}

// GetModel retrieves metadata for a specific model name.
func (s *ModelService) GetModel(ctx context.Context, modelName string) (*ModelInfo, error) {
	clean := strings.TrimPrefix(strings.TrimPrefix(modelName, "google:"), "models/")
	models, err := s.ListModels(ctx, false)
	if err != nil {
		return nil, err
	}
	for _, m := range models {
		if strings.EqualFold(m.Name, clean) {
			return &m, nil
		}
	}
	return nil, fmt.Errorf("model %q not found in available models", modelName)
}
