package workspace

import (
	"bytes"
	"crypto/aes"
	"crypto/cipher"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"fmt"
	"os"
	"strings"
)

// DecryptFernet decrypts a Fernet-encrypted payload using a standard 32-byte Fernet key.
func DecryptFernet(cipherTextBase64 string, fernetKeyBase64 string) ([]byte, error) {
	keyBytes, err := base64.URLEncoding.DecodeString(strings.TrimSpace(fernetKeyBase64))
	if err != nil {
		return nil, fmt.Errorf("invalid base64 fernet key: %w", err)
	}

	if len(keyBytes) != 32 {
		return nil, fmt.Errorf("fernet key must be 32 bytes, got %d", len(keyBytes))
	}

	signingKey := keyBytes[:16]
	encryptionKey := keyBytes[16:]

	payload, err := base64.URLEncoding.DecodeString(strings.TrimSpace(cipherTextBase64))
	if err != nil {
		return nil, fmt.Errorf("invalid base64 fernet payload: %w", err)
	}

	if len(payload) < 57 { // 1 (version) + 8 (timestamp) + 16 (IV) + 0 (min cipher) + 32 (HMAC)
		return nil, fmt.Errorf("fernet payload too short (%d bytes)", len(payload))
	}

	if payload[0] != 0x80 {
		return nil, fmt.Errorf("invalid fernet version byte: 0x%02x", payload[0])
	}

	hmacIndex := len(payload) - 32
	signedPortion := payload[:hmacIndex]
	expectedHMAC := payload[hmacIndex:]

	mac := hmac.New(sha256.New, signingKey)
	mac.Write(signedPortion)
	computedHMAC := mac.Sum(nil)

	if !hmac.Equal(computedHMAC, expectedHMAC) {
		return nil, fmt.Errorf("fernet signature verification failed")
	}

	iv := payload[9:25]
	cipherBytes := payload[25:hmacIndex]

	block, err := aes.NewCipher(encryptionKey)
	if err != nil {
		return nil, fmt.Errorf("failed to create AES cipher: %w", err)
	}

	if len(cipherBytes)%aes.BlockSize != 0 {
		return nil, fmt.Errorf("cipher text length is not a multiple of AES block size")
	}

	mode := cipher.NewCBCDecrypter(block, iv)
	plainPadded := make([]byte, len(cipherBytes))
	mode.CryptBlocks(plainPadded, cipherBytes)

	plainText, err := pkcs7Unpad(plainPadded, aes.BlockSize)
	if err != nil {
		return nil, fmt.Errorf("unpadding failed: %w", err)
	}

	return plainText, nil
}

// GetDerivedFernetKey computes the 32-byte urlsafe-base64 key matching auth_utils.py.
func GetDerivedFernetKey() string {
	tryLoadDotEnv()

	keyStr := os.Getenv("TOKEN_ENCRYPTION_KEY")
	if keyStr == "" {
		sysPw := os.Getenv("SYSTEM_PASSWORD")
		if sysPw == "" {
			sysPw = os.Getenv("AGENT_PASSWORD")
		}
		if sysPw == "" {
			sysPw = "default_secret_fallback_password"
		}
		keyHash := sha256.Sum256([]byte(sysPw))
		return base64.URLEncoding.EncodeToString(keyHash[:])
	}

	keyHash := sha256.Sum256([]byte(keyStr))
	return base64.URLEncoding.EncodeToString(keyHash[:])
}

func tryLoadDotEnv() {
	candidates := []string{".env", "config/.env"}
	for _, p := range candidates {
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
				k := strings.TrimSpace(parts[0])
				v := strings.Trim(strings.TrimSpace(parts[1]), `"'`)
				if os.Getenv(k) == "" {
					_ = os.Setenv(k, v)
				}
			}
		}
	}
}

// LoadTokenFile reads a token JSON file, decrypting via Fernet if encrypted.
func LoadTokenFile(filePath string) ([]byte, error) {
	raw, err := os.ReadFile(filePath)
	if err != nil {
		return nil, err
	}

	trimmed := bytes.TrimSpace(raw)
	if len(trimmed) == 0 {
		return nil, fmt.Errorf("token file %q is empty", filePath)
	}

	// Plain JSON compatibility
	if trimmed[0] == '{' {
		return trimmed, nil
	}

	key := GetDerivedFernetKey()
	return DecryptFernet(string(trimmed), key)
}

func pkcs7Unpad(data []byte, blockSize int) ([]byte, error) {
	length := len(data)
	if length == 0 || length%blockSize != 0 {
		return nil, fmt.Errorf("invalid padded data length")
	}

	padLen := int(data[length-1])
	if padLen == 0 || padLen > blockSize || padLen > length {
		return nil, fmt.Errorf("invalid padding byte %d", padLen)
	}

	for i := length - padLen; i < length; i++ {
		if data[i] != byte(padLen) {
			return nil, fmt.Errorf("inconsistent padding")
		}
	}

	return data[:length-padLen], nil
}
