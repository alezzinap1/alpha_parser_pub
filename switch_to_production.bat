@echo off
REM Скрипт для переключения на рабочее окружение (Windows)
echo Switching to PRODUCTION environment...
copy .env.production .env >nul 2>&1
if %errorlevel% equ 0 (
    echo ✓ Switched to PRODUCTION environment
    echo Current ENV_MODE: production
    echo Files will be created with standard names:
    echo   - userbot2_session.session
    echo   - channels_v2.db
    echo   - userbot2.log
    echo.
    echo ⚠ WARNING: This is PRODUCTION mode!
) else (
    echo ✗ Error: .env.production file not found!
    echo Please create .env.production file first.
    pause
    exit /b 1
)
