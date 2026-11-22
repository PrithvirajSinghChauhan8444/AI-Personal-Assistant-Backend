package telegram

import (
	"time"

	"assistant/src/gateway"
)

// ParseMode defines the text formatting mode for Telegram messages.
type ParseMode string

const (
	ParseModeMarkdown ParseMode = "Markdown"
	ParseModeHTML     ParseMode = "HTML"
)

// ChatAction defines chat status indicators such as typing.
type ChatAction string

const (
	ActionTyping ChatAction = "typing"
)

// User represents a Telegram user.
type User struct {
	ID        int64  `json:"id"`
	IsBot     bool   `json:"is_bot"`
	FirstName string `json:"first_name"`
	LastName  string `json:"last_name,omitempty"`
	Username  string `json:"username,omitempty"`
}

// Chat represents a Telegram chat (private, group, or channel).
type Chat struct {
	ID    int64  `json:"id"`
	Type  string `json:"type"`
	Title string `json:"title,omitempty"`
}

// Message represents a Telegram message.
type Message struct {
	MessageID int    `json:"message_id"`
	From      *User  `json:"from,omitempty"`
	Chat      *Chat  `json:"chat"`
	Text      string `json:"text,omitempty"`
	Date      int64  `json:"date"`
}

// InlineKeyboardButton represents one button in an inline keyboard.
type InlineKeyboardButton struct {
	Text         string `json:"text"`
	CallbackData string `json:"callback_data,omitempty"`
	URL          string `json:"url,omitempty"`
}

// InlineKeyboardMarkup represents an inline keyboard markup attached to a message.
type InlineKeyboardMarkup struct {
	InlineKeyboard [][]InlineKeyboardButton `json:"inline_keyboard"`
}

// CallbackQuery represents an incoming callback query from an inline keyboard button.
type CallbackQuery struct {
	ID      string   `json:"id"`
	From    *User    `json:"from"`
	Message *Message `json:"message,omitempty"`
	Data    string   `json:"data"`
}

// Update represents an incoming update from the Telegram Bot API.
type Update struct {
	UpdateID      int            `json:"update_id"`
	Message       *Message       `json:"message,omitempty"`
	CallbackQuery *CallbackQuery `json:"callback_query,omitempty"`
}

// BotCommand represents a bot command registered with Telegram's setMyCommands.
type BotCommand struct {
	Command     string `json:"command"`
	Description string `json:"description"`
}

// Config holds operational settings for the Telegram adapter and bot service.
type Config struct {
	// BotClient abstracts Telegram API communication (HTTP or Mock).
	Client BotClient

	// Gateway provides the connection to Layer 1 turn execution and HITL controls.
	Gateway *gateway.Gateway

	// Token is the Telegram Bot API token.
	Token string

	// ChatID is the default or bound chat ID (used for standalone observers).
	ChatID int64

	// AllowedUserIDs defines the whitelist of authorized Telegram user IDs.
	AllowedUserIDs []int64

	// ThrottleInterval controls minimum delay between message edits to avoid rate limits.
	ThrottleInterval time.Duration

	// PollingTimeout controls long-polling HTTP timeout in seconds (default: 30s).
	PollingTimeout time.Duration

	// MaxMessageLength sets maximum character limit per message chunk (default: 3500).
	MaxMessageLength int
}

// DefaultThrottleInterval is the default rate limit delay between progress edits.
const DefaultThrottleInterval = 1 * time.Second

// DefaultPollingTimeout is the default long-polling timeout.
const DefaultPollingTimeout = 30 * time.Second

// DefaultMaxMessageLength is the safe character threshold under Telegram's 4096 rune limit.
const DefaultMaxMessageLength = 3500
