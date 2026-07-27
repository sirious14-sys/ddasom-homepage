@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".git\index.lock" del /f /q ".git\index.lock"
if exist ".git\HEAD.lock" del /f /q ".git\HEAD.lock"
git add -A
git commit -m "site update"
git push origin main
echo ===RESULT=== > _push_result.txt
git log --oneline -1 >> _push_result.txt 2>&1
echo --- status --- >> _push_result.txt
git status -s >> _push_result.txt 2>&1
echo.
echo 푸시 완료. 아무 키나 누르면 닫힙니다.
pause >nul
