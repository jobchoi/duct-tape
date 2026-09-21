@echo off
chcp 65001 >nul
setlocal
net session >nul 2>&1
if errorlevel 1 goto NOT_ADMIN
pushd "%~dp0"
if errorlevel 1 goto PATH_FAILED
set "DEPLOY_ROOT=%CD%"
set "STATE_FILE=%TEMP%\Tapbook_State.json"
if not exist "%DEPLOY_ROOT%\Config\HancomKey.txt" goto KEY_MISSING
powershell -NoProfile -ExecutionPolicy Bypass -File "%DEPLOY_ROOT%\Scripts\Test-DeploymentPrerequisites.ps1"
if errorlevel 1 goto FAILED
echo [1/6] 01_GetInfo
powershell -NoProfile -ExecutionPolicy Bypass -File "%DEPLOY_ROOT%\Modules\01_GetInfo.ps1" -StateFile "%STATE_FILE%"
if errorlevel 1 goto FAILED
echo [2/6] 02_CheckOffice
powershell -NoProfile -ExecutionPolicy Bypass -File "%DEPLOY_ROOT%\Modules\02_CheckOffice.ps1" -StateFile "%STATE_FILE%"
if errorlevel 1 goto FAILED
echo [3/6] 03_RemoveOffice
powershell -NoProfile -ExecutionPolicy Bypass -File "%DEPLOY_ROOT%\Modules\03_RemoveOffice.ps1" -StateFile "%STATE_FILE%"
if errorlevel 1 goto FAILED
echo [4/6] 04_InstallOffice
powershell -NoProfile -ExecutionPolicy Bypass -File "%DEPLOY_ROOT%\Modules\04_InstallOffice.ps1" -StateFile "%STATE_FILE%"
if errorlevel 1 goto FAILED
echo [5/6] 05_CheckHancom
powershell -NoProfile -ExecutionPolicy Bypass -File "%DEPLOY_ROOT%\Modules\05_CheckHancom.ps1" -StateFile "%STATE_FILE%"
if errorlevel 1 goto FAILED
echo [6/6] 06_InstallHancom
powershell -NoProfile -ExecutionPolicy Bypass -File "%DEPLOY_ROOT%\Modules\06_InstallHancom.ps1" -StateFile "%STATE_FILE%"
if errorlevel 1 goto FAILED
echo [완료] 설치 단계가 완료되었습니다. 상태 파일: %STATE_FILE%
echo [안내] RebootRequired가 true이면 재부팅하세요. 앱 실행 및 정품 인증을 확인하세요.
popd
pause
exit /b 0

:KEY_MISSING
echo [오류] Config\HancomKey.txt가 없습니다. 예제를 복사하고 실제 키를 입력하세요.
goto FAILED
:FAILED
echo [오류] 작업을 중단했습니다. 앞 단계의 오류 코드와 로컬 Deployment.log를 확인하세요.
popd
pause
exit /b 1
:NOT_ADMIN
echo [오류] 관리자 권한으로 실행하세요.
pause
exit /b 1
:PATH_FAILED
echo [오류] 배포 경로에 접근할 수 없습니다. 공유 폴더 권한을 확인하세요.
pause
exit /b 1
