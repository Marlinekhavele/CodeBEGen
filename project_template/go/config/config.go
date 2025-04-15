package config

import (
	"os"
	"time"

	"github.com/joho/godotenv"
)

type Config struct {
	ServerPort     string
	DatabaseURL    string
	JWTSecret      string
	JWTExpiryHours time.Duration
}

func Load() (*Config, error) {
	// Load .env file if it exists
	godotenv.Load()

	return &Config{
		ServerPort:     getEnv("SERVER_PORT", "8080"),
		DatabaseURL:    getEnv("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/myapp"),
		JWTSecret:      getEnv("JWT_SECRET", "your-secret-key"),
		JWTExpiryHours: time.Duration(getEnvAsInt("JWT_EXPIRY_HOURS", 24)),
	}, nil
}

func getEnv(key, defaultValue string) string {
	if value, exists := os.LookupEnv(key); exists {
		return value
	}
	return defaultValue
}

func getEnvAsInt(key string, defaultValue int) int {
	if value, exists := os.LookupEnv(key); exists {
		if i, err := strconv.Atoi(value); err == nil {
			return i
		}
	}
	return defaultValue
}