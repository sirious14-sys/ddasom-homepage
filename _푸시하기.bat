@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".git\index.lock" del /f /q ".git\index.lock"
if exist ".git\HEAD.lock" del /f /q ".git\HEAD.lock"
echo ===RESULT=== > _push_result.txt
echo [1] add/commit >> _push_result.txt
git add -A >> _push_result.txt 2>&1
git commit -m "site update" >> _push_result.txt 2>&1
echo. >> _push_result.txt
echo [2] push  ← 여기서 실패하면 아래에 이유가 나옵니다 >> _push_result.txt
git push origin main >> _push_result.txt 2>&1
echo PUSH_EXIT_CODE=%errorlevel% >> _push_result.txt
echo. >> _push_result.txt
echo [3] local vs remote >> _push_result.txt
git log --oneline -1 >> _push_result.txt 2>&1
git rev-parse --short origin/main >> _push_result.txt 2>&1
git status -sb >> _push_result.txt 2>&1
echo.
echo ================================
type _push_result.txt
echo ================================
echo.
echo 위 내용을 확인해 주세요. 아무 키나 누르면 닫힙니다.
pause >nul
