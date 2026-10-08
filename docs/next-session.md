# 다른 Windows PC에서 작업 재개

2026-10-08 사용자의 중단 요청으로 작업을 일시정지했다. 이 문서는 현재 작업 상태와 다음 에이전트에게 전달할 지시문이다. Git에는 소스와 문서만 저장하며 연구 원자료·계정·생성된 실행 환경·설치 파일은 포함하지 않는다.

## 그대로 전달할 지시문

> `https://github.com/andongmin94/paper-factory`의 최신 main을 내려받고 `AGENTS.md` 지시, README, `docs/next-session.md`, `docs/standalone-verification.md`를 읽어 기존 작업을 이어가라. 목표는 앱에서 만든 원고가 학술지 투고를 검토할 수준인지 실제 앱 실행과 독립 평가로 확인하고, 부족하면 앱 설계를 개선하는 것이다. 코드 검사 통과를 논문 품질 통과로 보고하지 말고, 심사 기준을 낮추거나 근거를 만들어 승인하지 마라.
>
> 현재 소스는 0.14.20이다. 공식 Unicode 표준의 버전이 고정된 HTML 본문·서지·절 위치·원본 해시 검증과 인용 보존을 구현했다. 제안 3회를 마친 미실행 설계가 질문·비교·표본의 구조적 문제로 반려돼 문헌만 보완할 수 없는 경우에는 실제 문헌 횟수 0/1/2를 유지하면서 기존 독립 재설계 준비 검토를 열도록 개선했다. 기존 PDF·DOI·arXiv 경로, 근거 보존, root당 후속 2개 및 연구당 과학 실행 1회 한도는 유지한다.
>
> Desktop 478개와 native 고유 검사 1,065개가 통과했으며 기존 Windows symlink 권한 검사 3개는 건너뛰었다. Native 최초 실행의 30개 인코딩 오류는 부모·자식 UTF-8을 맞춘 뒤 동일한 실패 검사만 다시 실행해 모두 통과했다. 최초 실패·helper·출력은 보존했으며 한 번에 전부 통과했다고 주장하지 마라. 변경하지 않은 SDK와 Chromium worker는 이전 검사 기록을 그대로 유지한다.
>
> 0.14.20 Windows 설치 파일은 `.paper-factory/p20-release/`에 생성됐고 정적 대조와 숨김 패키지 엔진의 시작 두 번·browser control 7개·정상 종료·재시작·worker journal 비움이 통과했다. 기본 `desktop/release/`는 0.14.19 그대로다. 기본 배포본 전환 helper는 긴 경로 prefix를 이중으로 붙여 preflight에서 실패했으며 실제 rename/copy는 없었다. 사용자의 중단 요청 때문에 재시도하지 않았다. 새 설치·OAuth·다른 PC 실행·macOS는 확인하지 않았다.
>
> **실제 0.14.20 연구 실행은 아직 시작하지 않았다.** 평가 준비 자료는 `ready=false`로 보존했고 최종 `launch-bindings.json`과 `preparation-freeze.json`은 만들지 않았다. 다음 단계는 새 PC에서 환경과 보존 자료의 바인딩을 확인하고, 같은 JIZURA 연구의 앱 `improveResearch` 기능을 실행해 논문 생성까지 이어지는지 확인하는 것이다. 원래 저장소 `https://github.com/andongmin94/JIZURA`, 목표 `다양한 문자의 배치와 자동 크기 조절이 어떤 조건에서 안정적으로 동작하는지 연구해 주세요.`, 작성·검토 모델 `gpt-6-astra`를 유지하라. 실제 평가에 수동 논문 URL·DOI·본문·후보·프로토콜·selector·oracle·예상 결과를 넣지 마라. 후보·문헌 계획·실험·심사는 제품이 생성해야 한다.
>
> JIZURA 원래 연구는 `.paper-factory/j15/73b3b723c72b`, ID `research-7fc481808695`, 원본 source 166파일이다. 현재 부모 제안 3회·문헌 보완 0회·SCI 0회·후속 0개·원고 0개이며 `STUDY_REJECTED`로 보류됐다. 518개 물리 파일과 231개 동결 산출물, 이전 전체 archive와 실패 실행을 보존하라. 마지막 0.14.19 실제 실행은 모델 요청 7개가 완료됐지만 표준 근거·비교 규칙·기여 중요성이 부족해 논문까지 가지 못했다.
>
> 과거 Madi 연구 `.paper-factory/qpos/2dd124a6459a`는 root와 후속 2개의 한도를 이미 사용했다. 이전 원고의 유한 실험 수치가 맞더라도 신규성·중요성이 부족해 투고 준비도가 반려됐다. **Madi를 다시 실행·재가져오기·횟수 초기화하지 마라.** JIZURA도 새 root를 만들어 기존 횟수를 초기화하지 마라. 지금까지 새 투고 준비도를 통과한 실제 완료 원고는 없다.
>
> Git clone만으로 기존 연구 자료가 따라오지 않는다. 별도로 전달받은 `paper-factory-private-evidence-01420.zip`과 `manifest.json`을 먼저 확인하라. ZIP entry의 경로·크기·SHA256을 manifest와 대조하고 새 checkout에 저장소 상대 경로 그대로 복원하라. 기존 파일을 무조건 덮어쓰지 말고 충돌은 먼저 비교하라. 기록·DB·후보·심사·횟수·과학 근거를 수정하지 마라. 자료가 없다면 소스 분석과 환경 준비까지만 진행하고, 실제 같은 연구 재개에는 원자료 전송이 필요하다고 알려라.
>
> 다른 PC에서는 경로·실행 파일·런타임·컴파일 산출물·계정 저장 위치가 다를 수 있다. 이전 PC의 동결 helper와 receipt를 수정하거나 그대로 실행하지 말고, 원본 바이트·native artifact·source·계보·횟수의 동일성을 확인한 별도의 새 PC용 평가 준비 기록을 만들어라. 원본을 변경해야만 재개할 수 있다면 임의로 DB를 고치거나 새 연구를 만들지 말고 원인을 먼저 보고하라. 최신 lockfile과 고정 runtime manifest를 사용해 환경을 준비하고, 플랫폼 변경으로 필요한 검사만 수행하라. 기존 통과 검사를 이유 없이 모두 반복하지 마라.
>
> Windows 자체 실행을 유지하고 Docker를 요구하지 마라. 공식 Codex/ChatGPT 계정 연결을 사용하고 별도 회원가입이나 운영자 DB를 추가하지 마라. 이전 PC의 인증 파일·토큰을 복사하지 마라. 새 PC에 연결이 없으면 앱의 공식 로그인 절차를 사용자에게 안내하라. Electron·neobrutal-ui·모노 톤·Pretendard를 유지하라. Playwright와 숨김 창으로 확인하고 사용자의 다른 작업이나 화면을 방해하지 마라.
>
> 필수 바인딩과 실행 환경 확인을 마친 뒤 일반 앱 경로로 실제 연구를 이어가라. 결과가 보류되면 당시 설계·전체 문헌 원문·심사·raw 응답·실험 횟수·종료 상태를 보존하고 실제 제품 결함을 구분해 개선하라. 원고가 나오면 별도 문맥에서 최근접 원문 본문, 신규성·기여 중요성, 주장과 관측·증명의 대응, 재현 자료 및 모든 PDF 페이지를 확인한 후 결과를 보고하라. 사용자가 중단하면 소유 작업자를 안전하게 닫고 checkpoint를 남겨라.

## 보존 기록

| 항목 | 위치 |
| --- | --- |
| 0.14.20 native 검사 조합 기록 | `.paper-factory/runtime-admission-01420/native-final-reconciled-freeze.json` |
| 0.14.20 패키지 정적 기록 | `.paper-factory/runtime-admission-01420/package-build-71a340e4db25/full-static-source-freeze.json` |
| 포함 엔진 시작·종료 검사 | `.paper-factory/runtime-admission-01420/packaged-engine-dd6f1721-7031-47bf-a0ea-ff920631e065/receipt.json` |
| 평가 준비 중단 checkpoint | `.paper-factory/runtime-admission-01420/evaluator-stop-773349b92cdd/checkpoint.json` |
| 평가 helper·부분 준비 바인딩 | `.paper-factory/chromium-ordinary-jizura-01420/` |
| 새 final helper 독립 검토 중단 기록 | `.paper-factory/chromium-ordinary-jizura-01420/collector-peer-final-stop.json` |
| 마지막 실제 JIZURA 실행 | `.paper-factory/j19/d30d3537ed06/` |
| 실제 실행 종료 후 읽기 감사 | `.paper-factory/runtime-admission-01419/post-completion-audit-v3/closed-run-audit.json` |

인계 ZIP은 로컬 연구 기록이므로 공개 Git에 올리지 않는다. 생성된 runtime·이전 배포본·검사 임시 작업실 전체를 이 ZIP에 넣었다고 가정하지 마라. manifest의 실제 포함 범위를 확인하고, 패키지·환경은 별도로 준비한다.

완료된 인계 폴더는 `.paper-factory/handoff-20261008-01420-7c8476b0e034/`이다. ZIP은 186,413,558 B/SHA256 `5e1a74c9042de4547f8bb627438cb21781701c08d148e65f6bd4a58067f8cdba`, manifest는 1,243,948 B/SHA256 `b36494def5734e1f61d392ed33ae62b4b826e4caa1d91941577035249370d6e5`다. 원문 522,697,238 B의 4,766개 entry에 JIZURA 현재 518파일·231개 산출물과 이전 기록, 0.14.20 준비·검사·중단 자료, Madi 원자료와 계보 전체를 포함한다. ZIP 내부 모든 entry의 SHA256·크기·CRC와 원본 파일의 생성 전후 동일성을 확인했다. 인증 파일·설치 파일은 포함하지 않았으며 SQLite 연결·모델·SCI·원본 쓰기는 없었다. 구현 소스의 Git 커밋은 `fcc514690eeec0c4df05cc563ba323289908ee2e`이고 이후 인계 문서 변경은 별도 커밋이다.
