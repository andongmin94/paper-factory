# 플러그인 설치와 패키지

Paper Factory의 기본 배포는 스킬·JSON 컨트롤러·의존성 manifest·다운로드 transport와 QuickJS 런타임을 담는 ZIP입니다. 호스트별 의존성을 private scratch에 준비하며, MCP 서버를 시작하거나 별도 모델 로그인·API 키를 요청하지 않습니다. 계획·코드·독립 리뷰·원고는 현재 호스트 모델이 작성합니다. 동결된 `0.10.2` Cloud 검증, 개인 웹 설치본 `0.11.0`, 별도 개인 preview `0.12.0`과 이후 소스 수정을 구분하여 기록합니다.

## 사용자 설치

테스트 계정에서는 ChatGPT 웹 플러그인 화면의 **플러그인 압축 파일 업로드**로 개인 ZIP을 설치하고 Work Cloud에서 스크립트에 접근했습니다. private 검증 패키지의 Premiere 연구에 이어 일반 `paper-factory`의 Frontron·Neumorphism-ui·Madi·Garak 연구가 실제 실험·분석·원고 리뷰·PDF까지 완료됐습니다. 0.10.1에서는 실제 문헌 검색·DOI 재확인·초록 수집도 성공했습니다. 개인 설치본 0.10.2는 원래 승인된 원고를 변경하지 않고 최종 PDF 5편, 총 31쪽의 출력 서식을 검증했습니다. 연구별 완료·검토 범위는 [개발 목표](development-goal.md)에 기록합니다. 계정과 호스트가 같은 기능을 제공하는지는 확인해야 하며, 공개 디렉터리 설치는 별도 검증 대상입니다.

Frontron 첫 일반 설치 사본은 동결된 `paper-factory-0.10.0.zip`이며 SHA256은 `b1dfe2b6031ec51c3ad72c581c6d19355f3db64ae1c11f6db993e0456d6a7d0b`, skill inventory SHA256은 `9a21095859a425d03c214c6bf0e625c56248a5a3ed04aff8aa4904ebd72c1586`입니다. 이 사본의 SOCKS 프록시 transport 누락은 실제 Cloud의 요청 없는 HTTP 클라이언트 초기화로 재현했습니다. 0.10.1부터 공식 `socksio` wheel·라이선스를 포함하고 bootstrap에서 상속한 proxy 설정으로 실제 클라이언트 초기화·종료를 검사합니다. 준비 단계의 이 검사는 요청을 수행하지 않으며, 실제 검색·초록 수집은 별도 명령의 원본 응답으로 검증했습니다.

실제 최종 설치본 `paper-factory-0.10.2.zip`은 35,229,735 bytes, SHA256 `4208e293510237f36cf2248230b8aed0c45ebac544275990efa816e467e9c686`입니다. skill inventory SHA256은 `2a608be4c607174fceae05be0a28e91c77170a115bfaffe71aeb9dfd7e0b16b6`이며 Cloud의 52개 resource·19개 core·11개 wheel과 설치 inventory를 원본 ZIP에 대조했습니다. PDF 변환은 `--wrap=none`으로 긴 Typst 제목을 완전한 heading으로 유지합니다. 기존 원고·실험·export·재현 ZIP은 보존했고, 최종 표현만 별도 파일로 변환했습니다. 소스 변경은 명시적 빌드·설치 때 반영하며, 설치 사본은 해당 inventory로 검증합니다. 검증 후 작성한 개발 문서는 이 동결 ZIP을 다시 빌드하거나 변경하지 않습니다.

지원되는 ZIP 설치 경로에서 패키지를 설치한 뒤 새 대화에 Paper Factory를 선택하고, 공개 저장소 URL과 연구 요청을 입력합니다. 호스트가 아래 준비와 연구 절차를 수행합니다. 설치한 사본과 저장소 소스는 구분됩니다. 소스 변경은 이미 설치된 ZIP을 바꾸지 않습니다.

공개 디렉터리 게시·심사·계정 자격 확인은 이 빌더의 범위 밖입니다. [공식 플러그인 패키지 안내](https://developers.openai.com/plugins/build/plugins)를 참고하세요. 이 프로젝트가 외부 서버·유료 API·새 계정을 자동으로 준비하지는 않습니다.

## 실제 실행 환경

동결된 `0.10.2`는 **Linux x86_64 / CPython 3.12**의 기존 호스트 의존성을 전제로 합니다. 개인 설치본 `0.11.0`은 일반 GIL CPython 3.12·3.13·3.14와 Windows x86_64·Linux x86_64(glibc 2.28 이상)·Mac 14 이상(arm64/x86_64)의 의존성을 manifest로 고정합니다. `prepare_host.py`가 완전한 private venv와 Node·Pandoc를 준비합니다. 호스트가 스크립트 실행용 Python과 원본 패키지 파일을 제공해야 하며 공식 의존성 URL에 접근할 수 있어야 합니다. 프로필이 있다는 것만으로 해당 환경의 실제 지원이 검증되지는 않습니다. 최신 검증 상태는 [환경 지원 목표](portability-goal.md)에 있습니다.

현재 개인 웹 설치 사본은 `0.11.0`입니다. ZIP은 1,357,197 bytes, SHA256 `11b3fb20c9eb61d12f56918176ed089738d22975cf5634302317e62e50dcd70c`이며 설치 inventory SHA256은 `d126e509dac16954657cea1f2d8334aa9da8ba13796cad8a7f5bbde3b82a777a`입니다. Windows x86_64에서는 새 연구 `research-73b2dea0df76`의 실제 실행·분석·독립 리뷰·모든 export와 7쪽 PDF 시각 검수가 완료됐습니다. Work Cloud에서는 같은 설치 inventory의 private 준비·문서 변환·QuickJS readiness·종료 검사를 실제 통과했습니다. 이 Cloud 회귀 검사에서 새 연구를 수행한 것은 아닙니다. Mac 실제 실행과 일반 Chat 전체 제작은 아직 검증되지 않았습니다.

현재 Codex에 설치된 `0.11.0` 캐시도 원본 ZIP의 41개 자원과 일치합니다. 기존 private 준비를 재사용하여 승인된 호스트 실행 권한에서 readiness와 빈 종료 journal을 확인했습니다. 기본 도구 권한에서는 supervisor 잠금 파일 접근이 거부됐으며, 원래 실패를 보존했습니다. 이 결과는 해당 Windows 호스트의 승인된 실행 범위에 한정됩니다.

소스 `0.12.0`은 `--mode private|provided`를 명시하여 새 의존성을 준비하는 경로와 호스트가 이미 제공한 도구를 검증하는 경로를 구분합니다. `provided`는 다운로드·venv 생성·패키지 설치를 수행하지 않으며, `--pdf-engine typst|pdflatex`를 반드시 선택합니다. 실제 인터프리터·실행 파일·가져온 모듈 파일과 배포 metadata를 기록하고 launcher가 다시 검증합니다. 이는 관측한 설치 파일의 동일성 검사이며 upstream 패키지 인증이나 전체 호스트 불변성을 뜻하지 않습니다. 준비 결과의 schema는 2이며 동결된 0.11.0 설정 파일을 새 소스로 재사용하지 않습니다.

제공된 Node는 22.16 이상인 22 계열 또는 24 계열을 받으며, 실제 TypeScript 상대 import와 기존 메모리·시간·강제 종료 검사를 통과해야 준비 완료로 판정합니다. private 경로는 고정된 Node 24를 사용합니다. `pdflatex` 경로는 invocation alias를 보존하고 두 번의 `-no-shell-escape` 컴파일과 실제 PDF 재열기를 검사합니다. 선택한 변환기가 실패하면 다른 engine으로 바꾸지 않습니다. 상속한 proxy·TLS·PATH 설정은 유지합니다.

첫 설치 전 preview ZIP은 1,363,803 bytes, SHA256 `385936e25fd8a0f644d04953990500d10daadcd5787cb7403428a05efa080f70`, inventory SHA256 `ccc17c574722282411dea2a401ccdc73241b5956e2320a0ce214176b1f1ad896`입니다. 이 정확한 사본에서 Windows의 기존 Python 3.12.14·Node 22.16.0·Pandoc 3.9·Typst 0.15로 provided 준비·PDF/DOCX/TeX 진단·fresh QuickJS readiness와 종료 확인까지 통과했습니다. 새 연구를 수행한 검사는 아니며, preview는 웹 설치나 공개 게시되지 않았습니다. 검증 기록은 `.paper-factory/portability-implementation/2026-10-04/provided-host/actual-source-012/verification.json`에 있습니다. 이후 수정한 supervisor 오류 보고는 이 첫 preview에 포함되지 않습니다.

일반 Chat의 기존 Pandoc·pdflatex도 고정 진단 입력으로 PDF 1쪽·DOCX·TeX 출력을 실제 통과했습니다. 이 검사는 Paper Factory 컨트롤러를 실행하지 않았습니다. 설치 자원의 전체 원본 파일을 실행 공간에 전달하는 경로와 전체 연구 실행은 여전히 검증 대상입니다. 첫 세 text chunk 전달이나 개별 문서 변환 성공을 전체 제작 성공으로 계산하지 않습니다.

별도 개인 설치본 `paper-factory-preview-012`는 41개 자원·22개 core 파일의 원본을 대조하고 Work Cloud의 private 준비·PDF/DOCX/TeX 진단·fresh QuickJS readiness·종료 검사를 실제 통과했습니다. 이 사본 이후 Mac 준비 소스가 바뀌었으므로 최신 43개 자원 패키지의 성공으로 계산하지 않습니다.

일반 Chat에서는 실제 GitHub 도구로 첫 Mac CI의 진단 artifact를 받고 native Files로 실행 공간에 옮겼습니다. 원본 ZIP 13,774 bytes와 GitHub digest, 8개 member와 CRC가 일치했습니다. 이 파일 전달 검사는 패키지 코드·의존성 준비·연구를 실행하지 않았습니다. 첫 Mac arm64·Intel CI는 private 준비에서 실패했으며 원래 진단을 보존했습니다. 현재 Mac 수정은 원본 wheel의 누락된 라이선스와 잘못된 arm64 바이너리 대신 아키텍처별 공식 Pandoc 3.9 ZIP과 고정한 upstream 라이선스를 사용합니다. 실제 Mac 성공과 일반 Chat의 전체 패키지 준비·논문 제작은 다음 검증 대상입니다.

개발자용 `plugin-verification.yml`은 두 실제 Mac 아키텍처에서 준비·종료·문서 출력 검사를 수행하고, 성공한 원본 ZIP·build report를 14일간 별도 artifact로 남깁니다. 이 CI artifact는 검증용이고 OpenAI 공개 디렉터리 등록을 대신하지 않습니다.

호스트는 설치된 스킬 폴더를 읽기 전용으로 사용하고, 승인된 쓰기 가능한 durable scratch를 선택합니다. 그 안에서 공식 배포의 크기·SHA256을 검증하고 private venv에 고정 wheel을 `--no-index --require-hashes`로 설치합니다. Docker·WSL·OS 설치 프로그램이나 system PATH 변경은 요구하지 않습니다. 이후 명령은 준비 결과의 정확한 Python 경로와 `--environment-file`을 사용하여 private Node·Pandoc를 선택합니다. 상속한 proxy·TLS·네트워크 정책은 유지합니다.

`prepare_runtime.py`는 검증된 generic QuickJS ZIP만 scratch에 풀며, 실험이나 진단을 실행하지 않습니다. 반환된 정확한 `runtime_root`를 JSON 컨트롤러에 전달한 뒤 fresh environment check를 수행합니다. guest의 메모리·시간·종료 한계는 실제 응답에서 읽습니다. kernel 수준의 호스트 RSS 제한이나 임의 Python/Node 실행 지원을 가정하지 않습니다.

Cloud 명령은 필수 writable supervisor 경로를 `<data>/quickjs-supervisor`로 내부 전달합니다. 런타임 자원과 종료 추적 journal은 별도로 보관하며, 사용자에게 추가 설정은 필요하지 않습니다. 같은 data 경로를 계속 사용하고 journal을 보존합니다. 종료 확인이 실패하면 이를 해결할 때까지 실행을 중단하며, journal 삭제나 새 경로로 우회하지 않습니다.

새 0.12.0 소스는 supervisor 파일 접근 불가, 실제 잠금 소유자와의 경합, 잘못된 journal 상태를 구분합니다. 현재 상태를 읽거나 잠금을 확보하지 못하면 cleanup을 확인했다고 보고하지 않습니다. 파일 접근 오류는 호스트의 허용된 실행 권한 안에서 해결하며, 플러그인이 ACL이나 시스템 설정을 바꾸지 않습니다.

[연구 workflow](../skills/paper-factory/references/workflow.md)는 실제 명령, 동적 스키마, 원본/실험/관측값 읽기, 독립 리뷰, 실패·취소·cleanup 처리와 PDF 전달을 설명합니다. 일반 Chat에서는 스킬 문서와 실행 컨테이너의 파일 접근이 별개입니다. 바이너리 읽기나 직접 다운로드가 차단되면 원본 파일 전달을 먼저 해결해야 하며, 수동 ZIP 첨부를 설치만으로 실행하는 경로의 성공으로 계산하지 않습니다. 준비가 실패하면 원인을 해결하며, 실패한 scientific control을 새 ID나 유리한 반복 실행으로 우회하지 않습니다.

## 저장소에서 패키지 만들기

빌더를 실행하는 개발 환경에는 Python 3.11+가 필요합니다. 이 명령은 패키지 바이트 검증만 수행하며, 연구나 의존성 설치·계정 작업을 실행하지 않습니다.

```text
python scripts/build_plugin.py --check
python scripts/build_plugin.py
```

산출물은 다음과 같습니다.

- `dist/paper-factory/`: 설치 가능한 package root.
- `dist/paper-factory-<version>.zip`: root에 `plugin.json`이 있는 ZIP. 버전은 `pyproject.toml`에서 읽습니다.
- `dist/build-report.json`: 전체 입력·컨트롤러 파일별 해시·ZIP 크기와 해시.

기존 generated package와 같은 버전 ZIP은 `dist/previous/` 아래에 보관한 뒤 새 산출물로 교체합니다. 체크아웃이나 연구 상태를 재귀 삭제하지 않습니다. 소스가 빌드 도중 바뀌면 finalization을 중단하고, 검증되지 않은 staging을 release로 표시하지 않습니다.

`plugin.json`은 portable Agent Plugins manifest이고 `skills/` 경로를 명시합니다. 기본 패키지는 MCP manifest·서버·모델 provider를 포함하지 않습니다. 빌더는 명시한 컨트롤러 파일을 설치 스킬의 `src/`에 복사하고 helper·transport·의존성 manifest·라이선스·generic runtime을 포함합니다. 의존성마다 공식 URL·버전·크기·SHA256을 보존하고 QuickJS는 전체 module inventory와 production runner의 단일 inventory pin을 대조합니다.

모든 실행 자원이 스킬 폴더 안에 있으므로 별도 루트 sibling 파일이 Cloud importer에서 살아남는다고 가정하지 않습니다. package inventory를 먼저 검증하고, 현재 실행 환경과 출력 파일을 별도로 검사합니다. 빌더는 ZIP과 압축 전 파일 크기를 100 MiB 이하로 제한합니다.

private 검증용 저장소 snapshot·proposal·리뷰·수집 문헌·연구 결과는 일반 배포에 들어가지 않습니다. 원래 자료의 권리와 읽기 범위는 별도 기록으로 유지합니다. scratch의 probe 빌더나 해당 private 입력이 없어도 일반 패키지를 만들 수 있어야 합니다.

## 저자 정보와 파일 전달

플러그인은 `.env`를 자동으로 읽지 않습니다. 알 수 없는 저자 사실은 빈칸으로 남기며, 저장소 소유를 저자 승인으로 해석하지 않습니다. 수동 CLI의 명시적 `--env-file`와 출판 기능은 별도 범위입니다.

완료된 export는 실제 controller-owned 파일로 검증합니다. 호스트가 artifact bytes를 받아 size/SHA256을 재검산하고 PDF를 읽은 뒤 원본 파일을 첨부합니다. 호스트의 첨부 능력이 부족하면 export 완료와 파일 전달 제한을 구분해 보고합니다. Markdown 그림은 재현 ZIP의 상대 PNG 경로를 사용하며, PDF/DOCX는 독립 문서입니다.
