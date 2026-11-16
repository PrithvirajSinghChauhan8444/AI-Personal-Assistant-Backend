package workspace

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"sync"
	"time"
)

type OAuthCredentials struct {
	Installed struct {
		ClientID     string `json:"client_id"`
		ClientSecret string `json:"client_secret"`
		TokenURI     string `json:"token_uri"`
	} `json:"installed"`
}

type OAuthToken struct {
	AccessToken  string    `json:"access_token"`
	RefreshToken string    `json:"refresh_token"`
	Expiry       time.Time `json:"expiry"`
	TokenType    string    `json:"token_type"`
}

type GoogleClient struct {
	mu        sync.RWMutex
	configDir string
	creds     *OAuthCredentials
	tokens    map[string]*OAuthToken
	client    *http.Client
}

func NewGoogleClient(configDir string) *GoogleClient {
	if configDir == "" {
		configDir = "config"
	}
	return &GoogleClient{
		configDir: configDir,
		tokens:    make(map[string]*OAuthToken),
		client:    &http.Client{Timeout: 30 * time.Second},
	}
}

func (gc *GoogleClient) GetAccessToken(ctx context.Context, account string) (string, error) {
	gc.mu.Lock()
	defer gc.mu.Unlock()

	accountKey := gc.resolveAccountKey(account)

	if tok, exists := gc.tokens[accountKey]; exists && tok != nil {
		if time.Until(tok.Expiry) > 2*time.Minute && tok.AccessToken != "" {
			return tok.AccessToken, nil
		}
	}

	tok, err := gc.loadTokenFromDisk(accountKey)
	if err != nil {
		return "", fmt.Errorf("failed to load token for account %q: %w", accountKey, err)
	}

	if time.Until(tok.Expiry) <= 2*time.Minute && tok.RefreshToken != "" {
		if err := gc.refreshToken(ctx, tok); err != nil {
			return "", fmt.Errorf("failed to refresh token for account %q: %w", accountKey, err)
		}
	}

	gc.tokens[accountKey] = tok
	return tok.AccessToken, nil
}

func (gc *GoogleClient) DoAuthorizedRequest(ctx context.Context, account, method, endpoint string, body io.Reader) (*http.Response, error) {
	token, err := gc.GetAccessToken(ctx, account)
	if err != nil {
		return nil, err
	}

	req, err := http.NewRequestWithContext(ctx, method, endpoint, body)
	if err != nil {
		return nil, err
	}

	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("Accept", "application/json")
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}

	return gc.client.Do(req)
}

func (gc *GoogleClient) resolveAccountKey(account string) string {
	account = strings.TrimSpace(strings.ToLower(account))
	if account == "" || account == "default" {
		if mdPath := findAccountsMarkdownPath(); mdPath != "" {
			if pref := getPreferredAlias(mdPath); pref != "" {
				return pref
			}
		}
		return "email1"
	}

	// If account is a raw email, resolve its configured alias from accounts.md
	if strings.Contains(account, "@") {
		if mdPath := findAccountsMarkdownPath(); mdPath != "" {
			accounts := parseAccountsMarkdown(mdPath)
			for alias, email := range accounts {
				if email == account {
					return alias
				}
			}
		}
	}

	return sanitizeFilename(account)
}

func getPreferredAlias(path string) string {
	if path == "" {
		return ""
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return ""
	}
	scanner := bufio.NewScanner(bytes.NewReader(data))
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if strings.HasPrefix(line, "- preferred_email_alias:") || strings.HasPrefix(line, "* preferred_email_alias:") {
			parts := strings.SplitN(line, ":", 2)
			if len(parts) == 2 {
				return strings.ToLower(strings.TrimSpace(parts[1]))
			}
		}
	}
	return ""
}

func findAccountsMarkdownPath() string {
	if dir := os.Getenv("AI_ASSISTANT_MEMORY_DIR"); dir != "" {
		p := filepath.Join(dir, "accounts.md")
		if _, err := os.Stat(p); err == nil {
			return p
		}
	}

	// Check system.json if present
	for _, sysJSON := range []string{"config/system.json", "not_comit/system.json", "system.json"} {
		if data, err := os.ReadFile(sysJSON); err == nil {
			var m map[string]interface{}
			if json.Unmarshal(data, &m) == nil {
				if memDir, ok := m["memory_dir"].(string); ok && memDir != "" {
					p := filepath.Join(memDir, "accounts.md")
					if _, err := os.Stat(p); err == nil {
						return p
					}
				}
				if wsDir, ok := m["workspace_dir"].(string); ok && wsDir != "" {
					p := filepath.Join(wsDir, "Memory", "accounts.md")
					if _, err := os.Stat(p); err == nil {
						return p
					}
				}
			}
		}
	}

	if home, err := os.UserHomeDir(); err == nil {
		p := filepath.Join(home, ".config", "ai-assistant", "memory", "accounts.md")
		if _, err := os.Stat(p); err == nil {
			return p
		}
	}

	for _, cand := range []string{
		"workspace/Memory/accounts.md",
		"Memory/accounts.md",
		"config/accounts.md",
	} {
		if _, err := os.Stat(cand); err == nil {
			return cand
		}
	}
	return ""
}

func parseAccountsMarkdown(path string) map[string]string {
	result := make(map[string]string)
	if path == "" {
		return result
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return result
	}

	reBracket := regexp.MustCompile(`^\[([a-zA-Z0-9_\-\.]+)\]\s*([^\s\(]+)`)
	scanner := bufio.NewScanner(bytes.NewReader(data))
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if !strings.HasPrefix(line, "- ") && !strings.HasPrefix(line, "* ") {
			continue
		}
		item := strings.TrimSpace(line[2:])
		if m := reBracket.FindStringSubmatch(item); len(m) > 2 {
			alias := strings.ToLower(strings.TrimSpace(m[1]))
			email := strings.ToLower(strings.TrimSpace(m[2]))
			if strings.Contains(email, "@") {
				result[alias] = email
			}
		} else if strings.Contains(item, ":") {
			parts := strings.SplitN(item, ":", 2)
			alias := strings.ToLower(strings.TrimSpace(parts[0]))
			email := strings.ToLower(strings.TrimSpace(parts[1]))
			if strings.Contains(email, "@") {
				result[alias] = email
			}
		}
	}
	return result
}

func (gc *GoogleClient) loadCredentials() error {
	if gc.creds != nil {
		return nil
	}

	path := filepath.Join(gc.configDir, "credentials.json")
	data, err := os.ReadFile(path)
	if err != nil {
		return fmt.Errorf("credentials.json not found in %s: %w", gc.configDir, err)
	}

	var creds OAuthCredentials
	if err := json.Unmarshal(data, &creds); err != nil {
		return fmt.Errorf("failed parsing credentials.json: %w", err)
	}

	gc.creds = &creds
	return nil
}

func (gc *GoogleClient) loadTokenFromDisk(accountKey string) (*OAuthToken, error) {
	candidates := []string{
		filepath.Join(gc.configDir, fmt.Sprintf("token_%s.json", accountKey)),
		filepath.Join(gc.configDir, fmt.Sprintf("token_%s.json", sanitizeFilename(accountKey))),
		filepath.Join(gc.configDir, "token_email1.json"),
		filepath.Join(gc.configDir, "token_primary.json"),
		filepath.Join(gc.configDir, "token_default.json"),
		filepath.Join(gc.configDir, "token.json"),
	}

	var tokenBytes []byte
	var loadedPath string
	for _, cand := range candidates {
		data, err := LoadTokenFile(cand)
		if err == nil && len(data) > 0 {
			tokenBytes = data
			loadedPath = cand
			break
		}
	}

	if tokenBytes == nil {
		if mdPath := findAccountsMarkdownPath(); mdPath != "" {
			accounts := parseAccountsMarkdown(mdPath)
			if email, ok := accounts[accountKey]; ok && email != "" {
				cand := filepath.Join(gc.configDir, fmt.Sprintf("token_%s.json", sanitizeFilename(email)))
				if data, err := LoadTokenFile(cand); err == nil && len(data) > 0 {
					tokenBytes = data
					loadedPath = cand
				}
			}
			if tokenBytes == nil {
				for alias, email := range accounts {
					if email == accountKey {
						cand := filepath.Join(gc.configDir, fmt.Sprintf("token_%s.json", alias))
						if data, err := LoadTokenFile(cand); err == nil && len(data) > 0 {
							tokenBytes = data
							loadedPath = cand
							break
						}
					}
				}
			}
		}
	}

	if tokenBytes == nil {
		return nil, fmt.Errorf("no valid token file found for %q", accountKey)
	}

	var raw struct {
		Token        string `json:"token"`
		AccessToken  string `json:"access_token"`
		RefreshToken string `json:"refresh_token"`
		Expiry       string `json:"expiry"`
		ExpiresAt    int64  `json:"expires_at"`
		TokenType    string `json:"token_type"`
	}

	if err := json.Unmarshal(tokenBytes, &raw); err != nil {
		return nil, fmt.Errorf("failed parsing token JSON from %s: %w", loadedPath, err)
	}

	accessToken := raw.AccessToken
	if accessToken == "" {
		accessToken = raw.Token
	}

	token := &OAuthToken{
		AccessToken:  accessToken,
		RefreshToken: raw.RefreshToken,
		TokenType:    raw.TokenType,
	}

	if raw.Expiry != "" {
		if t, err := time.Parse(time.RFC3339, raw.Expiry); err == nil {
			token.Expiry = t
		}
	} else if raw.ExpiresAt > 0 {
		token.Expiry = time.Unix(raw.ExpiresAt, 0)
	}

	return token, nil
}

func (gc *GoogleClient) refreshToken(ctx context.Context, tok *OAuthToken) error {
	if err := gc.loadCredentials(); err != nil {
		return err
	}

	tokenURI := gc.creds.Installed.TokenURI
	if tokenURI == "" {
		tokenURI = "https://oauth2.googleapis.com/token"
	}

	params := url.Values{}
	params.Set("client_id", gc.creds.Installed.ClientID)
	params.Set("client_secret", gc.creds.Installed.ClientSecret)
	params.Set("refresh_token", tok.RefreshToken)
	params.Set("grant_type", "refresh_token")

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, tokenURI, strings.NewReader(params.Encode()))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")

	resp, err := gc.client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("token endpoint returned status %d: %s", resp.StatusCode, string(body))
	}

	var refreshResp struct {
		AccessToken string `json:"access_token"`
		ExpiresIn   int64  `json:"expires_in"`
		TokenType   string `json:"token_type"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&refreshResp); err != nil {
		return err
	}

	tok.AccessToken = refreshResp.AccessToken
	tok.Expiry = time.Now().Add(time.Duration(refreshResp.ExpiresIn) * time.Second)
	return nil
}

func sanitizeFilename(s string) string {
	var buf bytes.Buffer
	for _, r := range s {
		if (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') || (r >= '0' && r <= '9') || r == '-' || r == '_' || r == '@' || r == '.' {
			buf.WriteRune(r)
		}
	}
	return buf.String()
}
