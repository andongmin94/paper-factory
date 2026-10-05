# 독립 앱 전환 후 최소 정리 목록

## 정리 구현 완료 — 2026-10-05

아래 초기 목록을 실제로 적용했다. 엔진과 pyproject 버전은 `0.13.0`이다. IPC의 정적 import closure 20개와 별도 실행 macOS guardian 1개, QuickJS worker 1개만 런타임 소스로 남겼다. CLI·Cloud·플러그인 진입점·옛 투고·Docker/WindowsRunner/AppContainer 경로와 직접 대응 스크립트·테스트·plugin CI를 제거했다. `runner_common.py`는 QuickJS가 실제 사용하는 한도·원본 file tree·관측값·production receipt 검사만 담당한다. Windows Job Object/creation identity와 macOS guardian, 과학적 제어·복구·분석·실제 변환은 유지했다.

빌드 입력은 `desktop/runtime-inputs/`로 옮겼다. QuickJS archive/metadata와 Pandoc notices의 원본 bytes는 그대로다. host catalog는 Windows x64 및 macOS Intel/ARM CPython 3.14의 세 profile과 실제 사용하는 48개 wheel로 좁혔다. 현재 host catalog SHA256은 `78f90b767afbd9e1ca86a3c217803d796936ee10a297729c4c32a361769224a1`이며 runtime-manifest가 이 값을 검증한다. Typer/dotenv/jsonschema와 그 CLI runtime wheel은 제외했다. 기존 JSON Schema 독립 검증과 manifest generator 때문에 jsonschema/packaging은 dev extra에 남는다. 새 의존성을 도입하지 않았다.

`WorkflowService`의 home/runner는 명시적으로 필수화했으며 plan/bundle은 `quickjs`, 빈 dependencies, JavaScript 실험 entrypoint만 받는다. 실제 production TS 원본의 trusted compiler 경로는 유지한다. source snapshot에는 global current pointer·PF_HOME 기본값·외부 Git 실행이 없다. 공개 GitHub commit archive의 원본 수집과 sanitized freeze가 유지되며 로컬 원본 freeze는 trusted fixture/shared source helper로 남는다. 변환은 명시적 절대 Pandoc 경로와 Typst PDF를 사용하고 TeX/DOCX export를 유지한다. system PATH/pypandoc discovery 및 pdflatex branch는 제거했다. 옛 manual publication 코드만 쓰던 Workspace artifact rollback/rename helpers도 호출 관계를 확인한 뒤 제거했다.

검증은 별도 새 temp에서 수행했다. 성공 수를 실제 계정 인증·최종 세 논문·macOS 설치 성공으로 계산하지 않는다.

| 검사 | 결과 |
| --- | --- |
| core records, DOI, sanitized source, authentication exclusion, workspace, author, 실제 conversion 첫 회귀 | 138 passed, 1 symbolic-link permission skip, 17.17초; 이후 unused manual Workspace helper 삭제에 따른 해당 suite 재검사 25 passed |
| QuickJS runner/platform/standalone IPC | 170 passed, 2 actual macOS native tests skipped on Windows, 103.03초 |
| workflow 및 scientific controls/analysis/manuscript | 최종 전체 226 passed; 첫 두 fixture 실패를 수정한 뒤 전체 재검사 |
| autonomous literature 및 bounded PDF extraction | 48 passed, 3 symbolic-link permission skips, 2.16초 |
| common helpers 및 Windows Job/process identity | 최종 전체 28 passed, 1 symbolic-link permission skip, 7.32초; native subprocess cases도 실행 |
| static parse, builder syntax, runtime input digest equality, Git whitespace | 통과 |

첫 workflow/science 회귀의 두 실패는 Windows Pandoc fixture의 `.exe` 없는 경로와 이전 file-output 기대값이었다. 기존 checked Pandoc fixture와 QuickJS observations envelope 계약으로 수정했다. 원래 실패 workspace `C:/Users/Andongmin/AppData/Local/Temp/pf-cleanup-contract-084f7d175dc2453f8a6729a63eceda00`와 원래 exec stdout(대화의 session 86071 / completion chunk e78219)을 보존했다. 당시 별도 log file은 만들지 않았다. 최종 실제 combined stdout/stderr는 `C:/Users/Andongmin/AppData/Local/Temp/pf-cleanup-final-e0d4607e28b9409a80344a033ad0a89a/workflow-science.log`에 남았다.

옛 public skill resources 38개와 이전 전체 host manifest, 이동 전 문서 원본을 `.paper-factory/standalone-cleanup-preservation/plugin-0.12.0/`에 hash-확인하여 보존했다. `source-final.json`은 남은 22개 source files의 실제 SHA256와 아직 runtime build를 수행하지 않았다는 범위를 기록한다. 기존 `.paper-factory/output/`, root output/dist, runtime directories, runtime cache, installed app resources, 과거 receipt/evidence/history README를 변경하지 않았다. 옛 제품 문서 13개는 `docs/history/`로 옮기고 역사 범위와 이전 commit 소스 링크를 표시했다. 현재 제품 README와 최종 설치본 검증은 루트 작업에서 이어서 기록한다.

이 source-final을 Windows/macOS fresh runtime build에 넘겼다. 아래 내용은 정리 이전의 초기 조사·계획이며 현재 경로 목록으로 해석하지 않는다.

## 초기 조사 및 적용 계획 (정리 이전 소스 기준)

조사일: 2026-10-05. 현재 소스를 정적으로 읽은 정리 계획이다. 이 조사에서는 프로젝트 엔진·Electron 앱·브라우저를 실행하거나 런타임 입력·엔진 코드를 바꾸지 않았다. 표준 라이브러리 AST 파서는 소스 텍스트만 읽었으며 프로젝트 모듈을 import하지 않았다. 현재 Python SOURCE FINAL을 유지하며, 새 설치본의 동작을 확인한 뒤 아래 단위를 차례로 적용한다. 과거 논문·관측·receipt·실패 기록은 삭제 대상이 아니다.

## 현재 실행 경로와 조사 방법

`desktop/src/main/main.ts:8-10,60-61`은 `ConnectionController`, `EngineBridge`, `ResearchController`를 연결한다. `desktop/src/main/preload.ts`가 공개한 연구 API는 `research.ts`에서 정해진 `runtime.status` / `workflow.*` 호출로 이어진다. 인증과 모델 호출은 Electron main의 `@siwc/local`에 남는다. `desktop/src/main/engine.ts:96-109`는 환경을 명시적으로 제한하고 번들 Python을 `-I -B -m paper_factory.ipc --home … --runtime-root … --node … --pandoc …`로 실행한다. CLI, Cloud 어댑터, plugin manifest는 이 경로에서 읽거나 실행하지 않는다.

`src/paper_factory/**/*.py` 41개 모듈의 AST를 읽고 `ipc`·`standalone_runtime`에서 시작하는 상대/절대 import를 추적했다. 함수 내부·플랫폼 조건부 import를 포함한 보수적 closure는 21개다. 이는 실제 실행 로그가 아니며, 현재 실행하지 않는 기본 native runner도 포함한다. 별도 파일로 실행하는 guardian과 Node worker는 추가로 추적했다. 프로젝트 모듈을 import하거나 WorkflowService를 생성하지 않았다.

| closure의 모듈 (`paper_factory.` 생략) | 현재 import 이유 |
| --- | --- |
| `__init__`, `autonomous.__init__` | 패키지 초기화; 버전과 빈 autonomous 초기화 |
| `ipc` | bounded JSON Lines dispatcher; standalone runtime·workflow·workflow models·workspace |
| `standalone_runtime` | 명시적 앱 home, owner/lease, QuickJSRunner 및 literature collector 주입 |
| `workflow`, `workflow_models` | 단계·복구·동결·추론 receipt·분석·실제 변환·artifact 계약 |
| `workspace`, `models` | SQLite, 엄격한 JSON, 경로/파일 검증, 공용 Record·Asset·Project·시간·ID |
| `project` | 공개 GitHub commit/source 원본 수집·inventory·검증; workflow가 직접 사용 |
| `author` | workflow export와 science의 검증된 author metadata; 투고 코드 삭제와 별개로 유지 |
| `conversion` | workflow의 PDF/TeX/DOCX 출력 |
| `literature` | autonomous collector가 `_doi`·`_metadata`를 import |
| `autonomous.models`, `autonomous.science`, `autonomous.literature` | 계획/코드/검토/원고 스키마, 과학적 제어·분석·렌더링, 실제 문헌 조회·읽기 |
| `autonomous.quickjs_runner` | 실제 standalone experiment runner; 공용 bounded helper를 `runner`에서 import |
| `autonomous.quickjs_windows`, `autonomous.quickjs_macos` | QuickJSRunner의 플랫폼별 조건부 import |
| `autonomous.windows_runtime` | QuickJS Windows Job Object와 bounded literature PDF extractor |
| `autonomous.runner` | QuickJS helper import 및 workflow의 legacy LIMITS/default runner import |
| `autonomous.windows_runner` | `runner.research_runner()` 함수 내부 import; standalone은 명시적 QuickJSRunner를 주입하므로 이 selector를 호출하지 않음 |

import 외 파일 의존성도 유지해야 한다:

- `autonomous/quickjs_macos.py:17,80-90`은 `quickjs_guardian.py`를 번들 Python의 별도 자식으로 실행한다. guardian은 static import closure 밖에 있지만 **필수 런타임 소스**다.
- `autonomous/quickjs_runner.py:38`의 `WORKER`는 같은 폴더의 `quickjs_worker.mjs`다. guardian도 이 worker의 고정 경로·해시를 검사한다.
- `autonomous/literature.py:259-298`의 PDF extraction 자식은 같은 패키지의 `_extract_pdf`를 import하고 Windows에서 WindowsJob을 쓴다. 독립 앱의 trusted PDF extractor이며 옛 native experiment runner와 다르다.
- `desktop/scripts/build-runtime.mjs:320-321`은 아직 `src/paper_factory` 전체를 복사한다. 따라서 unreachable CLI·Cloud·투고 소스도 현재 payload에 들어간다. source 삭제 후 새 runtime inventory·binding·설치본을 생성해야 한다. 기존 runtime·receipt를 덮어쓰며 새 코드의 성공 증거로 재해석하지 않는다.

## 먼저 이동할 빌드 입력

가장 작은 이동은 현재 bytes를 그대로 `desktop/runtime-inputs/`로 옮기고 소비 경로만 바꾸는 것이다. 아래 다섯 파일의 실제 bytes를 SHA256으로 읽어 manifest 값과 일치함을 확인했다. 첫 이동에서 Python 버전·wheel pins·QuickJS bytes·라이선스를 함께 갱신하지 않는다. manifest의 내부 `licenses/pandoc/…` 키는 input root에 상대적인 키로 그대로 유지할 수 있다.

| 현재 입력 | 제안 위치 | 현재 실제 소비자 / 보존 사항 |
| --- | --- | --- |
| `skills/paper-factory/host-dependencies.json` | `desktop/runtime-inputs/host-dependencies.json` | `desktop/runtime-manifest.json:7-8`, builder `:64-67,245-249`; SHA256 `1ad1145cca20dc66784b9b96d5d4438153fe1427f9daf63d444bd097bd8ff9ed` 유지 |
| `skills/paper-factory/assets/quickjs-runtime.zip` | `desktop/runtime-inputs/assets/quickjs-runtime.zip` | manifest `:11,14-16`, builder `:68-70,225-241,317-318`; 486,998 bytes, SHA256 `7a28754c912a4bbfcc41dbe88598bb4ab348337b7d455547c20db29258d40b3a`, member inventory SHA256 `ab3b2f965197a33c3c58ee1ca26b75871e78e8b59e4f09fd24addd6d88d7e51a` 유지 |
| `skills/paper-factory/assets/quickjs-runtime.json` | `desktop/runtime-inputs/assets/quickjs-runtime.json` | metadata SHA256 `3a2c483164c2b1ac2ea0936aa66aa8de66d34c230634ab38f13df52fa3dd859b` 유지; archive member hashes 및 upstream npm license 그대로 유지 |
| `skills/paper-factory/licenses/pandoc/COPYING.md` | `desktop/runtime-inputs/licenses/pandoc/COPYING.md` | builder `:347-352`; 원본 17,787 bytes, SHA256 `9d56cac92294e206af026a5502bee0fed77200b08b51ec28aa63c9efda4dcfdd` 유지 |
| `skills/paper-factory/licenses/pandoc/COPYRIGHT` | `desktop/runtime-inputs/licenses/pandoc/COPYRIGHT` | builder `:347-352`; 원본 9,598 bytes, SHA256 `842e33ef01625e93f85bebb8bac83aa570186b7aa77a09971257cc29f8f60740` 유지 |

동시에 바꿔야 할 참조는 `desktop/runtime-manifest.json`, Pandoc input root를 하드코딩한 builder `:348`, `tests/test_quickjs_runner.py:24`, `tests/test_standalone_ipc.py:37`, `desktop/third-party/runtime-NOTICES.md:7`, `.github/workflows/desktop.yml:5,7`의 path filter다. `test_quickjs_platforms.py:21`도 해당 QuickJS fixture를 재사용하므로 이동 후 함께 검사한다. 이동만 해도 runtime-manifest bytes의 해시가 달라지므로 fresh runtime build·`runtime-inventory-binding.json`·package verification을 다시 만들 필요가 있다. 위 참조는 **이번 조사에서 변경하지 않았다**.

`scripts/generate_host_dependencies.py`는 현재 builder가 읽는 wheel/Node/Pandoc catalog의 생성기다. 즉시 삭제하지 않는다. 유지보수용 위치로 옮긴 뒤 default output `:161`과 host scope 문구 `:154-158`, 현재 불필요한 CPython 3.12/3.13·Linux profiles를 후속 단위에서 정리한다. `packaging`으로 wheel tag와 `requires_dist`를 검증하는 기능 `:12-16,118-130`은 재사용한다. 앱이 이 생성기를 실행하거나 다운로드하는 것으로 설명하지 않는다.

`skills/paper-factory/wheelhouse/`, `dependency-manifest.json`, `scripts/cloud-dependencies.lock`, Pandoc 외 `licenses/`는 현재 standalone builder가 읽지 않는다. builder는 host catalog의 공식 artifact URL·크기·SHA를 사용해 별도 cache에서 wheel을 내려받고, wheel/QuickJS의 원본 notices를 수집한다 (`:245-264,323-357`). 이 옛 입력들을 standalone payload에 복사할 필요는 없다. 다만 배포했던 plugin의 source/hash/license 기록으로 필요한 original manifest·lock·notices는 삭제 전에 역사 자료로 보존한다. 설치했던 plugin·오래된 archive/receipt 안의 originals는 손대지 않는다.

## 소스 삭제 전에 분리할 공용 부분

| 파일 / 현재 근거 | 최소 변경 |
| --- | --- |
| `autonomous/runner.py:36-43,230-249,301-342`; QuickJS import `quickjs_runner.py:24` | `MAX_ARTIFACT_BYTES`, `MAX_LOG_BYTES`, `_safe_tree`, `_retain_observations`, `_production_calls`와 그 함수의 `MAX_INPUT_BYTES`, `MAX_INPUT_FILES`, `MAX_PRODUCTION_FUNCTIONS` 의존성을 작은 `autonomous/runner_common.py`로 옮긴다. `ensure_unlinked`, `is_link`, `loads_json` 및 표준 라이브러리만 필요하다. Docker driver/launcher, `_entrypoint`, `_stage_tree`, DockerRunner를 옮기지 않는다. |
| `workflow.py:25,125-130,259` | 명시적 home·runner를 필수로 받아 standalone의 QuickJSRunner만 주입한다. `research_runner()` 및 native LIMITS fallback을 제거하고 선언된 QuickJS limits를 사용한다. 기존 workflow tests도 이미 명시적 runner를 주입한다 (`tests/test_workflow.py:152` 등). 이 작업 후 `runner.py`, `windows_runner.py`를 삭제할 수 있다. |
| `autonomous/windows_runtime.py` | `WindowsJob`, process creation identity인 `process_ticks`, nonce-bound `stop` 및 필요한 Win32 structures/API/security-descriptor helpers를 유지한다. QuickJS `quickjs_windows.py:13,18,42`와 PDF extraction `autonomous/literature.py:33,284`의 직접 의존이다. AppContainer profile/ACL preparation·native source launch·log/directory helpers만 후속으로 제거한다. `_api` 안의 shared Win32 declarations까지 연쇄 확인한 뒤 자른다. 파일 전체 삭제 금지. |
| `literature.py:33-86`; autonomous collector `:31` | `_doi`와 `_metadata`, metadata normalization helper를 작게 분리하거나 같은 파일의 필요한 부분만 유지한다. 옛 Study/Citation search/import/provenance API는 standalone이 쓰지 않는다. 분리 뒤 `models.py`의 Citation·Study·Provenance를 제거할 수 있다. |
| `models.py`, `workspace.py`, `project.py` | `Record`, `Asset`, `Project`, `now`, `uid`를 유지한다. Workspace의 strict JSON/SQLite/leases/path helpers도 유지한다. manual Study/Experiment/Claim/Paper/Submission 모델·state transitions는 관련 호출자를 삭제한 뒤 제거한다. app home을 명시적으로 전달하므로 `pf_home`, `current`/`make_current`, `project.ingest(make_current=…)`의 old CLI 선택 경로 및 'paperfactory start' 안내는 다음 작은 단위에서 정리한다. 기존 연구 directory를 읽거나 migrate하지 않는다. |
| `autonomous/models.py:21,55`, `autonomous/science.py`, workflow reproduction 안내 | 현재 스키마의 Python/Node branches와 native-host 설명을 QuickJS JS/TS scope로 좁힌다. 실제 analysis/recompute·controls·원본 검증은 유지한다. 재현 script를 Python으로 생성한다는 이유로 trusted Python 분석까지 삭제하지 않는다. |
| `conversion.py:76-96` 및 PDF engine branches | 실제 TeX/DOCX 변환·Typst PDF·native reopen·hash receipt를 유지한다. app의 명시적 bundled pandoc 전달에 맞춰 system/PATH discovery·CLI pip 설치 안내·pdflatex 실행 경로를 제거할 수 있다. **TeX export는 제거 대상이 아니다.** Windows `pypandoc_binary` wheel은 bundled pandoc executable을 공급하므로 import fallback 삭제만 보고 wheel을 삭제하면 안 된다. |

`autonomous/repositories.py`는 closure 및 현재 main/preload API에 없다. 현재 앱은 명시적인 공개 GitHub URL을 받으며 자동 저장소 discovery를 제공하지 않는다. 옛 CLI discovery 기능을 제거할 때 해당 소스와 `test_autonomous_repositories.py`도 제거 후보다. 고정 commit·license·선정/제외 근거는 [저장소 선정 기록](standalone-repository-selection.md)과 보존한 공개 원본 receipt에 남겨야 한다. 점수 기반 discovery를 새로운 연구 성공의 증거로 유지할 필요는 없다.

## 제거할 제품 진입점·스크립트·CI

빌드 입력을 먼저 이동한 뒤 아래 파일을 관련 테스트와 함께 삭제한다. standalone builder는 plugin extraction helper를 import하지 않고 자체 안전한 추출/검증을 구현한다 (`build-runtime.mjs:168-241`).

| 삭제 단위 | 정확한 파일 |
| --- | --- |
| plugin/host 진입점 | `plugin.json`; `skills/paper-factory/SKILL.md`; `skills/paper-factory/references/workflow.md`; skill scripts `host_context.py`, `probe.py`, `prepare_host.py`, `prepare_runtime.py`, `run_workflow.py`, `receive_package.py` |
| plugin·Cloud archive/transport 검증 | `scripts/build_plugin.py`, `build_skill_transfer.py`, `build_package_transfer.py`, `verify_archive_transfer.py`, `ci_verify_plugin.py`; `.github/workflows/plugin-verification.yml` |
| 수동 CLI/Cloud 어댑터 | `src/paper_factory/cli.py`, `cloud.py`, `config.py`; `.env.example`은 CLI-only dotenv/OJS/old PF_HOME/native runner 설정을 제거한다. 앱이 dotenv를 지원한다고 안내하지 않는다. `author.py`는 유지한다. |
| 과거 수동 연구/논문·투고 구현 | `src/paper_factory/evidence.py`, `experiments.py`, `integrity.py`, `manuscript.py`, `research.py`, `ojs.py`, `portal.py`, `preprints.py`, `publication.py`, `revisions.py`, `revision_submission.py`, `submission_package.py`, `venues.py`, `venue_compiler.py`, `venue_policy.py` |
| 과거 CLI smoke/export | `scripts/smoke.py`, `repository_smoke.py`, `phase2_smoke.py`, `phase3_smoke.py`, `phase4_smoke.py`, `portal_smoke.py`, `build_research_artifacts.py` |
| unsupported native experiment runtime | shared helpers 분리 후 `src/paper_factory/autonomous/runner.py`, `windows_runner.py`; `scripts/build_autonomous_image.py`, `setup_windows.ps1`, `research-runtime-requirements.txt` |

위 과거 연구/투고 소스 15개와 CLI/Cloud/config, repositories는 IPC closure 밖이다. 다른 현재 제품을 위한 compatibility shim을 추가하지 않는다. 구현 소스를 삭제하는 것과 그 구현으로 이미 생성한 연구 결과·실패·receipt를 삭제하는 것은 별개다.

`.github/workflows/desktop.yml`은 유지한다. native pinned runtime build, installer, payload 검사, synthetic controller/SDK tests가 현재 제품의 CI다. `.github/workflows/tests.yml` 전체를 삭제하면 유지할 Python 엔진 검증도 사라지므로 파일을 남겨 지원 범위의 Python suite로 좁힌다. 기존 `:31`의 `.[dev,pdf,research,automation]`·native worker requirements와 `:37`의 `paperfactory --help`는 제거한다. 현재 generic shard가 남은 모든 `test_*.py`를 대상으로 하므로 obsolete test 삭제를 먼저 같이 반영한다. macOS engine/owned guardian의 실제 host 검증은 별도 지원 CI에서 수행하며 YAML 존재를 실행 증거로 계산하지 않는다.

## 테스트 정리

| 처리 | 대상 / 근거 |
| --- | --- |
| 유지 | `test_standalone_ipc.py`, `test_quickjs_runner.py`, `test_quickjs_platforms.py`, `test_workflow.py`, `test_autonomous_science.py`, `test_autonomous_literature.py`, `test_conversion.py`, `test_author.py`, `test_workspace.py`; 현재 engine integrity 및 실제 converter/owned process 경계 |
| plugin/Cloud와 함께 삭제 | `test_archive_transfer.py`, `test_skill_transfer.py`, `test_cloud_packaging.py`, `test_host_context.py`, `test_provided_probe.py`, `test_macos_pandoc_preparation.py`, `test_cloud.py`; 마지막 Pandoc 준비 테스트의 plugin-host 경로 대신 standalone native build probe의 라이선스/hash/실제 converter 검증은 유지 |
| CLI/투고/옛 실험과 함께 삭제 | `test_cli.py`, `test_config.py`, `test_manuscript.py`, `test_ojs.py`, `test_portal.py`, `test_portal_audit.py`, `test_preprints.py`, `test_publication.py`, `test_publication_cli.py`, `test_retargeting.py`, `test_revision_cli.py`, `test_revision_submission.py`, `test_revisions.py`, `test_submission.py`, `test_venue_policy.py`, `test_venues.py`, `test_research_artifacts.py` |
| unsupported runtime와 함께 삭제/분리 | `test_windows_runner.py`, `test_windows_dependencies.py`; `test_autonomous_runner.py`의 Docker-only tests는 삭제하되 common helper의 bounded observation·production identity·file tree 검증이 QuickJS/helper tests에서 계속 검증되는지 확인 |
| 일부 유지 후 정리 | `test_windows_runtime.py`는 WindowsJob·creation-time identity·owned cleanup tests를 유지하고 AppContainer ACL/native launch/log tests를 제거. `test_literature.py`는 DOI/metadata pure helper 검증을 유지하고 manual Study search tests 제거. `test_models.py`는 남은 core types를 검증하도록 축소. `test_execution.py:90-152`의 원본 sanitization·symlink·snapshot 불변성 검증과 `:280`의 remote credential 사전 거절을 shared project tests로 분리한 뒤 manual experiment tests를 제거한다. local Git dirty-checkout 전용 검증은 해당 ingestion branch의 지원 여부와 함께 정리한다. `test_authentication_import.py`는 source ingestion에서 별도 인증 directory·자료가 제외되는 경계 테스트이므로 이름 때문에 삭제하지 않음. |

`desktop/tests/`의 connection/Responses/research controller tests와 Electron fixture tests는 유지한다. safeStorage fixture, synthetic IPC state, 실제 OAuth/구독 응답의 검증 범위를 혼동하지 않는다. 이 조사에서 테스트를 실행하거나 성공으로 추가 기록하지 않았다.

## pyproject 및 dependency 연결

- `pyproject.toml:20-21`의 `paperfactory = "paper_factory.cli:app"`를 CLI 삭제와 같은 단위에서 제거한다. package는 standalone Python engine를 위한 내부 패키지로 남길 수 있으며 `ipc`의 argparse는 표준 라이브러리이므로 Typer를 필요로 하지 않는다.
- `typer`는 CLI의 직접 의존, `python-dotenv`는 config의 직접 의존이다. 이 호출자를 삭제한 뒤 pyproject 및 runtime-manifest의 해당 pins/wheels와 native probe import 목록을 정리한다. `jsonschema`도 조사한 engine closure에서 import되지 않는다. JSON validation은 현재 Pydantic과 strict JSON loader가 담당한다. generator·tests·wheel `requires_dist`까지 확인하고 unused direct pin을 제거한다.
- `pyproject.toml:18`의 `automation = [mido==1.3.3, packaging…]`은 `setup_windows.ps1:20`, tests CI `:31`, native worker package group `windows_runner.py:34-35`, `research-runtime-requirements.txt`와 연결된다. 이 native guest 기능을 제거한 뒤 automation extra와 `mido`를 제거한다. **`packaging`은 matplotlib의 전이 의존이자 manifest generator 도구이므로 runtime에서 무조건 제거하지 않는다.**
- Typer/jsonschema의 전이 wheel로 보이는 `rich`, `shellingham`, `annotated-doc`, `attrs`, `referencing`, `rpds-py` 등은 실제 남은 wheel dependency graph를 확인해 제거한다. 이름만으로 한꺼번에 삭제하지 않는다. 유지할 controller/document dependencies는 Pydantic, httpx+SOCKS, bs4, pypdf, python-docx/lxml, matplotlib/numpy, Typst, Windows pandoc 공급 wheel과 그 전이 의존이다.
- `pyproject.toml`의 package-data `quickjs_worker.mjs`와 runtime builder의 동일 파일 복사를 유지한다. runtime은 CPython 3.14 native platform pins를 사용한다. pyproject의 개발 설치 범위와 installed app offline payload를 혼동하지 않는다.

## 보존할 자료와 문서

`.paper-factory/`, `output/`, 오래된 root `dist/` 및 그 안의 논문·fixture·raw observation·receipt·journal·failed probe·CI evidence·archive는 이번 정리의 파일 작업 대상에서 제외한다. 새 연구는 별도의 app-owned home에 남는다. 폴더 이름만 보고 recursive 삭제하거나 옛 worker cleanup을 실행하지 않는다. 이미 생성된 current runtime·package도 정리 문서 작성 때문에 변경하지 않는다.

`LICENSE`, 실제 포함한 upstream license originals/inventories, UI/SDK provenance, [독립 앱 검증](standalone-verification.md), [앱 계획](standalone-app-plan.md), [엔진 조사](standalone-engine-inventory.md), [인증 조사](standalone-auth-research.md), [UI provenance](standalone-ui-provenance.md), [저장소 선정](standalone-repository-selection.md)은 유지한다. 초기 계획의 현재 상태는 완료 증거와 별도로 읽는다.

`docs/history/README.plugin-0.12.0.md`는 commit-pinned 역사 문서이므로 그대로 보존한다. `docs/plugin.md`, `autonomous-research.md`, `portability-goal.md`, `development-goal.md`, `code-audit.md`, `status.md`, `project-audit.md`, `reuse-decisions.md`, `pdf-reuse.md`, `phase2-reuse.md`, `phase3-reuse.md`, `phase4-reuse.md`, `submission-reuse.md`는 옛 host·수동 연구·투고의 사용법/결정/증거가 혼합되어 있다. 본문·receipt 참조를 지우지 않고 `docs/history/`로 옮겨 제품·날짜 범위를 명시한다. 현재 README의 안내 링크와 옮긴 문서의 상대 링크를 정리한다. 과거 명령을 현재 앱 설치법으로 광고하지 않는다. 원본 history README는 이미 고정 commit 링크를 쓰므로 불필요한 rewrite를 하지 않는다.

## 적용 순서와 검증 경계

1. 현재 SOURCE FINAL 설치본의 사용 검증이 끝날 때까지 engine/build inputs를 유지한다. inventory 문서만 추가한다.
2. 다섯 build input files를 bytes 그대로 이동하고 소비 경로·tests·notices·CI path filters만 바꾼다. 해시 비교, QuickJS/IPC tests, native pinned runtime build, package payload 검증으로 이 작은 단위를 확인한다.
3. plugin entry/Cloud/CLI/투고 소스와 직접 대응 tests/scripts/CI를 삭제한다. 현재 IPC/research/exports regression tests를 확인한다. historical docs와 옛 결과는 보존한다.
4. QuickJS common helpers를 추출하고 WorkflowService의 명시적 runner/home 계약을 정리한 뒤 unsupported runners와 native guest extras를 제거한다. Windows owned job 및 macOS guardian cleanup 검증을 유지한다.
5. mixed DOI/core types/workspace/conversion branches를 필요한 범위로 줄이고 dependency graph와 manifest pins를 정리한다. 각 단위마다 별도 fresh app data로 검증하며, root가 보존한 evidence를 새 결과로 대체하지 않는다.

경로 이동·소스 삭제마다 원래 실패 기록은 남겨 두고 fresh runtime inventory 및 설치본 hash를 기록한다. 기존 Windows 성공, synthetic tests, foreign-platform assembly, 실제 macOS 실행·설치, 최종 세 연구의 성공은 각각 다른 검증이다.
