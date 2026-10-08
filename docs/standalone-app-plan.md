# Paper Factory 독립 데스크톱 앱 전환

갱신일: 2026-10-08 (Asia/Seoul). 현재 앱·엔진 소스 버전은 `0.14.15`이다. 최신 실행 설계와 아래 날짜별 전환·검증 이력을 구분한다. 당시 생성한 원고와 기술 검사를 최신 기준에서 승인된 학술 논문으로 계산하지 않는다.

## 현재 실행 설계

Windows에서는 계획에 맞춰 QuickJS 또는 준비 확인을 통과한 Chromium 프로필을 선택한다. QuickJS는 JS/TS 함수의 Wasm 실행을 맡고, Chromium은 변경하지 않은 classic `.js` 원문을 선언한 순서로 읽어 DOM·Canvas를 사용하는 동기 함수를 호출한다. 실험 `.js`/`.mjs` 코드는 비동기 `callProduction`·`retainFixture`·`readScientificInput`을 기다린다. 원본 함수와 주고받는 값은 유한한 일반 JSON 자료로 제한되므로 DOM 객체나 Promise를 반환하는 함수, 저장소 전체 앱 실행까지 지원하는 것은 아니다. 선택한 프로필이 실패하면 다른 프로필로 바꾸어 실행하지 않는다.

Chromium의 원본과 실험은 서로 다른 sandbox renderer와 임시 세션을 쓴다. 계정 정보와 Node·호스트 파일 API를 전달하지 않으며 네트워크·다운로드·장치 권한을 차단한다. Windows Job은 작업 메모리 1 GiB와 프로세스 16개를 제한하고 소유한 작업의 종료를 확인한다. 실행 시간 제한은 CPU 할당량이 아니며 OS 전체 파일 접근을 차단하는 보장은 아니다. 지정 실행 파일·worker·자산의 크기와 SHA를 연결하지만 그 연결만으로 Electron의 전체 바이너리 의존성을 검증했다고 주장하지 않는다.

고정 원문·순서·프로토콜·문헌·리뷰·입력과 실제 호출/fixture·원시 응답·관측·종료 확인을 보존하고 이후 분석과 내보내기에서도 연결을 확인한다. 정리 미확인 상태에서는 계속 실행하지 않는다. 계측에는 브라우저 및 비동기 bridge 비용이 포함되므로 일반 앱의 지연 성능으로 해석할 수 없다. UI와 문서는 Pretendard를 사용하지만 Canvas 글자는 Windows에 있는 글꼴과 실험 환경에 의존하며 외부 글꼴을 내려받지 않는다.

이 설계의 Chromium 지원은 Windows에 한정한다. macOS 네이티브 Chromium 실행·배포, 실제 앱 전체 사용성, 시각 인지나 기하 정확도, 학술지 수준 논문 품질은 별도 확인이 필요하다. 현재 소스와 설치본의 검증 상태는 [검증 기록](standalone-verification.md)에 기록한다.

## 0.13.1 전환 및 검증 이력 — 2026-10-06

당시 앱·엔진 소스 버전은 `0.13.1`이었다. 아래 전환 작업의 실제 설치·계정·논문 검사는 이전 `0.13.0`의 이력이다. 과거 플러그인 논문·Cloud export·Mac 엔진 CI를 새 앱의 성공으로 계산하지 않는다.

승인한 5단계 개선은 소스 반영과 검증을 완료했다. 0.13.1 Windows 설치 파일을 만들고 패키지의 소스·글꼴·런타임을 전수 대조했다. 새 설치·실계정·논문 생성과 macOS 빌드는 이번에 실행하지 않았다. 검사 수·해시·범위는 [0.13.1 검증 기록](standalone-ui-provenance.md)에 있다.

| 단계 | 반영 및 확인 |
| --- | --- |
| 1. 빌드와 글꼴 | Tailwind renderer 스캔 범위, 로컬 Pretendard Variable·OFL, 실제 글꼴 로딩과 ASAR 포함 확인 |
| 2. 취소와 잠금 | 실제 종료·증거 저장을 확인한 뒤 해제, 실패/재시작 시 잠금 유지, 로그인 없이 정리 재시도 |
| 3. 종료와 재시도 | 닫기·종료 단일 작업, 저장 완료 대기, 실패 시 창 유지, 엔진 ack와 실제 정상 종료 확인 |
| 4. 재개 eligibility | 준비/원고 재개를 구분하고 근거 재검증, 불명확 실행·제어 실패·정리 미확인 거부 |
| 5. 저장과 패키징 | 네이티브 선택창, Markdown·TeX와 PNG 함께 저장, 원자적 교체, Windows 0.13.1 NSIS 및 전수 SHA 확인 |

**독립 앱과 legacy 정리를 구현했고, 이용 가능한 Windows 환경에서 실제 구독 연구3/3편을 완료했다. Source12 앱/SDK203/1skip·Electron4(20.2초), Windows 실제 설치·파일 대조·자체 새 응답을 통과했다. 변경 없는 Source11 Python794/7skip·세 런타임 및 Mac 전량 정적 검사 근거를 보존하고 설치 runtime4463/source22를 전수 대조했다. Premiere·navigation·Frontron CLI의 단회 실험·새 원고·별도 문맥 리뷰·5종 출력 및 실제 앱 저장15개를 확인했다. PDF29쪽 직접 시각 검수·DOCX 전체 내용·ZIP 전 멤버 검수를 통과했다. 앱 PDF 열기 요청·실제 폴더 표시와 별도 Chrome의 정확한 저장본 PDF 표시를 구분했고, 정상 종료 뒤 같은 연결·5개 작업 복원과 새 Astra 응답을 확인했다. 이전 artifact와 단회 과학실험을 보존한다.** 완료한 구현·합성 검사·실제 계정 검사·외부 플랫폼 정적 조립을 아래에서 구분한다. 이전 다섯 번째 설치본에서 프로토콜 무효 보고서 export를 완료한 이력은 보존하며 합격 논문으로 계산하지 않는다.

## 시작 상태와 보존 경계

- 실제 체크아웃: `C:\Users\Andongmin\Desktop\repository\paper-factory`.
- 최초 조사 시점은 branch `main`, HEAD `ac22fdd`, Python `0.12.0`, 깨끗한 작업 트리였다. 당시 `desktop/`의 추적되지 않은 `dist/`, `node_modules/`는 재사용 가능한 앱 소스로 간주하지 않았다.
- 사용자가 제공한 AGENTS.md에 따라 필요한 변경과 기존 의존성 조사를 바탕으로 작은 동작 단위로 구현했고, 교체한 경로는 호환 fallback 없이 제거했다.
- 기존 `.paper-factory/`, `output/`, 과거 `dist/`의 연구 자료·receipt·실패 기록과 다른 세션의 프로세스는 보존한다. 새 앱은 OS 앱 데이터의 `Paper Factory Standalone/`만 사용하며 이전 연구를 자동 복구하거나 수정하지 않는다. fixture 검증은 별도 소유 임시 데이터 디렉터리를 사용했다.

## 최종 구현과 정리 범위

| 분류 | 최종 상태 |
| --- | --- |
| 앱 | Electron main의 공식 SDK·OS 보호 저장소, 제한된 preload IPC, React 19/Tailwind 4/Base UI와 원본 neobrutal-ui 화면 구현 |
| 연구 | 공개 저장소 URL·계정별 최근 공개 저장소 최대 100개, 목표·작성/리뷰 모델 선택, 실제 단계·오류·취소·명시 재개·재시작 상태, 결과 저장/열기/폴더 구현. 서로 다른 저장소의 실제 연구3/3편·실제 저장15종·정상 재시작 복원 완료 |
| 엔진 | IPC import closure Python 20개와 별도 macOS guardian 1개, QuickJS worker 1개로 구성. 고정 원본·SQLite·프로토콜/관측·receipt/journal·종료 확인·scientific controls·분석·문서 변환 유지; 실제 완료 연구3편의 출력과 이전 실패 보고서 export 보존 |
| 빌드 입력 | QuickJS archive/metadata, host catalog, Pandoc notices를 `desktop/runtime-inputs/`로 이동. Windows x64와 macOS Intel/ARM CPython 3.14의 실제 입력만 유지 |
| 제거 | plugin manifest·host skill·Cloud 전달·plugin ZIP·CLI·Docker/WindowsRunner/AppContainer·범위 밖 투고/포털 코드 및 직접 대응 설정·스크립트·CI·테스트 제거 완료 |
| 증거 | 이전 논문·관측·receipt·실패 기록 보존. 제거 전 자원/문서의 원본 bytes·해시와 역사 문서 보존 |

세부 근거는 [정리 완료 기록](standalone-cleanup-inventory.md), [인증 조사](standalone-auth-research.md), [UI 출처](standalone-ui-provenance.md), [검증 기록](standalone-verification.md)에 있다. 당시 Python engine과 pyproject도 `0.13.0`이며, trusted 분석·문서 변환·Windows Job Object와 macOS guardian을 유지했다. 당시 앱 실험 범위는 빈 dependencies의 QuickJS JS/TS 생산 함수였고 DOM·네트워크·범용 Node/Python 실험으로 확장하지 않았다. 현재 Windows Chromium 지원 범위는 위 최신 설계에 별도로 기록한다.

## 단계별 완료 기준

### 0. 조사 및 계획

- [x] 요청 전문·실제 Git 상태·버전·기존 desktop 내용 확인.
- [x] 공식 cookbook/sign-in/models/preview 문서, 엔진·테스트·의존성·DevKit·neobrutal-ui 조사.
- [x] 실제 import와 실행 책임을 추적해 재사용·이동·삭제·증거 보존 범위를 확정.

### 1. 연결 검증용 최소 Electron 앱 — 실제 통과 게이트

- [x] Electron main에서 공식 DevKit/SDK로 자체 ChatGPT OAuth 등록·로그인.
- [x] OS 보호 저장소와 Renderer/Python에 토큰을 전달하지 않는 경계 구현.
- [x] 실제 계정별 모델 목록과 OAuth Responses 호출, `response.completed` 및 비어 있지 않은 출력 확인.
- [x] 취소·만료·권한 부족·사용량 제한·통신 실패의 구분과 조치 표시 구현; 모의 오류 검사와 실제 사용량 제한 실패 증거 보존.
- [x] 크레딧 안내와 공식 설정 페이지 연결. 앱 확인 체크박스를 계정 설정 읽기/변경으로 표현하지 않음.
- [x] React 19/Tailwind 4/Base UI와 고정 원본 neobrutal-ui 컴포넌트 적용, 빌드·타입 검사·Electron fixture 통과.
- [x] Windows 첫 실제 OAuth 게이트에서 완료 응답, 앱 정상 완전 종료, 새 프로세스의 같은 연결 복원과 새로운 완료 응답 확인.
- [x] Windows 두 번째 설치본의 런타임 준비, 자체 연결 복원과 새로운 완료 응답 확인.
- [x] 내보내기·비재실행·파일별 컴파일 receipt 보완을 반영한 다섯 번째 Windows 설치본의 자체 연결 복원과 새 실제 응답 확인.
- [x] 합성 controller/SDK/OS 암호화 fixture와 실제 OAuth·구독 증거 구분.

첫 연결 게이트는 2026-10-05 지정된 Chrome에서 앱의 신규 OAuth와 구독 권한 동의를 사용했다. 사용자가 승인한 크레딧 사용 옵션을 공식 페이지에서 켜고 다시 로드해 저장을 확인했다. 다른 앱의 인증 파일은 읽거나 복사하지 않았다. 이 성공은 최종 새 설치본의 연구 3편 성공을 증명하지 않는다.

### 2. 저장소 하나의 연구

- [x] 제한된 Python IPC와 앱 내부 실행 환경 연결, 포함 런타임 상태와 GUI ready 일치 확인.
- [x] 새 계획·코드·별도 문맥 리뷰·격리 실험·분석·원고·별도 문맥 원고 리뷰·변환을 잇는 controller 구현.
- [x] 모델 원문과 해시를 먼저 보존한 뒤 검증·단계 제출. 리뷰 거절·수정·중단·실패 기록 유지.
- [x] 재개 시 receipt·엔진 상태·실행 요청 기록·worker journal·cleanup 경계 유지. 실험 dispatch를 요청 전에 저장하며 중단·불명확한 실험을 자동 재실행하지 않음.
- [x] 실제 설치본의 ChatGPT 연결에서 Premiere/navigation/Frontron CLI의 전체 연구·원본 PDF 저장·앱 열기 요청·Chrome의 정확한 저장본 표시 검증. 연구3편의 최종 파일과 정상 재시작 검증은 아래 기준에 기록.

새 reviewer 요청은 이전 응답/대화 ID 없이 전체 후보와 고정 프로토콜·실제 근거를 전달한다. 엔진은 controller의 host-submitted review를 기록하며 학술지의 peer review나 외부 검증된 연구자 독립성으로 표현하지 않는다.

### 3. 작업 및 결과 관리

- [x] 실제 workflow/SQLite 상태에 맞는 목록·단계·오류·취소·명시 재개·재시작 복원 구현.
- [x] 공개 GitHub 계정 URL의 실제 공개 저장소 선택과 실패 안내 구현.
- [x] 연결·새 연구·결과의 고정 사이드 탭과 독립 패널 스크롤 구현, 입력/모델 선택 유지 및 키보드 탐색 fixture 확인. 네 번째 Windows 설치본에서 실제 화면·연결 복원·새 응답 확인.
- [x] 성공한 기존 실험 이후 취소된 원고의 명시 재개 경로 구현. 전수 해시·실행·cleanup·실제 양성/음성 제어·분석 연결을 확인하고 이전 상태와 재개 receipt를 추가 보존하며 실험은 재실행하지 않음.
- [x] 대기 중인 생성·계획·분석 작업의 추가 근거 native 선택과 다음 작성/별도 리뷰 전달 구현. 여덟 번째 설치본에서 6개·37,667 bytes 보존과 가져오기 후 대기 해제·실행 버튼 활성 상태 확인; 자동 재개·모델 호출 없음.
- [x] 결과 ID allowlist·동결 해시·앱 데이터 경로 확인을 공통으로 사용해 저장·열기·폴더 표시 구현. 저장은 검증한 bytes를 기록하고 다시 해시 확인.
- [x] 다섯 번째 설치본에서 기존 프로토콜 무효 보고서의 export를 명시 재개해 `exported·completed` 표시와 PDF reader 열기를 확인. 성공 논문 수에 포함하지 않음.
- [x] 실제 완료 연구3편의 PDF/DOCX/Markdown/TeX/재현 ZIP을 앱에서 각각 저장해15개 전체 크기/SHA 대조. 앱 PDF 열기 요청·정확한 폴더 표시와 Chrome 저장본 표시 확인; native Reader의 정확한 파일·렌더링은 미확인.

### 4. 런타임 포함 설치본

- [x] 개발·빌드 단계에서 해시로 고정한 Python·Node·QuickJS·실험/분석/문서 변환 의존성을 포함하도록 구현. 설치 앱의 실행 시 다운로드·사용자 터미널 설치 흐름 없음.
- [x] 정리 후 최종 Windows 런타임 4,463개 파일·30개 wheel, 전체 해시 및 native probe 통과.
- [x] 정리 후 최종 Mac 외부 플랫폼 정적 조립·해시 검사: ARM 4,349개 파일, Intel 4,346개 파일.
- [x] Windows·macOS ARM/Intel의 전체 런타임·설치본·패키지 검증 CI 정의.
- [x] 여덟 번째 Windows 설치본 설치·EXE/ASAR 대조·4,463개 runtime 파일 전수 해시·실제 연결 복원·새 응답 확인.
- [x] 아홉 번째 Windows 설치본의 전체 계획 원문 전달과 취소 상태 갱신 구현·회귀·실제 설치·파일 대조·자체 새 응답·native 취소 완료 확인. Premiere의 새 계획 요청 원문 전체 대조; 과학실험 완료와는 구분.
- [x] 열 번째 Windows 설치본의 원고 수정, 전체 회귀·세 런타임 재조립·설치와 파일 대조. Premiere 두 번째 원고·리뷰·export 및 원래 76개 artifact 보존·실험 재실행 없음 확인. 제목 표시의 실제 시각 검사 실패는 보존.
- [x] 실제 설치 앱을 Playwright Electron에 연결해 동일 앱 데이터·실제 버튼·원고 요청을 조작. OS 화면 캡처·좌표 입력·dialog mock 없음.
- [x] 열한 번째 소스의 전체 Python794/7skip·앱/SDK184/1skip·Electron4 검사와 세 런타임 재조립·Mac 전량 정적 검사, Windows NSIS 설치·EXE/ASAR/화면/runtime4463/source22 대조·자체 새 응답. 실제 원고 수정 receipt의 이전100개 전량 불변 확인.
- [x] 화면에 의존하지 않는 앱 내부 저장 경로 창의 구현·새 설치와 Premiere 실제5종 저장·원본 size/SHA 일치 확인.
- [x] Source12에서 root README·모든 경로의 license/notice 원문과 controller 보존 계약을 코드/원고 작성·새 리뷰에 전달. 신규19/전체203·Electron4 검사, Windows NSIS 실제 설치·앱/runtime 전량 대조·자체 연결 복원·새 Astra 응답. 과학실험·프로토콜·기존 실패 변경 없음.
- [x] 최신 Windows 설치본에서 단회 실험·별도 원고 리뷰·최종 파일/저장 검수를 마친 연구3편 완료. 정상 종료·새 프로세스의 같은 연결/5개 작업 복원·새 완료 응답 확인, 추가 과학실험0회.
- [ ] 개발 도구 없는 Windows 환경에서 설치 및 전체 연구 검증.
- [ ] macOS 네이티브 실행·POSIX 실행 권한·DMG 생성/설치·CI 실행·로그인·전체 연구 검증.
- [ ] Windows 코드 서명 및 macOS 코드 서명/공증 검증.

현재 Windows·Mac ARM·Mac Intel 세 프로필의 정적 파일 대조는 통과했다. Mac 자료는 Windows NTFS에서 조립한 정적 증거다. 원본 아카이브 Python 실행 모드는 `0775`, Node/Pandoc은 `0755`이며 builder의 최종 실행 모드는 `0755`다. 파일 내용·해시·아키텍처 확인을 실제 Mac 파일시스템의 권한 유지나 실행 성공으로 계산하지 않는다. Mac 네이티브 실행·DMG·CI와 개발 도구 없는 환경은 미검증이며 설치본은 서명하지 않았다. 이전 정리 전 소스의 Mac 조립·정적 패키지 및 실패 기록도 별도 이력으로 보존한다.

### 5. 서로 다른 공개 저장소 3개의 최종 검증

- [x] 서로 다른 `andongmin94` 공개 저장소 `neobrutal-ui`, `frontron`, `premiere-ai-harness`의 실제 원본·고정 commit·원문 라이선스·production callable·독립 oracle/comparator 및 선정/제외 이유 조사·보존.
- [x] 최종 설치본과 실제 ChatGPT 연결에서 서로 다른 연구3개 완료. 각 성공 실행1회, 기존 결과 주입·과학실험 재실행 없음.
- [x] PDF10/10/9쪽 전쪽 직접 시각 검수, DOCX 전체 내용·각 OOXML19멤버, ZIP176/476/261멤버 전량 CRC/크기/SHA 및 동결 inventory 대조.
- [x] 앱 버전·설치본 해시·실제 모델 요청·환경·연구 ID·단계/리뷰/실패 증거 및 현재124/72/112개 artifact 전량 해시 보존.
- [x] 완료3편의 PDF/DOCX/Markdown/TeX/재현 ZIP/증거 경로·크기/SHA 및 검증 표를 [최종 검증 기록](standalone-verification.md)에 통합.

[저장소 선정 기록](standalone-repository-selection.md)의 후보 질문과 fixture는 사전 명세이며 관측값이 아니다. 완료3편의 실제 DOCX 전체 본문·표·그림·OOXML 내용 검사를 마쳤다. 실패 보고서의 별도 내용·ZIP 해시 진단은 보존했고, 관리 런타임에 LibreOffice가 없어 DOCX 페이지 렌더링에 따른 시각 검증은 수행하지 않았다. DOCX 내용·ZIP 해시 검증을 DOCX 시각 검증으로 표현하지 않는다.

### 6. 정리와 보고

- [x] 현재 요구 밖 obsolete code·plugin/Cloud/CLI 안내·설정·CI·테스트·링크 잔재 정리, 필요한 런타임 입력 이동.
- [x] 과거 결과·실패·원본 자원과 문서 증거 보존, 역사 문서와 현재 사용 안내 분리.
- [x] 구현·합성 검사·실제 계정·외부 플랫폼 정적 검사·미검증 제한을 구분하고 초안을 학술지 승인/출판으로 표현하지 않음.
- [x] 최종 새 설치본 및 실제 연구3편 결과를 [검증 기록](standalone-verification.md)과 산출물 표에 통합하고 [설치·UI 근거](standalone-ui-provenance.md)에 실제 저장/열기/종료/복원 경계를 기록.

## 최종 세 연구 완료: 2026-10-06 04:20 KST

| 연구 | 실제 연구 ID | 성공 실행 / 코드 attempt / 최종 draft | 전쪽 PDF 직접 검수 | DOCX 내용 | 재현 ZIP |
| --- | --- | --- | --- | --- | --- |
| Premiere 승인 구간 | `research-a90ccd5fee76` | 1 / 1 / 3 | 10/10쪽 통과 | 65문단·3200단어 | 176멤버 전량 통과 |
| Navigation 활성 경계 | `research-6561ac63db99` | 1 / 1 / 1 | 10/10쪽 통과 | 66문단·3261단어 | 476멤버 전량 통과 |
| Frontron CLI 입력 | `research-f68ee0139f78` | 1 / 1 / 1 | 9/9쪽 통과 | 62문단·3046단어 | 261멤버 전량 통과 |

각 DOCX는 표2개·그림1개와 OOXML19멤버를 전량 검사했다. 실제 Astra 작성·새 Sol 리뷰가 최종 원고를 승인했고, 각 연구의 기본5종은 앱의 실제 저장 동작으로 원본과 같은 크기/SHA를 확인했다. Markdown·TeX의 상대 참조 `figure-1.png`는 실제 사용자 저장 ZIP의 기존 bytes를 CRC·inventory·동결 SHA로 대조한 뒤 **2026-10-05 19:11:24 UTC**에 세 사용자 폴더에 별도로 전달했다. 기본15종과 실제 원고·관측은 변경하지 않았으며 그림 전달을 앱 Save 동작으로 계산하지 않는다.

PDF 열기3회는 앱의 shell 요청 완료·pending 해제·오류0을 확인했고, 폴더3회는 Explorer의 정확한 전체 export 경로와 각20개 항목을 읽었다. 별도 Chrome에서 세 사용자 저장 PDF의 정확한 file URL·전체 SHA와 첫 페이지를 확인했다. native Reader의 정확한 파일 경로/렌더링과 DOCX 페이지 시각 검증은 미확인이다.

**2026-10-05 19:11:59 UTC** 정상 종료와 해당 EXE 프로세스0개를 확인한 뒤 **19:12:24 UTC** 새 packaged 프로세스에서 같은 ASAR·자체 userData·연결 및5개 작업을 복원했다. 세 연구는 exported/completed/idle이고 **19:13:33 UTC** 새 Astra 연결 확인 응답이 완료됐다. 추가 과학실험0회이며 앱은 유휴 상태로 열려 있다. 세 연구의 결론은 각각 고정한 유한 입력·연구자 정의 계약에 한정하며 학술적 새로움·학술지 승인·출판을 보장하지 않는다. Mac native/POSIX 권한/DMG/설치/CI, clean VM 및 코드 서명/공증은 미검증으로 유지한다.

후속 **19:23:34 UTC** 읽기 전용 재시작 감사에서 세 완료 연구의 workflow17필드·동결 metadata/path/size/SHA 및124/72/112개 전체 bytes가 종료 전 기준과 일치했다. 설치 EXE/ASAR·앱 자산6개·runtime4463파일·engine22원문도 일치했다. 이전 SemVer의102개 역사 artifact는 이전 기준과 대조했고, preview는 현재110개 해시를 확인했지만 전체 이전 bytes 기준이 없어 전후 동일을 주장하지 않는다. 감사 영수증과 최종 저장본·그림 의존성 교차검수는 [최종 검증 기록](standalone-verification.md)에 기록한다.

## Source8/9 검증과 초기 연구 이력: 2026-10-05

최신 앱·SDK 회귀는 **160 passed, 1 skipped**, 별도 임시 데이터의 Electron fixture는 **4 passed, 16.9초**다. 계획에서도 선언한 원문 전체·루트 메타데이터를 전달하며 Unicode 페이지·SHA·바이트 크기·문맥 상한을 검증한다. 취소 완료까지 lease를 유지하고 엔진의 실제 상태를 저장·반환한다. 소스 완료 근거는 `desktop/.paper-factory/standalone-verification/controller-source9-fix-6bb85d72-e958-4fac-a5a1-91f126de2d43/source-final.json`이다. 이전 추가 근거 반환 snapshot의 `busy=false` 회귀는 수정 전 실패·수정 후 통과를 보존했으며 근거는 `.paper-factory/standalone-verification/evidence-return-lease-20261005-c86ec677b92747c5b3814be040434628/`이다. 변경 없는 Python 엔진의 전체 회귀는 **756 passed, 7 skipped (134.25초)**이며 `.paper-factory/standalone-verification/supporting-import-full-20261005-2b032b42f8d34d338d0bb855888d2f38/`에 있다. fixture의 합성 인증과 모의 요청은 실제 OAuth·모델 응답·논문 증거와 구분한다.

여덟 번째 Windows 설치는 **2026-10-05 13:50:24.002–13:51:12.871 UTC, exit 0**으로 완료했다. **13:51:15.081 UTC**에 런타임 **4,463개 파일·564,850,370 bytes·소스 22개(Python 21개·worker 1개)**를 전수 대조했고, 자체 연결 복원 후 Astra의 새 완료 응답을 **13:52:54 UTC**에 확인했다. 기존 5개·29,186 bytes의 근거에 고정 commit의 공개 API 자료 8,481 bytes를 추가해 **6개·37,667 bytes**를 실제 보존했다. 가져오기 후 버튼이 활성 상태임을 확인했으며 새 작성·리뷰 요청은 대기 중이다. 현재 가져온 시각은 문서가 주장하는 실험 전 활동의 증거가 아니다. 설치본 크기·해시는 [UI 검증 기록](standalone-ui-provenance.md)에 있고 실제 native 가져오기 근거는 `.paper-factory/standalone-verification/evidence-return-install-a2101e4c-cd61-4b57-9583-09a50971e26e/`에 있다. 이 설치·연결·가져오기 확인은 다섯 번째 설치본의 실패 보고서 export와 별도이며, 합격 논문은 여전히 **0/3**이다.

이전 Node identity 수정 체크포인트의 앱 controller/Responses parser와 공식 SDK 회귀는 **101 passed, 1 Windows skip**이었다. 당시 Electron fixture는 **4 passed, 14.3초**이며 OS 보호 저장소의 합성 자료·재실행, 사이드 탭과 입력 유지, 크레딧/연구 화면과 제한된 IPC 등을 확인했다. 합성 암호화와 모의 모델 결과는 실제 계정 인증·논문 생성 증거가 아니다. 당시 early Agg 초기화 회귀를 포함한 Python 전체 검사는 **671 passed, 7 skipped (126.10초)**였다. 지정한 앱 내장 Node와 다른 경로를 가리키던 합성 process handle fixture 두 곳을 고쳤고 생산 프로세스 소유권 검사는 유지했다. 이전 잘못 지정한 Node의 skipped 검사와 불일치 fixture 실패 로그도 보존했다. 집중 검사들은 전체 검사와 겹치므로 합산하지 않는다. 근거는 `.paper-factory/standalone-verification/node-identity-fixture-20261005-37266708786b4352a82f3f21d60608b1/`이며 이전 정리 단계 검사는 [정리 기록](standalone-cleanup-inventory.md)에 별도로 있다.

첫 실제 연구 `research-9a477cc5d054`는 실험 attempt 1과 분석까지 수행했다. 실제 production 호출 17회, scalar 관측 32개, 실제 양성 및 의도적 오류 음성 제어가 통과했고 worker cleanup을 확인했다. 누락됐던 전체 원시 자료·고정 소스·실험 코드·runtime manifest·승인 코드 리뷰를 작성/리뷰 양쪽에 전달하고 문헌 검색을 보충한 뒤, 실험을 반복하지 않고 원고 작성만 재개했다.

완전한 자료를 받은 별도 문맥의 실제 원고 reviewer는 JSON projection으로 관찰할 수 없는 own-key/undefined 구분을 고정 metric이 요구하고, 보존되지 않는 emitted JavaScript 원문과 별도 pre-call 검증 receipt를 고정 프로토콜이 요구한 점을 지적했다. 기존 프로토콜과 관측을 고쳐 유효한 연구로 바꾸지 않았다. 새 작성자는 프로토콜 무효를 보고하는 실패 원고로 수정했고, 실제 reviewer가 그 해석을 수락했다. 이 실패 연구는 합격 3편에 포함하지 않는다.

이 실패 원고의 첫 PDF(9쪽)·DOCX·Markdown·TeX·ZIP 생성 뒤 export 검증 요청은 시간 초과로 중단됐다. 독립 읽기 진단에서 PDF 전쪽 텍스트, DOCX 내용, ZIP CRC와 510개 inventory 해시는 일치했고 기존 부분 파일과 실패 기록을 보존했다. 고유 export attempt·phase journal·부작용 없는 통계 재계산 보완을 반영한 다섯 번째 설치본에서는 같은 실패 보고서의 export를 명시 재개해 `exported·completed` 상태와 PDF reader 열기를 확인했다. 첫 과학실험 attempt 1은 다시 실행하지 않았다. 과거 timeout의 원인을 이 성공만으로 확정하지 않으며, 전체 사용자 저장 동작과 최종 문서 시각 검수는 남아 있다. 같은 저장소의 다른 navigation callable과 별도 질문은 새로운 후보로 조사했으며 아직 실행하지 않았다. 최종 합격 논문 수는 현재 **0/3**이다.

첫 실제 인증 게이트와 이후 설치본의 실제 새 응답은 통과했고, 네 번째 설치본에 사이드 탭 UI를 적용했다. 이후 export·비재실행·컴파일 증거 보완 소스의 Windows 런타임과 Mac ARM/Intel 정적 조립을 갱신했다. 다섯 번째 Windows 설치는 11:42:29 UTC에 종료 코드 0으로 끝났으며 전수 해시·자체 연결 복원·새 실제 응답과 실패 보고서 export를 확인했다. 근거는 `.paper-factory/standalone-verification/installed-app-20261005/goal-install-f4f99acd-fa8d-40ec-b4e9-52bc7d18b18b/`에 있다. **과학적으로 유효한 실제 구독 연구 3편은 아직 검증 완료로 체크하지 않았다.** Mac 실행·DMG·CI, 개발 도구 없는 환경, 코드 서명/공증, 최종 문서 검수는 남은 범위다.

초기 Electron launch 실패·diagnostic 실패·이전 설치본의 미포함 파일·사용량 제한 실패 기록을 삭제하지 않았다. `.paper-factory/standalone-verification/electron-launch-before-resume/`, `electron-launch-after-resume/`, `electron-launch-path-normalized/` 등은 당시 실패의 이력이다. 끝 슬래시의 Windows 인자 인용 문제는 `resolve` 정규화로, ESM 최상위 `await app.whenReady()`의 순환대기는 readiness `.then(...)` 초기화로 수정했다. 이전 빌드 해시와 당시 성공 수는 최신 검사와 구분한다.

## 공식 근거

- [Sign in with ChatGPT cookbook](https://developers.openai.com/cookbook/articles/sign-in-with-chatgpt)
- [공식 sign-in 문서](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)
- [Models and inference](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference)
- [Preview limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)

현재 직접 호출은 `https://api.openai.com/v1/responses`, OAuth bearer, `store: false`, `stream: true`, 배열 `input`을 사용한다. 성공 판정에는 `response.completed`가 필요하다. 미지원 요청 필드는 보내지 않으며 실제 계정 권한·이용 제한은 실제 호출로 확인한다.
