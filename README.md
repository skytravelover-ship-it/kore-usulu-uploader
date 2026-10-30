# 인스타 자동 업로드 (@kore.usulu.annelik)

정해진 시간에 카드뉴스 캐러셀을 인스타그램 공식 API로 올리고, 첫 댓글까지 답니다.
GitHub Actions가 30분마다 확인하므로 Mac이 꺼져 있어도 올라갑니다.

## 구성
| 파일 | 역할 |
|---|---|
| `posts.json` | 게시 일정. `launch_date`(런칭일)와 각 게시물의 `day`(런칭일로부터 며칠 뒤)·`time`(터키 시간) |
| `posts/<id>/01.jpg…` | 올릴 이미지 (JPEG, 1080×1350) |
| `posts/<id>/caption.txt` | 캡션 |
| `posts/<id>/comment.txt` | 게시 직후 다는 첫 댓글 (고정은 앱에서 직접) |
| `build_posts.py` | 카드 PNG → JPEG 변환 (카드를 다시 렌더링한 뒤 실행) |
| `publish.py` | 시간이 된 게시물 업로드. `state.json`에 기록해 두 번 올리지 않음 |
| `.github/workflows/publish.yml` | 30분마다 `publish.py` 실행 |

현재 일정 (런칭일 = 0일, 터키 시간):
| id | 카드 | 날짜 | 시간 |
|---|---|---|---|
| 01-joriwon | A. 산후조리원 | 0일 | 20:00 |
| 02-geumjul | B. 금줄 vs 40일 | 0일 | 20:45 |
| 03-hamile | C. 임산부 7가지 | 0일 | 21:30 |
| 04-destek | D. 출산 지원금 | 1일 | 20:30 |
| 05-doljabi | E. 돌잡이 | 7일 | 20:30 |

## 처음 한 번만 하는 설정 (직접 해야 하는 단계)
비밀번호 입력, 계정 생성, 앱 권한 승인은 본인이 해야 합니다.

1. **인스타 계정 만들기 → 프로페셔널 계정으로 전환**
   설정 → 계정 유형 → 프로페셔널(크리에이터 또는 비즈니스). API 게시는 프로페셔널 계정만 됩니다.
2. **Meta 개발자 앱 만들기** (developers.facebook.com)
   - 앱 만들기 → 유형 "비즈니스"
   - 제품 추가: **Instagram API (Instagram 로그인 방식)**
   - 권한: `instagram_business_basic`, `instagram_business_content_publish`, `instagram_business_manage_comments`
   - 내 인스타 계정을 연결하고 **액세스 토큰 생성**을 누르면 장기 토큰(60일)과 인스타 사용자 ID가 나옵니다.
   - 내 계정에만 올리는 용도라 앱 심사 없이 개발 모드로 쓸 수 있습니다 [추정: 화면에서 확인].
3. **GitHub 저장소 만들기 (공개)**
   - 이 폴더(`instagram-uploader`)의 내용을 저장소 맨 위에 올립니다.
   - 공개여야 하는 이유: 인스타 API는 이미지를 공개 URL에서 가져갑니다. 올라가기 전 이미지가 저장소에서 보일 수 있습니다.
   - Settings → Secrets and variables → Actions에 두 개 등록: `IG_USER_ID`, `IG_ACCESS_TOKEN`
4. **런칭일 넣기**
   `posts.json`의 `"launch_date": null` → `"launch_date": "2026-11-09"` 처럼 바꾸고 저장소에 올리면 끝.
   Actions 탭에서 "Run workflow"로 바로 한 번 돌려 오류가 없는지 확인합니다.

## 평소 운영
- **새 게시물 추가:** 카드 렌더링 → `posts.json`에 항목 추가 → `python3 build_posts.py` → `caption.txt`·`comment.txt` 작성 → `python3 publish.py --check` → 저장소에 올리기
- **점검:** `python3 publish.py --check` (파일·장수·비율·캡션 길이), `python3 publish.py --dry-run` (지금 올라갈 것)
- **하나만 지금 올리기:** `python3 publish.py --only 04-destek` (Actions에서 하려면 로컬에서 환경변수 3개를 넣고 실행)
- **첫 댓글 고정:** API로는 고정이 안 됩니다. 올라간 뒤 앱에서 첫 댓글을 길게 눌러 고정합니다.

## 토큰 갱신 (60일마다, 놓치면 업로드 중단)
50일쯤 되면 아래 주소를 브라우저에서 열고, 나온 새 토큰으로 `IG_ACCESS_TOKEN` 시크릿을 바꿉니다.
```
https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token&access_token=지금토큰
```

## 안전장치
- 이미 올린 게시물은 `state.json`에 남아 다시 올리지 않습니다.
- 게시 시각에서 6시간 넘게 지난 게시물은 자동으로 올리지 않습니다(런칭일을 잘못 넣었을 때 한꺼번에 올라가는 것 방지).
- 문제가 있는 게시물(장수 2~10장 밖, 8MB 초과, 비율 오류, 캡션 2,200자·해시태그 30개 초과)은 건너뜁니다.
- 하루 게시 한도를 API에서 확인한 뒤 올립니다.

## API 없이 쓰는 방법 (예비)
`posts/<id>/` 폴더에 이미지·캡션·첫 댓글이 다 있으므로, 인스타 앱이나 Meta Business Suite의 **예약 게시**로 직접 올려도 됩니다. 한 번에 여러 개를 미리 예약할 수 있습니다.
