# 라즈베리파이 서버 운영 방향

## 권장 구성

라즈베리파이가 FastAPI 웹/API, SQLite 작업 큐·진행 이력, 설치 원본 전달을 담당한다. Windows PC의 에이전트가 실제 Office·한컴 설치를 실행한다. 파이에 Windows 설치 파일을 실행할 필요는 없다.

기존과 같은 Tailscale 네트워크에 파이를 연결하고 Tailscale Serve로 127.0.0.1:8000을 HTTPS로 전달하는 구성이 우선이다. 관리자/클라이언트 화면과 API를 같은 주소로 제공하므로 현재 세션·요청 구조를 유지할 수 있다.

```text
Windows PC (Tailscale + 에이전트)
    → 파이의 HTTPS 주소 (Tailscale Serve)
    → FastAPI / SQLite / 설치 원본
```

현재 WSL 서버를 옮기는 것이며 WSL 전용 Windows localhost 전달 단계는 파이에서는 필요 없다. OS가 바뀌므로 `.venv`를 복사하지 않고 파이에서 Python 환경과 requirements를 새로 설치한다. ARM64 의존성 설치는 해당 OS/Python 버전에서 확인한다.

## 준비 순서

1. 파이에 64비트 Raspberry Pi OS와 Python 3.11 이상을 준비한다.
2. 저장소 코드와 Git 제외된 실제 키·설치 원본을 구분해 옮긴다. 실제 키/원본을 GitHub에 올리지 않는다.
3. 파이에서 가상환경을 새로 만들고 Server/requirements.txt를 설치한다.
4. `.env`의 운영 인증·DB 경로와 배포 원본 루트를 설정한다. 기존 등록을 이전할 때 서버를 중지한 일관된 SQLite 백업과 기존 인증 정보를 함께 관리한다.
5. FastAPI를 127.0.0.1:8000으로 실행하고 파이에 Tailscale을 설치·연결한다.
6. `sudo tailscale serve --bg http://127.0.0.1:8000`으로 HTTPS 주소를 만든다.
7. 새 주소에서 받은 최신 실행 도구로 클라이언트를 연결한다. 서버 주소가 바뀌므로 기존 바로가기/에이전트 설정도 반영해야 한다.
8. 시스템 서비스 자동 시작·권한·DB 백업을 구성하고 Windows 테스트 PC 1대에서 연결/매체 전송/설치를 검증한다.

## 저장 공간과 성능

설치 원본, ZIP 임시 파일, DB는 파이의 로컬 SSD에 두는 구성을 권장한다. 현재 한컴 원본은 약 1.08GB이며 클라이언트는 다운로드·압축 해제·배치 공간이 필요하다.

현재 서버는 매체 요청마다 임시 ZIP을 만든다. 여러 PC 동시 다운로드의 CPU·디스크·네트워크 사용량은 실제 파이에서 측정해야 한다. 임시 ZIP이 RAM 기반 /tmp에 몰리지 않도록 SSD의 쓰기 가능한 임시 폴더를 만들고 서비스 실행 환경에 TMPDIR을 지정한다. 대규모 배포 전 ZIP 캐시/전송 제한은 별도 검토한다. SQLite DB를 SMB 공유폴더에 두지 않는다.

## GitHub Pages의 역할

GitHub Pages는 정적 HTML/CSS/JS 호스팅이다. Python/FastAPI 실행과 SQLite 작업 큐·인증 API를 대신하지 않는다. 현재 프로그램을 Pages로 옮기더라도 별도의 API 서버는 필요하다.

Pages는 공개 사용 설명서나 소개 페이지에 사용할 수 있다. 현재 운영 화면까지 분리하면 API 주소, CORS/CSP, 쿠키 인증 정책을 다시 설계해야 하므로 기본 운영 구성에는 추가하지 않는다. 실제 키·기관 설치 매체를 Pages에 게시하지 않는다.

## 클라이언트 Tailscale

서로 다른 네트워크에서 현재 방식으로 접속하려면 파이와 PC를 같은 tailnet에 연결한다. 같은 LAN 전용 운영은 클라이언트 Tailscale 없이도 설계할 수 있으나 현재 설치 도구는 HTTPS를 요구하므로 LAN HTTPS 주소와 인증 설정을 맞춰야 한다. 공개 인터넷 배포는 별도 운영 보안 검토 대상이다.

## 공식 참고

- [GitHub Pages 설명](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)
- [Tailscale Linux 설치](https://tailscale.com/docs/install/linux)
- [Tailscale Serve](https://tailscale.com/docs/reference/tailscale-cli/serve)
- [Raspberry Pi 외부 저장 장치](https://www.raspberrypi.com/documentation/computers/configuration.html)

이 문서는 운영 계획이다. 실제 파이에 배포하거나 ARM64 설치·성능을 검증한 상태는 아니다.
