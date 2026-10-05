# Paper Factory

Windows·macOS용 독립 Electron 연구 앱입니다. 앱과 엔진 소스 버전은 **0.13.0**입니다. 공식 Sign in with ChatGPT SDK와 실제 neobrutal-ui 컴포넌트로 계정 연결, 크레딧 설정 안내, 계정별 모델 목록, 공개 저장소 선택, 연구 작업과 결과 파일 화면을 구현했습니다.

**열두 번째 Windows 설치본의 최종 검증까지 서로 다른 공개 저장소의 실제 구독 연구 3/3편을 완료했습니다. Premiere·navigation·Frontron CLI의 단회 실험, 새 원고와 별도 문맥 리뷰, 5종 출력과 실제 앱 저장 15개를 확인했습니다. PDF 총29쪽 직접 시각 검수, DOCX 전체 내용과 ZIP 전 멤버 무결성 검사를 통과했습니다. 앱의 PDF 열기 요청·결과 폴더 표시와 Chrome의 정확한 저장본 PDF 표시를 구분해 확인했습니다. 정상 종료 후 새 설치 앱 프로세스에서 5개 작업과 같은 연결을 복원하고 새 Astra 완료 응답을 받았습니다. 이전 실패 연구·원고·출력·관측은 보존합니다.** 첫 연결 게이트의 자체 OAuth·완전 종료 후 연결 복원과 이후 설치본의 검증 이력을 보존했습니다. 다섯 번째 설치본에서 export한 첫 preview 연구 보고서는 프로토콜 무효를 명시하므로 성공 논문에 포함하지 않습니다. 기존 플러그인 논문과 Mac 엔진 CI도 새 앱의 성공 증거와 구분합니다.

## 현재 상태

| 항목 | 상태 |
| --- | --- |
| Electron main 인증·모델 요청, 제한된 preload IPC, React 화면 | 구현·타입 검사·빌드 |
| React 19·Tailwind 4·Base UI, 원본 neobrutal-ui Button/Card/Badge/Select/Checkbox | 실제 원본 도입, commit·라이선스·해시 보존 |
| 자체 OAuth 등록, OS 보호 저장소, 계정별 모델 조회, `response.completed` 판정 | Windows 실제 계정 검증 통과 |
| 앱 controller·Responses parser·공식 SDK 회귀 | 최신203 passed, 1 skipped; 전체 원문·라이선스 공지 전달·취소 상태·원고 수정·앱 내부 저장 창의 합성 자료·모의 transport 검사 |
| Electron UI·OS 보호 저장소 fixture | 최신4 passed, 20.2초; 실제 계정·논문 증거와 분리 |
| 화면 구성 | 연결·새 연구·결과를 고정 사이드 탭으로 분리; 탭 전환 시 입력과 모델 선택 유지. 새 Windows 설치본 적용·실제 화면 확인 |
| 제한된 Python IPC·QuickJS·문서 변환 런타임 | 최종 Windows 런타임 4,463개 파일·30개 wheel, 전체 해시와 native probe 통과; 이전 시스템 PATH 없는 실행·한글 경로 이동·native 문서 검사도 별도 보존 |
| 독립 엔진과 legacy 정리 | Python 21개와 QuickJS worker 1개로 구성; 최신 전체 Python 794 passed/7 skipped. 플러그인·Cloud·CLI·구 runner·투고 경로 제거 완료 |
| 실제 연구 작업·최종 설치본·새 논문 3편 | 최종3/3편. Premiere/navigation 각18회, CLI17회 실제 생산 호출·각32관측·연구별 성공 실행1회·별도 리뷰 승인. 현재124/72/112개 동결 artifact 전량 해시와 이전 실패 보존. 정상 종료·새 프로세스의5개 작업/연결 복원·새 응답 확인, 추가 과학실험0회 |
| macOS ARM/Intel 런타임 | 최종 소스의 외부 플랫폼 조립·해시 검사: ARM 4,349개·Intel 4,346개 파일; Mac 네이티브 실행·DMG·CI·설치 미검증 |
| 최종 논문 파일 검수 | PDF10/10/9쪽 전쪽 직접 검수·DOCX65/66/62문단(3200/3261/3046단어)·각 표2/그림1·각 OOXML19 및 ZIP176/476/261멤버 전량 CRC/크기/SHA 검수·실제 저장본15개 원본 일치. 관리 런타임에 LibreOffice가 없어 DOCX 시각 검증 미수행 |

[계획과 완료 기준](docs/standalone-app-plan.md), [현재 검증 기록](docs/standalone-verification.md)을 확인하세요.

## 앱의 동작

`Continue with ChatGPT`는 이 앱의 공식 OAuth 등록과 사용자 동의를 사용합니다. 다른 앱의 인증 파일을 읽거나 복사하지 않으며 API 키 입력이나 별도 API 결제를 요구하지 않습니다. 로그인과 ChatGPT 구독 사용 권한은 별도로 확인합니다.

계정을 선택하고 모델을 새로 조회한 뒤 짧은 실제 응답 확인 요청을 보냅니다. 앱은 `https://api.openai.com/v1/responses`를 직접 호출하며 전체 응답 완료와 비어 있지 않은 텍스트를 확인해야 사용 성공을 표시합니다. 인터넷과 계정의 이용 권한·사용량이 필요합니다. 현재 미리보기 제약은 [공식 문서](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)를 따릅니다.

공개 GitHub 저장소 URL을 입력하거나 계정 URL의 최근 공개 저장소 최대 100개를 조회해 선택합니다. 연구 목표와 실제 목록에 있는 작성·리뷰 모델을 지정하면 고정 원본 수집, 계획, 문헌 수집, 코드와 별도 문맥 리뷰, 격리 실험, 분석, 원고와 별도 문맥 리뷰, 파일 변환을 진행합니다. 화면은 엔진의 실제 단계·오류·취소·명시 재개 상태를 표시하며, 완료 결과의 PDF·DOCX·Markdown·TeX·재현 ZIP을 검증한 뒤 저장하거나 열고 폴더를 표시합니다. 이용 가능한 Windows 환경에서 이 전체 흐름의 실제 구독 연구 3편 검증을 완료했습니다.

세 연구의 Markdown·TeX가 참조하는 `figure-1.png`는 실제 저장된 재현 ZIP의 원본 bytes를 CRC·inventory·동결 SHA와 대조한 뒤 각 사용자 저장 폴더에 별도로 전달했습니다. 앱에서 저장한 기본15개 파일은 변경하지 않았으며 그림 전달을 앱 Save 동작으로 계산하지 않습니다. PDF 열기는 오류 없는 앱의 shell 요청과 Chrome의 정확한 저장본·첫 페이지 표시까지 확인했습니다. native Reader의 정확한 파일 경로·렌더링과 DOCX 페이지 시각 검증은 미확인입니다.

대기 중인 생성·계획·분석 단계에서는 **추가 근거 선택**으로 UTF-8 원문 문서를 가져올 수 있습니다. 영문 파일명의 `.md`·`.txt`·`.json`을 파일마다 128 KiB, 연구 전체 최대 8개·256 KiB까지 보존합니다. 원본 바이트·SHA256·현재 가져온 시각을 기록하고 다음 작성·별도 리뷰 요청과 재현 ZIP에 포함합니다. 문서 안의 과거 활동 주장을 앱이 검증한 사실로 표시하지 않으며, 가져오기만으로 연구를 재개하거나 프로토콜·실험 결과·리뷰 판정을 바꾸지 않습니다. 여덟 번째 실제 설치본에서 6개 문서·37,667 bytes와 가져오기 후 실행 버튼의 활성 상태를 확인했습니다.

토큰은 Electron main에서 운영체제 보호 저장소로 암호화하며 Renderer와 Python에 전달하지 않습니다. 크레딧 설정 버튼은 공식 ChatGPT 사용량 페이지를 엽니다. 한도 오류가 나면 **“사용량 한도에 도달한 후 다른 앱에서 크레딧 사용 허용”**을 켜고 앱에서 확인 후 재시도할 수 있습니다. 앱 체크박스는 사용자 확인이며 계정의 실제 설정을 변경하거나 읽는 척하지 않습니다. 로컬 callback listener는 인증 동안만 사용하며 별도 운영 서버가 필요하지 않습니다.

앱 데이터는 OS 사용자 앱 데이터의 `Paper Factory Standalone/`에 저장합니다. 기존 `.paper-factory/`나 과거 Electron/플러그인의 연구 상태를 열어 복구하거나 수정하지 않습니다. `chatgpt/`는 보호된 인증 자료이고 `evidence/connection-checks.jsonl`은 계정 연결 ID·모델·시각·완료 텍스트와 해시·오류 기록입니다. `research/`와 `engine/`에는 새 앱의 작업 목록, 모델 원문 receipt, 고정 원본·프로토콜·관측·결과를 보존합니다. 인증 디렉터리를 지원 자료나 Git에 넣지 마세요.

## 개발 및 검증

다음 명령은 **개발자용**입니다. 최종 사용자가 Python·Node·패키지를 터미널로 설치하는 흐름은 제품 완료 기준에 포함되지 않습니다. 개발에는 Node 24와 npm이 필요합니다.

```powershell
cd desktop
npm ci --no-audit --no-fund
npm test
npm run package:app
```

`npm test`는 타입·빌드·모의 controller/Responses/공식 SDK 회귀 검사입니다. `package:app`는 해시로 고정한 런타임을 개발 단계에서 준비하고 설치본과 전체 파일 검증 기록을 생성합니다. 설치된 앱은 실행 환경을 다운로드하거나 사용자 터미널 설치를 요구하지 않습니다.

GUI 검사는 `npm run test:electron`으로 별도 실행합니다. 최신 Source12의 앱/SDK 203개 회귀가 통과했고 SDK 검사 1개는 Windows에서 건너뛰었습니다. Electron fixture 4개도 20.2초에 통과했습니다. 바이트가 동일한 Python 엔진의 최신 전체 검사는 794 passed, 7 skipped(138.08초)입니다. fixture의 합성 인증 암호화·재실행 복원과 모의 오류/IPC는 실제 OAuth나 논문 생성 증거로 계산하지 않습니다. 실제 로그인→모델 조회→응답 완료→앱 종료/재실행→같은 연결로 새 응답 확인은 별도 Windows 연결 체크포인트에서 통과했습니다.

Windows·macOS ARM/Intel용 [독립 앱 빌드 CI](.github/workflows/desktop.yml)는 전체 런타임·설치본·패키지 검증을 요구합니다. CI 실행·통과를 실제 설치·로그인·논문 제작 성공으로 표현하지 않습니다. 여섯 번째 Windows 설치본은 분석 라이브러리 초기화와 모델 응답 deadline 보완을 포함하며 설치·전수 해시·자체 연결 복원·새 완료 응답을 통과했습니다. 이전 다섯 번째 설치본의 실패 보고서 export도 보존했습니다. 최신 Windows 설치본의 새 연구3편·최종 산출물·정상 종료/복원 검증은 완료했고, 코드 서명/공증 및 개발 도구 없는 환경 검증은 남아 있습니다.

여덟 번째 설치는 2026-10-05 13:50:24.002–13:51:12.871 UTC에 종료 코드 0으로 완료했고, 13:51:15.081 UTC에 런타임 4,463개 파일·564,850,370 bytes·엔진 소스 22개를 전수 대조했습니다. 자체 연결 복원 후 Astra의 새 완료 응답을 13:52:54 UTC에 확인했습니다. 추가 근거 가져오기 반환값이 대기 상태를 덮어쓰던 결함도 수정해 실제 화면에서 확인했습니다. [설치본 해시와 UI 증거](docs/standalone-ui-provenance.md)에 기록했습니다.

아홉 번째 설치는 2026-10-05 14:53:20.143–14:54:11.817 UTC에 종료 코드 0으로 완료했습니다. 설치 앱·화면 파일과 런타임 4,463개/엔진 소스 22개가 현재 빌드와 일치했고, 자체 연결로 14:55:56.029 UTC에 새 Astra 응답을 받았습니다. 실제 취소 뒤 `analyzed/cancelled`와 유휴 상태를 확인했습니다. Premiere 계획 재개는 14:58:36.469 UTC에 시작됐으며 전체 planner·소비자·LICENSE·NOTICE·README 원문이 전달됐습니다. 설치·화면 근거는 `.paper-factory/standalone-verification/planning-material-install-e96560c6-5b66-460c-abde-e917ff0589de/`에 보존했습니다. 이 확인을 완료된 과학실험·승인 원고로 합산하지 않습니다.

최종 Windows·Mac ARM/Intel 세 런타임 프로필의 정적 파일 대조를 통과했습니다. Mac 런타임은 Windows에서 정적으로 조립했습니다. 원본 아카이브의 Python 실행 모드는 `0775`, Node·Pandoc은 `0755`이고 builder의 최종 실행 모드는 `0755`입니다. NTFS에서 조립한 결과로 실제 macOS 파일시스템의 POSIX 실행 권한을 증명할 수 없습니다. Mac 네이티브 probe·DMG 생성/설치·CI 실행은 미검증이며 설치본은 서명하지 않았습니다.

## 연구 엔진과 전환 경계

연구 엔진의 단계·SQLite·원본 commit/SHA256·QuickJS 격리·worker receipt/journal/종료 확인·scientific controls·분석·문서 변환을 재사용합니다. 현재 연구 범위는 기존 엔진이 지원하는 JS·TS 함수입니다. Python·DOM·범용 Node·네트워크 실험 지원을 새 앱의 기능으로 주장하지 않습니다.

연구 계획·코드·원고와 독립 리뷰는 새 모델 호출로 작성하고 거절·수정·실패 기록을 보존해야 합니다. 앱 재시작이나 응답 중단을 이유로 과학실험을 자동 재실행하지 않습니다. 완료된 실험 뒤 원고 작성이 취소된 경우에는 동결 해시·성공 실행·정리 완료·양성/음성 제어·분석 연결을 검증한 뒤 명시적으로 원고만 재개할 수 있습니다. 이전 취소 상태와 재개 receipt를 추가 보존하며 실험 실행 횟수를 늘리지 않습니다. 최종 논문은 근거와 재현 자료가 연결된 초안이며 학술지 승인·출판이나 새로움을 보장하지 않습니다.

legacy 정리를 완료했습니다. `plugin.json`, 호스트 skill/Cloud 실행·전달·plugin ZIP, CLI, Docker·WindowsRunner/AppContainer, 현재 범위 밖 투고·포털 코드와 직접 대응하는 설정·스크립트·CI·테스트를 제거했습니다. 필요한 QuickJS archive/metadata, host catalog와 Pandoc 라이선스는 `desktop/runtime-inputs/`로 옮겼습니다. 최종 엔진은 Python 21개와 QuickJS worker 1개를 포함하며 과학적 제어·복구·원본 검증·분석·실제 변환과 Windows/macOS worker 종료 보호를 유지합니다. 새 앱에는 플러그인 호환 fallback이 없습니다. 완료 범위와 회귀 결과는 [정리 기록](docs/standalone-cleanup-inventory.md)에 있습니다.

이전 플러그인 검증과 안내는 [0.12.0 역사적 README](docs/history/README.plugin-0.12.0.md) 및 기존 증거 문서에 보존했습니다. 역사적 문서의 설치·호스트·Cloud 명령을 독립 앱의 사용 안내로 적용하지 않습니다. 원본 연구 결과와 private 증거 자료는 삭제하지 않았습니다.

서로 다른 공개 저장소 `neobrutal-ui`, `frontron`, `premiere-ai-harness`의 고정 commit·원문 라이선스·생산 함수·독립 oracle 및 선정/제외 근거는 [선정 기록](docs/standalone-repository-selection.md)에 있습니다. 선정 자료와 미실행 fixture는 실제 관측 결과가 아닙니다.

## 라이선스와 출처

독립 작성된 Paper Factory 코드는 [MIT](LICENSE)입니다. neobrutal-ui 원본은 MIT이며 [출처와 해시](docs/standalone-ui-provenance.md)를 보존합니다. 공식 SIWC SDK는 **Sign-in with ChatGPT DevKit Noncommercial License v1.0**이며 앱 전체를 일괄 MIT로 배포한다고 주장하지 않습니다. [SDK 라이선스](desktop/vendor/siwc-local/LICENSE), [변경 범위와 출처](desktop/vendor/siwc-local/PROVENANCE.md), [인증 조사](docs/standalone-auth-research.md)를 확인하세요.
