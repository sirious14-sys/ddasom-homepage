@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".git\index.lock" del /f /q ".git\index.lock"
git add -A
git commit -m "review: yeongju hwaseong blackout curtain 2026-07-22"
git push origin main
echo ===RESULT=== > _push_result.txt
git log --oneline -1 >> _push_result.txt 2>&1
echo --- status --- >> _push_result.txt
git status -s >> _push_result.txt 2>&1
