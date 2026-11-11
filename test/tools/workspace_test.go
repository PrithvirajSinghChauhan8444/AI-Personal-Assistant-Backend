package tools_test

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/binary"
	"os"
	"path/filepath"
	"testing"
	"time"

	"assistant/src/tools/tools/workspace"
)

func generateTestFernetToken(plainText string, keyBytes []byte) string {
	signingKey := keyBytes[:16]
	encryptionKey := keyBytes[16:]

	iv := make([]byte, 16)
	_, _ = rand.Read(iv)

	block, _ := aes.NewCipher(encryptionKey)
	mode := cipher.NewCBCEncrypter(block, iv)

	plainPadded := pkcs7Pad([]byte(plainText), aes.BlockSize)
	cipherBytes := make([]byte, len(plainPadded))
	mode.CryptBlocks(cipherBytes, plainPadded)

	var payload []byte
	payload = append(payload, 0x80) // version

	timeBytes := make([]byte, 8)
	binary.BigEndian.PutUint64(timeBytes, uint64(time.Now().Unix()))
	payload = append(payload, timeBytes...)
	payload = append(payload, iv...)
	payload = append(payload, cipherBytes...)

	mac := hmac.New(sha256.New, signingKey)
	mac.Write(payload)
	payload = append(payload, mac.Sum(nil)...)

	return base64.URLEncoding.EncodeToString(payload)
}

func pkcs7Pad(data []byte, blockSize int) []byte {
	padLen := blockSize - (len(data) % blockSize)
	pad := make([]byte, padLen)
	for i := range pad {
		pad[i] = byte(padLen)
	}
	return append(data, pad...)
}

func TestFernetDecryptRoundtrip(t *testing.T) {
	keyBytes := make([]byte, 32)
	_, _ = rand.Read(keyBytes)
	keyB64 := base64.URLEncoding.EncodeToString(keyBytes)

	original := `{"access_token":"ya29.test12345","refresh_token":"1//refresh_token"}`
	tokenB64 := generateTestFernetToken(original, keyBytes)

	decrypted, err := workspace.DecryptFernet(tokenB64, keyB64)
	if err != nil {
		t.Fatalf("decryption failed: %v", err)
	}

	if string(decrypted) != original {
		t.Fatalf("expected decrypted text %q, got %q", original, string(decrypted))
	}
}

func TestFernetTamperedPayload(t *testing.T) {
	keyBytes := make([]byte, 32)
	_, _ = rand.Read(keyBytes)
	keyB64 := base64.URLEncoding.EncodeToString(keyBytes)

	tokenB64 := generateTestFernetToken("secret payload", keyBytes)

	raw, _ := base64.URLEncoding.DecodeString(tokenB64)
	raw[20] ^= 0xFF // Tamper byte in ciphertext
	tamperedB64 := base64.URLEncoding.EncodeToString(raw)

	_, err := workspace.DecryptFernet(tamperedB64, keyB64)
	if err == nil {
		t.Fatalf("expected error on tampered payload, got nil")
	}
}

func TestLoadTokenFilePlainJSON(t *testing.T) {
	tempDir := t.TempDir()
	tokenPath := filepath.Join(tempDir, "token_plain.json")
	plainJSON := `{"access_token":"plain123","token_type":"Bearer"}`

	if err := os.WriteFile(tokenPath, []byte(plainJSON), 0600); err != nil {
		t.Fatalf("failed to write test token: %v", err)
	}

	data, err := workspace.LoadTokenFile(tokenPath)
	if err != nil {
		t.Fatalf("unexpected error loading plain JSON token: %v", err)
	}

	if string(data) != plainJSON {
		t.Fatalf("expected %q, got %q", plainJSON, string(data))
	}
}
