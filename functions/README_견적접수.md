# 견적 요청 서버 접수 초안

작성·공식 문서 확인일: 2026-10-08. 현재 **꺼짐**입니다. 배포, 원격 저장소 push, 실제 키 설정, 실제 알림 전송은 하지 않았습니다. `배포.py`와 그 `올릴것` 목록은 변경하지 않았습니다.

## 현재 동작

- `apply.html`의 `#applyForm`은 `data-server-submit="off"`입니다. 추가 스크립트는 즉시 종료하므로 기존 문자 작성·복사·SMS 앱 이동·네이버 `custom001` 흐름이 유지됩니다.
- 서버도 환경변수 `QUOTE_SUBMIT_ENABLED=on`이 있어야 동작합니다. 미설정/off이거나 `QUOTES`가 없으면 HTTP 503과 전화·문자 안내를 반환하며 저장하지 않습니다.
- 두 스위치가 모두 켜지면 기존 문자 초안과 함께 `/api/quote`로 JSON POST를 보냅니다. KV 저장 성공 후 `{ok:true,id}`를 받고 `접수되었습니다(접수번호)`를 표시하며 네이버 `lead`를 보냅니다. 이때 문자 작성 `custom001`은 보내지 않습니다. 전화 클릭 `call`은 기존대로입니다.
- 서버 실패·네트워크 오류·12초 대기 초과 시 접수를 확인하지 못했다는 안내와 전화·문자 연락 안내를 표시합니다. 기존 문자 내용·복사·담당 전화·SMS 주소는 유지합니다. 응답 유실/시간 초과는 서버 미저장을 보장하지 않으므로 다시 신청하면 중복 접수될 수 있습니다.
- 모바일에서 문자 앱으로 전환하는 동안 브라우저가 요청을 중단할 가능성은 있습니다. `keepalive`를 설정했지만 성공 표시가 없으면 접수 여부를 단정하지 않습니다. 실제 기기 검증은 별도로 필요합니다.

## API와 저장

`functions/api/quote.js`는 `/api/quote`에 대응합니다. POST 외에는 405, 잘못된 JSON/입력은 400, 교차 출처는 403, JSON 외 형식은 415, 횟수 초과는 429, 비활성화/KV 오류는 503입니다. 실패 JSON은 `{ok:false,id:null,message:"서버 접수가 어려워요. 전화·문자로 연락 주세요."}`입니다. 응답은 `Cache-Control: no-store`이며 공개 조회 API는 없습니다.

| JSON 필드 | 내용 | 조건/최대 길이 |
| --- | --- | --- |
| `name` | 성함 | 필수, 50자 |
| `tel` | 연락처 | 필수, 입력 20자 이내. 숫자/공백/괄호/하이픈만 허용. 정규화 후 0으로 시작하는 9~11자리 |
| `region` | 시공 지역 | 필수, 30자. apply.html의 31개 지역만 허용 |
| `addr` | 상세 주소 | 선택, 200자 |
| `place` | 실측 장소 | 선택, 50자. 폼의 선택값만 허용 |
| `state` | 공간 상황 | 선택, 50자. 폼의 선택값만 허용 |
| `product` | 제품 | 선택, 50자. 폼의 선택값만 허용 |
| `msg` | 요청사항 | 선택, 2,000자. 줄바꿈 허용 |
| `agree` | 수집·이용 동의 | boolean `true` 필수. 문자열 `"true"`는 거절 |
| `website` | 숨은 honeypot | 비워 둠. 입력이 있으면 거절 |

입력 길이는 JavaScript 문자열 길이 기준이며, 본문은 실제 스트림 기준 16KiB까지 읽습니다. 불필요한 JSON 필드는 버립니다. 전화 소유자 인증 기능은 없습니다.

`QUOTES`에 `quote:<UUID>`로 입력 8개 항목, 동의 여부, 접수번호, 접수 시각, 서버가 결정한 담당 코드/공개 전화번호를 저장합니다. IP 원문, 브라우저 정보, honeypot, 임의 추가 항목은 견적 레코드에 저장하지 않습니다. `expirationTtl:2592000`으로 접수 후 30일에 자동 만료됩니다. 별도 개인정보 로그도 남기지 않습니다. TTL 동작은 [Cloudflare KV 쓰기 API](https://developers.cloudflare.com/kv/api/write-key-value-pairs/)에 근거합니다.

담당 규칙은 폼과 같습니다. 대구 9개 구·군과 경산·구미·김천·청도·칠곡·성주·고령은 정실장 `010-5495-9500`, 나머지 폼의 경북 동부·북부 15개 지역은 이실장 `010-2825-7275`입니다. 클라이언트가 보내는 담당 번호는 신뢰하지 않습니다.

### 스팸 제한의 범위

`CF-Connecting-IP`와 UTC 날짜를 SHA-256으로 변환한 `rate:<해시>` 키에 최근 60초의 요청 시각을 기록하고 4번째 유효 요청을 거절합니다. 이 키는 마지막 기록 후 60초에 만료됩니다. 해시는 익명화 보장이 아닌 단기 가명 식별자입니다. IP가 없는 로컬 요청에는 횟수 제한을 생략하며 임의 `X-Forwarded-For`는 신뢰하지 않습니다. KV가 없으면 접수 자체를 허용하지 않습니다.

KV는 원자적 카운터가 아니므로 동시 요청·다른 데이터센터·캐시 때문에 엄격한 전역 3회 제한을 보장하지 않습니다. UTC 날짜가 바뀌면 해시도 바뀝니다. 같은 키에 대한 쓰기는 초당 1회 제한이 있어 매우 빠른 재요청은 KV 오류 안내로 처리될 수도 있습니다. 이번 초안은 간단한 제한이며, 엄격한 차단이 필요하면 Durable Objects 등 별도 구현을 선택해야 합니다. 근거: [KV 일관성 설명](https://developers.cloudflare.com/kv/concepts/how-kv-works/), [KV 한도](https://developers.cloudflare.com/kv/platform/limits/).

## 켜는 순서 (현재 실행하지 않음)

1. 사장님이 아래 운영 선택사항과 개인정보 문구를 정합니다. 현재 privacy.html의 “서버에 저장하지 않습니다” 설명은 서버 접수와 충돌하므로 **활성화 전에** 고쳐야 합니다.
2. Cloudflare 계정의 Workers KV에서 운영용 namespace를 만듭니다. Preview 테스트를 할 경우 운영과 분리한 namespace를 만듭니다.
3. Workers & Pages → `ddasom` → Settings → Bindings → Add → KV namespace에서 **Variable name `QUOTES`**와 운영 namespace를 연결합니다. Preview에는 분리된 namespace를 연결합니다. 바인딩 변경은 재배포가 필요합니다. [공식 Pages 바인딩 안내](https://developers.cloudflare.com/pages/functions/bindings/).
4. Pages의 해당 환경 변수/Secrets를 설정합니다. 처음에는 `QUOTE_SUBMIT_ENABLED=off`, `NOTIFY_MODE=none`을 유지합니다. 아래 실제 비밀키는 소스/HTML/문서/커밋에 넣지 않습니다.
5. 개인정보처리방침과 폼 안내를 일치시키고, Preview에서 테스트 데이터로 저장·TTL·담당 매핑·성공/실패 문구를 확인합니다. on일 때 폼의 수집 안내는 서버 보유 30일 문구로 바뀝니다. 안내 변경 후 기존 동의에 의존하지 않도록 새로 페이지를 엽니다.
6. 승인된 활성화 작업에서 환경변수 `QUOTE_SUBMIT_ENABLED=on`과 폼 `data-server-submit="on"`을 함께 적용하고 기존 배포 경로로 공개합니다. 이번 작업에서는 어느 설정도 실제로 켜지 않았습니다.
7. 네이버 검색광고 계정에서 `lead`의 의미/목표를 접수 완료로 확인하고 기존 `custom001`과 보고서 집계를 구분합니다. 고객 개인정보/접수번호는 전환 payload에 보내지 않습니다. 광고 차단기·분석 스크립트 로드 실패 시 접수는 성공해도 전환 기록이 없을 수 있습니다.

끄려면 폼을 off로 되돌리고 서버 환경변수도 off로 바꿉니다. 서버 스위치는 브라우저가 on인 기존 페이지를 열고 있어도 저장을 차단합니다. Cloudflare 환경변수 변경 반영에 필요한 재배포도 고려합니다. 이미 저장된 레코드는 원래 TTL대로 만료되며 즉시 삭제가 필요하면 관리자가 KV에서 지웁니다.

### 환경변수와 알림

| 환경변수 | 설정 |
| --- | --- |
| `QUOTE_SUBMIT_ENABLED` | `on`일 때만 서버 저장. 기본은 꺼짐 |
| `NOTIFY_MODE` | `none`(권장 초기값), `email`, `telegram`. 미설정/알 수 없는 값은 none |
| `RESEND_API_KEY` | email용 Secret. 실제 값 미입력 |
| `NOTIFY_EMAIL_FROM` | Resend에서 인증한 발신 주소 |
| `NOTIFY_EMAIL_JEONG`, `NOTIFY_EMAIL_LEE` | 각각 정실장/이실장 수신 이메일 |
| `TELEGRAM_BOT_TOKEN` | telegram용 Secret. 실제 값 미입력 |
| `TELEGRAM_CHAT_ID_JEONG`, `TELEGRAM_CHAT_ID_LEE` | 각각 담당 실장 수신 chat ID |

email은 Resend HTTPS API를 구현했습니다. 다른 이메일 서비스/Cloudflare Email Routing을 쓰려면 별도 어댑터·바인딩을 구현해야 하며 이번 코드가 자동 선택하지는 않습니다. 선택한 모드의 키/발신자/해당 담당 수신처가 없으면 외부 호출 없이 none으로 처리합니다. 근거: [Resend 전송 API](https://resend.com/docs/api-reference/emails/send-email), [Telegram sendMessage](https://core.telegram.org/bots/api#sendmessage).

알림은 KV 저장 후 `waitUntil`에서 실행합니다. **접수번호·지역·담당 공개 정보만** 알리며 고객 성함·연락처·상세 주소·요청사항은 외부 알림 서비스로 보내지 않습니다. 실장은 Cloudflare 관리 화면에서 `quote:<접수번호>`의 값을 확인해야 합니다. `none`이면 알림이 전혀 없으므로 접수 목록을 정기적으로 확인할 담당자가 필요합니다. 공개 관리 화면/실장 로그인 기능은 이번 범위에 없습니다.

알림 실패는 저장 성공을 취소하지 않으며 고정 오류 로그만 남깁니다. 자동 재시도/알림 성공 여부 관리 기능은 없습니다. 활성화 전 수신처와 확인 담당자를 모두 정해야 합니다. 외부 알림 메시지와 기존 휴대폰 문자는 KV TTL로 삭제되지 않으므로 별도의 보유/삭제 규칙을 정합니다.

### `배포.py`의 `올릴것`에 `functions` 추가가 필요한가?

**현재 배포 방식에서는 필요하지 않습니다.** Cloudflare 공식 [Direct Upload의 Functions 설명](https://developers.cloudflare.com/pages/get-started/direct-upload/#functions)은 Wrangler 명령을 실행한 위치에 `functions`가 있으면 프로젝트와 함께 처리한다고 명시합니다. 대시보드 drag-and-drop은 `functions` 컴파일을 지원하지 않습니다.

현재 `배포.py`는 정적 파일만 임시 dist에 담고, `cwd=str(ROOT)`에서 `wrangler pages deploy <dist>`를 실행합니다. 따라서 ROOT의 `functions/api/quote.js`는 정적 파일 허용 목록과 별개로 Wrangler가 발견할 수 있습니다. 이 판단은 공식 문서와 스크립트 분석이며, 이번에 실제 Wrangler 배포를 실행해서 확인한 것은 아닙니다.

**이 초안을 둔 채 다음 일반 배포를 하면 폼이 off여도 Functions 코드가 함께 배포될 수 있습니다.** 서버의 별도 off 스위치가 저장/알림을 막습니다. 루트 functions 자동 처리로 인해 “올릴것만 업로드”라는 기존 설명에는 Functions 예외가 생깁니다. 사장님은 다음 배포 전에 이 예외를 인지해야 합니다. Functions를 배포에서 완전히 제외하려면 별도의 배포 경로 변경 작업이 필요합니다.

`"functions"`를 정적 파일 목록에 무작정 추가하면 소스와 내부 README/테스트 문서를 dist에 복사할 수 있으므로 추가하지 않습니다. 테스트는 `tests/`에 있으며 배포 목록 밖입니다. Functions 라우팅과 `_routes.json` 자동 생성은 [공식 Routing 문서](https://developers.cloudflare.com/pages/functions/routing/)를 참고하고, 실제 빌드에서 API만 Functions를 호출하는지 확인합니다. 현재 배포 목록/스크립트는 한 바이트도 수정하지 않았습니다.

## 개인정보처리방침에 반영할 문장 초안

현재 방침의 1항 “서버에 저장하지 않습니다” 박스/수집 방법/보유 기간을 아래 내용으로 교체하고, 2항의 “실제 접수 여부는 측정하지 않음”과 전환 측정 설명도 서버 접수 성공 측정을 포함하도록 고칩니다. 이는 활성화 시 사용할 초안이며 현재 방침 파일 자체는 변경하지 않았습니다.

> 따솜커튼블라인드는 견적 상담과 방문 예약 안내를 위해 성함, 연락처, 시공 지역, 개인정보 수집·이용 동의 여부를 필수로 수집합니다. 고객이 입력한 상세 주소, 실측 장소, 공간 상황, 문의 제품, 요청사항은 선택적으로 수집합니다. 서버 접수 시 접수번호와 접수 시각을 함께 기록합니다. 서버에 저장된 견적 요청은 접수일로부터 30일간 보유한 뒤 자동 삭제합니다. 개인정보 수집·이용 동의를 거부할 수 있으며, 거부하면 서버 견적 접수를 이용할 수 없습니다. 전화 또는 문자로 상담을 요청할 수 있습니다.

> 견적 요청의 서버 처리 및 보관은 Cloudflare, Inc.에 위탁합니다. 알림 서비스를 이용하는 경우 [실제로 선택한 Resend 또는 Telegram의 계약상 수탁사명]에 접수 알림 전송을 위탁합니다. 알림에는 접수번호, 시공 지역, 담당자 공개 정보만 포함하며 고객 성함, 연락처, 상세 주소와 요청사항은 보내지 않습니다. 동의 철회·삭제 요청은 따솜 상담 전화(정실장 010-5495-9500, 이실장 010-2825-7275)로 연락해 주십시오.

> 스팸 방지를 위해 접속 IP 주소를 요청 처리 중 사용하며, IP와 날짜로 만든 해시 식별자 및 요청 시각을 마지막 기록 후 60초까지 저장합니다. IP 원문은 견적 요청 레코드에 저장하지 않습니다. 담당 실장에게 별도로 보낸 휴대폰 문자와 외부 알림은 서버의 자동 삭제와 별개로 관리합니다.

`[ ]` 부분은 실제 서비스 선택에 맞게 완성하거나 `none`이면 알림 위탁 문장을 빼야 합니다. 국외 처리에 대한 현 방침의 Microsoft 설명만으로 Cloudflare 등의 처리를 설명할 수는 없습니다. 실제 계약·처리 국가·이전 항목/목적/시점/방법/보유 및 권리 행사 안내를 확정해 추가하고, 외부 알림·문자 보유 규칙도 확정합니다. 국내 저장만을 보장하는 문구는 쓰지 않습니다. 참고: [KV 데이터 위치](https://developers.cloudflare.com/kv/reference/data-location/), [Cloudflare 처리 계약](https://www.cloudflare.com/cloudflare-customer-dpa/). 개인정보 문구 확정 전에는 활성화하지 않습니다.

## 비용과 무료 한도 확인

2026-10-08 확인 결과입니다. 한도는 계정의 다른 사용량과 공유될 수 있으며 실제 요금제는 계정에서 확인합니다.

| 서비스 | 확인한 무료 한도/요금 | 공식 출처 |
| --- | --- | --- |
| Pages Functions | Workers Free와 합산 하루 100,000 요청. Functions가 실행되지 않는 정적 자산 요청은 무료·무제한 | [Pages Functions 가격](https://developers.cloudflare.com/pages/functions/pricing/) |
| Workers KV | 읽기 하루 100,000키, 쓰기/삭제 각각 하루 1,000키, 목록 조회 하루 1,000회, 저장 1GB. 무료 한도 초과 시 해당 작업 실패, UTC 00시에 일일 한도 초기화 | [KV 가격](https://developers.cloudflare.com/kv/platform/pricing/) |
| Resend | Free 월 3,000통, 하루 100통, 월 $0. 유료 Pro 월 $20에 50,000통(별도 초과요금) | [Resend 가격](https://resend.com/pricing) |
| Telegram Bot API | 기본 메시지 무료. 한 chat에 초당 약 1개, 그룹 분당 20개, 대량 알림 초당 약 30개 제한. 유료 broadcast 미사용 | [Telegram Bots FAQ](https://core.telegram.org/bots/faq#my-bot-is-hitting-limits-how-do-i-avoid-this) |

IP가 있는 정상 접수 1건은 대략 KV 읽기 1회 + 쓰기 2회(횟수 키와 접수 키)입니다. 이 코드만 사용하고 다른 KV 쓰기가 없다고 가정하면 무료 쓰기 한도 기준 **하루 약 500건**이며, 관리 작업/다른 서비스 사용량에 따라 줄어듭니다. 알림 없음 모드는 외부 발송 비용이 없습니다. Telegram은 본 초안의 일반 Bot API `sendMessage`만 사용하며 유료 broadcast 옵션은 요청하지 않습니다. 발송 제한은 [공식 Bots FAQ](https://core.telegram.org/bots/faq#my-bot-is-hitting-limits-how-do-i-avoid-this)를 확인합니다. 서비스 요금·한도는 바뀔 수 있으므로 활성화 시 다시 확인합니다.

## 사장님이 정할 것

1. 서버 접수를 언제 켤지, 30일 보유와 개인정보처리방침/위탁·국외 처리 문구를 확정할지.
2. 알림 방식(none/email/telegram), 실장별 수신처, 접수 목록을 확인할 담당자와 확인 주기.
3. 외부 알림과 휴대폰 문자 보유/삭제 규칙, Cloudflare 접근 권한을 줄 담당자.
4. 무료 한도 안에서 운영할지, 엄격한 스팸 차단/알림 재시도/중복 접수 방지가 추가로 필요한지.
5. 다음 일반 배포에 Functions가 포함되는 예외를 수용할지. 목록 변경 없이 자동 포함되는 현재 Wrangler 방식을 숙지해야 합니다.

테스트 실행법과 실제 확인 범위는 [_테스트결과.md](./_테스트결과.md)에 정리했습니다.
