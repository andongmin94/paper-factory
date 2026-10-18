# Windows 독립 앱 검증: IEEE Software·Security & Privacy

2026-10-18 재평가 정정: 아래 Software의 투고 권장 표현은 10월 15일 당시 판단이며 현재는 철회한다. 근거 인용·조건부 추론·분량·페이지 검사 통과와 충분한 게재 가치를 구분하지 못했다. 단일 사례에서 기존 보안 지침보다 제공하는 추가 판단 가치, 검토 가능한 개선 설계와 적용 근거를 실질적으로 보완해야 한다. 내부 심사의 기여 항목도 있었지만 공식 문서와 소스만으로 실무 교훈이 충분하다고 판단한 기준이 관대했다. 현재 권고는 **투고 전 실질 보완 필요**이며 점수나 출판사의 판정은 아니다. 원고·원 심사·자료·횟수·QA 기록은 변경하지 않았고, S&P의 현재 게재 가치는 이번에 재평가하지 않았다.

2026-10-15 KST 현재 체크포인트. 검증 대상은 Docker 없이 실행하는 실제 Electron 앱과 공식 계정 모델 호출이다. 합성 회귀·패키지 무결성·실제 원고 생성·투고 준비도는 각각의 증거로 기록한다. 이번 새 연구의 최신 상태는 [다음 세션](next-session.md)과 함께 갱신한다.

`output/`·`.paper-factory/`와 빌드 경로는 이 Windows PC의 로컬 자료이며 Git에서 제외한다. 원고·개인정보·인증·실제 모델 요청을 저장소나 릴리스에 게시하지 않는다. 상대 경로는 저장소 루트 기준이고 새 복제본에는 증빙 파일이 없다.

## 초기화와 새 연구

사용자의 최신 전체 삭제 요청에 따라 2026-10-14 14:06:17 UTC 이전 연구·원자료·원고·심사·횟수·전달 ZIP 760개 파일, 60,455,815 bytes를 삭제했다. 대상은 설치 앱 `%APPDATA%/Paper Factory Standalone`과 실제 검증 앱 `.paper-factory/jizura-new-01420-20261008-04e3b1a0-4ee/app-data`의 연구·워크플로 및 과거 실제 출력이다. 자체 계정 저장소·연결 설정·소스·포함 런타임·설치 파일은 유지했다.

이번 증빙 루트는 `output/playwright/frontron-fresh-20261014/`다. `reset-verification.json`은 삭제 대상 없음과 보존 항목을, `empty-stores-before-app.json`은 두 저장소의 jobs/workflows 0을, `empty-app-before-start.json`은 실제 앱의 빈 연구·엔진 ready·오류 없음 상태를 확인한다. 연구 시작 후 저장소가 계속 비어 있다고 설명하지 않는다.

새 연구는 `research-7008ca97102a`, 입력은 `https://github.com/andongmin94/frontron`이다. 14:09:19 UTC 실제 앱의 정상 입력과 **연구 시작** 한 번으로 생성했다. 고정 commit `3a7da2822721801db88ea059d204c8c6c622fab4`에서 189개 파일을 내려받고 분석용 161개 파일, 1,121,077 bytes를 보존했으며 해시가 모두 일치한다. 이전 연구나 원고를 가져오지 않았다.

## 실제 패키지와 공식 연결

| 항목 | 이번 실행 경로/증거 |
| --- | --- |
| 작업공간 | `C:/Users/Andongmin/Desktop/repository/paper-factory` |
| 실제 데이터 | `.paper-factory/jizura-new-01420-20261008-04e3b1a0-4ee/app-data` |
| 최초 executable | `desktop/release/final-ready-0.14.20-20261014/win-unpacked/Paper Factory.exe` |
| 최초 executable SHA256 | `6a655a7f33264a75cbeb9841c58a162f08da0c2d23e5d5608ce58a6392726a3d` |
| 현재 executable | `desktop/release/orcid-autofill-20261015/win-unpacked/Paper Factory.exe` |
| 현재 executable SHA256 | `1d96593555e63505059d8fc767052d3f8a4af69ca8a4cfb9ef3a84592a0916ab` |
| 정상 입력 | `normal-user-input.json` |
| 공식 연결·모델 목록 | `official-connection-proof.json` |
| 숨김 packaged 창 | `window-launch-proof.json` |
| 첫 원고 생성 결과·정상 UI·저장·종료 | `resume-2/final-summary.json` / `resume-2/proof.json` |
| 후보 저자 출력·6개 저장·정상 종료 | `author-2/proof.json` |

증거 JSON은 위 이번 증빙 루트 기준이다. 공식 자체 계정의 `connected=true`, `sharing=true`, 실제 모델 목록과 작성·독립 평가 모델 `gpt-6.1-sol`을 확인했고 `sdkMocked=false`다. 계정 토큰이나 다른 앱 인증 파일을 읽거나 복사하지 않는다.

최초 실행은 공개 NSIS와 같은 unpacked payload, 완료 재개는 아래 계약 수정을 포함한 미배포 로컬 패키지다. 두 실행 모두 `isPackaged=true`, 버전 0.14.20과 runtime/repository analysis ready를 확인했다. 일회용 검증 prelude는 패키지 entry 실행 전 데이터 경로를 자체 연구 저장소로 매핑하고 창에 `show:false`, `offscreen:true`, `backgroundThrottling:false`를 적용했다. production controller·SDK·engine·모델·IPC와 native 변환을 사용했다. sandbox·context isolation·web security와 Node isolation을 유지하며 Playwright로 정상 입력·모델 선택·시작·재개를 조작했다. 원고·심사·모델 응답은 주입하지 않았다. PowerShell에서 숨김 helper를 시작할 때는 `-WindowStyle Hidden`을 사용한다.

## 새 원고 결과와 실제 외부 보완

첫 분석 응답은 `INVALID_ARGUMENT: Analysis observation evidence must bind unique existing identifiers`로 수락되지 않았다. 첫 정상 UI 재개는 같은 완료 응답을 재검증해 추가 모델 호출이나 횟수 증가 없이 정상 종료했다. 원인은 분석 스키마 계층과 근거 ID 계약의 불일치였다. 스키마를 수정하고 원 응답·원 자료·횟수를 보존한 채 엄격한 native 검증을 통과해야 하는 보정 요청을 한 번 허용했다. 보정도 실제 분석 요청 횟수에 포함하며 반복 보정이나 검증 조건 완화는 하지 않는다.

수정된 실제 패키지의 같은 연구에서 정상 **IEEE 매체별 미완료 투고본 재개**를 한 번 눌렀다. 2026-10-14 15:03:34 UTC / 10-15 00:03:34 KST 최종 생성 스냅샷은 `busy=false`, `error=null`, `phase=idle`, `pipeline=paused`다. 분석 보정 요청을 수락했고 두 매체 원고·독립 평가·실제 출력이 완료됐다.

| 실제 누적 요청/산출물 | S&P 보완 완료 시점 |
| --- | --- |
| 설계 / 문헌 | 1 / 1 |
| 공통 분석 요청 / 채택된 분석 | 2 / 1 |
| 공통 원고 / 코드 / 실제 실행 | 0 / 0 / 0 |
| Software 집필 / 독립 심사 / 채택 원고 | 1 / 1 / 1 |
| S&P 집필 / 독립 심사 / 채택 원고 | 2 / 2 / 2 |
| 실제 매체별 Word/PDF/Markdown | 생성·정상 저장 완료 |
| 앱 scientific/content ready | 두 매체 모두 true / true |
| 별도 내용·확인한 수치·전페이지 검수 | 두 매체 통과 |
| 최종 저자·권리·제출 승인 | 미확인, 실제 투고 없음 |

두 새 심사의 7개 기준·비교·기여는 모두 통과했고 차단 문제·후속 작업은 비어 있으며 native `allContentReady=true`다. Word·PDF·Markdown 6개를 정상 저장 버튼으로 내보내 bytes/SHA를 대조하고 앱 정상 종료 exit 0을 확인했다. 재개 전 원 파일의 변경·누락은 0이며 `resume-2/immutable-research-final.json`에 기록했다. 첫 실패와 분석 요청 1회를 삭제하거나 승인으로 바꾸지 않았다. 과거 삭제한 연구의 원고·심사·페이지 검수·저자 ZIP을 이번 결과로 사용하지 않는다.

정상 후보 저자 정보 출력 `author-2/proof.json`은 Word·PDF·Markdown 6개 저장·정상 종료 exit 0과 추가 모델 호출 0을 확인한다. 최종 저자·권리·선언 승인은 추정하지 않는다.

Software 제목은 *Authorize the Operation, Not Just the Renderer: Maintaining Native Bridges in Frontron*이다. 별도 내용 감사 `quality-software-audit.json`과 `.md`는 단일 사례의 근거·비교·실무 교훈과 확인한 수치 형식을 통과시켜 저자 최종 검토와 투고 결정을 권한다. 실제 Microsoft Word의 3,199단어에 표 1개 allowance 250을 더한 3,449단어는 한도 안이다. Word 10쪽·native PDF 8쪽을 각각 전페이지 시각 검수했고 잘림·겹침·누락 글리프·표 문제는 없다. 별도 숨김 Word read-only COM으로 렌더링하고 원 DOCX를 저장·변경하지 않았다. canonical renderer의 LibreOffice 미설치 실패도 기록하고 실제 Word 대안 검수를 사용했다. 증거는 `output/word-qa/frontron-fresh-20261014/author-2/word-render-proof.json`과 `visual-qa-report.json`이다. `output/pdf/frontron-fresh-20261014/IEEE-Software.docx`, `.pdf`, `.md`는 앱 native bytes와 일치한다.

S&P 제목은 *What a Compromised Renderer Can Still Ask For: Authorizing Native Operations in Electron Bridges*이다. 첫 원고의 앱 내용 평가는 통과했고 별도 내용 감사에서도 실질적인 근거 없는 보안 주장은 발견하지 않았다. 그러나 실제 저자 Word는 4,455단어·표 1개 allowance 250으로 4,705단어다. 일반 최소 4,900단어보다 195단어 부족해 최종 형식 검수에서 차단됐다. 앱의 내용 PASS를 최종 제출 준비 완료로 해석하지 않는다.

현재 공식 CFP [Real-world Security Impact](https://www.computer.org/digital-library/magazines/sp/cfp-real-world-security-impact)와 [One Decade of GDPR Challenges](https://www.computer.org/digital-library/magazines/sp/cfp-one-decade-gdpr-challenges)가 일반 Author Information을 명시적으로 재명시한 규정을 읽어 확인했다. 요구는 본문·초록·키워드·참고문헌·약력·표 텍스트를 포함한 4,900–7,200단어에 시각 자료당 250단어를 더하는 방식, 초록 최대 50단어·참고문헌 최대 15개다. 이번에 일반 Author Information 본문을 직접 다시 읽었다고 주장하지 않으며 특정 특별호를 투고처로 선택하지 않았다. 확인 기록은 `official-sp-numeric-verification.json`이다. 새 연구의 안내에는 확인한 일반 수치를 반영하지만 기존 연구의 동결 catalog는 바꾸지 않았다.

이 실제 분량 결함과 필요한 실질 보완을 `sp-external-feedback.txt`에 기록해 정상 앱의 외부 검수 보완 UI에 한 번 입력했다. 보완은 현재 S&P 원고·원 심사에 결속하고 같은 채택 분석과 원자료를 사용하며 기존 긍정 심사·원고·실패·횟수와 Software 1/1을 보존했다. 제안된 정책 사례·권한 만료·회수·비용·잔여 위험을 근거 범위 안에서 보완하는 새 집필·독립 평가를 각각 한 번 완료했다. 실험이나 구현 효과를 만들어 분량을 늘리지 않았다.

2026-10-14 15:43:32 UTC / 10-15 00:43:32 KST `sp-revision-1/proof.json`은 status passed·정상 종료 exit 0, 모든 이전 과학 자료·Software bytes·후보 저자 정보의 불변을 확인한다. 새 실제 모델 요청은 집필 `130e33f0-879f-4ee4-83dc-ff3f3ae078b8`과 독립 심사 `264b4046-25e3-46eb-ba7a-5f573cec67ca` 두 개다. 전체 연구는 journal의 별칭·상태 중복을 제외한 실제 UUID 12개이며, 후보 저자 출력 모델 호출은 0이다. 누적 S&P 집필·심사·채택 원고는 2/2/2, Software는 1/1/1, 공통 분석 요청은 2로 유지됐다. 새 심사의 7개 기준·비교·기여가 통과하고 차단 문제·후속 작업은 없다.

기존 정상 UI에서 저장한 후보 저자 정보를 재사용해 수정 원고의 Word·PDF·Markdown 3개를 정상 저장했다. 실제 Microsoft Word 16의 5,192단어에 표 1개 allowance 250을 더한 5,442단어는 4,900–7,200 범위 안이다. Word 14쪽·native PDF 12쪽을 각각 모든 페이지 시각 검수했고 잘림·겹침·누락 글리프·표·캡션 문제는 없다. read-only 렌더링 전후 원 DOCX와 native PDF SHA는 불변이다. Software까지 총 44쪽을 확인했다. S&P의 분량·렌더·전페이지 증거는 `output/word-qa/frontron-fresh-20261014/sp-revision-1/word-render-proof.json`과 `visual-qa-report.json`이다.

별도 수정본 내용 감사 `quality-sp-revision-audit.json`과 `.md`는 차단 결함·근거 없는 주장 0, 소스 근거 13개·문서 근거 7개 일치, 초록 50단어·참고문헌 8개를 확인했다. 내용과 확인한 수치 기준에서 저자 최종 검토와 투고 검토를 권한다. 두 원고 모두 이 수준에 도달했으며 학술지 채택은 예측하지 않는다. 후보 저자 정보는 정상 앱 출력에 반영됐지만 신원·저자 해석·권리·지원/이해관계·최종 제출 승인과 필요한 약력·사진은 남아 있다. 두 원고는 같은 연구의 대안 투고본으로 두 곳에 동시에 독립 논문으로 제출하지 않는다.

## 최종 전달 묶음

전달 루트는 `output/pdf/frontron-fresh-20261014/`다. 두 매체의 Word·PDF·Markdown 6개와 최종 native 독립 심사 2개는 bytes 그대로 전달하고 최종 manifest의 SHA와 대조했다. 정상 저장 증거는 `author-2/proof.json`과 `sp-revision-1/proof.json`, S&P 전달 복사는 `native-delivery-copy-proof.json`이다. 별도 내용 감사·QA·공식 수치 확인과 원고를 구분했다. 인증·SDK 원 응답은 묶음에 포함하지 않았다.

`Frontron-IEEE-manuscripts.zip`은 259,316 bytes, 16개 member의 모든 해시를 대조했으며 `bundle-verification.json` status passed다. ZIP SHA256은 `3468916fe6b0568d11646684220540ea4bbe0c31e454505296bc545ed4301fe4`, `manifest.json` SHA256은 `af75d68e68db703ebc135e824f77e14a42e99f47663ebf8fc25b9766e728db42`다. 이 ZIP은 전달 원고 묶음이며 앱 계정·전체 연구 저장소의 복원 패키지가 아니다.

앱 흐름은 저장소 확보→범위·기여 설계→적합한 매체 선정→문헌·완전한 비교 문서 확보→공통 정적 분석→매체별 원고→Word/PDF와 형식 선검사→독립 내용 심사→실제 지적에 따른 보완이다. 내용 PASS 이후에도 실제 출력의 외부 검수 지적을 정상 UI로 입력해 해당 매체의 원고·독립 심사를 추가할 수 있다. 원 심사와 이력을 고치지 않고 남은 매체별 예산을 사용한다. 프로젝트 코드 실행은 원고 생성의 필수 조건이 아니며 실행·효과·성능 근거를 꾸며내지 않는다. 완료 응답 수와 검증을 통과한 분석·원고 수를 구분한다.

## 실제 제출 파일 준비와 승인 경계

새 [투고 흐름](submission-workflow.md)은 연구 원고 생성 이후의 제출 행정을 별도 native 모듈에 저장한다. 한 매체 선택·약력/키워드/지원/이해관계 입력→새 제출용 Word/PDF 생성→그 새 파일 QA와 저자 명시적 확인→제출 ZIP/manifest/편지/포털 입력 정보→고정 공식 Author Portal→사용자 확인 접수 기록 순서다. 파일 생성은 `awaiting_file_check`, 확인한 묶음은 `prepared`, 실제 접수번호·시각을 사용자가 기록해야 `submitted`다. 상태와 원고·저자·파일 SHA를 결속하며 포털 열기·파일 저장은 접수가 아니다. 준비 취소와 실제 학술지 철회를 구분하고 제출 후 원고가 바뀌어도 제출 당시 접수 기록은 유지한다.

이번 실제 연구는 S&P 준비 2의 `awaiting_file_check`까지 검증했다. 후보 약력·키워드를 새 제출 파일에 추가했으며 기존 과학 본문을 그대로 복원할 수 있다. 지원·이해관계는 `저자 확인 대기`, 저자 확인 7개는 모두 false, 앱의 파일 QA 입력 5개는 빈 값이고 최종 확인 버튼은 비활성이다. 최종 제출 ZIP·편지·확인·접수 기록은 생성하지 않았으며 공식 사이트 버튼도 누르지 않았다. IEEE 로그인·업로드·최종 제출과 저자 승인을 완료 처리하지 않는다.

증빙 루트는 `output/submission-design/actual-app-20261015/`다. 준비 1은 provenance 경계 검사에서 변환 helper 입력과 소스 경계 차이를 발견해 실패했고, 준비 2는 새 파일 생성은 완료했으나 저장 검증의 atomic temp 파일 조회가 실패했다. 원 두 failed proof와 `first-run-diagnosis.json`, `run-2-diagnosis.json`을 보존했다. 준비 2의 등록 산출물 10개와 이전 연구를 유지하고 새 생성 없이 저장만 다시 검증했다.

`ui-run-3/proof.json`은 2026-10-14 16:45:12 UTC / 10-15 01:45:12 KST passed·정상 종료 exit 0을 확인한다. 기존 준비 2의 실제 제출 Word·PDF·Markdown 3개를 정상 저장했고 native descriptor SHA와 일치한다. 재생성·새 행정 산출물·연구 초기화·추가 모델 요청·저자 승인·포털/접수 동작은 0이다. 이전 과학 자료·두 준비·실패·12개 모델 요청·기존 원고 ZIP/manifest와 실행 build 결속은 모두 불변이다.

새 제출 Word는 실제 Microsoft Word 16에서 5,217단어이며 표 1개 allowance 250을 더한 5,467단어가 S&P 4,900–7,200 범위 안이다. Word 14쪽·native PDF 12쪽, 모든 26페이지를 각각 시각 검수해 잘림·겹침·글리프·표·캡션·키워드·후보 약력 표시가 통과했다. 원 DOCX/PDF를 저장·변경하지 않았다. 이 QA는 앞선 과학 원고 44페이지 QA와 별도이며 신원·권리·실제 약력·저자 승인·투고 완료를 확인하지 않는다. 증거는 `output/word-qa/submission-flow-20261015/preparation-2/word-render-proof.json`, `visual-qa-report.json`이다.

실제 새 DOCX SHA256은 `a8d9fda6bf0b0dbf71e2a5d26b8096389b6b2a5c8d108ac89286d75f9c325b2f`, PDF SHA256은 `4961d1d11e366b3024d2e8d4a0a76319f4095be1a640b0d5a67192e28e705df3`이다. 저장본은 `output/submission-design/actual-app-20261015/ui-run-3/saved/`에 있다. 지원/이해관계와 실제 약력·사진·7개 저자 확인, 새 파일 QA 입력은 사람의 다음 작업이며 확인 값을 자동으로 만들지 않는다.

## ORCID 공개 정보 자동채움 구현

저자 입력에 ORCID 번호나 공식 프로필 주소를 넣으면 공개 이름·현재 소속·이메일·약력을 조회해 빈 항목에만 반영한다. 저장된 값·직접 입력한 값은 유지하며 복수 현재 소속·이메일은 사용자가 선택한다. 공개 약력이 없을 때 직위·학력으로 새 약력을 만들지 않는다. 조회 결과는 저장 전 초안이며 본인 인증·동의·저자 승인이나 제출 확인이 아니다. 조회만으로 연구·심사·횟수·원고·제출 준비를 바꾸지 않는다.

공개 API의 person/employments/educations 고정 경로를 인증 없이 읽는다. 요청은 20초·응답 1MiB 한도로 제한하고 프로필의 현재 기관을 중복 제거한다. 저자 약력은 선택 값이며 빈 약력을 추가해 기존 저자 해시를 바꾸지 않는다. ORCID 구현의 native 저자 64개·기존 저자 출력 10개, desktop 집중 81개(ORCID 9·저자 14·제출 5·publication 53)와 타입·빌드가 통과했다. 합성 검사 통과를 사용자의 실제 ORCID 조회나 새 패키지 실행 통과로 설명하지 않는다.

새 Windows 패키지에서 사용자가 제공한 ORCID의 실제 공개 API·정상 UI를 검증했다. `output/playwright/orcid-autofill-20261015/actual-app/proof.json`은 2026-10-15 12:17:57 UTC / 21:17:57 KST passed·정상 종료 exit 0이다. 실제 SDK·native·ORCID API를 사용했고 mock 없이 숨김/offscreen·sandbox·context isolation·Node integration off를 유지했다.

공개 이름·현재 기관은 빈 항목에 자동으로 채워졌고 중복 기관은 하나로 표시됐다. 공개 이메일·약력은 없어 빈 편집 항목으로 남았다. 저장 전 수기 값 4개를 넣고 재조회해도 보존됐으며 화면을 다시 열면 저장 전 변경을 버리고 기존 저장 저자 정보가 그대로 복원됐다. 이를 본인 인증이나 최종 저자 동의로 해석하지 않는다.

기존 workflow 381개 파일의 변경·추가 0, 모델 요청 12개·기존 원고 ZIP/manifest·저장 저자 정보·제출 준비 2와 실행 build는 불변이다. 새 모델 요청·저자 저장·출력·준비·포털·확인·접수는 모두 0이며 저자 확인 7개 false·QA 입력 5개 빈 값을 유지했다. 앞선 제출 패키지의 실제 준비·저장·26페이지 QA와 원고 생성·44페이지 QA 증거는 별도로 보존한다.

## 현재 미배포 로컬 패키지

공개 릴리스를 덮어쓰지 않고 ORCID 자동채움·분석 계약·외부 검수 보완·실제 투고 준비 흐름이 포함된 Windows 패키지를 `desktop/release/orcid-autofill-20261015/win-unpacked/`에 만들었다. 버전 표기는 0.14.20이지만 공개 설치본과 bytes가 다르며 아직 배포하지 않았다. 현재 결속 기록은 `output/playwright/orcid-autofill-20261015/build-proof.json`이다. 앞선 제출 패키지의 `output/submission-design/actual-app-20261015/ready-build-proof.json`, `final-build-proof.json`과 원고 생성 패키지의 증거도 보존한다.

| 로컬 패키지 결속 항목 | SHA256 |
| --- | --- |
| executable | `1d96593555e63505059d8fc767052d3f8a4af69ca8a4cfb9ef3a84592a0916ab` |
| ASAR | `961779f55649ba16a465e046e7c4285d48b916e25ece1a969b3a2698e5b52864` |
| runtime inventory | `da8e10d274b0de291b166daa1579808a730a530b30c976bb20dc66f67bf0cef8` |
| production 입력 121개 | `e88c6dd0b11209e2269af54e3e4a4fe6ea4b9242fd534a284f373dcfa1091261` |

runtime 2,231개 파일·474,654,303 bytes의 전체 SHA와 native 소스·데이터·폰트 결속 39개, production 입력 121개와 ASAR asset 결속이 일치한다. 이 패키지의 실제 ORCID UI 검증·정상 종료와 실행 전후 결속 불변을 확인했다. 기존 제출 준비 2·저장 파일·26페이지 QA와 앞선 패키지의 아래 읽기 전용 실행 증거도 유지하며 새 ORCID 검증과 구분한다.

앞선 `submission-ready` 패키지의 `output/submission-design/actual-app-20261015/ui-run-5-readonly/proof.json`은 2026-10-14 16:55:53 UTC / 10-15 01:55:53 KST passed·정상 종료 exit 0이다. 공식 계정 connected/sharing, 숨김 창·sandbox·context isolation·Node integration off와 기존 준비 2의 `awaiting_file_check`, 저자 확인 7개 false·QA 입력 5개 빈 값을 확인했다. 새 준비·행정 산출물·저장·모델 요청·공식 사이트·확인·접수 동작은 모두 0이며 전체 workflow·12개 모델 요청·기존 원고 ZIP/manifest를 유지했다. `ui-run-4-readonly`는 entry 실행 전 prelude 이름 allowlist 불일치로 실패했고 원 증거·exit 0·모델 0·자료 보존을 별도로 기록했다. 이 실패를 통과로 덮어쓰지 않았으며 새 ORCID 기능의 실행 증거로 사용하지 않는다.

## 보존한 공개 0.14.20 Windows 배포본

이번 초기화는 소프트웨어 배포·합성 검증 자료를 삭제하지 않았다. 최종 NSIS와 포함 파일의 무결성 기록은 `output/playwright/package-smoke-20261013-8e4bfa7/final-ready/`에 남아 있다.

| 패키지 항목 | 값 |
| --- | --- |
| NSIS | `desktop/release/final-ready-0.14.20-20261014/Paper Factory Setup 0.14.20.exe` |
| NSIS 크기 / SHA256 | 213,342,831 bytes / `968f7bd258858eccb5ecf45675099c3caa5851373fec2f9487fe2ec78c9c523e` |
| ASAR SHA256 | `518fc837a3c2e4f2226204f0a2ecab03bf6d5d2f6e631da6069d4da2e838b3bb` |
| runtime inventory SHA256 | `f5a2d7cf7fcbef5949ad613b7f1bc073bf4ca0becd25f279c5e85d40914ada77` |
| 최종 production 입력 114개 SHA256 | `f3e9ddca05ad03edf1748a263a470682907f5c927089cbc84a5d45f4fb259183` |

NSIS 압축 무결성과 핵심 payload 4개, ASAR 7,668 members, runtime 2,230개 파일·474,589,236 bytes의 전체 SHA, Python 소스 33개와 포함 bytes의 일치를 확인했다. 포함 Python·Node·Pandoc·Typst·폰트로 동작하며 시스템 Docker·TeX 설치를 요구하지 않는다. Setup과 unpacked 앱은 `NotSigned`다. 실제 시스템 설치·제거와 macOS 실행은 검증하지 않았다.

짧은 자체 데이터 경로 `tmp/ps14-2`에서 숨김 packaged 앱의 전체 runtime/repository analysis ready, 보안 설정, 빈 계정·모델·연구와 정상 종료 exit 0을 확인했다. 같은 binary/runtime의 긴 데이터 경로 검사에서 발생한 GPU cache 오류·Chromium 종료 시간 초과는 원 실패로 보존했고 짧은 경로의 통과로 덮어쓰지 않았다. 실제 패키지의 `app.asar` 물리 파일 SHA는 내장 `original-fs`로, ASAR 내부 runtime binding JSON은 기존 Electron 가상 fs로 확인한다.

검증한 설치 파일·blockmap·공개 checksum manifest는 [0.14.20 릴리스](https://github.com/andongmin94/paper-factory/releases/tag/v0.14.20)에 게시했다. 공개 태그 commit은 `aa75606c01772d8df45a48d90753bbaabc20f455`이며 익명 다운로드와 세 asset digest가 일치한다. 공개 checksum manifest SHA256은 `4ab81c9fba39b37553a0dc9707d5d219c157ec29d6aafcc18c7608c5840d6711`이다. 공개 확인 기록은 `output/releases/0.14.20/final-public-verification.json`이다. 연구 원고나 인증은 배포하지 않았다.

## 소프트웨어 회귀 검증 범위

현재 제출 흐름의 native 43개와 converter helper 1개, desktop 집중 159개·최종 guard 5개 부분집합, 숨김 합성 UI 1개가 통과했다. 합성 자료로 준비·파일 QA·저자 확인·ZIP/편지·사용자 확인 접수 기록의 전체 흐름을 검사했다. 실제 Frontron 연구는 파일 생성·정상 저장·별도 시각 검수까지만 진행했으며 사람의 승인·공식 포털 접수는 검증하지 않았다.

마지막 사진 입력 수정은 한글·`.JPG` 파일명을 MIME에 맞는 `author-photo.jpg`/`.png`로 정규화하며 파일 bytes를 유지한다. 기존 합성 UI 시나리오를 이 JPEG 경우까지 확장해 1/1 통과(11.1초)와 TypeScript 검사를 완료했다. 동일 시나리오의 확장 재검증이며 합성 UI 수를 2개로 합산하지 않는다. 실제 연구에 사진이나 저자 승인을 추가하지 않았다.

앞선 외부 피드백 구현의 desktop 138개, native 피드백 15개와 기존 portfolio·분석 보정 49개도 통과했다. 아래 이전 배포본의 회귀 수를 현재 변경을 다시 검사한 수로 합산하지 않는다.

2026-10-12 정리 후 타입·빌드, desktop Node 425개, SDK 48개(운영체제 전용 1개 제외), 숨김 Chromium 29개, Electron 13개가 통과했다. Python 선택 목록의 완료 보고·분할 검사·정정 재검사를 합산한 결과는 3,113 통과·macOS 전용 2 제외이며 누락·미해결 실패는 0이다. 초기 실패와 정정 이력은 로컬 `tmp/cleanup-native-final-coverage-20261012.json`, `tmp/cleanup-native-final-node-outcomes-20261012.json`, `tmp/cleanup-native-repaired-files-pass-receipts-20261012.json`에 유지한다. 합성 자료의 검사 수를 실제 연구·심사·실험 횟수에 합산하지 않는다.

공개 배포본의 저자 출력 관련 native 41개, author/shared 집중 61개, Chromium contract 22개와 TypeScript·빌드도 통과했다. desktop Node 전체 434개는 그 이전 수정 단계에서 통과했고 당시 마지막 한정 수정은 위 집중 검사로 검증했다. 합성 Electron 두 시나리오는 최초 부하 시간 초과 후 단독 재검사에서 통과했으며 원 로그를 유지했다. 이 결과는 소프트웨어 검사이고 이번 분석 계약 수정이나 새 원고의 품질을 직접 증명하지 않는다.

두 실제 과학 원고의 생성·평가·검수·전달 묶음과 현재 S&P 새 제출 파일의 준비·저장·별도 페이지 검수는 완료했다. 다음 작업은 저자의 실제 약력·사진·지원/이해관계와 7개 승인·새 파일 QA 5개를 확인해 제출 묶음을 만들고 한 공식 포털에서 실제 제출한 뒤 접수번호·시각을 기록하는 것이다. 현재 준비는 `awaiting_file_check`이며 제출 승인이나 접수 기록은 없다. 새로운 실제 지적 없이 연구·집필·심사를 재실행하거나 횟수를 초기화하지 않는다. 추가 코드 수정은 앱 정상 종료 후 집중 검사·빌드·결속을 확인하고 같은 연구에서 검증한다.
