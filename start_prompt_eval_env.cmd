@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -NoExit -Command ". '%SCRIPT_DIR%start_prompt_eval_env.ps1' %*"

endlocal
