# 플러그인 설치와 패키지

Paper Factory의 기본 배포는 스킬·JSON 컨트롤러·의존성 manifest·다운로드 transport와 QuickJS 런타임을 담는 ZIP입니다. 호스트별 의존성을 private scratch에 준비하며, MCP 서버를 시작하거나 별도 모델 로그인·API 키를 요청하지 않습니다. 계획·코드·독립 리뷰·원고는 현재 호스트 모델이 작성합니다. 과거 Cloud 설치본의 실제 연구, 동결된 `0.10.2`의 서식 재변환, 현재 개인 웹 설치본 `0.11.0`, 별도 개인 preview `0.12.0`과 이후 소스 수정을 구분하여 기록합니다.

현재 개발·배포 지원 목표는 **ChatGPT Work Cloud와 Windows/macOS의 local Work·Codex**입니다. 일반 Chat에서의 단독 논문 제작은 지원 범위에서 제외합니다. Docker·WSL·운영체제 기능 변경·사용자가 관리하는 런타임 설치 프로그램 없이 호스트가 제공한 도구 또는 플러그인의 private 준비를 사용합니다. 이 범위 결정은 과거 일반 Chat 실험·실패·원본 증거를 삭제하거나 성공으로 바꾸는 조치가 아니며, 아래 과거 검증 기록에 보존합니다.

설치형 전체 사용 검증의 완료 기준은 **정확한 설치본을 실제 대상 앱 대화에서 선택한 뒤 저장소 URL과 연구 요청으로 시작하여, 앱 호스트가 계획·코드·원고를 만들고 native fresh 독립 리뷰·통제 실험·분석·export를 거쳐 사용자가 원본 논문 파일을 받는 것**입니다. 외부에서 미리 만든 계획·코드·리뷰·원고를 주입하지 않아야 합니다. 준비·readiness·변환 진단·CI·standalone launcher 연구는 별도 기반 검사이며 이 완료 기준을 대신하지 않습니다. 과거 설치본의 실행 성공도 현재 버전이나 다른 앱의 전체 사용 성공으로 계산하지 않습니다.

| 지원 목표 | 설치형 전체 사용 검증 | 별도 기반 검사와 남은 검증 |
| --- | --- | --- |
| Work Cloud | 일반 설치본 `0.11.0`으로 URL 요청부터 앱 호스트의 새 계획·코드·원고, native fresh 독립 리뷰·연구·export 완료. 원본 8쪽 PDF는 보조 전달로 수령·해시·전쪽 검수 완료. **원래 시험 대화의 사용자 접근·native 원본 직접 전달은 미검증** | 현재 웹 Work 진입 화면은 확인됨. 원래 시험 대화의 URL 연결과 native 원본 다운로드·원격 해시는 미검증. 첫 전달 실패·크기가 바뀐 단독 PDF를 보존. `0.12.0` preview/소스의 새 설치형 연구를 수행한 결과가 아님 |
| Windows Codex | 일반 설치본 `0.11.0`의 **전체 사용 검증 완료**. URL 요청부터 앱 호스트 직접 작성·native fresh 리뷰·실험·export·원본 8쪽 PDF 전달·전쪽 검수 | 현재 `danger-full-access` 호스트 범위. 과거 기본 권한 접근 실패와 일반 Tests의 Windows 실패 8건은 남음. 과거 dist launcher의 7쪽 연구는 별도 증거 |
| Windows local Work | 일반 설치본 `0.11.0`의 **전체 사용 검증 완료**. 사용자가 ChatGPT Work로 확인한 실제 Windows 로컬 대화에서 호스트 직접 작성·새 독립 리뷰·실험·export·원본 7쪽 PDF 전달·전쪽 검수 완료 | 원본 PDF·Word·Markdown·TeX·재현 ZIP·최종 증거 ZIP과 56개 명령 출력 검증 완료. 최초 포장 실패는 보존하고 연구·export 반복 없이 복구 |
| macOS local Work·Codex | 설치한 플러그인을 실제 앱 대화에서 사용한 전체 연구·논문 수령은 미검증 | 소스 `68cb8e2463a1ddb715ff4d12f2c6ede1c2d45307`의 hosted ARM·Intel CI에서 각 258개 통과·Windows 전용 skip 2개, private 준비·변환·readiness·native lifecycle 검증. 실제 앱 설치·새 연구·논문 수령 검증은 남음 |

지원 목표 전체의 검증은 아직 완료되지 않았습니다. Windows Codex·로컬 Work의 원본 논문 수령과 Work Cloud의 새 연구·원본 PDF 보조 수령은 완료했으며 원래 Cloud 시험 대화의 사용자 접근·native 원본 직접 전달이 남았습니다. Mac은 실제 앱별 설치·새 연구·논문 수령이 미검증입니다. 정확한 최신 `0.12.0` 출시 패키지의 배포·설치 회귀 검사, 동결된 작업 설치본의 업그레이드, OpenAI 공개 디렉터리 심사·등록도 완료하지 않았습니다. 소스의 실행·패키지 검사는 위 `68cb8e...`와 원본 CI artifact에 묶입니다. README와 이 설치 안내는 ZIP root 입력이며 이후 지원 범위 문구를 바꾼 `plugin.json`·`SKILL.md`도 당시 artifact와 구분합니다. 이번 문서 정정은 패키지를 다시 빌드하거나 설치본을 바꾸지 않습니다.

### 실제 일반 설치본 검증 checkpoint — 2026-10-04

세 앱 시험은 일반 `paper-factory` `0.11.0`의 원본 41개 자원·22개 core와 inventory SHA256 `d126e509dac16954657cea1f2d8334aa9da8ba13796cad8a7f5bbde3b82a777a`에 연결됩니다. 저장소 URL과 연구 요청에서 앱 호스트가 각각 새 계획·실험 코드·원고를 작성하고 native fresh 독립 리뷰를 받습니다. 다른 시험의 연구 입력이나 관측 결과를 주입하지 않았습니다.

- Windows Codex의 `research-531f73211969`는 코드·실행·원고 제출 각 1회로 completed/exported, cleanup 확인·최종 worker journal 비어 있음입니다. 원본 PDF는 173,565 bytes·8쪽·SHA256 `eb28687da9578bb8b0a9bf5a7c0655301b34ab6140a89b73ea1d44246c88bf59`, 재현 ZIP은 445,799 bytes·SHA256 `e5c17ca99fac047053cb746bdc9410db1d8edaeb483a91532b3a12ec518de407`입니다. 실제 파일은 `output/installed-codex-study/`에 있고 전쪽 시각 검수가 완료됐습니다. 현재 호스트는 `danger-full-access`이며 ACL·journal을 바꾸지 않았습니다. 실제 파일을 제공했지만 사용자 클릭은 관찰하지 않았습니다.
- Work Cloud의 별도 `research-70313f77d566`도 실행·원고 제출 각 1회로 completed/exported입니다. native 원고 리뷰의 최초 거절과 수정 후 승인을 보존했습니다. 원본 PDF는 206,313 bytes·8쪽·SHA256 `4f0f89ae1b8da770106c39ddabb8db6f3e09fe2e77c334780d23915dcc93a5aa`입니다. 첫 native 첨부는 `transfer_failed`였고 한 번의 재첨부는 성공 metadata를 반환했지만 단독 PDF 크기가 231,030 bytes로 바뀌었습니다. 6,662,325 bytes 증거 ZIP의 실제 다운로드·원격 해시는 HTTP 502와 Chrome `ERR_BLOCKED_BY_CLIENT` 때문에 미검증입니다. 이후 21개 잘리지 않은 host stdout 출력의 원본 PDF를 Windows 수신 호스트가 복구해 해시·전쪽 시각 검수를 완료했고 `output/installed-cloud-study/`에 보관했습니다. **원본 PDF 보조 전달 성공이며 Cloud native 원본 직접 전달 또는 PC 없는 전체 전달 성공은 아닙니다.**
- Windows 로컬 Work는 사용자가 제공한 시험 대화입니다. 앱 도구의 backing `kind=codex`만으로 제품을 추정하지 않고 사용자의 직접 답변 `ChatGPT의 Work`와 실제 Windows 로컬 실행을 함께 기록했습니다. 별도 호스트 작성 `research-a890a5e45870`는 새 코드·원고 독립 리뷰를 통과하고 코드·실행·원고 제출 각 1회로 completed/exported, cleanup 확인·최종 owned workers 비어 있음입니다. 실제 paired units 192개·scalar observations 768개·production calls 194개·fixtures 195개와 scientific controls 3개 통과를 보존했습니다. 원본 PDF는 153,986 bytes·7쪽·SHA256 `8f533373248cfd49bacb833c54f89b3a091628f90a61c91bdd283632c3bd7c53`, 원본 재현 ZIP은 427,807 bytes·SHA256 `6560d20aca8be78f5c5b21c1e805ef294470f22080c9a4dd4dab548373ab5015`입니다. `output/frontron-study-20261004-01a106f1/delivery/`의 PDF·Word·Markdown·TeX·재현 ZIP을 원본 controller artifact와 크기·SHA256으로 대조했고 ZIP CRC·inventory 39개와 PDF 전쪽 시각 검수도 통과했습니다. 최종 증거 ZIP은 7,858,322 bytes·SHA256 `9d94a53ec51167f734fc48527e7b87c7cea0dfc6d8dcb4b6456ca948cdcd9a6a`이며 579개 CRC·578개 manifest 구성원 해시·56개 명령의 112개 stdout/stderr 원본을 검증했습니다. 최종 앱 turn도 오류 없이 완료되어 원본 PDF·재현 ZIP·증거 ZIP·artifact 해시 링크를 전달했습니다. 최초 1980년 이전 timestamp 포장 실패와 partial ZIP은 보존하고 연구·export 반복 없이 포장만 복구했습니다. 수신·최종 검수는 `windows-work/received-original-exports-audit.json`·`windows-work/final-installed-work-result.json`에 기록했습니다.

2026-10-04 실제 Chrome의 [ChatGPT 홈](https://chatgpt.com/)에서 활성화된 Work 버튼과 `ChatGPT로 Work 시작` 입력창을 확인했습니다. 기존 프로젝트 대화에는 이 전환 버튼이 없었습니다. 과거 준비 대화의 웹 주소는 이번 확인에서 홈의 빈 새 Chat 입력 화면으로 돌아갔습니다. 현재 Work 진입 화면은 확인됐지만 원격 시험 ID와 사용자용 URL의 연결·원래 시험 대화 접근·native 원본 전달은 미검증입니다. 화면 증거는 아래 private 기록의 `cloud/browser-delivery/work-entry-visible-20261004.png`에 보존했고 새 메시지나 시험은 제출하지 않았습니다.

원본 명령·리뷰 provenance·PDF 수신·전쪽 검수는 private `.paper-factory/installed-app-acceptance/2026-10-04/`의 앱별 기록에 보존합니다. 과거 준비 검사, standalone dist 연구·7쪽 PDF, `0.10.x` Cloud 연구와 `0.12.0` 소스·preview 검사는 각각 당시 범위로 유지합니다.

## 사용자 설치

테스트 계정에서는 ChatGPT 웹 플러그인 화면의 **플러그인 압축 파일 업로드**로 개인 ZIP을 설치하고 실제 Work Cloud 앱 대화에서 선택했습니다. private 설치형 probe `0.0.6`의 Premiere 1편은 일반 패키지와 별도로 실제 새 연구·독립 리뷰·export·논문 수령까지 확인했습니다. 일반 `paper-factory` 설치본 `0.10.0`에서는 Frontron·Neumorphism-ui 2편, `0.10.1`에서는 Madi·Garak 2편의 설치 실행과 논문 수령을 확인했습니다. 네 일반 연구의 실제 create/run/submit-manuscript/export/artifact-bytes 명령은 설치 캐시 경로를 사용했으며 PDF와 재현 ZIP 원본도 검증했습니다. 다만 proposal과 일부 보존 문헌은 별도 입력으로 제공됐으므로, 이 기록은 플러그인 설치와 저장소 URL 요청만으로 전단계를 자율 완료한 증거가 아닙니다. `0.10.1`에서는 실제 문헌 검색·DOI 재확인·초록 수집도 성공했습니다.

설치본 `0.10.2`는 과학 연구가 완료된 기존 승인 원고 5편을 재변환하여 최종 PDF 5편·31쪽의 출력 서식을 검증한 결과입니다. 이 버전으로 새 연구를 처음부터 수행한 전체 사용 검증은 아닙니다. 과거 `0.11.0`과 별도 private `0.12.0` preview의 Cloud 회귀 검사는 새 연구를 수행하지 않았으며, 이후 일반 설치본 `0.11.0`의 새 연구는 위 checkpoint에 별도로 기록했습니다. 현재 `0.12.0` 소스의 Cloud 설치형 전체 사용은 미검증입니다. 연구별 설치본과 완료·검토 범위는 [개발 목표](development-goal.md)에 기록합니다. 과거 설치본의 성공과 계정별 기능, 최신 버전의 전체 사용, 공개 디렉터리 설치는 각각 별도 검증 대상입니다.

Frontron 첫 일반 설치 사본은 동결된 `paper-factory-0.10.0.zip`이며 SHA256은 `b1dfe2b6031ec51c3ad72c581c6d19355f3db64ae1c11f6db993e0456d6a7d0b`, skill inventory SHA256은 `9a21095859a425d03c214c6bf0e625c56248a5a3ed04aff8aa4904ebd72c1586`입니다. 이 사본의 SOCKS 프록시 transport 누락은 실제 Cloud의 요청 없는 HTTP 클라이언트 초기화로 재현했습니다. 0.10.1부터 공식 `socksio` wheel·라이선스를 포함하고 bootstrap에서 상속한 proxy 설정으로 실제 클라이언트 초기화·종료를 검사합니다. 준비 단계의 이 검사는 요청을 수행하지 않으며, 실제 검색·초록 수집은 별도 명령의 원본 응답으로 검증했습니다.

동결된 서식 검증 설치본 `paper-factory-0.10.2.zip`은 35,229,735 bytes, SHA256 `4208e293510237f36cf2248230b8aed0c45ebac544275990efa816e467e9c686`입니다. skill inventory SHA256은 `2a608be4c607174fceae05be0a28e91c77170a115bfaffe71aeb9dfd7e0b16b6`이며 Cloud의 52개 resource·19개 core·11개 wheel과 설치 inventory를 원본 ZIP에 대조했습니다. PDF 변환은 `--wrap=none`으로 긴 Typst 제목을 완전한 heading으로 유지합니다. 기존 원고·실험·export·재현 ZIP은 보존했고, 최종 표현만 별도 파일로 변환했습니다. 소스 변경은 명시적 빌드·설치 때 반영하며, 설치 사본은 해당 inventory로 검증합니다. 검증 후 작성한 개발 문서는 이 동결 ZIP을 다시 빌드하거나 변경하지 않습니다.

지원되는 ZIP 설치 경로에서 패키지를 설치한 뒤 새 대화에 Paper Factory를 선택하고, 공개 저장소 URL과 연구 요청을 입력합니다. 호스트가 아래 준비와 연구 절차를 수행합니다. 설치한 사본과 저장소 소스는 구분됩니다. 소스 변경은 이미 설치된 ZIP을 바꾸지 않습니다.

공개 디렉터리 게시·심사·계정 자격 확인은 이 빌더의 범위 밖입니다. [공식 플러그인 패키지 안내](https://developers.openai.com/plugins/build/plugins)를 참고하세요. 이 프로젝트가 외부 서버·유료 API·새 계정을 자동으로 준비하지는 않습니다.

## 실제 실행 환경

동결된 `0.10.2`는 **Linux x86_64 / CPython 3.12**의 기존 호스트 의존성을 전제로 합니다. 개인 설치본 `0.11.0`은 일반 GIL CPython 3.12·3.13·3.14와 Windows x86_64·Linux x86_64(glibc 2.28 이상)·Mac 14 이상(arm64/x86_64)의 의존성을 manifest로 고정합니다. `prepare_host.py`가 완전한 private venv와 Node·Pandoc를 준비합니다. 호스트가 스크립트 실행용 Python과 원본 패키지 파일을 제공해야 하며 공식 의존성 URL에 접근할 수 있어야 합니다. 프로필이 있다는 것만으로 해당 환경의 실제 지원이 검증되지는 않습니다. 최신 검증 상태는 [환경 지원 목표](portability-goal.md)에 있습니다.

현재 일반 개인 웹 설치 사본은 `0.11.0`입니다. ZIP은 1,357,197 bytes, SHA256 `11b3fb20c9eb61d12f56918176ed089738d22975cf5634302317e62e50dcd70c`이며 설치 inventory SHA256은 `d126e509dac16954657cea1f2d8334aa9da8ba13796cad8a7f5bbde3b82a777a`입니다. 과거 Windows x86_64에서는 동결된 `dist/paper-factory/skills/paper-factory` launcher를 사용한 standalone 로컬 호스트 실행으로 `research-73b2dea0df76`의 실제 실행·분석·독립 리뷰·모든 export와 7쪽 PDF 시각 검수가 완료됐습니다. 당시 Work Cloud 회귀 검사는 같은 inventory의 private 준비·문서 변환·QuickJS readiness·종료만 확인했습니다. 이후 실제 Codex 설치 캐시·별도 로컬 Work의 새 연구·원본 파일 전달과 Work Cloud의 새 연구·원본 PDF 보조 전달은 위 checkpoint의 별도 근거입니다. `0.12.0` 소스의 Mac·과거 일반 Chat 결과는 이 설치 사본의 검증으로 계산하지 않습니다.

현재 Codex에 설치된 `0.11.0` 캐시도 원본 ZIP의 41개 자원과 일치합니다. 과거 기존 private 준비를 재사용한 승인 권한의 readiness·빈 종료 journal 검사는 연구 실행 전 checkpoint였습니다. 이후 같은 캐시의 새 연구·원본 PDF 검증을 완료했습니다. 기본 도구 권한의 supervisor 잠금 파일 접근 거부는 원래 실패로 보존하며, 현재 `danger-full-access` 성공으로 해결 처리하지 않습니다.

별도 [일반 Tests run 37184571403](https://github.com/andongmin94/paper-factory/actions/runs/37184571403)는 Linux 4개와 Windows 2·3 shard가 성공했지만 Windows 0·1 shard는 실패했습니다. 기존 native staging/private-DACL cleanup 실패 1건과 legacy WindowsRunner 실패 7건이 남아 있으며, 아래 성공한 Mac Plugin verification이나 scientific control 결과와 구분합니다. 전체 테스트가 모두 통과했거나 ACL·legacy runner 문제가 해결됐다는 의미는 아닙니다.

소스 `0.12.0`은 `--mode private|provided`를 명시하여 새 의존성을 준비하는 경로와 호스트가 이미 제공한 도구를 검증하는 경로를 구분합니다. `provided`는 다운로드·venv 생성·패키지 설치를 수행하지 않으며, `--pdf-engine typst|pdflatex`를 반드시 선택합니다. 실제 인터프리터·실행 파일·가져온 모듈 파일과 배포 metadata를 기록하고 launcher가 다시 검증합니다. 이는 관측한 설치 파일의 동일성 검사이며 upstream 패키지 인증이나 전체 호스트 불변성을 뜻하지 않습니다. 준비 결과의 schema는 2이며 동결된 0.11.0 설정 파일을 새 소스로 재사용하지 않습니다.

제공된 Node는 22.16 이상인 22 계열 또는 24 계열을 받으며, 실제 TypeScript 상대 import와 기존 메모리·시간·강제 종료 검사를 통과해야 준비 완료로 판정합니다. private 경로는 고정된 Node 24를 사용합니다. `pdflatex` 경로는 invocation alias를 보존하고 두 번의 `-no-shell-escape` 컴파일과 실제 PDF 재열기를 검사합니다. 선택한 변환기가 실패하면 다른 engine으로 바꾸지 않습니다. 상속한 proxy·TLS·PATH 설정은 유지합니다.

첫 설치 전 preview ZIP은 1,363,803 bytes, SHA256 `385936e25fd8a0f644d04953990500d10daadcd5787cb7403428a05efa080f70`, inventory SHA256 `ccc17c574722282411dea2a401ccdc73241b5956e2320a0ce214176b1f1ad896`입니다. 이 정확한 사본에서 Windows의 기존 Python 3.12.14·Node 22.16.0·Pandoc 3.9·Typst 0.15로 provided 준비·PDF/DOCX/TeX 진단·fresh QuickJS readiness와 종료 확인까지 통과했습니다. 새 연구를 수행한 검사는 아니며, preview는 웹 설치나 공개 게시되지 않았습니다. 검증 기록은 `.paper-factory/portability-implementation/2026-10-04/provided-host/actual-source-012/verification.json`에 있습니다. 이후 수정한 supervisor 오류 보고는 이 첫 preview에 포함되지 않습니다.

별도 개인 설치본 `paper-factory-preview-012`는 41개 자원·22개 core 파일의 원본을 대조하고 Work Cloud의 private 준비·PDF/DOCX/TeX 진단·fresh QuickJS readiness·종료 검사를 실제 통과했습니다. 새 연구·과학 리뷰·원고·논문 수령까지의 전체 사용을 검사한 것은 아닙니다. 이 사본 이후 Mac 준비 소스가 바뀌었으므로 최신 43개 자원 패키지의 성공으로 계산하지 않습니다.

첫 Mac arm64·Intel 준비 실패와 이후 모의 플랫폼 테스트 실패의 원래 진단은 보존합니다. 현재 Mac 준비는 누락된 라이선스와 잘못된 arm64 wheel 바이너리 대신 아키텍처별 공식 Pandoc 3.9 ZIP과 고정한 upstream 라이선스를 사용합니다.

검증된 실행·패키지 소스 커밋 `68cb8e2463a1ddb715ff4d12f2c6ede1c2d45307`의 [실제 Mac CI run 37184571428](https://github.com/andongmin94/paper-factory/actions/runs/37184571428), attempt 1은 ARM·Intel 모두 성공했습니다. 각 Darwin CPython 3.12.10 private 프로필은 43개 자원·22개 core, Node 24.21.0·Pandoc 3.9·Typst 0.15.0 준비와 실제 변환·readiness·종료 검사를 통과했습니다. 원본 JUnit은 각 258개 통과·Windows 전용 skip 2개·실패/오류 0건이며, 필수 5개 native/문서 case와 converter bytes도 독립 확인했습니다. ARM CI의 원본 plugin ZIP은 1,378,652 bytes, SHA256 `aebaaffebb1126e03ee26321444e9f59c15386af0cbff8a2293c3562d1f3acf7`, inventory SHA256 `035e2049acd609a5184cbb8b36184c904e4fb2fb465b05ed59de8dc24591eede`입니다. 이 43개 자원 사본은 위의 설치된 41개 자원 preview와 다릅니다. Intel diagnostics 원본도 검증했으며 Intel 배포 ZIP body는 이 독립 audit에서 수신하지 않았습니다.

이 결과는 실제 hosted native Mac CI의 준비·변환·종료 검증입니다. Mac의 local Work나 Codex 앱 대화에서 설치한 플러그인으로 새 연구를 수행하고 논문 파일을 받은 검사는 아닙니다. Mac의 설치형 전체 사용은 미검증입니다.

개발자용 `plugin-verification.yml`은 두 실제 Mac 아키텍처에서 준비·종료·문서 출력 검사를 수행하고, 성공한 원본 ZIP·build report를 14일간 별도 artifact로 남깁니다. 이 CI artifact는 검증용이고 OpenAI 공개 디렉터리 등록을 대신하지 않습니다.

호스트는 설치된 스킬 폴더를 읽기 전용으로 사용하고, 승인된 쓰기 가능한 durable scratch를 선택합니다. 그 안에서 공식 배포의 크기·SHA256을 검증하고 private venv에 고정 wheel을 `--no-index --require-hashes`로 설치합니다. Docker·WSL·OS 설치 프로그램이나 system PATH 변경은 요구하지 않습니다. 이후 명령은 준비 결과의 정확한 Python 경로와 `--environment-file`을 사용하여 private Node·Pandoc를 선택합니다. 상속한 proxy·TLS·네트워크 정책은 유지합니다.

`prepare_runtime.py`는 검증된 generic QuickJS ZIP만 scratch에 풀며, 실험이나 진단을 실행하지 않습니다. 반환된 정확한 `runtime_root`를 JSON 컨트롤러에 전달한 뒤 fresh environment check를 수행합니다. guest의 메모리·시간·종료 한계는 실제 응답에서 읽습니다. kernel 수준의 호스트 RSS 제한이나 임의 Python/Node 실행 지원을 가정하지 않습니다.

Cloud 명령은 필수 writable supervisor 경로를 `<data>/quickjs-supervisor`로 내부 전달합니다. 런타임 자원과 종료 추적 journal은 별도로 보관하며, 사용자에게 추가 설정은 필요하지 않습니다. 같은 data 경로를 계속 사용하고 journal을 보존합니다. 종료 확인이 실패하면 이를 해결할 때까지 실행을 중단하며, journal 삭제나 새 경로로 우회하지 않습니다.

새 0.12.0 소스는 supervisor 파일 접근 불가, 실제 잠금 소유자와의 경합, 잘못된 journal 상태를 구분합니다. 현재 상태를 읽거나 잠금을 확보하지 못하면 cleanup을 확인했다고 보고하지 않습니다. 파일 접근 오류는 호스트의 허용된 실행 권한 안에서 해결하며, 플러그인이 ACL이나 시스템 설정을 바꾸지 않습니다.

[연구 workflow](../skills/paper-factory/references/workflow.md)는 실제 명령, 동적 스키마, 원본/실험/관측값 읽기, 독립 리뷰, 실패·취소·cleanup 처리와 PDF 전달을 설명합니다. 지원 대상 호스트의 원본 파일·실행 도구·쓰기 권한을 먼저 확인합니다. 준비가 실패하면 원인을 해결하며, 실패한 scientific control을 새 ID나 유리한 반복 실행으로 우회하지 않습니다. 같은 연구 data·journal과 원래 실행 receipt를 보존하고, 응답 중단을 이유로 실험을 반복하지 않습니다.

도구를 찾지 못할 때는 connector catalog와 호스트의 native 내장 도구가 별도로 노출될 수 있음을 확인합니다. 실제 사용 가능한 모든 namespace를 살펴본 뒤 실행 기능의 부재를 판단합니다.

## 일반 Chat 과거 검증 기록

다음은 지원 범위를 변경하기 전에 수행한 일반 Chat 호환성 시험의 기록입니다. 성공·실패·원본 증거를 보존하며, 일반 Chat 지원을 재개하거나 단독 제작을 개발·배포 완료 조건으로 요구하는 내용은 아닙니다. 자세한 시점별 기록과 원본 핀은 [환경 지원 목표](portability-goal.md)에 있습니다.

초기 일반 Chat의 Pandoc·pdflatex 진단은 고정 입력으로 PDF 1쪽·DOCX·TeX 출력을 통과했으며 Paper Factory 컨트롤러를 실행하지 않았습니다. 첫 세 text chunk 전달이나 이 개별 변환 성공은 전체 제작 성공으로 계산하지 않았습니다. 첫 GitHub→native Files 시험은 Mac CI의 실패 진단 artifact를 옮긴 검사였습니다. 원본 ZIP 13,774 bytes와 GitHub digest, 8개 member와 CRC가 일치했지만 패키지 코드·의존성 준비·연구를 실행하지 않았습니다.

2026-10-04의 후속 시험에서는 성공한 원본 전체 배포를 실제 GitHub artifact 도구와 native Files로 전달받고 inventory를 확인했습니다. 기존 Python 3.13.5·Node 22.16.0·Pandoc 3.1.11.1·pdflatex로 명시적 `provided` 준비와 연구를 완료했으며, 의존성 다운로드·설치나 새 venv를 만들지 않았습니다. `research-9704196954a3`의 검증된 최종 상태는 `completed/exported`, 코드 제출·실험·원고 제출 각 1회이고 cleanup과 빈 journal을 확인했습니다. 36개 입력·72개 관측값·158개 fixture와 39개 production 호출, control 통과·분석·문헌·승인 원고의 원본 연결을 독립 검증했습니다. 문헌의 TC39 자료는 제한된 절의 전사로, 전체 HTML을 수집한 것은 아닙니다. 원고 수정 후 외부 독립 리뷰 003이 승인한 원본으로 첫 submit/export를 수행했습니다. PDF·DOCX·TeX·Markdown·figure·재현 ZIP의 실제 파일과 해시를 검증했으며, 150,310 bytes의 6쪽 PDF는 전쪽 시각 검수를 통과했습니다. 최종 PDF SHA256은 `77e12c6638d9dff3a1847c4c4014ecbc194c4985992565d56f92545e9115d134`입니다.

당시 ordinary Chat의 실제 도구 목록에는 fresh 과학 검토자·subagent·위임 모델 호출이 노출되지 않아 코드와 최종 원고의 독립 과학 리뷰는 외부 Codex에서 받았습니다. 원고 리뷰 001·002의 실제 수정 요청과 003의 승인도 보존했습니다. 같은 Chat의 Deep Research 정적 리뷰 시험은 완료됐고 Work로 넘기지 않았습니다. 입력 전체 읽기·해시 확인·정적 검토는 가능했지만 별도 native 리뷰 job ID와 독립된 새 컨텍스트를 입증하지 못했으며, 보고서는 독립 승인을 거부하는 `accepted=false`를 반환했습니다. 이 판정은 소스 알고리즘이나 실험 control 실패를 뜻하지 않습니다. 이 과거 결과는 외부 독립 리뷰를 사용한 일반 Chat의 호환 실행·export 검증이며 단일 대화의 독립 검토 기능이나 전자동·PC 없는 전체 제작 성공을 입증하지 않았습니다. 변환 receipt의 pdflatex 두 pass는 exit 0과 input/output 해시를 확인했지만 stdout 전체 원본은 동봉되지 않고 각 4,000자 tail만 보존했습니다.

당시에는 설치된 스킬 문서와 실행 컨테이너의 파일 접근이 별개였으며, 원본 파일 전달이 별도로 필요했습니다. 수동 ZIP 첨부를 플러그인 설치만으로 실행하는 경로의 성공으로 계산하지 않았습니다. connector 목록만으로 파일 실행 도구가 없다고 판단한 오류도 있었지만, 전체 namespace를 다시 확인하여 native `container.exec`를 찾았습니다. 후속 복구에서는 같은 연구 data·journal과 원래 실행 receipt를 보존했고, 응답 중단을 이유로 실험을 반복하지 않았습니다.

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
