# Windows 독립 앱 검증: IEEE Software·Security & Privacy

2026-10-14 현재 체크포인트. 검증 대상은 Docker 없이 실행하는 실제 Electron 앱과 공식 계정 모델 호출이다. 합성 fixture 통과, runtime 빌드, 실제 원고 생성, 학술지 투고 가능성은 서로 다른 증거로 기록한다. 최신 실행 결과는 [다음 세션](next-session.md)과 함께 갱신한다.

이 문서는 실제 실행 결과의 요약이다. `output/`·`.paper-factory/`와 빌드·runtime 경로는 해당 Windows PC의 로컬 자료이며 Git에서 제외된다. 원고·인증·모델 요청을 저장소에 게시하지 않는다. 아래 상대 경로는 저장소 루트 기준이고 새 복제본에는 증빙 파일이 없다.

## 초기화와 현재 연구

사용자의 전체 삭제 요청에 따라 설치 앱 `%APPDATA%/Paper Factory Standalone`와 개발 앱 `.paper-factory/jizura-new-01420-20261008-04e3b1a0-4ee/app-data`의 이전 연구·워크플로·횟수를 삭제했다. 예전 출력·독립 연구 ZIP도 삭제했으며 복원을 전제로 재개하지 않는다. 자체 계정 저장소·연결 설정·포함 런타임은 유지했다.

초기화 검사 (`output/playwright/two-magazine-fresh-20261011/reset-verification.json`), 앱 시작 전 빈 저장소 (`output/playwright/two-magazine-fresh-20261011/empty-stores-before-app.json`), 연결된 빈 앱 (`output/playwright/two-magazine-fresh-20261011/empty-app-before-start.json`)이 새 연구 이전의 증거다. 현재는 새 연구가 있으므로 저장소가 계속 비어 있다고 설명하지 않는다.

새 실제 연구는 `research-100e940ea80b`, 입력은 `https://github.com/andongmin94/frontron`이다. 원문은 실제 앱 데이터의 `engine/workflows/research-100e940ea80b`에 저장된다. active catalog는 IEEE Software·IEEE Security & Privacy의 Feature Article 두 곳이며 부적합 판정 매체는 집필 대상에서 제외한다.

## 실제 앱과 공식 연결

| 항목 | 현재 경로/증거 |
| --- | --- |
| 저장소 | `C:/Users/Andongmin/Desktop/repository/paper-factory` |
| 개발 앱 자체 데이터 | `.paper-factory/jizura-new-01420-20261008-04e3b1a0-4ee/app-data` |
| 개발 Electron | `desktop/node_modules/electron/dist/electron.exe` |
| 포함 runtime | `desktop/runtime/win32-x64` |
| Python / Node | `python/python.exe` / `node/node.exe` (runtime 기준 상대 경로) |
| 문서 변환 | 포함 Pandoc·Typst·폰트; 시스템 Docker·TeX 설치를 요구하지 않음 |
| 초기 정상 입력 | normal-user-input.json (`output/playwright/two-magazine-fresh-20261011/normal-user-input.json`) |
| 재개 정상 입력 | resume-1/normal-resume-input.json (`output/playwright/two-magazine-fresh-20261011/resume-1/normal-resume-input.json`) |
| 공식 연결/모델 목록 | resume-1/official-connection-proof.json (`output/playwright/two-magazine-fresh-20261011/resume-1/official-connection-proof.json`) |
| 숨김/offscreen 창 | resume-1/window-launch-proof.json (`output/playwright/two-magazine-fresh-20261011/resume-1/window-launch-proof.json`) |

실제 자체 계정의 `connected=true`, `sharing=true`, 공식 모델 목록을 확인했으며 `sdkMocked=false`다. 작성·검토 모델은 `gpt-6.1-sol`이다. 계정 토큰·다른 앱 인증 파일을 읽거나 복사하지 않는다. 연결 목록 확인은 추가 연구나 고정 응답 probe가 아니다.

검증 당시의 일회용 숨김 launcher는 창에 `show:false`, `offscreen:true`, `backgroundThrottling:false`만 적용했다. production controller·모델·IPC는 바꾸지 않았다. Playwright Electron API로 정상 입력·모델 선택·결과 재개 버튼을 조작하고 DOM/Chromium 화면을 기록했다. `PF_DESKTOP_DATA_DIR`는 위 개발 데이터 경로였다. 재검증 시에는 보존한 종료 상태와 연구 SHA를 확인하고 정상 UI를 사용한다. 새 helper를 PowerShell `Start-Process`로 실행하면 `-WindowStyle Hidden`을 사용한다.

## 현재 소스와 포함 빌드

resume-1은 소스/runtime 결속 (`output/playwright/two-magazine-fresh-20261011/resume-1/source-runtime-build-proof.json`)에 기록한 빌드로 실행했고 정상 종료했다. 종료 시 빌드 SHA도 불변이다. 아래 SHA는 이 실제 연구 검증 시점의 스냅샷이며 이후 소스 정리·새 빌드의 최종 SHA를 나타내지 않는다.

| 항목 | 값 |
| --- | --- |
| runtime inventory SHA256 | `820913ed3eb8c8fa08f513f2fe116f7444aec8648d7d8cc9ac11609543164c42` |
| `desktop/dist/app.js` SHA256 | `1d742c5dcb6c3aed163d8a192dac7e9a0a2114d615373e9a81b8b2344fdc04cb` |
| runtime 파일/bytes | 2,230 / 474,575,535 |
| 실제 Windows host probe | `actualHostTested=true` |
| builder receipt | `.paper-factory/standalone-runtime-builder/build-win32-x64-7e15cf1d-96e7-45ad-ad55-e48dd2b97f11/build-receipt.json` |

IPC·workflow·models·catalog·repository paper/portfolio/supplement의 소스 SHA와 포함 파일 SHA를 대조했다. builder receipt 자체의 `applicationLaunchTested=false`는 별도 실제 Electron 실행 증거로 보완된다. 이 개발 실행을 새로운 NSIS 설치본 배포나 macOS 실행으로 주장하지 않는다.

앱을 정상 종료하고 소스 변경을 마친 뒤에만 `desktop`에서 다음 작업을 한다. 빌드 도중 실제 연구를 실행하지 않는다.

```powershell
npm run build:runtime -- --platform win32 --arch x64
npm run build
```

필요한 집중 테스트를 먼저 수행하고 builder receipt·runtime inventory·현재 native 소스/포함 bytes·생성된 app hash를 확인한다. 검증의 일회용 marker는 실행 증빙에 보존했다. marker를 지워 새 요청을 만들지 않는다. 새 실행에서는 고유 검증 디렉터리를 만들고 정상 UI의 같은 연구 재개 동작을 사용한다.

## 첫 실행 결과와 수정한 흐름

첫 실행 최종 상태 (`output/playwright/two-magazine-fresh-20261011/final-summary.json`), 정상 종료/저장 횟수 (`output/playwright/two-magazine-fresh-20261011/normal-close-and-stored-counts.json`), 실제 요청 원장 (`output/playwright/two-magazine-fresh-20261011/fresh-model-request-journal.json`)을 기준으로 기록한다.

- 설계 1·문헌 1·분석 요청 2·범용 원고 0·코드/실험 0이다. 채택된 분석은 1개다. 분석 2의 완료 응답은 존재하지만 observation evidence ID가 잘못돼 채택되지 않았다. 그 응답과 사용 횟수는 유지한다.
- Software와 S&P 각각 실제 원고 1·독립 심사 1·Word/PDF 출력이 있다. 첫 PDF는 각각 8·11페이지이며 품질 감사 (`output/playwright/two-magazine-fresh-20261011/quality-audit.md`)에 내용을 기록했다. 최신 수정본의 전페이지 검수 완료로 소급하지 않는다.
- Software는 완전한 외부 비교 문서와 standing authority의 전체 정책 조건을 요구했다. S&P는 개별 과학/내용 기준이 통과했으나 선택적 조언을 issues에 넣어 준비도는 false다. 원 심사 bytes·보수적 판정은 그대로 유지한다.
- 수집된 PDF 두 개는 body range가 검증되지 않았으므로 모델에 검증된 완전 본문으로 전달하지 않았다. metadata/full_text 표기만으로 실제 본문 읽기를 주장하지 않는다.

보완 구현은 설계 후 비교 문서를 먼저 수집하고, 이후 실제 부정 심사에 요청이 있으면 같은 분석·원고·심사 SHA에 결속한 문서 수집 한 번을 허용한다. 동일 기준의 실패·중단도 소비하며 URL 재수집·예산 초기화는 거부한다. 새 완전 문서는 공통 분석 1을 유지한 원고 수정과 새 독립 심사에 사용한다. 과거 수정 계획의 요구로 현재 통과한 원고를 계속 재분석하지 않는다. `issues`는 차단 결함만, 비차단 조언은 criterion reason에 쓰도록 계약을 명확히 했다.

이 변경의 집중 native 검증 21개와 shared/controller의 집중 검사·typecheck가 통과했다. 합성 테스트의 원고·심사·출력은 실제 연구 수에 합산하지 않는다.

## resume-1 최종 결과

2026-10-11 13:50:24 UTC 정상 종료했다. 최종 상태 (`output/playwright/two-magazine-fresh-20261011/resume-1/final-summary.json`), 정상 종료 (`output/playwright/two-magazine-fresh-20261011/resume-1/normal-close.json`), 횟수·원 심사 보존 (`output/playwright/two-magazine-fresh-20261011/resume-1/final-counts-and-first-drafts-proof.json`), 282개 원 파일 보존 (`output/playwright/two-magazine-fresh-20261011/resume-1/immutable-research-final.json`)이 실제 증거다. 기존 파일의 SHA/크기 변경 0, 새 파일 59, 같은 연구 ID·모델·계획·원자료 유지, 추가 연구·횟수 초기화·프로젝트 실행 0이다.

| 실제 최신 산출물 | IEEE Software | IEEE Security & Privacy |
| --- | --- | --- |
| 집필 / 독립 평가 | 2 / 2 | 2 / 2 |
| native scientific/content ready | true / true | true / true |
| 7개 기준 / 비교·기여 | 모두 통과 | 모두 통과 |
| 차단 문제 / 다음 작업 | 없음 / 없음 | 없음 / 없음 |
| 실제 Word·PDF | 생성, 오류 없음 | 생성, 오류 없음 |
| PDF | 8쪽 | 11쪽 |
| 초록 / 참고문헌 | 133단어 / 8개 | 50단어 / 8개 |

문서 수집 1회에서 공식 Electron security·context isolation·IPC 본문 3개, 총 63,615자를 HTTP200으로 실제 확보했다. 완전 본문·SHA·literal 인용을 수정 원고에 연결했다. 공통 분석 요청 2·채택된 분석 1을 그대로 유지하며 두 매체의 비교·정책 설명만 수정했다. 새 심사는 문서 admission 자체와 실제 분석의 타당성을 구분해 판정했다.

독립 품질 감사 (`output/playwright/two-magazine-fresh-20261011/resume-1/quality-audit.md`)는 두 실제 원고 모두 내용상 투고 검토를 권할 수준으로 판단한다. PDF 검수 (`output/playwright/two-magazine-fresh-20261011/resume-1/pdf-qa`)는 총 19쪽을 렌더링해 전체 페이지와 표를 확인했으며 눈에 띄는 잘림·겹침·누락 글리프가 없다. Word는 OOXML 본문 보존과 실제 파일 생성을 확인했으며 Word의 최종 시각 검수는 미완료다.

Software의 확인한 수치 규정을 충족한다. S&P는 별도 숨김 Playwright에서 [일반 Author Information](https://www.computer.org/csdl/magazine/sp/write-for-us/14680?title=Author%20Information&periodical=IEEE%20Security%20%26%20Privacy)을 직접 읽었다. 전체 본문·초록·키워드·참고문헌·소개·표 4,900–7,200단어, 시각 자료당 250단어, 초록 50단어, 참고문헌 15개를 확인했다. 현재 Word 약 5,004단어와 표 allowance를 보수적으로 더한 약 5,254단어·초록50·참고8이 해당 수치 안이다. 브라우저 snapshot (`output/playwright/two-magazine-fresh-20261011/resume-1/sp-author-information-browser-snapshot.txt`)이 별도 검증이며, 연구 시작 시 동결한 catalog의 `checked_scope`를 소급 수정하지 않았다.

전달 파일 (`output/pdf/frontron-two-ieee-20261011/manifest.json`)은 앱의 최신 Word·PDF·Markdown·원 심사를 bytes 그대로 복사해 SHA를 대조했다. manifest SHA256은 `c4b881e272401f5af15e39886e9316be5457bede110b61d3ef5c04ab6e8013dc`다. 실제 저자 정보·승인·권리와 제출 선언은 미입력이며 실제 투고하지 않았다. 두 버전은 같은 사례의 대안 투고본이다.

수정 후 native 집중 21개, shared/portfolio/recovery 148개, research/routing 167개, 문서 selector 6개가 통과했다. 앱 빌드·타입 검사·Windows runtime host probe·diff 검사를 완료했다. 설치 파일을 새로 배포하지 않았다. 일회용 launcher와 브라우저·테스트 임시 파일은 Git에서 제외했다. 2026-10-12 이 로컬 파일의 삭제 명령이 자동 검토에서 `blocked by policy`로 거절돼 남아 있으며 실제 앱·연구·인증에 사용하지 않는다.

활성 앱 동안 소스/runtime를 수정하거나 live engine을 별도 CLI로 열지 않는다. 현재 연구 실패를 숨기려고 새 연구·횟수 초기화·Madi 재실행을 하지 않는다. 다음 PC에서는 계정 연결과 절대 경로를 다시 확인한다.

## 2026-10-12 푸시 전 정리와 보존 확인

현재 두 IEEE 매체에 맞춰 문서와 검사 잔재를 정리했다. 폐기된 9곳 계획·이전 Software 단독 설계·이미 실행한 특정 PC용 초기화 스크립트는 제거했다. 개인 JIZURA 캐시에 의존하던 optional 검사는 제거하고 재현 가능한 합성 Chromium 검사를 유지했다. 브라우저 캡처·일회용 launcher·임시 검사 파일은 Git에서 제외했다. 실제 원고·연구·인증 파일은 커밋에 포함하지 않는다.

앱이나 엔진을 실행하지 않고 기존 최종 증빙과 실제 파일을 읽기·해시로 대조했다. 같은 연구의 기존 282개 파일은 SHA·크기 변경과 누락 0, 최종 등록 산출물 178개는 기록 차이와 실제 bytes 변경·누락 0, 추가 파일은 기존 증빙과 같은 59개다. 설계 1·문헌 1·분석 요청 2·범용 원고 0·코드/실험 0, 매체별 집필 2·심사 2와 내용 준비도 true를 유지한다. 현재 `paused`, `cleanupRequired=false`이며 새 연구나 모델 요청을 만들지 않았다.

정리 후 앱 빌드·타입 검사, desktop Node 425개, SDK 48개(운영체제 전용 1개 제외), 숨김 Chromium 통합 29개가 통과했다. Playwright Electron은 최초 12개 통과·1개 실패였고, 변경된 preload API 목록을 반영하지 않은 기대값을 수정한 뒤 해당 검사가 통과해 13개 모두 검증했다. 이 회귀 검사는 합성 자료를 사용하며 실제 계정 연결·모델 호출·연구 재개를 수행하지 않았다.

Python 비네트워크 회귀 검사는 오래 걸리는 파일 보존 검증을 병렬로 마무리하기 위해 완료한 1,823개와 전체 선택 목록 3,115개를 기록한 뒤 남은 파일을 세 그룹으로 나눴다. 최초 실패 25개 중 24개는 변경된 스키마·문헌 수집 인자·공개 HTTPS URL 허용·버전 지정 계산·최신 ledger 별칭을 반영하지 않은 테스트였다. 함수 인자는 실제 구현에 전달하고, 잘못된 HTTP URL의 호출 전 거절과 이전 파일·이력의 bytes 보존 검사는 유지했다. 변경된 검사와 관련 파일을 재검증했고 원 실패 보고는 삭제하지 않았다.

Windows owned-process 검사 1개는 최초 실행에서 실패했고, 수정 없이 단독 재검사와 파일 전체 61개가 통과했다. 원 worker frame은 성공, owned-worker 목록은 비어 있었으나 빈 profile 디렉터리가 남았다. 당시 실패 사유 receipt가 없어 원인을 단정하지 않으며 원 frame·목록·해시 증거를 보존한다. 병렬 보고 도구의 상대 경로 때문에 workspace 검사 도중 별도 INTERNALERROR가 발생한 것은 절대 경로로 수정하고 workspace 파일 전체 38개 통과로 보완했다.

최종 선택 목록과 완료 보고·분할 검사·정정 재검사를 합산한 결과는 3,113 통과·macOS 전용 2 제외이며 누락·예상 밖 검사·미해결 실패는 모두 0이다. workflow는 최초 288개 완료 결과와 변경된 4개 집중 검사의 통과를 사용했다. 불필요한 전체 파일 반복은 중단하고 그중 완료된 209개만 반영했다. 최종 합산은 로컬 `tmp/cleanup-native-final-coverage-20261012.json`, 검사별 이력은 `tmp/cleanup-native-final-node-outcomes-20261012.json`, 전체 파일·집중 검사 receipt는 `tmp/cleanup-native-repaired-files-pass-receipts-20261012.json`에 보존하며 Git에는 포함하지 않는다.

## 2026-10-14 실제 패키지 저자 출력과 배포 검증

0.14.20 Windows x64 NSIS를 생성했다. 최신 파일은 `desktop/release/final-ready-0.14.20-20261014/Paper Factory Setup 0.14.20.exe`, 213,342,831 bytes, SHA256 `968f7bd258858eccb5ecf45675099c3caa5851373fec2f9487fe2ec78c9c523e`다. Setup과 unpacked 앱은 `NotSigned`이며 실제 시스템 설치·제거 및 macOS 실행은 이번 검증에 포함하지 않는다.

NSIS 압축 무결성과 핵심 payload 4개의 SHA, ASAR 7,668 members, runtime 2,230개 파일의 전체 SHA, 현재 Python 소스 33개와 포함 bytes의 일치를 확인했다. runtime inventory SHA는 `f5a2d7cf7fcbef5949ad613b7f1bc073bf4ca0becd25f279c5e85d40914ada77`, ASAR SHA는 `518fc837a3c2e4f2226204f0a2ecab03bf6d5d2f6e631da6069d4da2e838b3bb`다. 최종 production 114개 파일의 결속 SHA는 `f3e9ddca05ad03edf1748a263a470682907f5c927089cbc84a5d45f4fb259183`이며 새 저자 출력 helper도 포함한다. 기존 release 7개 파일과 npm Electron 44.5.1 원본 73개 파일의 변경은 0이다.

패키지 검증 기록은 `output/playwright/package-smoke-20261013-8e4bfa7/final-ready/`다. 짧은 자체 검증 데이터 경로 `tmp/ps14-2`에서 숨김/offscreen packaged 앱의 전체 runtime ready, repository analysis ready, sandbox·context isolation·web security와 Node isolation, 빈 계정·모델·연구, 정상 종료 exit 0을 확인했다. NSIS payload와 같은 unpacked 앱을 실행했으며 계정·연구·모델을 주입하지 않았다. 긴 검증 데이터 경로의 GPU cache 오류·Chromium 종료 시간 초과는 별도 원 실패로 보존했다. 같은 binary/runtime에서 짧은 경로로 검사했을 때 9.38초에 전체 검사·정상 종료가 통과했으며 긴 경로의 실패를 성공으로 바꾸지 않았다.

실제 패키지의 `app.asar`는 Electron 가상 fs에서 디렉터리로 보이므로 Chromium 결속에서만 내장 `original-fs`로 물리 파일·canonical path·전체 SHA를 검증한다. ASAR 내부 runtime binding JSON 읽기는 기존 가상 fs를 유지한다. 실제 저자 선택·출력 영수증이 공개 근거 목록에 추가되는 경우 정확한 ID·SHA·크기와 순서를 확인하고, 조회에서만 포함되는 `source_context`의 누락은 동결 context artifact가 불변일 때만 허용한다. 제공된 변경값·null·기존 원문/근거 변경은 계속 거부한다.

저자 출력 native 관련 검사는 서로 다른 41개가 통과했고, 현재 소스의 author/shared 집중 검사 61개와 Chromium contract 22개, TypeScript와 빌드가 통과했다. 전체 desktop Node 434개는 그 이전 수정 단계에서 통과했으며 마지막 한정 수정은 위 집중 검사로 검증했다. 합성 Electron 두 관련 시나리오는 최초 부하 시간 초과 후 단독 재검사에서 모두 통과했고 원 로그를 유지했다.

실제 연구 검증은 `output/submission-preflight/frontron-20261014/app/packaged-author-final-6/proof.json`이다. 패키지 entry 실행 전에 데이터 경로를 기존 Frontron 저장소로 매핑하고 창만 숨겼다. production controller·SDK·engine·native 변환과 저장을 사용했으며 원고·모델 응답을 주입하지 않았다. 공식 자체 계정의 연결·공유 상태를 확인하고 제공된 ORCID와 연결 계정에 근거한 후보 정보를 정상 저자 입력 UI에서 보존했다. 최종 신원·저자 승인·권리·제출 선언은 추정하지 않는다.

두 매체의 현재 저자 Word·PDF·Markdown 6개를 실제 저장 버튼으로 내보내 해시·크기를 대조하고 정상 종료 exit 0을 확인했다. Software의 완료 저자 출력 1회를 재사용하고 S&P만 새 저자 출력 1회를 수행했다. Markdown은 파일 선택이 아닌 원고·그림 저장 폴더 선택 동작을 그대로 사용했다. 실패한 일회용 검증과 먼저 저장된 파일은 삭제하거나 덮어쓰지 않았다.

`output/submission-preflight/frontron-20261014/app/after.json`은 기존 341개 파일·178개 등록 산출물의 SHA·크기·기록 변경/누락 0, 새 저자 관련 파일 22개를 확인한다. 같은 연구 ID·계획·문헌·분석 요청 2·채택 분석 1·매체별 집필 2·심사 2·내용 준비도 true를 유지했다. 새 연구·집필·심사·실험·모델 요청과 횟수 초기화는 0이다.

최신 저자본의 Word는 별도 숨김 Microsoft Word read-only COM 인스턴스로 PDF를 렌더링했고, 앱 native PDF도 별도로 PNG를 생성해 총 44페이지를 확인했다. Software Word 10쪽·native PDF 8쪽, S&P Word 14쪽·native PDF 12쪽이다. 네 가지 저자 문자열이 출력에 존재하고, 표·글리프·잘림·겹침·푸터 검수와 두 기존 본문·참고문헌의 bytes/SHA 대조가 통과했다. Word 열기로 원 DOCX bytes를 저장·변경하지 않았다. canonical renderer의 LibreOffice 미설치 실패와 실제 Word 대안 검수 기록을 함께 보존한다. S&P 첫 PDF 푸터 간격의 의심은 실제 좌표의 37.350526 pt 빈 간격과 확대 확인으로 오인임을 정정했으며 재출력하거나 본문을 고치지 않았다.

검수 기록은 `output/word-qa/frontron-two-ieee-author-20261014/final-qa-summary.json`과 `.md`다. 최종 출력·원 심사와 커버레터·후보 약력·미서명 제출 선언 검토서 및 해시 결속은 `output/submission-preflight/frontron-20261014/final/manifest.json`에 담는다. 저자 정보는 후보이며 최종 승인·기관/권리·지원과 이해관계·관련 공개·비동시투고 선언은 확인되지 않았고, Software 사진·관심사와 최종 약력 승인은 남아 있다. 외부 투고·서명·메일 발송은 하지 않았다.

검증한 설치 파일·blockmap·공개 checksum manifest만 [0.14.20 릴리스](https://github.com/andongmin94/paper-factory/releases/tag/v0.14.20)에 게시한다. 원고·개인정보·실행 증빙·인증·모델 요청은 커밋하거나 릴리스에 포함하지 않는다.

로컬 전달 묶음은 `output/submission-preflight/frontron-20261014/Frontron-IEEE-final-20261014.zip`이며 17개 파일의 CRC와 모든 member bytes를 확인했다. ZIP SHA256은 `00a0db9f61d624984ec3b21dec17646a97e33ea0e7d0b1c8fcc2dec4848571b0`, 원고·선언·검수 manifest SHA256은 `490c7c4a9dae08befdc32889ff9c30fa746f3b0b22c3da782e981b9d690ef3b0`이다. 이 묶음은 원고 전달본이며 앱 인증이나 전체 연구 저장소의 복원 패키지가 아니다.
