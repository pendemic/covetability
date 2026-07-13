@echo off
REM Weekly Google Trends pull (pytrends). Registered as a Windows Scheduled Task.
REM Requires the Postgres container to be running.
cd /d C:\Users\mikeo\Desktop\covetability\pipeline
if not exist .runtime mkdir .runtime
set TRENDS_SOURCE=pytrends
echo ==== %DATE% %TIME% trends start ==== >> .runtime\trends.log
"C:\Users\mikeo\.local\bin\uv.exe" run python -m jobs.weekly_trends >> .runtime\trends.log 2>&1
echo ==== %DATE% %TIME% trends end (exit %ERRORLEVEL%) ==== >> .runtime\trends.log
