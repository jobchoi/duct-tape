# Office LTSC 설치 파일 위치

이 폴더에 실제 설치 파일과 설정을 준비합니다.

- `setup.exe`: Microsoft Office Deployment Tool 실행 파일.
- `install.xml`: 구매한 Office LTSC 2024 제품과 정품 인증 방식에 맞춘 설정. MAK 키는 Product의 PIDKEY에 입력합니다.
- `remove.xml`: 기존 Office 제거 설정.
- 정식 Office 설치 원본: ODT 다운로드/설치 설정에 맞는 전체 파일.

현재 프로그램의 설치 판별은 Office LTSC Professional Plus 2024를 기준으로 합니다. Standard 라이선스라면 제품 ID와 설치 판별도 맞춰야 합니다. 2021 키는 2024 설정에 혼용하지 않습니다.

이 안내 파일만 Git에 포함합니다. 실제 키·XML·실행 파일·설치 원본은 Git에서 제외하지만 로컬 실행과 서버 매체 전달에는 사용합니다. 안내 파일만 있는 상태에서는 셋업 준비가 완료되지 않습니다.

[배포 가이드](../docs/wiki/Deployment-Guide.md)
