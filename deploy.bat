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
%SCP% data        %REMOTE%/
%SCP% agents      %REMOTE%/
%SCP% .env.production %SERVER%:/home/opc/marketing_multibot_telegram/.env
%SCP% scraper\base.py          %SERVER%:/home/opc/marketing_multibot_telegram/scraper/base.py
%SCP% scraper\http_scraper.py  %SERVER%:/home/opc/marketing_multibot_telegram/scraper/http_scraper.py
%SCP% scraper\__init__.py      %SERVER%:/home/opc/marketing_multibot_telegram/scraper/__init__.py
%SCP% scraper\__main__.py      %SERVER%:/home/opc/marketing_multibot_telegram/scraper/__main__.py
%SCP% scraper\adapters         %SERVER%:/home/opc/marketing_multibot_telegram/scraper/
%SCP% scraper\categories       %SERVER%:/home/opc/marketing_multibot_telegram/scraper/
%SCP% tests       %REMOTE%/
%SCP% main.py     %SERVER%:/home/opc/marketing_multibot_telegram/main.py
%SCP% requirements.txt %SERVER%:/home/opc/marketing_multibot_telegram/requirements.txt

echo.
echo [1b/3] Deploying facebook-scraper service...
%SCP% facebook-scraper.service %SERVER%:/home/opc/marketing_multibot_telegram/facebook-scraper.service
%SSH% "sudo cp /home/opc/marketing_multibot_telegram/facebook-scraper.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable facebook-scraper"

echo.
echo [1c/3] Syncing .env.production to /etc/multibot.env...
%SCP% .env.production %SERVER%:/home/opc/marketing_multibot_telegram/.env.production
%SCP% sync_env.py %SERVER%:/home/opc/marketing_multibot_telegram/sync_env.py
%SSH% "cd /home/opc/marketing_multibot_telegram && python3 sync_env.py && sudo cp /tmp/multibot_new.env /etc/multibot.env && rm sync_env.py && echo Done"

echo.
echo [2/3] Installing dependencies...
%SSH% "cd /home/opc/marketing_multibot_telegram && .venv/bin/pip install -r requirements.txt -q"
%SSH% "cd /home/opc/marketing_multibot_telegram && .venv/bin/python -m playwright install chromium 2>/dev/null || true"

echo.
echo [3/3] Restarting services...
%SSH% "sudo systemctl restart multibot multibot-admin facebook-scraper"
timeout /t 5 /nobreak >nul
%SSH% "sudo systemctl is-active multibot multibot-admin facebook-scraper"

echo.
echo ============================================================
echo   Done!
echo   Admin:  http://130.61.84.155:8600
echo   Logs:   ssh -i "%KEY%" %SERVER% "journalctl -u multibot -f"
echo ============================================================
endlocal
