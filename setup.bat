@echo off
setlocal

:: ============================================================================
:: Setup Script for BlogCore
:: ============================================================================

echo(
echo --- BlogCore Setup Script ---
echo(

:: --- Check for .env file ---
if exist .env (
    echo [.INFO.] .env file already exists. Skipping creation.
) else (
    echo [.INFO.] .env file not found. Creating from template...
    copy /Y .env.tmp .env > nul
    if not errorlevel 1 (
        echo [.SUCCESS.] .env file created successfully.
        echo(
        echo [IMPORTANT] Please open the .env file and fill in your credentials!
        echo(
    ) else (
        echo [ERROR] Failed to create .env file.
        goto :error
    )
)

echo(
echo [.INFO.] Installing/synchronizing dependencies with uv...

:: --- Run uv sync and check for errors ---
:: Removed output redirection ('>nul 2>nul') to show uv process output.
:: The '&&' and '||' operators check the exit code of the preceding command.
call uv sync && (
    echo [.SUCCESS.] Dependencies synchronized.
) || (
    echo(
    echo [ERROR] Failed to install dependencies with uv.
    echo Please run 'uv sync' manually to see the detailed error.
    goto :error
)

echo(
echo ============================================================================
echo  Setup Complete!
echo ============================================================================
echo(
echo  To activate the virtual environment, run:
echo  %~dp0.venv\Scripts\activate
echo(
echo  Then, after filling out your .env file, run the application with:
echo  python run.py
echo(
goto :end

:error
echo(
echo [FAILURE] Setup did not complete successfully.
pause
exit /b 1

:end
pause
exit /b 0