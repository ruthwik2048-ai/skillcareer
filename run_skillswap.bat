@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating the project virtual environment...
    where py >nul 2>nul
    if not errorlevel 1 (
        py -3 -m venv .venv
    ) else (
        where python >nul 2>nul
        if errorlevel 1 (
            echo Python was not found. Install Python 3 and try again.
            goto :error
        )
        python -m venv .venv
    )
    if errorlevel 1 goto :error
)

set "PYTHON=%CD%\.venv\Scripts\python.exe"

echo Installing project dependencies...
"%PYTHON%" -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo Preparing the local database...
"%PYTHON%" manage.py migrate
if errorlevel 1 goto :error

echo.
echo SkillCareer is starting at http://127.0.0.1:8000/
echo Your browser will open when the site is ready.
echo Keep this window open while using the site. Press Ctrl+C to stop it.
echo.
start "" powershell.exe -NoProfile -WindowStyle Hidden -Command "$timeout=(Get-Date).AddSeconds(30); $connected=$false; while ((Get-Date) -lt $timeout) { try { $client=New-Object System.Net.Sockets.TcpClient; $client.Connect('127.0.0.1',8000); $client.Close(); $connected=$true; break } catch { Start-Sleep -Milliseconds 500 } }; if ($connected) { Start-Process 'http://127.0.0.1:8000/' }"
"%PYTHON%" manage.py runserver 127.0.0.1:8000
exit /b %errorlevel%

:error
echo.
echo SkillCareer could not start. Check the error above and try again.
pause
exit /b 1
