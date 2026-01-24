#!/bin/bash
# Скрипт для переключения на тестовое окружение (Linux/Mac)

echo "Switching to TEST environment..."
if cp .env.test .env 2>/dev/null; then
    echo "✓ Switched to TEST environment"
    echo "Current ENV_MODE: test"
    echo "Files will be created with _test suffix:"
    echo "  - userbot2_test_session.session"
    echo "  - channels_v2_test.db"
    echo "  - userbot2_test.log"
else
    echo "✗ Error: .env.test file not found!"
    echo "Please create .env.test file first."
    exit 1
fi
