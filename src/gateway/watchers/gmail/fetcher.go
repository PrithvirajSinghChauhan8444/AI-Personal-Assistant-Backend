package gmail

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"

	"assistant/src/tools/tools/workspace"
)

// GoogleMailFetcher implements MailFetcher via the Gmail REST API.
type GoogleMailFetcher struct {
	client *workspace.GoogleClient
}

// NewGoogleMailFetcher creates a MailFetcher backed by GoogleClient.
func NewGoogleMailFetcher(client *workspace.GoogleClient) *GoogleMailFetcher {
	return &GoogleMailFetcher{client: client}
}

// FetchUnread retrieves unread email summaries for the specified account.
func (f *GoogleMailFetcher) FetchUnread(ctx context.Context, account string, limit int) ([]EmailSummary, error) {
	if limit <= 0 {
		limit = 5
	}

	listURL := fmt.Sprintf("https://gmail.googleapis.com/gmail/v1/users/me/messages?q=is:unread&maxResults=%d", limit)
	resp, err := f.client.DoAuthorizedRequest(ctx, account, http.MethodGet, listURL, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to query unread messages for %s: %w", account, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("gmail list endpoint returned status %d for %s", resp.StatusCode, account)
	}

	var listData struct {
		Messages []struct {
			ID string `json:"id"`
		} `json:"messages"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&listData); err != nil {
		return nil, fmt.Errorf("failed to decode message list: %w", err)
	}

	if len(listData.Messages) == 0 {
		return nil, nil
	}

	summaries := make([]EmailSummary, 0, len(listData.Messages))
	for _, m := range listData.Messages {
		if summary, err := f.fetchSingleMessage(ctx, account, m.ID); err == nil {
			summaries = append(summaries, summary)
		}
	}

	return summaries, nil
}

func (f *GoogleMailFetcher) fetchSingleMessage(ctx context.Context, account, messageID string) (EmailSummary, error) {
	endpoint := fmt.Sprintf(
		"https://gmail.googleapis.com/gmail/v1/users/me/messages/%s?format=metadata&metadataHeaders=From&metadataHeaders=To&metadataHeaders=Subject&metadataHeaders=Date",
		messageID,
	)

	resp, err := f.client.DoAuthorizedRequest(ctx, account, http.MethodGet, endpoint, nil)
	if err != nil {
		return EmailSummary{}, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return EmailSummary{}, fmt.Errorf("message metadata returned %d", resp.StatusCode)
	}

	var item struct {
		ID       string `json:"id"`
		ThreadID string `json:"threadId"`
		Snippet  string `json:"snippet"`
		Payload  struct {
			Headers []struct {
				Name  string `json:"name"`
				Value string `json:"value"`
			} `json:"headers"`
		} `json:"payload"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&item); err != nil {
		return EmailSummary{}, err
	}

	summary := EmailSummary{
		ID:       item.ID,
		ThreadID: item.ThreadID,
		Account:  account,
		Snippet:  item.Snippet,
		Date:     time.Now().UTC(),
	}

	for _, h := range item.Payload.Headers {
		switch strings.ToLower(h.Name) {
		case "from":
			summary.From = h.Value
		case "to":
			summary.To = h.Value
		case "subject":
			summary.Subject = h.Value
		case "date":
			if t, err := mailParseDate(h.Value); err == nil {
				summary.Date = t
			}
		}
	}

	return summary, nil
}

func mailParseDate(raw string) (time.Time, error) {
	formats := []string{
		time.RFC1123Z,
		time.RFC1123,
		time.RFC822Z,
		time.RFC822,
		"Mon, 2 Jan 2006 15:04:05 -0700",
		"2 Jan 2006 15:04:05 -0700",
	}
	for _, fmtStr := range formats {
		if t, err := time.Parse(fmtStr, raw); err == nil {
			return t, nil
		}
	}
	return time.Now().UTC(), nil
}
