@echo off
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Scripts\diagnostics\Collect-ClientDiagnostics.ps1"
if errorlevel 1 goto FAILED
echo.
echo [완료] 표시된 report.json 파일을 확인하세요.
pause
exit /b 0
:FAILED
echo [오류] 진단을 완료하지 못했습니다. 관리자 권한으로 다시 실행하세요.
pause
exit /b 1
