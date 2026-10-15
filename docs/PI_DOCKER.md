# Pi 5 Docker 배포

기준: 2026-10-15. Pi 호스트에 Tailscale을 설치하고 Serve로 HTTPS를 제공한다. Nginx 정적 페이지·File Browser와 별도로 FastAPI 앱을 실행한다. Windows 설치기는 Pi에서 실행하지 않는다.

## 기존 Compose 수정

~/my-server/docker-compose.yml의 File Browser ports를 기본 설정 기준 "8080:80"으로 변경한다. settings.json에서 실제 수신 포트를 별도로 바꿨다면 해당 포트와 일치시킨다. version: '3'은 최신 Compose에서 불필요하다.
기존 File Browser DB/settings 파일은 유지한다. 없는 파일을 bind mount하면 디렉토리로 생성될 수 있으므로 실제 파일인지 확인한다. 기존 서비스 전체를 down할 필요 없이 docker compose up -d fileserver로 변경한다.
Nginx의 html과 File Browser의 storage에는 앱 DB·.env·제품 키를 넣지 않는다. 우리 서비스의 데이터/매체 디렉토리를 별도로 둔다.

## 디렉토리와 환경

```text
~/my-server/
  docker-compose.yml          # 기존 Nginx/File Browser
  compose.duct-tape.yml        # 저장소 deploy/compose.pi.yml을 복사
  duct-tape/                  # 최신 코드, Dockerfile, .env
  duct-data/                  # SQLite 영속 보관
  duct-temp/                  # 배포 ZIP 임시 공간, SSD 권장
  duct-uploads/               # 관리자 업로드 영속 보관
  deployment/
    Office/                   # setup.exe, install.xml, remove.xml 및 원본
    Hancom/                   # Install/Hwp130.msi 등 전체 원본
    Config/
      HancomKey.txt
      OfficeKey.txt
```

코드는 최신 develop 검증 커밋 또는 확정한 태그를 사용한다. WSL의 아직 push되지 않은 변경은 Pi의 git pull에 포함되지 않는다. DB를 새로 시작하면 기존 PC 승인을 다시 받아야 한다. 기존 DB를 이전한다면 활성 작업 종료 후 서버를 멈추고 SQLite 백업으로 일관성을 확보한다. v1/v2 DB를 공유하지 않는다.

Pi의 duct-tape/.env에는 DUCT_REPORT_TOKEN, DUCT_READ_TOKEN, DUCT_ADMIN_TOKEN을 서로 다른 ASCII 32자 이상 값으로 설정한다. 공개 예제나 채팅에 실제 키를 넣지 않는다. 기존 WSL 전용 DUCT_SCHOOLS_PATH 등은 Pi에서 사용할 경로로 검토한다. 매체/DB 경로는 Compose가 컨테이너 경로로 지정한다. 이 예제는 별도 GAS 기관 레지스트리를 마운트하지 않는다.

Dockerfile과 .dockerignore는 원본 매체·라이선스·.env·DB를 이미지에 넣지 않고 공개 실행 도구와 서버만 포함한다. 초기 이미지는 python:3.13-slim이며 운영 검증 후 이미지 digest를 고정할 수 있다. Pi는 64비트 OS/ARM64 Docker 환경을 확인한다.

## 실행

아래는 최신 파일과 .env, 정식 원본을 Pi에 준비한 다음 실행한다.

```bash
cd ~/my-server
cp duct-tape/deploy/compose.pi.yml compose.duct-tape.yml
mkdir -p duct-data duct-temp duct-uploads deployment/Office deployment/Hancom deployment/Config
chmod 600 duct-tape/.env
docker compose -f compose.duct-tape.yml config --quiet
docker compose -f compose.duct-tape.yml up -d --build
docker compose -f compose.duct-tape.yml ps
docker compose -f compose.duct-tape.yml logs --tail=80 duct-tape
curl -f http://127.0.0.1:8000/api/config
```

8000이 다른 프로세스에서 사용 중이면 먼저 충돌을 해소한다. File Browser는 8080으로 옮기며 앱은 Pi loopback:8000에만 공개한다. proxy header 신뢰는 이 loopback/Tailscale 프록시 전제에서 사용한다. 포트를 모든 인터페이스에 공개하면서 그대로 신뢰 설정을 유지하지 않는다.

Pi의 Tailscale 로그인/연결 후 호스트에서 실행:

```bash
sudo tailscale serve --bg http://127.0.0.1:8000
tailscale serve status
```

출력된 **Pi 자신의 HTTPS 주소**의 /admin 및 /client를 사용한다. 기존 Windows 서버의 ts.net 주소와 다르다. HTTPS /client에서 에이전트 ZIP을 받고 Config/ServerUrl.txt가 Pi의 HTTPS 기본 주소인지 확인한다. 컨테이너 내부 IP나 localhost 주소를 클라이언트에 등록하지 않는다. proxy header 처리를 포함해 실제 HTTPS 경로에서 ZIP 주소 생성까지 확인해야 한다.

## 업데이트와 검증

업데이트는 설치 작업 종료 후 최신 코드를 반영하고 같은 Compose up -d --build를 실행한다. Git 제외 매체·환경·DB는 git pull로 전송되지 않는다. Docker DB 볼륨을 삭제하거나 down -v를 실행해 복구하려 하지 않는다.

확인: healthcheck, HTTPS 화면/로그인, 새 에이전트 ZIP, PC 등록/승인, 관리자 요청→에이전트 실행→동일 작업 ID 완료 보고, UTF8 로그. 설치 후 앱 실행과 정품 인증은 별도로 확인한다. Docker 로그는 서버 로그이며 Windows 상세 로그는 클라이언트에 있다.

현재 작업 환경에는 Docker CLI가 없어 이미지 빌드/Compose 실행/Pi ARM64 실장 시험은 수행하지 못했다. 로컬 서버/API 및 패키지 검증 결과와 실제 Pi 검증을 구분한다.
로컬 검증: 앱 원본/작업 큐 Python 회귀 테스트 14개 통과. Dockerfile 복사 구조로 에이전트 ZIP을 생성하고 필수 파일·HTTPS 주소·키 제외를 확인했다.

공식 참고: [Compose version](https://docs.docker.com/reference/compose-file/version-and-name/), [File Browser Docker 포트/볼륨](https://github.com/filebrowser/filebrowser/blob/master/docs/installation.md).
