package telegram

import (
	"os"
	"strconv"
	"strings"
	"time"
)

// LoadConfigFromEnv reads Telegram configuration from process environment and local .env files.
func LoadConfigFromEnv() Config {
	loadDotEnvFiles(".env", "config/.env")

	token := strings.TrimSpace(os.Getenv("TELEGRAM_BOT_TOKEN"))
	rawUserIDs := strings.TrimSpace(os.Getenv("TELEGRAM_ALLOWED_USER_IDS"))
	allowedIDs := parseAllowedUserIDs(rawUserIDs)

	throttle := DefaultThrottleInterval
	if rawMs := strings.TrimSpace(os.Getenv("TELEGRAM_THROTTLE_MS")); rawMs != "" {
		if ms, err := strconv.Atoi(rawMs); err == nil && ms > 0 {
			throttle = time.Duration(ms) * time.Millisecond
		}
	}

	pollingTimeout := DefaultPollingTimeout
	if rawSec := strings.TrimSpace(os.Getenv("TELEGRAM_POLLING_TIMEOUT_SEC")); rawSec != "" {
		if sec, err := strconv.Atoi(rawSec); err == nil && sec > 0 {
			pollingTimeout = time.Duration(sec) * time.Second
		}
	}

	return Config{
		Token:            token,
		AllowedUserIDs:   allowedIDs,
		ThrottleInterval: throttle,
		PollingTimeout:   pollingTimeout,
		MaxMessageLength: DefaultMaxMessageLength,
	}
}

func parseAllowedUserIDs(raw string) []int64 {
	if raw == "" {
		return nil
	}
	parts := strings.Split(raw, ",")
	var result []int64
	for _, part := range parts {
		trimmed := strings.TrimSpace(part)
		if trimmed == "" {
			continue
		}
		if id, err := strconv.ParseInt(trimmed, 10, 64); err == nil {
			result = append(result, id)
		}
	}
	return result
}

func loadDotEnvFiles(paths ...string) {
	for _, p := range paths {
		data, err := os.ReadFile(p)
		if err != nil {
			continue
		}
		lines := strings.Split(string(data), "\n")
		for _, line := range lines {
			line = strings.TrimSpace(line)
			if line == "" || strings.HasPrefix(line, "#") {
				continue
			}
			parts := strings.SplitN(line, "=", 2)
			if len(parts) == 2 {
				key := strings.TrimSpace(parts[0])
				val := strings.Trim(strings.TrimSpace(parts[1]), `"'`)
				if os.Getenv(key) == "" {
					_ = os.Setenv(key, val)
				}
			}
		}
	}
}
