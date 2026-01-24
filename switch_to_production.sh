#!/bin/bash
# Скрипт для переключения на рабочее окружение (Linux/Mac)

echo "Switching to PRODUCTION environment..."
if cp .env.production .env 2>/dev/null; then
    echo "✓ Switched to PRODUCTION environment"
    echo "Current ENV_MODE: production"
    echo "Files will be created with standard names:"
    echo "  - userbot2_session.session"
    echo "  - channels_v2.db"
    echo "  - userbot2.log"
    echo ""
    echo "⚠ WARNING: This is PRODUCTION mode!"
else
    echo "✗ Error: .env.production file not found!"
    echo "Please create .env.production file first."
    exit 1
fi
