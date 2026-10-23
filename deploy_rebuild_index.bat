@echo off
setlocal

set SERVER=opc@130.61.84.155
set KEY=%USERPROFILE%\.ssh\oracle-6gb.key
set REMOTE=%SERVER%:/home/opc/marketing_multibot_telegram
set SSH=ssh -i "%KEY%" -o StrictHostKeyChecking=no %SERVER%
set SCP=scp -i "%KEY%" -o StrictHostKeyChecking=no -r

echo ============================================================
echo   Rebuild Vector Index ^| %SERVER%
echo ============================================================

echo.
echo [1/3] Copying data and vector_faq...
%SCP% data %REMOTE%/
%SCP% src\multibot\core\vector_faq.py %SERVER%:/home/opc/marketing_multibot_telegram/src/multibot/core/vector_faq.py

echo.
echo [2/3] Exporting existing Q^&A and rebuilding vector index...
%SSH% "cd /home/opc/marketing_multibot_telegram && .venv/bin/python data/building_bot/export_learned.py"
%SSH% "cd /home/opc/marketing_multibot_telegram && .venv/bin/python data/building_bot/build_vector_kb.py"

echo.
echo [3/3] Restarting multibot...
%SSH% "sudo systemctl restart multibot"
timeout /t 3 /nobreak >nul
%SSH% "sudo systemctl is-active multibot"

echo.
echo ============================================================
echo   Done! Vector index rebuilt.
echo ============================================================
endlocal
