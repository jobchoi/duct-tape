# duct-tape Wiki

학교 Windows 기기 20~50대의 Office LTSC 2024 및 한컴오피스 2024 배포 자동화입니다. FastAPI 중앙 관제와 GAS 미러링 코어의 로컬 검증을 완료했으며 실제 GAS/Windows 인수 검증을 준비합니다.

- [[Modules-Specification]]: 모듈별 입력·처리·출력·실패 계약
- [[GAS-Mirroring]]: GAS 배포 설정 및 현장 테스트 체크리스트
- [[Central-Monitoring]]: FastAPI 서버·클라이언트 설정 및 중앙 대시보드
- [[Deployment-Guide]]: 매체 준비, 실행, 로그, 검증

이 디렉터리의 모든 Markdown 파일을 GitHub Wiki 저장소 루트에 같은 이름으로 복사하면 됩니다. 페이지 링크는 Wiki 문법을 사용하므로 경로 수정이 필요 없습니다. 이번 작업은 문서 준비만 수행하며 Wiki 원격 게시·인증 설정은 수행하지 않습니다.

브랜치 운영: main은 검증된 배포본, develop은 통합, feature/*는 Phase별 작업입니다. 현재 Phase 4 작업 브랜치는 feature/phase-4-gas-mirroring이며 코어 보완 커밋은 2067162입니다.
