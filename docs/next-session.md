# 다음 세션: 두 IEEE 매체의 실제 Frontron 원고

2026-10-11 체크포인트. 현재 목표는 GitHub 저장소에서 **IEEE Software·IEEE Security & Privacy의 적합한 Feature Article을 실제 앱으로 작성하고, 각각 투고를 권할 만한지 평가하는 것**이다. 두 매체의 범위에 맞지 않는 프로젝트를 억지로 두 원고로 만들지 않는다.

사용자가 기존 연구 자료·심사·횟수 전체 삭제를 명시했고 초기화했다. 과거 JIZURA·9곳 포트폴리오·인계 ZIP은 현재 복원 대상이 아니다. 이 문서와 [현재 검증 기록](standalone-verification.md), [두 매체 설계](ieee-magazine-redesign.md)가 현재 지시다.

아래 `output/`와 `.paper-factory/` 경로는 검증한 PC에만 보존한 로컬 자료다. Git에는 원고·계정 자료·실행 증빙을 포함하지 않으며 저장소를 새로 복제하면 이 경로는 없다. 상대 경로는 저장소 루트 기준이다.

## 실제 연구와 재개 상태

- 저장소: `https://github.com/andongmin94/frontron`
- 현재 연구: `research-100e940ea80b`
- Windows 작업공간: `C:/Users/Andongmin/Desktop/repository/paper-factory`
- 실제 앱 데이터: `.paper-factory/jizura-new-01420-20261008-04e3b1a0-4ee/app-data` — 디렉터리 이름만 과거 이름이며 새 Frontron 연구가 저장된다.
- 첫 실행 증거: two-magazine-fresh-20261011 (`output/playwright/two-magazine-fresh-20261011/final-summary.json`)
- 현재 종료 증거: resume-1 (`output/playwright/two-magazine-fresh-20261011/resume-1/final-summary.json`)

첫 실제 실행은 설계 1·문헌 1·분석 요청 2, 공통 원고 0·코드/실험 0이다. **분석 1만 채택됐고 분석 2는 완료 응답의 잘못된 evidence ID 때문에 채택되지 않았다.** 두 매체 모두 원고 1·심사 1·실제 PDF/Word 출력이 있다. Software는 완전한 Electron 비교 문서와 해석 보완을 요구했다. S&P는 개별 기준을 통과했으나 비차단 조언이 `issues`에 들어가 보수적 준비도는 false다. 어느 원 심사도 수정하거나 승인으로 재해석하지 않는다.

**resume-1은 2026-10-11 13:50:24 UTC 정상 종료했다.** 공식 Electron 문서 3개를 확보한 뒤 두 매체 모두 원고 2·독립 심사 2·실제 Word/PDF를 생성했다. 두 새 심사의 7개 기준과 비교·기여가 모두 통과하고 차단 문제·후속 작업은 비어 있으며, native `all_content_ready=true`다. 분석 요청은 2·채택된 분석은 1로 유지했고 추가 재분석·실험은 하지 않았다. 기존 282개 파일의 SHA/크기 변경은 0이고 첫 원고·원 심사·실패·횟수는 유지했다.

최종 상태 (`output/playwright/two-magazine-fresh-20261011/resume-1/final-summary.json`) · 원 파일 보존 (`output/playwright/two-magazine-fresh-20261011/resume-1/immutable-research-final.json`) · 독립 품질 감사 (`output/playwright/two-magazine-fresh-20261011/resume-1/quality-audit.md`) · 전달 파일 manifest (`output/pdf/frontron-two-ieee-20261011/manifest.json`).

내용상 두 Feature Article 모두 투고 검토를 권할 수준이다. Software PDF 8쪽·S&P PDF 11쪽을 렌더링하고 전체 페이지와 표를 확인했다. Word는 본문/표 보존만 확인했으며 최종 Word 시각 검수는 남아 있다. 실제 저자 정보·승인·제출 선언은 미입력이고 실제 투고하지 않았다. 두 원고는 같은 사례의 대안 투고본이다.

## 현재 앱 흐름

저장소 가져오기→범위와 기여를 설계→적합한 두 매체 선정→관련 문헌과 완전한 비교 문서 수집→공통 정적 분석 1회→매체별 Feature Article→실제 Word/PDF와 형식 선검사→독립 내용 심사→실제 지적에 연결된 보완이다. 범용 첫 원고·첫 심사를 중복 생성하지 않는다. 프로젝트 실행은 이 경로의 필수 조건이 아니며 정적 근거로 효과·성능·배포 결과를 주장하지 않는다.

미완료 원래 출력·원고·심사를 먼저 수락한다. 그 뒤 실제 문서 보완 지적이 있으면 비교 문서를 수집하고 필요한 원고만 수정·재심사한다. 완전한 새 문서는 채택된 공통 분석 1을 유지한 채 원고의 비교와 해석을 고치는 데 사용할 수 있다. 과거 공통 수정 계획은 기록으로 남지만 현재 심사에서 사라진 요구를 다시 실행하지 않는다.

문서 보완은 동일한 현재 분석·원고·심사 SHA 기준에서 한 번이며 실패·중단도 소비한다. 회당 서로 다른 비교 URL 1–3개, 전체 수집 3회와 완전 본문 120,000자 한도를 유지한다. 문헌·분석·집필·심사 예산과 실패 횟수를 초기화하지 않는다. `issues`는 차단 결함만 기록하고 통과 기준의 선택적 조언은 criterion reason에 남긴다.

## 다음 작업 순서

1. 두 원고는 내용 평가를 마쳤다. 작업이 없는 상태에서 새 집필·심사를 재개하지 않는다. 실제 저자 정보·승인·최종 제출 형식과 Word 시각 확인부터 이어간다.
2. 종료 상태·실제 요청 영수증·채택된 산출물·이전 파일 SHA를 확인한다. 완료 응답 수와 채택된 분석/원고 수를 구분한다.
3. 결과 화면의 정상 **IEEE 매체별 미완료 투고본 재개** 동작으로 필요한 작업만 이어간다. 직접 원고·심사 입력, 모델 응답 주입, 삭제된 예전 자료 복원, Madi/JIZURA 재실행을 하지 않는다.
4. 실제 매체별 원고의 기여·비교·근거·실무적 조언·한계와 PDF 전페이지·Word 보존을 확인한다. 학술지별 공식 형식 확인·저자 정보/승인·AI 공개도 별도로 확인한다. 내부 PASS를 투고·채택·교수 임용 실적 인정으로 설명하지 않는다.
5. 코드 변경이 필요하면 앱 정상 종료 후 집중 회귀→Windows runtime/desktop 빌드→소스/포함 bytes 결속→숨김 Electron·Playwright 정상 UI 재개 순서로 검증한다. 현재 코드와 횟수를 보존한 같은 연구로 계속한다.

Git 상태와 `origin/main`을 읽기 전용으로 대조한 뒤 현재 수정 내용을 유지한다. 다음 PC에서는 절대 경로·공식 계정 연결·포함 런타임 SHA를 새로 확인하고 이 PC의 경로를 그대로 가정하지 않는다.
