> Historical record: plugin source 0.12.0 at ac22fdd. Retained on 2026-10-05. This is not the standalone app installation or support guide. Repository links point to the historical commit.

# Paper Factory

GitHub 저장소를 연구하고, 실제 실험 근거가 연결된 논문 초안과 PDF를 만드는 플러그인입니다. 호스트 모델이 연구 계획·실험 코드·리뷰·원고를 작성하고, Paper Factory가 원본과 제출물의 해시를 고정해 격리 실험·분석·파일 검증을 수행합니다. Work Cloud와 로컬 Work·Codex는 같은 연구 컨트롤러를 사용하며, 환경에 맞는 의존성과 실행기만 준비합니다. 별도 MCP 서버나 Paper Factory 모델 로그인은 필요하지 않습니다.

## 지원 범위

지원 목표는 **ChatGPT Work Cloud와 Windows·macOS의 로컬 Work·Codex**입니다. 2026-10-04 사용자 결정으로 일반 ChatGPT Chat 지원은 개발·배포 대상에서 제외했습니다. **사용 검증의 완료 기준은 앱에 설치한 플러그인을 대화에서 호출하여 저장소 URL 요청부터 새 연구·독립 리뷰·실험·논문 생성·원본 PDF 전달까지 마치는 것입니다.** 앱 호스트가 계획·코드·원고를 작성하고 새 독립 리뷰를 받아야 하며, 외부에서 미리 만든 제출물을 주입하지 않습니다. 배포 코드를 직접 실행한 연구나 CI 통과는 구현 검사이며, 이 완료 기준을 대신하지 않습니다.

| 환경 | 설치한 플러그인의 전체 사용 검증 | 별도로 완료한 구현 검사와 남은 작업 |
| --- | --- | --- |
| Work Cloud | 일반 설치본 **0.11.0의 URL 요청부터 새 연구·독립 리뷰·export 완료**. 원본 8쪽 PDF는 보조 전달로 수령·해시·전쪽 검수 완료. **원래 시험 대화의 사용자 접근·Cloud native 원본 직접 전달은 미검증** | 현재 웹 Work 진입 화면은 확인됨. 원래 시험 대화의 URL 연결과 native 원본 다운로드·최신 출시본 검증이 남음. native 재첨부의 단독 PDF는 크기가 변했고 원본 증거 ZIP의 실제 다운로드는 확인하지 못함 |
| Windows Codex | 일반 설치본 **0.11.0의 전체 사용 검증 완료**. 앱 호스트가 새 계획·코드·원고를 작성하고 native fresh 독립 리뷰·실험·export·원본 8쪽 PDF 전달·전쪽 검수 완료 | 현재 호스트의 `danger-full-access` 범위. 과거 기본 권한 접근 문제와 native 회귀 실패 8건은 별도로 남음. 소스 0.12.0의 설치형 연구 결과가 아님 |
| Windows 로컬 Work | 일반 설치본 **0.11.0의 전체 사용 검증 완료**. 사용자가 ChatGPT Work로 확인한 Windows 로컬 대화에서 호스트 직접 작성·새 독립 리뷰·실험·export·원본 7쪽 PDF 전달·전쪽 검수 완료 | 원본 재현 ZIP·최종 증거 ZIP과 56개 명령의 원본 출력도 검증 완료. 최초 ZIP 포장 실패는 보존하고 연구·export를 반복하지 않고 복구 |
| macOS 로컬 Work·Codex | **미완료**. 실제 앱에 설치하여 논문을 받는 과정은 미검증 | ARM·Intel 실제 CI의 준비·변환·실행기·종료 검사에서 각각 258개 통과·Windows 전용 skip 2개. 실제 Mac에서 각 앱의 설치·대화 호출·새 연구·PDF 전달 필요 |

지원 목표에 포함되었다는 뜻이 해당 앱의 사용 검증 완료를 뜻하지는 않습니다. 현재 문서·스킬의 지원 범위 변경은 기존 설치 ZIP에 자동 반영되지 않으며, 공개 디렉터리 등록·심사·설치 검증도 남아 있습니다. 다음 작업은 [환경 지원 목표](https://github.com/andongmin94/paper-factory/blob/ac22fdd95778572968e3227d271a0b9846cd7f8b/docs/portability-goal.md#현재-남은-작업)에서 관리합니다.

**설치형 검증 checkpoint — 2026-10-04:** 세 실제 앱 시험은 일반 설치본 `paper-factory` `0.11.0`의 원본 41개 자원·22개 core와 inventory SHA256 `d126e509dac16954657cea1f2d8334aa9da8ba13796cad8a7f5bbde3b82a777a`를 사용합니다. 앱 호스트가 저장소 URL 요청에서 새 연구 입력을 작성하며, 다른 시험의 계획·코드·리뷰·원고·관측값을 주입하지 않습니다. Windows Codex의 `research-531f73211969`는 실행 1회·제출 원고 1회로 완료됐고 원본 PDF는 173,565 bytes·8쪽입니다. 원본 파일과 재현 ZIP은 `output/installed-codex-study/`에 있습니다.

Work Cloud의 별도 `research-70313f77d566`도 실행 1회·제출 원고 1회로 완료됐습니다. 첫 원고 리뷰의 거절과 수정 후 승인을 보존했습니다. native 첨부는 처음 실패했고 재첨부 결과의 단독 PDF는 원본 206,313 bytes와 다른 231,030 bytes였습니다. 증거 ZIP의 native 성공 metadata가 있어도 실제 원격 파일 해시는 미검증이며 다운로드는 HTTP 502와 Chrome `ERR_BLOCKED_BY_CLIENT`로 실패했습니다. 이후 원본 PDF를 21개 잘리지 않은 host stdout 출력에서 Windows 수신 호스트로 복구해 SHA256과 8쪽 전쪽 검수를 확인했습니다. 이 보조 전달 파일은 `output/installed-cloud-study/`에 있으며, **Cloud native 원본 직접 전달이나 PC 없이 원본을 받는 전체 흐름의 완료로 계산하지 않습니다.** 원본 명령·리뷰·수신·검수 기록은 private `.paper-factory/installed-app-acceptance/2026-10-04/`에 보존합니다.

2026-10-04 실제 Chrome의 [ChatGPT 홈](https://chatgpt.com/)에서 활성화된 Work 버튼과 `ChatGPT로 Work 시작` 입력창을 확인했습니다. 기존 프로젝트 대화에는 이 전환 버튼이 없었습니다. 과거 준비 대화의 웹 주소는 이번 확인에서 홈의 빈 새 Chat 입력 화면으로 돌아갔으므로, 원격 시험 ID와 사용자용 대화 URL의 연결·원래 시험 대화 접근은 미검증입니다. 현재 Work 진입 화면 확인을 원래 시험 대화 접근이나 원본 파일 전달 성공으로 계산하지 않습니다. 화면 증거는 위 private 기록의 `cloud/browser-delivery/work-entry-visible-20261004.png`에 보존했습니다. 새 메시지나 시험은 제출하지 않았습니다.

Windows 로컬 Work의 별도 `research-a890a5e45870`도 코드·실행·원고 제출 각 1회로 export·원본 파일 수령을 완료했습니다. 원본 PDF는 153,986 bytes·7쪽·SHA256 `8f533373248cfd49bacb833c54f89b3a091628f90a61c91bdd283632c3bd7c53`이며 전쪽 시각 검수를 통과했습니다. PDF·Word·Markdown·TeX·원본 재현 ZIP·최종 증거 ZIP은 `output/frontron-study-20261004-01a106f1/delivery/`에 있고 원본 controller artifact·명령 출력·ZIP 구성원과 크기·SHA256을 대조했습니다. 최종 앱 대화도 오류 없이 완료돼 원본 파일 링크를 전달했습니다. 최초 ZIP timestamp 포장 오류와 실패한 사본은 보존했고, 연구·export를 반복하지 않고 포장만 복구했습니다.

**과거 Cloud 설치 검증:** 테스트 계정의 ChatGPT Work Cloud에서 설치한 일반 플러그인 `0.10.0`·`0.10.1`로 공개 저장소 4개의 격리 실험·분석·독립 원고 리뷰·논문 생성·파일 전달을 완료했습니다. 별도 설치한 시험 플러그인 `paper-factory-capability-probe` `0.0.6`의 연구 1편까지 포함하면 총 5편입니다. 부족한 의존성의 오프라인 준비와 실제 문헌 검색·DOI 재확인·초록 수집도 검증했습니다. 이후 설치한 `0.10.2`는 승인된 원고를 그대로 사용하여 최종 PDF 5편, 총 31쪽을 재변환하고 긴 제목의 서식 문제를 해결했으며, 새로운 연구 5편을 수행한 버전은 아닙니다. 연구별 결과·원본 증거는 [개발 목표](https://github.com/andongmin94/paper-factory/blob/ac22fdd95778572968e3227d271a0b9846cd7f8b/docs/development-goal.md), 설치 사본과 현재 소스의 구분은 [설치 안내](https://github.com/andongmin94/paper-factory/blob/ac22fdd95778572968e3227d271a0b9846cd7f8b/docs/plugin.md)에 기록합니다.

이 과거 Cloud 시험에서는 연구 proposal과 일부 문헌을 별도 입력으로 제공했습니다. 실제 설치본으로 실행·논문 전달한 근거는 있지만, 저장소 URL 요청부터 앱 호스트가 모든 계획·코드·리뷰·원고를 생성한 위의 새 `0.11.0` 시험과는 구분합니다.

패키지 `0.11.0`은 Docker·WSL 없이 private 환경과 운영체제별 프로세스 종료 처리를 사용합니다. 과거 Windows x86_64의 Frontron 실험·독립 원고 리뷰·7쪽 PDF·Word·LaTeX·재현 ZIP 검증은 `dist`의 배포 launcher를 직접 실행한 결과로 보존합니다. 이후 위의 실제 Codex 설치 cache 연구와 Work Cloud 설치형 새 연구를 별도로 수행했습니다. Codex 성공은 현재 호스트의 `danger-full-access` 범위이며 ACL·supervisor journal을 바꾸지 않았습니다. 과거 기본 권한 접근 실패나 native 회귀 실패 8건이 해결된 증거는 아닙니다.

현재 개발 소스 `0.12.0`은 기존 호스트 도구를 사용하는 명시적 `provided` 준비와 pdflatex PDF 변환을 추가합니다. Windows에서는 기존 Python·Node 22·Pandoc·Typst로 새 다운로드·venv·설치 없이 실제 준비·문서 진단·launcher readiness를 통과했습니다. 별도 개인 preview의 41개 자원도 Work Cloud 회귀 검사를 통과했습니다. 검증된 실행·패키지 소스 커밋 `68cb8e2463a1ddb715ff4d12f2c6ede1c2d45307`의 43개 자원·22개 core는 [Mac CI run 37184571428](https://github.com/andongmin94/paper-factory/actions/runs/37184571428)에서 ARM·Intel의 실제 준비·변환·종료 검사를 모두 통과했습니다. 두 Mac 각각 258개 테스트 통과, Windows 전용 skip 2개, 실패·오류 0건이며 원본 artifact와 필수 native case도 독립 검증했습니다.

과거 일반 Chat 시험은 외부 Codex의 독립 리뷰를 받아 6쪽 PDF까지 완료했으나, Chat 단독 제작을 입증하지 못했습니다. 원본 패키지 전달·연구·실패·독립성 검사 기록은 [환경 지원 목표](https://github.com/andongmin94/paper-factory/blob/ac22fdd95778572968e3227d271a0b9846cd7f8b/docs/portability-goal.md)에 역사적 증거로 보존합니다.

## 사용하기

1. 지원되는 호스트에서 Paper Factory 플러그인을 설치하고 새 대화에서 선택합니다. 현재 확인한 개인 ZIP 경로와 패키지 준비 방법은 [설치 안내](https://github.com/andongmin94/paper-factory/blob/ac22fdd95778572968e3227d271a0b9846cd7f8b/docs/plugin.md)에 있습니다.
2. 연구할 공개 저장소와 원하는 결과를 요청합니다.

> Paper Factory로 https://github.com/andongmin94/frontron 의 결정적인 함수를 연구해 줘. 독립 oracle과 비교 조건을 정하고 실제 통제 실험을 수행한 뒤, 근거·재현 자료와 논문 PDF를 전달해 줘.

여러 저장소에서 적합한 대상을 골라 달라고 요청할 수도 있습니다. 호스트는 현재 실행 환경과 실제 원본을 먼저 확인하고, 독립 리뷰를 거쳐 연구를 진행합니다. 실행 조건을 충족하지 못하면 준비한 자료와 구체적인 차단 사유를 알려줍니다.

별도 Paper Factory 모델 로그인이나 OpenAI API 키는 필요하지 않습니다. 호스트의 모델 이용 조건·사용량 제한·도구 실행 정책은 적용됩니다.

## 연구와 결과

실험은 bounded QuickJS Wasm guest에서 수행합니다. 현재 대상은 순수 JavaScript와 실제 검증된 타입 제거가 가능한 TypeScript 함수입니다. Python 실험, DOM/React, Node 파일·네트워크 API, 네이티브 확장과 저장소 설치 스크립트는 이 Cloud 경로의 지원 범위 밖입니다. 실행 시 호스트 파일 시스템과 네트워크를 guest에 노출하지 않으며, 실제 환경 검사와 실행 receipt로 한계를 확인합니다. Wasm 메모리 제한은 호스트 전체 RSS 제한을 뜻하지 않습니다.

원본 파일, 계획·코드 해시, 입력 fixture, 실제 관측값, source-call receipt, 분석, 읽은 문헌, 원고와 검증 결과를 보관합니다. 실패한 scientific control은 연구를 중단합니다. 결과를 유리하게 만들기 위한 재실행이나 수동 관측값 대체는 허용하지 않습니다.

검증된 PDF, DOCX, TeX, Markdown과 재현 ZIP을 전달합니다. 실제 파일을 호스트에서 받을 수 있는지까지 확인하며, artifact ID만 다운로드 링크로 제시하지 않습니다. 논문 초안은 저자 검토를 위한 산출물이며, 새로움·학술지 승인·출판을 보장하지 않습니다. 저자 정보는 사용자가 제공한 사실만 사용합니다.

## 개발 및 패키지

[연구 workflow](https://github.com/andongmin94/paper-factory/blob/ac22fdd95778572968e3227d271a0b9846cd7f8b/skills/paper-factory/references/workflow.md)에 환경 준비부터 원본 읽기·독립 리뷰·실험·원고·실제 파일 전달까지의 명령이 있습니다. `python scripts/build_plugin.py --check`로 고정된 입력을 확인하고, `python scripts/build_plugin.py`로 일반 배포 ZIP을 만듭니다. 빌더는 현재 `pyproject.toml` 버전과 소스별 해시를 기록합니다.

일반 패키지는 MCP·모델 클라이언트·계정 정보와 private 연구 입력을 포함하지 않습니다. QuickJS 바이트와 다운로드에 필요한 검증된 transport를 포함하고, 호스트별 의존성은 공식 배포 URL·크기·SHA256으로 고정하여 private scratch에 준비합니다. 공개 게시는 별도 승인·검토 절차이며, 패키지 빌드나 개인 ZIP 설치로 완료되지 않습니다.

기존 native isolated runner와 수동 CLI 도메인은 개발 코드에 남아 있습니다. Cloud 경로에서 격리가 실패했을 때 사용하는 fallback은 아닙니다. 과거 재사용·문서 변환 결정과 수동 출판 관련 기록은 `docs/`에 유지합니다.
