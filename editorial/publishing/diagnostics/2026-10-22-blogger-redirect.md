# Blogger 리디렉션 오류 점검

2026-10-22. 사용자 제보: phase-1.html이 Googlebot 스마트폰 기준 크롤링 허용이지만 페이지 가져오기 실패/리디렉션 오류로 표시됨. 처음 제공한 링크는 https://m.lealnspire.blogspot.com/2026/06/phase-1.html이다. 이후 제공한 두 주소는 Search Console의 '참조 페이지' 목록이며 상단의 실제 검사 URL은 아직 미확인이다.

## 수행한 읽기 전용 검사

Windows curl의 기본 TLS 검증을 사용했다. 현재 Linux HTTP 환경의 TLS 검증 문제와 실제 공개 페이지 상태를 혼동하지 않았다. Googlebot 형태의 모바일 User-Agent는 실제 Google 크롤러 IP나 Search Console 검사를 대체하지 않는다.

| 대상 | 관측 결과 |
| --- | --- |
| HTTPS 기본 글 | HTTP 200, 리디렉션 없음 |
| HTTPS 기본 글 + 모바일 Googlebot 형태 UA | 302 → 같은 호스트의 ?m=1 → 200 |
| ?m=1 + 같은 모바일 UA | 200, 리디렉션 없음 |
| m.lealnspire.blogspot.com 주소 | TLS 이름 불일치 SEC_E_WRONG_PRINCIPAL, HTTP 응답 전 실패 |
| HTTP 기본 글 | HTTPS 기본 글로 301 한 번 → 200 |
| HTTP 피드 | HTTPS 피드로 301 한 번 → 재확인 결과 200 |
| HTTPS 피드 | 200, 해당 글의 기본 HTTPS 링크 포함 |

- 데스크톱/모바일 HTML의 canonical은 모두 https://lealnspire.blogspot.com/2026/06/phase-1.html이다.
- 모바일 응답의 X-Robots-Tag는 all이며 페이지에서 noindex나 meta refresh를 발견하지 않았다.
- robots.txt는 /search를 제외한 / 크롤링을 허용하고 기본 호스트 sitemap.xml을 가리킨다.
- 사이트맵 URL 20개에 대상 기본 URL이 포함되어 있고 m. 호스트 항목은 없다.
- 공개 글 20편과 피드에서 m.lealnspire.blogspot.com 링크를 발견하지 않았다. 페이지 HTML에서도 해당 호스트를 발견하지 않았다.
- 피드 첫 HTTP 요청은 HTTPS 전환 후 로컬 TLS 단계 실패였으나 직접 HTTPS 및 HTTP 재확인에서 정상 응답했다. 이를 Googlebot의 실패 원인으로 단정하지 않는다.

## 현재 판단

기본 주소의 모바일 리디렉션은 한 번이며 순환/과도한 이동을 재현하지 못했다. 처음 전달한 m. 주소는 별도 TLS 문제가 있지만 이것이 실제 Search Console 검사 주소인지 아직 확인되지 않았다. DNS가 조회된다는 이유로 m. 호스트가 유효한 Blogger 모바일 주소라고 보지 않는다. 현재 관측한 모바일 주소는 기본 호스트의 ?m=1이다.

사용자가 제공한 참조 페이지는 Google이 URL을 발견한 출처를 뜻하며 실패한 검사 URL 자체가 아니다. HTTP 피드가 참조 페이지에 있다는 사실만으로 HTTP 리디렉션 오류라고 판단하지 않는다.

## 이어서 필요한 확인

Search Console 상단 검사 URL, 마지막 크롤링 시각과 '실제 URL 테스트'의 페이지 가져오기 결과를 사용자에게 요청했다. 현재 API 권한은 Blogger이며 Search Console에 로그인해 실제 검사를 실행하거나 색인 요청을 전송하지 않았다.

- 검사 URL이 m. 주소라면 기본 HTTPS 글 주소로 검사/공유 주소를 정리하고 필요한 곳의 잘못된 링크를 수정한다. 인증서 이름 불일치는 글 본문의 리디렉션 코드로 해결할 문제가 아니다.
- 기본 주소의 실제 테스트가 성공하면 최신 결과를 확인하고 필요 시 색인 생성을 요청한다. 성공이 색인/노출을 보장하지는 않는다.
- 기본 주소에서도 실제 테스트가 계속 실패하면 해당 검사 결과/시각/리디렉션 대상과 렌더링 정보를 추가로 확인한다. Blogger의 표준 ?m=1 이동을 무조건 제거하거나 테마를 바꿔 해결됐다고 주장하지 않는다.

블로그 설정/테마/본문/리디렉션/검색 설정은 수정하지 않았다. Search Console 오류 해결 완료나 색인 성공을 확인한 상태가 아니다. 진단 글을 블로그에 업로드하지 않았다.

## 근거

- https://support.google.com/webmasters/answer/9012289?hl=en : 참조 페이지·과거 수집 결과·실제 URL 검사 구분.
- https://support.google.com/webmasters/answer/7440203?hl=en : 리디렉션 오류의 유형.
- https://support.google.com/blogger/answer/9691230?hl=en : Blogger HTTPS 리디렉션 설정.
