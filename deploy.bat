@echo off
setlocal

set SERVER=opc@130.61.84.155
set KEY=%USERPROFILE%\.ssh\oracle-6gb.key
set REMOTE=%SERVER%:/home/opc/marketing_multibot_telegram
set SSH=ssh -i "%KEY%" -o StrictHostKeyChecking=no %SERVER%
set SCP=scp -i "%KEY%" -o StrictHostKeyChecking=no -r

echo ============================================================
echo   Multibot Deploy ^| %SERVER%
echo ============================================================

echo.
echo [1/3] Copying files...
%SCP% src         %REMOTE%/
%SCP% bots        %REMOTE%/
%SCP% admin       %REMOTE%/
%SCP% scraper     %REMOTE%/
%SCP% tests       %REMOTE%/
%SCP% main.py     %SERVER%:/home/opc/marketing_multibot_telegram/main.py
%SCP% requirements.txt %SERVER%:/home/opc/marketing_multibot_telegram/requirements.txt

echo.
echo [2/3] Installing dependencies...
%SSH% "cd /home/opc/marketing_multibot_telegram && .venv/bin/pip install -r requirements.txt -q"

echo.
echo [3/3] Restarting services...
%SSH% "sudo systemctl restart multibot multibot-admin"
timeout /t 5 /nobreak >nul
%SSH% "sudo systemctl is-active multibot multibot-admin"

echo.
echo ============================================================
echo   Done!
echo   Admin:  http://130.61.84.155:8600
echo   Logs:   ssh -i "%KEY%" %SERVER% "journalctl -u multibot -f"
echo ============================================================
endlocal
