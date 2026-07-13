@echo off
REM Daily Covetability data pull (live sources). Registered as a Windows Scheduled Task.
REM Requires the Postgres container to be running (see docker-compose restart policy).
cd /d C:\Users\mikeo\Desktop\covetability\pipeline
if not exist .runtime mkdir .runtime
set EBAY_SOURCE=live
REM Uncomment to include affiliate-feed sources:
REM set SOURCES_CONFIG=sources.json
echo ==== %DATE% %TIME% refresh start ==== >> .runtime\refresh.log
"C:\Users\mikeo\.local\bin\uv.exe" run python -m jobs.refresh >> .runtime\refresh.log 2>&1
echo ==== %DATE% %TIME% refresh end (exit %ERRORLEVEL%) ==== >> .runtime\refresh.log
