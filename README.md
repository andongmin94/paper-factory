# Paper Factory

GitHub 저장소를 연구하고, 실제 실험 근거가 연결된 논문 초안과 PDF를 만드는 플러그인입니다. 호스트 모델이 연구 계획·실험 코드·리뷰·원고를 작성하고, Paper Factory가 원본과 제출물의 해시를 고정해 격리 실험·분석·파일 검증을 수행합니다. Work Cloud와 로컬 Work·Codex는 같은 연구 컨트롤러를 사용하며, 환경에 맞는 의존성과 실행기만 준비합니다. 별도 MCP 서버나 Paper Factory 모델 로그인은 필요하지 않습니다.

**현재 상태:** 테스트 계정의 ChatGPT Work Cloud에서 공개 저장소 5개의 격리 실험·분석·독립 원고 리뷰·논문 PDF 생성을 완료했습니다. 부족한 의존성의 오프라인 준비와 실제 문헌 검색·DOI 재확인·초록 수집도 검증했습니다. 개인 설치본 `0.10.2`는 승인된 원고를 그대로 사용하여 최종 PDF 5편, 총 31쪽을 생성하고 긴 제목의 서식 문제를 해결했습니다. 지원 범위는 아래 실행 경계와 현재 호스트 검사 결과에 따릅니다. 공개 디렉터리 설치는 별도 검증 대상입니다. 연구별 결과·원본 증거는 [개발 목표](docs/development-goal.md), 설치 사본과 현재 소스의 구분은 [설치 안내](docs/plugin.md)에 기록합니다.

개발 버전 `0.11.0`은 Docker·WSL 없이 private 환경과 운영체제별 프로세스 종료 처리를 사용합니다. 현재 Windows x86_64에서 새 Frontron 실험을 한 번 수행하고 독립 원고 리뷰·7쪽 PDF·Word·LaTeX·재현 ZIP 생성과 파일 검증을 완료했습니다. 같은 설치 사본은 Work Cloud의 환경 준비·문서 변환·QuickJS readiness·종료 검사도 통과했습니다. Mac 구현과 프로필은 있지만 현재 기기가 없어 실제 실행 검증이 남습니다. 일반 ChatGPT 채팅에서는 설치 리소스의 실행 공간 전달을 별도로 시험하고 있으며 전체 논문 제작은 아직 검증되지 않았습니다. 최신 진행·완료 조건은 [환경 지원 목표](docs/portability-goal.md)에 기록합니다.

현재 개발 소스 `0.12.0`은 기존 호스트 도구를 사용하는 명시적 `provided` 준비와 pdflatex PDF 변환을 추가합니다. Windows에서는 기존 Python·Node 22·Pandoc·Typst를 사용해 새 다운로드·venv·설치 없이 실제 준비·문서 진단·launcher readiness를 통과했습니다. Node 22 격리 실행 검사도 통과했습니다. 이 소스는 웹 개인 설치본 `0.11.0`과 별도이며, 일반 Chat 전체 제작과 Mac 실기 성공을 뜻하지 않습니다.

## 사용하기

1. 지원되는 호스트에서 Paper Factory 플러그인을 설치하고 새 대화에서 선택합니다. 현재 확인한 개인 ZIP 경로와 패키지 준비 방법은 [설치 안내](docs/plugin.md)에 있습니다.
2. 연구할 공개 저장소와 원하는 결과를 요청합니다.

> Paper Factory로 https://github.com/andongmin94/frontron 의 결정적인 함수를 연구해 줘. 독립 oracle과 비교 조건을 정하고 실제 통제 실험을 수행한 뒤, 근거·재현 자료와 논문 PDF를 전달해 줘.

여러 저장소에서 적합한 대상을 골라 달라고 요청할 수도 있습니다. 호스트는 현재 실행 환경과 실제 원본을 먼저 확인하고, 독립 리뷰를 거쳐 연구를 진행합니다. 실행 조건을 충족하지 못하면 준비한 자료와 구체적인 차단 사유를 알려줍니다.

별도 Paper Factory 모델 로그인이나 OpenAI API 키는 필요하지 않습니다. 호스트의 모델 이용 조건·사용량 제한·도구 실행 정책은 적용됩니다.

## 연구와 결과

실험은 bounded QuickJS Wasm guest에서 수행합니다. 현재 대상은 순수 JavaScript와 실제 검증된 타입 제거가 가능한 TypeScript 함수입니다. Python 실험, DOM/React, Node 파일·네트워크 API, 네이티브 확장과 저장소 설치 스크립트는 이 Cloud 경로의 지원 범위 밖입니다. 실행 시 호스트 파일 시스템과 네트워크를 guest에 노출하지 않으며, 실제 환경 검사와 실행 receipt로 한계를 확인합니다. Wasm 메모리 제한은 호스트 전체 RSS 제한을 뜻하지 않습니다.

원본 파일, 계획·코드 해시, 입력 fixture, 실제 관측값, source-call receipt, 분석, 읽은 문헌, 원고와 검증 결과를 보관합니다. 실패한 scientific control은 연구를 중단합니다. 결과를 유리하게 만들기 위한 재실행이나 수동 관측값 대체는 허용하지 않습니다.

검증된 PDF, DOCX, TeX, Markdown과 재현 ZIP을 전달합니다. 실제 파일을 호스트에서 받을 수 있는지까지 확인하며, artifact ID만 다운로드 링크로 제시하지 않습니다. 논문 초안은 저자 검토를 위한 산출물이며, 새로움·학술지 승인·출판을 보장하지 않습니다. 저자 정보는 사용자가 제공한 사실만 사용합니다.

## 개발 및 패키지

[연구 workflow](skills/paper-factory/references/workflow.md)에 환경 준비부터 원본 읽기·독립 리뷰·실험·원고·실제 파일 전달까지의 명령이 있습니다. `python scripts/build_plugin.py --check`로 고정된 입력을 확인하고, `python scripts/build_plugin.py`로 일반 배포 ZIP을 만듭니다. 빌더는 현재 `pyproject.toml` 버전과 소스별 해시를 기록합니다.

일반 패키지는 MCP·모델 클라이언트·계정 정보와 private 연구 입력을 포함하지 않습니다. QuickJS 바이트와 다운로드에 필요한 검증된 transport를 포함하고, 호스트별 의존성은 공식 배포 URL·크기·SHA256으로 고정하여 private scratch에 준비합니다. 공개 게시는 별도 승인·검토 절차이며, 패키지 빌드나 개인 ZIP 설치로 완료되지 않습니다.

기존 native isolated runner와 수동 CLI 도메인은 개발 코드에 남아 있습니다. Cloud 경로에서 격리가 실패했을 때 사용하는 fallback은 아닙니다. 과거 재사용·문서 변환 결정과 수동 출판 관련 기록은 `docs/`에 유지합니다.
