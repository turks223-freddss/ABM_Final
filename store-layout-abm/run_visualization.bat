@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found.
    echo Run: python -m venv .venv
    echo Then: .venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)

if "%PORT%"=="" (
    for /f %%P in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "$ip=[Net.IPAddress]::Parse(''127.0.0.1''); foreach($p in 8765..8775){ try { $listener=[Net.Sockets.TcpListener]::new($ip,$p); $listener.Start(); $listener.Stop(); Write-Output $p; break } catch {} }"') do set "PORT=%%P"
)

if "%PORT%"=="" (
    echo No free port found between 8765 and 8775.
    echo Close an existing Solara/Python server and try again.
    pause
    exit /b 1
)

echo Solara server is starting at http://127.0.0.1:%PORT%
".venv\Scripts\python.exe" -m solara run app.py --host 127.0.0.1 --port %PORT%
