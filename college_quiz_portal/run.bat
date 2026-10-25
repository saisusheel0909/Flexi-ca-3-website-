@echo off
title CampusQuiz - College Assessment Portal
echo ================================================================
echo       CampusQuiz - College Assessment & Evaluation Portal
echo ================================================================
echo.
echo [1/2] Initializing Database and Checking Tables...
python database.py
echo.
echo [2/2] Opening Web Browser at http://127.0.0.1:5000 ...
start http://127.0.0.1:5000
echo.
echo Server running! Press Ctrl+C in this window to stop the server.
echo ================================================================
python app.py
pause
