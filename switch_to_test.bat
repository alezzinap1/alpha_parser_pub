@echo off
REM Скрипт для переключения на тестовое окружение (Windows)
echo Switching to TEST environment...
copy .env.test .env >nul 2>&1
if %errorlevel% equ 0 (
    echo ✓ Switched to TEST environment
    echo Current ENV_MODE: test
    echo Files will be created with _test suffix:
    echo   - userbot2_test_session.session
    echo   - channels_v2_test.db
    echo   - userbot2_test.log
) else (
    echo ✗ Error: .env.test file not found!
    echo Please create .env.test file first.
    pause
    exit /b 1
)
