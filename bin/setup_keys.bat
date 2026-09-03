@echo off
rem ============================================================================
rem Chatybot API Key Setup Script for Windows
rem Double-click or run from Command Prompt / PowerShell:
rem   bin\setup_keys.bat
rem ============================================================================

setlocal enabledelayedexpansion

echo ======================================================
echo           Chatybot API Key Setup (Windows)           
echo ======================================================

rem Check if Python is installed and accessible
where python >nul 2>nul
if %errorlevel% equ 0 (
    rem Prefer running the cross-platform setup wizard via Python
    python -m chatybot.setup_keys
    if %errorlevel% equ 0 goto done
    rem Fallback to direct script path if package not installed in editable mode
    if exist "%~dp0..\src\chatybot\setup_keys.py" (
        python "%~dp0..\src\chatybot\setup_keys.py"
        goto done
    )
)

echo.
echo Python was not found in PATH or chatybot is not installed.
echo Running basic Windows batch setup...
echo.

echo Enter your API keys below (press Enter to skip or leave unchanged):
echo.

set /p MISTRAL_KEY="Mistral AI Key (MISTRAL_API_KEY): "
if not "%MISTRAL_KEY%"=="" (
    setx MISTRAL_API_KEY "%MISTRAL_KEY%"
    echo [OK] Saved MISTRAL_API_KEY to Windows User Environment
)

set /p OPENAI_KEY="OpenAI Key (OPENAI_API_KEY): "
if not "%OPENAI_KEY%"=="" (
    setx OPENAI_API_KEY "%OPENAI_KEY%"
    echo [OK] Saved OPENAI_API_KEY to Windows User Environment
)

set /p OPENROUTER_KEY="OpenRouter Key (OPENROUTER_API_KEY): "
if not "%OPENROUTER_KEY%"=="" (
    setx OPENROUTER_API_KEY "%OPENROUTER_KEY%"
    echo [OK] Saved OPENROUTER_API_KEY to Windows User Environment
)

set /p GEMINI_KEY="Google Gemini Key (GEMINI_API_KEY): "
if not "%GEMINI_KEY%"=="" (
    setx GEMINI_API_KEY "%GEMINI_KEY%"
    echo [OK] Saved GEMINI_API_KEY to Windows User Environment
)

set /p ANTHROPIC_KEY="Anthropic Key (ANTHROPIC_API_KEY): "
if not "%ANTHROPIC_KEY%"=="" (
    setx ANTHROPIC_API_KEY "%ANTHROPIC_KEY%"
    echo [OK] Saved ANTHROPIC_API_KEY to Windows User Environment
)

set /p NVIDIA_KEY="NVIDIA Key (NVIDIA_API): "
if not "%NVIDIA_KEY%"=="" (
    setx NVIDIA_API "%NVIDIA_KEY%"
    echo [OK] Saved NVIDIA_API to Windows User Environment
)

echo.
echo ======================================================
echo Setup completed!
echo Keys saved permanently via setx will be active in all
echo NEW Command Prompt and PowerShell windows.
echo ======================================================

:done
rem If launched by double-clicking in Explorer, keep window open
echo %cmdcmdline% | find /i "%~0" >nul
if %errorlevel% equ 0 pause

endlocal
