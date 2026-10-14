# 다음 세션: 새 Frontron 연구

2026-10-15 KST 체크포인트. 목표는 공개 GitHub 저장소에서 **IEEE Software·IEEE Security & Privacy의 적합한 Feature Article을 실제 앱으로 작성하고, 각각 투고를 권할 만한지 평가하는 것**이다. 두 매체의 범위에 맞지 않는 프로젝트를 억지로 두 원고로 만들지 않는다.

사용자의 최신 전체 삭제 요청에 따라 이전 연구·원고·원자료·심사·횟수·전달 ZIP을 다시 삭제했다. 예전 연구의 통과 판정이나 원고는 현재 실행의 결과가 아니다. 과거 JIZURA·9곳 포트폴리오·인계 ZIP을 복원하지 않는다. [현재 검증 기록](standalone-verification.md)과 [두 매체 설계](ieee-magazine-redesign.md)를 함께 확인한다.

아래 `output/`와 `.paper-factory/`는 이 Windows PC의 로컬 자료이며 Git에는 원고·계정 자료·실행 증빙을 포함하지 않는다. 새 복제본에는 이 경로가 없다. 상대 경로는 저장소 루트 기준이다.

## 현재 실제 실행

- 입력: `https://github.com/andongmin94/frontron`
- 새 연구: `research-7008ca97102a`
- 고정 Frontron commit: `3a7da2822721801db88ea059d204c8c6c622fab4`
- 작업공간: `C:/Users/Andongmin/Desktop/repository/paper-factory`
- 실제 데이터: `.paper-factory/jizura-new-01420-20261008-04e3b1a0-4ee/app-data` — 과거 디렉터리 이름이며 내용은 이번에 초기화한 새 연구다.
- 현재 실제 패키지: `desktop/release/frontron-final-20261015/win-unpacked/Paper Factory.exe` — 분석 계약과 외부 검수 보완 흐름을 수정한 미배포 로컬 빌드, 버전 0.14.20.
- 이번 실행 증빙: `output/playwright/frontron-fresh-20261014/`

2026-10-14 14:06:17 UTC 초기화에서 760개 파일·60,455,815 bytes를 삭제했다. 설치 앱과 실제 검증 데이터 양쪽 모두 연구·워크플로가 없는 상태를 확인했다. 자체 계정 연결·설정·소스·런타임·설치 파일은 유지했다. `reset-verification.json`, `empty-stores-before-app.json`, `empty-app-before-start.json`이 새 연구 시작 전 증거다.

2026-10-14 14:09:19 UTC 실제 packaged 앱의 정상 UI에서 저장소·목표·모델을 입력하고 **연구 시작**을 한 번 눌렀다. 공식 자체 계정의 `connected=true`, `sharing=true`, 실제 모델 목록과 작성·검토 `gpt-6.1-sol`을 확인했다. SDK mock, 이전 연구 가져오기, 직접 원고·심사 입력은 없다. 창만 숨김/offscreen으로 운영하며 Docker를 사용하지 않는다.

첫 분석 응답은 스키마와 근거 ID 계약의 불일치로 수락되지 않았고, 첫 정상 재개는 같은 완료 응답을 다시 확인해 추가 모델 호출·횟수 증가 없이 종료했다. 원 응답과 분석 1회를 그대로 보존한 채 계약을 수정하고 엄격한 native 검증을 통과해야 하는 보정 요청을 한 번 허용했다. 수정한 실제 로컬 패키지에서 같은 연구의 정상 **IEEE 매체별 미완료 투고본 재개**를 한 번 눌러 분석 2를 수락하고 두 원고를 생성했다. 실패를 승인으로 바꾸거나 검증 조건을 낮추지 않았다.

2026-10-14 15:03:34 UTC / 10-15 00:03:34 KST 원고 생성·독립 평가와 정상 종료 exit 0을 확인했다. 설계 1·문헌 1·분석 요청 2·채택 분석 1, 공통 원고·코드/실험 0이다. 매체별 실제 원고 1·독립 심사 1이 있으며 두 심사의 7개 기준·비교·기여가 모두 통과하고 차단 문제와 후속 작업이 없다. native `allContentReady=true`다. 실제 Word·PDF·Markdown 6개를 정상 저장 버튼으로 내보내 해시를 대조했고, 재개 전 원 파일의 변경·누락은 0이다.

| 실제 원고 | 제목 | 현재 별도 검수 |
| --- | --- | --- |
| IEEE Software | Authorize the Operation, Not Just the Renderer: Maintaining Native Bridges in Frontron | 독립 내용 감사·최종 Word 10쪽/PDF 8쪽 검수 통과 |
| IEEE Security & Privacy | What a Compromised Renderer Can Still Ask For: Authorizing Native Operations in Electron Bridges | 원고 2·심사 2, 별도 내용·수치·Word 14쪽/PDF 12쪽 검수 통과 |

첫 두 원고 생성 증거는 `resume-2/final-summary.json`, 정상 UI·저장·종료는 `resume-2/proof.json`, 원 파일 보존은 `resume-2/immutable-research-final.json`이다. 정상 저자 정보 UI로 후보 정보를 반영한 `author-2/proof.json`은 6개 실제 저장·정상 종료와 추가 모델 호출 0을 확인한다. Software의 실제 Word는 3,199단어에 표 allowance 250을 더해 분량 범위 안이고, Word 10쪽·native PDF 8쪽의 모든 페이지를 확인했다. 전달본 `output/pdf/frontron-fresh-20261014/IEEE-Software.docx`, `.pdf`, `.md`는 앱 native bytes와 일치한다. 검수 기록은 `output/word-qa/frontron-fresh-20261014/author-2/visual-qa-report.json`이다.

S&P 첫 저자 Word는 4,455단어·표 1개 allowance 250으로 4,705단어다. 일반 최소 4,900단어보다 195단어 부족해 내용 PASS만으로 최종 투고 준비 완료가 아니다. 공식 CFP 두 곳의 일반 Author Information 재명시를 확인한 수치는 `official-sp-numeric-verification.json`에 기록했다. 이 확인은 특정 특별호 선택이나 기존 연구의 동결 catalog 변경이 아니다.

정상 앱의 외부 검수 보완 입력에 `sp-external-feedback.txt`를 한 번 제출해 같은 분석·원자료에서 S&P만 보완했다. 2026-10-14 15:43:32 UTC / 10-15 00:43:32 KST `sp-revision-1/proof.json`은 새 집필·독립 심사 각 1회와 정상 종료 exit 0, 기존 과학 자료·Software·후보 저자 정보의 불변을 확인한다. S&P 누적 원고 2·심사 2·채택 원고 2, Software 1/1, 공통 분석 요청 2·코드/실험 0이다. 새 심사의 7개 기준·비교·기여는 모두 통과하고 차단 문제·후속 작업은 없다. 후보 저자 출력에는 추가 모델 호출 0이며 기존 정상 입력 정보를 재사용해 새 Word·PDF·Markdown 3개를 저장했다.

S&P 수정 저자본의 실제 Word는 5,192단어·표 1개 allowance 250으로 5,442단어이며 4,900–7,200 범위를 충족한다. 별도 최종 내용 감사 `quality-sp-revision-audit.json`과 `.md`는 차단 결함·근거 없는 주장 0, 소스 근거 13개·문서 근거 7개 일치와 초록 50단어·참고문헌 8개를 확인했다. Word 14쪽·native PDF 12쪽을 각각 전페이지 시각 검수했고 원 파일 SHA는 불변이다. Software까지 총 44쪽의 잘림·겹침·글리프·표·캡션을 확인했다. S&P 기록은 `output/word-qa/frontron-fresh-20261014/sp-revision-1/word-render-proof.json`과 `visual-qa-report.json`이다.

두 대안 원고 모두 내용·확인한 수치·페이지 기준에서 **저자 최종 검토와 투고 검토를 권할 수준**이다. 같은 연구이므로 두 매체에 동시에 독립 논문으로 제출하지 않는다. 후보 저자 정보는 출력에 반영됐지만 신원·저자 해석·권리·지원/이해관계·최종 제출 승인과 필요한 약력·사진은 확인해야 한다. 실제 투고나 학술지 채택을 완료·예측하지 않았다. 공개 0.14.20 설치본에는 이번 앱 수정이 없으며 기존 공개 릴리스는 보존했다.

전달 루트는 `output/pdf/frontron-fresh-20261014/`다. 두 매체의 Word·PDF·Markdown 6개와 최종 native 독립 심사 2개는 앱 bytes 그대로이고 최종 manifest에 결속한다. 정상 저장은 `author-2/proof.json`과 `sp-revision-1/proof.json`, S&P 전달 복사는 `native-delivery-copy-proof.json`이 확인한다. 전달 ZIP `Frontron-IEEE-manuscripts.zip`은 259,316 bytes, 16개 member의 모든 해시를 대조해 `bundle-verification.json` status passed다. ZIP SHA256은 `3468916fe6b0568d11646684220540ea4bbe0c31e454505296bc545ed4301fe4`, `manifest.json` SHA256은 `af75d68e68db703ebc135e824f77e14a42e99f47663ebf8fc25b9766e728db42`다. 별도 감사·QA·공식 수치 확인은 원고와 구분하며 SDK 원 응답·인증은 묶음에 포함하지 않는다.

## 현재 앱 흐름

저장소 가져오기→범위와 기여 설계→적합한 매체 선정→관련 문헌과 완전한 비교 문서 확보→공통 정적 분석→매체별 Feature Article→실제 Word/PDF와 형식 선검사→독립 내용 심사→실제 지적에 연결된 보완이다. 내용 PASS 후에도 실제 출력의 외부 검수 지적을 해당 매체의 현재 원고·심사에 결속해 정상 UI로 보완할 수 있다. 원 심사를 고치지 않고 새 원고·독립 심사를 추가하며 남은 예산을 사용한다. 범용 첫 원고·첫 심사는 중복 생성하지 않는다. 프로젝트 실행은 필수 조건이 아니며 정적 근거만으로 효과·성능·배포 결과를 주장하지 않는다.

완료 응답과 검증을 통과한 분석·원고를 구분한다. 미완료 출력·원고·심사를 먼저 수락하고, 실제 현재 심사의 지적이 있을 때 필요한 문서를 확보하거나 원고를 수정한다. 문헌·분석·집필·심사·문서 보완의 실패·중단도 횟수에 남긴다. 이번 새 연구의 횟수를 다시 초기화하지 않는다.

## 다음 작업

1. 생성·독립 평가·별도 내용/형식/전페이지 검수·전달 묶음은 완료됐다. 실제 새 지적 없이 재실행·초기화·집필·심사를 반복하지 않는다. 보존한 원고와 manifest/ZIP 해시를 먼저 확인한다.
2. 저자가 실제 원고의 해석·AI 사용 공시·신원·소속·연락처·권리·지원/이해관계와 필요한 약력·사진을 최종 확인한다. 두 대안 중 투고처 한 곳을 선택하고 정확한 제출 파일과 최신 포털 요건을 확인한다. 제출 승인은 아직 없고 외부 투고하지 않았다.
3. 원고나 저자 정보를 실제로 변경해야 할 때만 정상 앱의 해당 보완·저자 출력 기능을 사용하고 바뀐 출력의 근거·형식·모든 페이지와 SHA를 다시 검수한다. 내부 PASS를 학술지 채택이나 교수 임용 인정으로 설명하지 않는다.
4. 코드 변경이 필요하면 앱을 정상 종료하고 집중 회귀→Windows runtime/desktop 빌드→소스와 포함 bytes 결속→숨김 packaged Electron·Playwright 정상 UI 재개 순서로 검증한다. 원자료·실패·횟수와 같은 새 연구 ID를 유지한다.

다른 PC에서는 절대 경로·공식 계정 연결·포함 런타임 SHA를 다시 확인한다. 이 PC의 경로나 로컬 자료가 새 복제본에 있다고 가정하지 않는다.
