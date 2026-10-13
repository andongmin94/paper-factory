# Paper Factory

공개 GitHub 저장소를 분석해 **IEEE Software·IEEE Security & Privacy에 투고할 영문 Feature Article을 만드는 데스크톱 앱**입니다. 실제 소스·문헌·공식 기술 문서를 읽고 분석, 매체별 원고, 독립 평가, Word·PDF를 저장합니다.

현재 소스 버전은 **0.14.20**입니다. 두 매체 중 저장소의 실제 근거와 맞는 대상만 작성합니다. Software는 실무 설계 대안·비용·적용 조건·교훈, S&P는 보안·프라이버시 문제·위협과 권한 경계·완화책·잔여 위험에 집중합니다.

[현재 설계](docs/ieee-magazine-redesign.md) · [현재 상태와 인계](docs/next-session.md) · [실제 앱 검증](docs/standalone-verification.md)

## 처음 사용하기

1. **연결**에서 **Continue with ChatGPT**로 로그인하고 모델 목록을 새로고침합니다.
2. **새 연구**에 공개 GitHub 저장소와 분석 목표를 입력하고 작성·독립 평가 모델을 선택합니다.
3. **연구 시작**을 누릅니다. 설계·필요한 근거 확보·공통 분석·적합한 매체별 집필·출력 선검사·독립 평가가 이어집니다.
4. **결과**에서 원고별 근거·평가·보완 항목과 실제 Word·PDF를 확인합니다.
5. 중단된 작업은 **IEEE 매체별 미완료 투고본 재개**로 같은 연구에서 이어갑니다. 이미 완료되거나 실패한 요청을 새 요청으로 반복하지 않습니다.
6. **실제 저자 정보 입력**에 이름·소속·이메일과 ORCID를 저장하고, 각 매체의 **저자 정보 반영해 출력**으로 새 Word·PDF를 만듭니다. 본문·심사·기존 파일과 연구 횟수는 유지합니다.

목표에는 독자가 내려야 할 판단을 적습니다. 예: “이 데스크톱 앱의 네이티브 권한 경계를 추적하고, 개발자가 선택할 설계 대안과 적용 조건을 설명해 주세요.”

## 작성과 보완

고정한 소스에서 한 설계를 만들고, 공식 기술 문서와 가까운 문헌을 확보해 공통 분석을 수행합니다. 범용 첫 원고·심사를 따로 만들지 않고 적합한 매체의 실제 원고를 바로 작성합니다. 읽기 쉬운 주제별 제목을 허용하며 실제 근거·방법·한계·AI 사용 공개를 유지합니다.

Word·PDF를 먼저 생성해 분량과 형식을 점검한 뒤, 완전한 원고와 근거를 새 독립 요청으로 평가합니다. 공식 비교 문서가 부족하면 실제 심사가 지정한 문서를 확보하고 해당 원고를 수정합니다. 보존된 소스에서 재도출할 수 있는 국소 분석·문장 수정에는 공통 분석을 다시 실행하지 않습니다. 새 분석이 필요한 작업은 실제 심사 요청과 남은 분석 예산에 연결합니다.

공통 분석·문헌 수집과 매체별 집필·평가는 각각 최대 3회의 실제 요청을 누적합니다. 비교 문서 수집도 최대 3회이며 한 수집에는 최대 3개 문서를 사용합니다. 실패·중단과 원 자료를 보존하고, 새 근거가 없는 동일 요청을 반복하거나 한도를 초기화하지 않습니다. 끊긴 원고의 완성된 본문이 보존돼 있을 때만 누락된 꼬리를 별도 1회 복구합니다.

## 투고 준비도

내용 평가, 현재 Word·PDF와 확인한 공식 형식, 저자·제출 확인을 구분합니다. 내부 평가 통과는 학술지의 채택 판단이 아닙니다. IEEE Software의 확인한 분량·초록·참고문헌·세 가지 시사점을 검사하며, S&P의 직접 확인하지 못한 제출 수치는 미확인으로 표시합니다.

최종 제출에는 실제 저자 이름·소속·연락처, 해석과 AI 사용 공시·권리·선언 승인, 최신 투고 규정과 모든 출력 페이지 검토가 필요합니다. 같은 사례를 바탕으로 만든 두 버전은 투고처 선택용이며 별개의 독립 연구로 동시에 제출하는 산출물이 아닙니다.

저자 정보 출력은 모델을 호출하지 않으며 현재 원고마다 최대 3회입니다. 실패·중단도 사용 횟수에 남고, 같은 정보의 완료 출력은 다시 생성하지 않습니다. 저자 정보나 원고가 바뀌면 이전 출력을 현재본으로 표시하지 않습니다. 정보 입력만으로 저자 승인이나 실제 투고를 완료 처리하지 않습니다.

## 결과 저장과 초기화

연구는 이 PC의 앱 데이터에 저장됩니다. 취소 후에는 종료 정리를 확인한 다음 같은 연구를 재개합니다. 이전 원고·심사·근거·실패·횟수는 보완 과정에서 유지합니다.

2026-10-11 사용자의 명시적 삭제 요청으로 기존 연구와 출력·연구 ZIP·횟수를 초기화하고, Frontron을 숨김 Electron·Playwright의 정상 UI에서 새로 시작했습니다. 새 검증 기록은 로컬 `output/playwright/two-magazine-fresh-20261011`에 보존합니다. 원고·실행 증빙·계정 자료는 Git에 포함하지 않습니다. 과거 연구 파일과 9개 학술지 작업은 현재 실행에 사용하지 않습니다.

## 설치

[Windows x64 설치 파일 0.14.20](https://github.com/andongmin94/paper-factory/releases/tag/v0.14.20)을 제공합니다. Python·Node·문서 변환 런타임이 포함되어 Docker나 별도 TeX 설치가 필요하지 않습니다. 코드서명 인증서가 없는 unsigned 배포본입니다.

NSIS payload와 포함 파일의 해시를 대조했고, 같은 payload의 실제 앱에서 엔진 초기화·Frontron 저자 출력·파일 저장·정상 종료를 검증했습니다. 이번 검증은 unpacked payload 실행이며 실제 시스템 설치·제거와 macOS 실행은 포함하지 않습니다. 상세 범위는 [실제 검증 기록](docs/standalone-verification.md)을 확인하세요.

## 계정과 데이터

계정 연결 정보는 운영체제 보호 저장소로 암호화합니다. 모델 요청에는 목표, 선정한 코드와 관련 자료가 OpenAI로 전송됩니다. 연구 기록은 이 컴퓨터에 저장하며 기본 Windows 위치는 `%APPDATA%\Paper Factory Standalone\`입니다.

연결 해제는 연구 파일을 삭제하지 않습니다. 연구 데이터 삭제와 계정·런타임 관리는 구분합니다. 인증 정보가 있는 `chatgpt/` 폴더를 공유하지 마세요.

## 지원 범위

공개 GitHub 저장소의 코드·문서 분석을 지원합니다. 공식 문서·문헌 부족을 숨기거나 가상의 측정값으로 보완하지 않습니다. 저장소 전체 실행, 벤치마크·사용자 연구와 범용 실험 설계는 새 원고 생성 경로에 포함하지 않습니다. 기존 실험 엔진은 보존 기록의 확인·정리와 관련 검사에 필요한 부분을 유지합니다.

연결·모델 목록·연구 엔진 문제가 있으면 해당 화면의 새로고침과 상태 설명을 확인하세요. 취소·종료 정리가 확인되지 않으면 **정리 다시 확인**을 먼저 사용합니다. 실제 검증 범위와 미검증 항목은 [검증 문서](docs/standalone-verification.md)에 기록합니다.

## 개발

아래 명령은 소스 개발자용입니다. Node.js 24와 npm이 필요합니다.

```powershell
cd desktop
npm ci --no-audit --no-fund
npm run build:runtime
npm start
```

`build:runtime`은 해시로 고정한 실행 환경을 개발 단계에서 다운로드·검증합니다. 설치된 앱은 이 명령을 실행하거나 런타임을 따로 내려받지 않습니다.

```powershell
# desktop/에서 실행
npm test                 # 타입·빌드·controller·SDK 회귀
npm run build:runtime    # 현재 엔진을 포함한 실행 환경 준비
$env:PF_CHROMIUM_TEST_PYTHON = (Resolve-Path runtime/win32-x64/python/python.exe).Path
npm run test:chromium    # Windows 실제 브라우저 실행·격리·종료 검사
npm run test:electron    # Electron UI와 네이티브 IPC 검사
npm run package:app      # 런타임·설치 파일 생성과 패키지 검증
```

Windows 설치 파일과 패키지 검증 기록은 `desktop/release/`에 생성됩니다. 네이티브 IPC 검사는 해당 플랫폼의 런타임을 먼저 빌드해야 실행됩니다.

Python 엔진을 수정하거나 검사하려면 Python 3.11 이상이 필요합니다. 아래는 저장소 루트에서 실행하는 Windows 예시입니다.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,pdf]"
$env:PF_NODE_BIN = (Resolve-Path desktop/runtime/win32-x64/node/node.exe).Path
.\.venv\Scripts\python.exe -m pytest -q
```

## 코드 구성과 문서

| 경로 | 역할 |
| --- | --- |
| `desktop/src/main/` | 계정 연결, 연구 제어, 엔진 실행과 네이티브 파일 저장 |
| `desktop/src/renderer/` | React·neobrutal-ui·Pretendard로 구성한 화면 |
| `desktop/src/shared/` | 화면과 main 사이의 제한된 IPC 계약 |
| `desktop/vendor/siwc-local/` | 출처와 라이선스를 보존한 공식 Sign in with ChatGPT SDK |
| `src/paper_factory/` | 고정 저장소·근거·원고 보존, 로컬 SQLite와 문서 변환; 과거 실험 기록 조회 |
| `desktop/runtime-inputs/` | 배포 런타임의 고정 입력과 라이선스 |

[앱 전환 이력](docs/standalone-app-plan.md) · [인증 구현 기록](docs/standalone-auth-research.md) · [과거 저장소 선정 이력](docs/standalone-repository-selection.md) · [코드 정리 기록](docs/standalone-cleanup-inventory.md)

현재 입력부터 원고·심사·보완·저자 출력까지의 전체 흐름과 이번 분석에서 고친 문제는 [두 IEEE 매체 연구·집필 설계](docs/ieee-magazine-redesign.md)에 정리했습니다.

다른 PC에서 앱 개발이나 새 연구를 시작하려면 [현재 상태와 재개 지시문](docs/next-session.md)을 확인하세요. 2026-10-11 삭제 요청 이후에는 이전 연구 ZIP이나 사본을 복원해 재개하지 않습니다.

이전 플러그인의 설치·호스트·Cloud 명령은 [0.12.0 역사적 README](docs/history/README.plugin-0.12.0.md)에 보존했습니다. 현재 독립 앱의 사용 방법과 구분해 주세요.

## 라이선스

Paper Factory의 독립 작성 코드는 [MIT](LICENSE)입니다. 함께 포함된 구성 요소는 각자의 라이선스를 따릅니다.

- neobrutal-ui: MIT — [출처와 검증 기록](docs/standalone-ui-provenance.md)
- Pretendard Variable: [SIL Open Font License](desktop/third-party/pretendard/LICENSE) — [출처·해시](desktop/third-party/pretendard/provenance.json)
- 공식 SIWC SDK: [Sign-in with ChatGPT DevKit Noncommercial License v1.0](desktop/vendor/siwc-local/LICENSE) — [변경 범위와 출처](desktop/vendor/siwc-local/PROVENANCE.md)
