package gmail

import (
	"bufio"
	"context"
	"crypto/tls"
	"encoding/base64"
	"errors"
	"fmt"
	"net"
	"net/textproto"
	"strings"
	"sync"
	"time"
)

var (
	ErrNotConnected    = errors.New("imap stream is not connected")
	ErrAuthFailed      = errors.New("imap xoauth2 authentication failed")
	ErrIDLERefused     = errors.New("imap server refused idle command")
	ErrStreamClosed    = errors.New("imap stream was closed")
)

// TLSIMAPStream implements IMAPStream over a secure TLS connection.
type TLSIMAPStream struct {
	mu       sync.Mutex
	conn     net.Conn
	tp       *textproto.Reader
	writer   *bufio.Writer
	tagIndex int
	inIDLE   bool
}

// NewTLSIMAPStream creates an uninitialized TLS IMAP stream.
func NewTLSIMAPStream() *TLSIMAPStream {
	return &TLSIMAPStream{}
}

// Connect dials the secure IMAP host and reads the server greeting.
func (s *TLSIMAPStream) Connect(ctx context.Context, host string) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	dialer := &tls.Dialer{
		Config: &tls.Config{
			ServerName: strings.Split(host, ":")[0],
			MinVersion: tls.VersionTLS12,
		},
	}

	conn, err := dialer.DialContext(ctx, "tcp", host)
	if err != nil {
		return fmt.Errorf("failed to dial imap server %s: %w", host, err)
	}

	s.conn = conn
	s.writer = bufio.NewWriter(conn)
	s.tp = textproto.NewReader(bufio.NewReader(conn))

	greeting, err := s.tp.ReadLine()
	if err != nil {
		_ = conn.Close()
		return fmt.Errorf("failed to read imap server greeting: %w", err)
	}

	if !strings.HasPrefix(greeting, "* OK") {
		_ = conn.Close()
		return fmt.Errorf("unexpected server greeting: %s", greeting)
	}

	return nil
}

// AuthenticateXOAUTH2 authenticates using the SASL XOAUTH2 protocol.
func (s *TLSIMAPStream) AuthenticateXOAUTH2(email, token string) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.conn == nil {
		return ErrNotConnected
	}

	authString := FormatXOAUTH2String(email, token)
	encoded := base64.StdEncoding.EncodeToString([]byte(authString))
	tag := s.nextTag()

	cmd := fmt.Sprintf("%s AUTHENTICATE XOAUTH2 %s\r\n", tag, encoded)
	if _, err := s.writer.WriteString(cmd); err != nil {
		return err
	}
	if err := s.writer.Flush(); err != nil {
		return err
	}

	for {
		line, err := s.tp.ReadLine()
		if err != nil {
			return fmt.Errorf("error reading auth response: %w", err)
		}

		if strings.HasPrefix(line, tag+" OK") {
			return nil
		}
		if strings.HasPrefix(line, tag+" NO") || strings.HasPrefix(line, tag+" BAD") {
			return fmt.Errorf("%w: %s", ErrAuthFailed, line)
		}
		if strings.HasPrefix(line, "+") {
			// SASL challenge/error payload: acknowledge with CRLF to complete abort sequence
			_, _ = s.writer.WriteString("\r\n")
			_ = s.writer.Flush()
		}
	}
}

// SelectMailbox issues the SELECT command for the specified folder.
func (s *TLSIMAPStream) SelectMailbox(mailbox string) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.conn == nil {
		return ErrNotConnected
	}

	tag := s.nextTag()
	cmd := fmt.Sprintf("%s SELECT %s\r\n", tag, mailbox)
	if _, err := s.writer.WriteString(cmd); err != nil {
		return err
	}
	if err := s.writer.Flush(); err != nil {
		return err
	}

	for {
		line, err := s.tp.ReadLine()
		if err != nil {
			return fmt.Errorf("failed to read select response: %w", err)
		}
		if strings.HasPrefix(line, tag+" OK") {
			return nil
		}
		if strings.HasPrefix(line, tag+" NO") || strings.HasPrefix(line, tag+" BAD") {
			return fmt.Errorf("select %s failed: %s", mailbox, line)
		}
	}
}

// EnterIDLE sends the IDLE command and awaits the continuation response (+ idling).
func (s *TLSIMAPStream) EnterIDLE() error {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.conn == nil {
		return ErrNotConnected
	}

	tag := s.nextTag()
	cmd := fmt.Sprintf("%s IDLE\r\n", tag)
	if _, err := s.writer.WriteString(cmd); err != nil {
		return err
	}
	if err := s.writer.Flush(); err != nil {
		return err
	}

	line, err := s.tp.ReadLine()
	if err != nil {
		return fmt.Errorf("failed to read idle acknowledgment: %w", err)
	}

	if !strings.HasPrefix(line, "+") {
		return fmt.Errorf("%w: %s", ErrIDLERefused, line)
	}

	s.inIDLE = true
	return nil
}

// WaitForUpdate listens on the connection for an EXISTS or RECENT update line.
func (s *TLSIMAPStream) WaitForUpdate(ctx context.Context, timeout time.Duration) (bool, error) {
	if s.conn == nil {
		return false, ErrNotConnected
	}

	type readResult struct {
		line string
		err  error
	}

	readChan := make(chan readResult, 1)

	go func() {
		line, err := s.tp.ReadLine()
		readChan <- readResult{line: line, err: err}
	}()

	select {
	case <-ctx.Done():
		return false, ctx.Err()
	case <-time.After(timeout):
		return false, nil
	case res := <-readChan:
		if res.err != nil {
			return false, res.err
		}
		return ParseMailboxUpdate(res.line), nil
	}
}

// ExitIDLE sends DONE to terminate IDLE mode and consumes the completion line.
func (s *TLSIMAPStream) ExitIDLE() error {
	s.mu.Lock()
	defer s.mu.Unlock()

	if !s.inIDLE || s.conn == nil {
		return nil
	}

	if _, err := s.writer.WriteString("DONE\r\n"); err != nil {
		return err
	}
	if err := s.writer.Flush(); err != nil {
		return err
	}

	s.inIDLE = false

	// Consume completion line with 5s deadline
	_ = s.conn.SetReadDeadline(time.Now().Add(5 * time.Second))
	defer func() { _ = s.conn.SetReadDeadline(time.Time{}) }()

	for {
		line, err := s.tp.ReadLine()
		if err != nil {
			return nil
		}
		if strings.Contains(line, "OK IDLE") || strings.Contains(line, "OK") {
			return nil
		}
	}
}

// Close gracefully closes the underlying connection.
func (s *TLSIMAPStream) Close() error {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.conn == nil {
		return nil
	}

	if s.inIDLE {
		_, _ = s.writer.WriteString("DONE\r\n")
		_ = s.writer.Flush()
		s.inIDLE = false
	}

	_, _ = s.writer.WriteString("A999 LOGOUT\r\n")
	_ = s.writer.Flush()

	err := s.conn.Close()
	s.conn = nil
	return err
}

func (s *TLSIMAPStream) nextTag() string {
	s.tagIndex++
	return fmt.Sprintf("A%03d", s.tagIndex)
}

// FormatXOAUTH2String generates the SASL XOAUTH2 authentication string.
func FormatXOAUTH2String(email, accessToken string) string {
	return fmt.Sprintf("user=%s\x01auth=Bearer %s\x01\x01", email, accessToken)
}

// ParseMailboxUpdate returns true if an IMAP line denotes a mailbox addition (EXISTS or RECENT).
func ParseMailboxUpdate(line string) bool {
	upper := strings.ToUpper(line)
	return strings.Contains(upper, "EXISTS") || strings.Contains(upper, "RECENT")
}
