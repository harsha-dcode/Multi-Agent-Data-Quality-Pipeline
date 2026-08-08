@echo off
setlocal enabledelayedexpansion

if not exist .env (
    echo [error] .env file not found. Copy .env.example to .env first:
    echo     copy .env.example .env
    exit /b 1
)

REM Load .env into environment. Skips blank lines and # comments.
for /f "usebackq tokens=* eol=#" %%a in (".env") do (
    set "line=%%a"
    if not "!line!"=="" (
        REM strip surrounding quotes from the value if any
        set "kv=!line!"
        set "kv=!kv:"=!"
        set "!kv!"
    )
)

if "%~1"=="" (
    echo Usage: run.bat "<brief>" "<path-to-csv>"
    echo Example: run.bat "Find why Q4 sales dropped." tests\sample_data\sales.csv
    exit /b 1
)

if "%~2"=="" (
    echo Usage: run.bat "<brief>" "<path-to-csv>"
    exit /b 1
)

python -m agent.main --brief %1 --csv %2
endlocal
