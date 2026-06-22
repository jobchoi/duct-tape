@echo off
:: CMD 창을 UTF-8 모드로 강제 전환하여 한글 깨짐 완벽 방지
chcp 65001 >nul
setlocal

:: 1. 관리자 권한 확인 (괄호 구조를 안전하게 변경)
net session >nul 2>&1
if errorlevel 1 goto NOT_ADMIN
goto ADMIN_OK

:NOT_ADMIN
echo [경고] 관리자 권한으로 실행해주세요! (우클릭 - 관리자 권한으로 실행)
pause
exit /b

:ADMIN_OK
:: 2. 네트워크(UNC) 경로 및 USB 실행 지원
pushd "%~dp0"
set "DEPLOY_ROOT=%CD%"
set "STATE_FILE=%TEMP%\Tapbook_State.json"

echo ==========================================
echo     학교 탭북 유지보수 자동화 시스템 v1.0
echo ==========================================
echo.

:: --- [1단계] 기기 정보 수집 ---
echo [1/7] 기기 정보 수집 중...
powershell -NoProfile -ExecutionPolicy Bypass -File "%DEPLOY_ROOT%\Modules\01_GetInfo.ps1" -StateFile "%STATE_FILE%"

if errorlevel 1 (
    echo [오류] 정보 수집 중 문제가 발생했습니다. 작업을 중단합니다.
    pause
    popd
    exit /b
)

:: --- [2단계] Office 상태 판별 ---
echo.
echo [2/7] Office 설치 상태를 확인하는 중...
powershell -NoProfile -ExecutionPolicy Bypass -File "%DEPLOY_ROOT%\Modules\02_CheckOffice.ps1" -StateFile "%STATE_FILE%"

if errorlevel 1 (
    echo [오류] Office 판별 중 문제가 발생했습니다.
    pause
    popd
    exit /b
)

echo.
echo [성공] 1단계, 2단계 완료! 상태 파일: %STATE_FILE%


:: (앞부분 생략 - 2단계 코드 아래에 이어서 추가)

:: --- [3단계] 기존 Office 완벽 삭제 ---
echo.
echo [3/7] 기존 Office를 삭제하는 중...
powershell -NoProfile -ExecutionPolicy Bypass -File "%DEPLOY_ROOT%\Modules\03_RemoveOffice.ps1" -StateFile "%STATE_FILE%"

if errorlevel 1 (
    echo [오류] Office 삭제 중 문제가 발생했습니다.
    pause
    popd
    exit /b
)


echo.
echo [성공] 3단계 삭제 완료! 상태 파일: %STATE_FILE%

:: --- [4단계] Office LTSC 2024 설치 ---
echo.
echo [4/7] Office LTSC 2024를 설치하는 중... (화면에 아무 창도 뜨지 않으니 기다려주세요.)
powershell -NoProfile -ExecutionPolicy Bypass -File "%DEPLOY_ROOT%\Modules\04_InstallOffice.ps1" -StateFile "%STATE_FILE%"

if errorlevel 1 (
    echo [오류] Office 설치 중 문제가 발생했습니다.
    pause
    popd
    exit /b
)

echo [성공] 4단계 삭제 완료! 상태 파일: %STATE_FILE%

:: --- [5단계] 한컴오피스 설치 여부 확인 ---
echo.
echo [5/7] 한컴오피스 설치 상태를 확인하는 중...
powershell -NoProfile -ExecutionPolicy Bypass -File "%DEPLOY_ROOT%\Modules\05_CheckHancom.ps1" -StateFile "%STATE_FILE%"


:: --- [6단계] 한컴오피스 자동 설치 ---
echo.
echo [6/7] 한컴오피스 설치 중... (기다려주세요)
powershell -NoProfile -ExecutionPolicy Bypass -File "%DEPLOY_ROOT%\Modules\06_InstallHancom.ps1" -StateFile "%STATE_FILE%"

if errorlevel 1 (
    echo [오류] 한컴 설치 실패. 작업을 중단합니다.
    pause
    popd
    exit /b
)

:: --- [7단계] 완료 보고 및 로그 기록 ---
echo [%date% %time%] 한컴오피스 설치 완료 >> "%DEPLOY_ROOT%\Logs\InstallLog.txt"
echo [7/7] 모든 작업이 완료되었습니다. 창을 닫아도 좋습니다.
pause

popd
pause