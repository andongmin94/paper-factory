# main용 독립 이식과 게시 전 검증

2026-11-09, 추가 지시 2/5. 로컬 커밋 `91ecd792fba0456a424a859dd56e55e74adb8712`와 `154f40021e5e60553fa93c04f0aee9ad2ebf723b`의 결함 수정만 최신 main의 기존 API에 이식했다. PR #2의 다른 기능은 포함하지 않았다. 이 문서는 게시 전 검증 기록이며, 실제 원격 반영과 해당 SHA의 CI 결과는 게시 후 별도로 확인해야 한다.

## 비교 기준과 결론

| 구분 | 확인한 상태 |
| --- | --- |
| 원격 main | `1aff3b7d1df45c2d7b9505c4d1be1761ba08b030` |
| 유일한 열린 PR | Draft [#2](https://github.com/andongmin94/paper-factory/pull/2), head `659fa818fab67fae2259d758c4472e423fa157ed` |
| main → PR #2 | 17개 커밋, 변경 파일 41개 |
| 이전 두 회차 | PR head 위의 `91ecd79` → `154f400`, 변경 파일 16개 |
| 이번 이식 | main에서 직접 분기한 `fix/main-verified-tool-handoff` |

`154f400`을 그대로 main으로 push하면 우리 두 커밋 외에 PR #2의 17개 선행 커밋까지 들어간다. 따라서 그 브랜치를 직접 반영하지 않는다. 기존 main, PR 기반 로컬 브랜치, 두 회차 패치·ZIP·검증 문서는 보존했다. 이전 산출물 다섯 개의 SHA-256과 두 검증 문서의 원본 바이트를 다시 대조해 일치를 확인했다.

저장소와 상위 경로에서 추가 AGENTS.md를 발견하지 못했다. 사용자가 제공한 단순한 구현, 기존 의존성 활용, 호환 계층 금지 지침을 적용했다. 의존성·CI·권한·보안 설정은 변경하지 않았다.

## 문맥 충돌과 실제 기능 의존성 구분

기존 누적 패치의 `git apply --check`는 main에서 실패했다. README, tools 안내, editorial scanner, exporter, 두 테스트 파일의 문맥이 PR #2와 달랐다. 검사만 실행했으며 실패한 패치로 작업 파일을 변경하지 않았다.

처음에는 기존 테스트를 그대로 유지하기 위해 PR의 두 기능을 추가한 별도 로컬 후보를 검토했다.

- `37765d9`의 DOCX-only export: 기존 그림 회귀 대부분이 `docx_only=True`를 호출했다. main의 export API에 같은 인자를 전달하면 실제로 `TypeError`가 발생했다.
- `daaaa9e` 중 full 40-character SHA capture: 환경 격리 회귀의 commit/tag 조합 중 main에 없는 full-SHA 두 경우가 실패했다. 환경 격리만 적용한 main 실험은 **2 failed, 2 passed**였으며, 실패 이유는 해당 SHA 이름의 branch를 찾지 못한 것이다.

이 결과는 수정 알고리즘 자체가 그 기능에 의존한다는 뜻이 아니다. 두 기능을 추가한 로컬 후보 `813c98c35fc63eb8bd46bb2e740596a22d3c8a4b`는 **462 passed, 63 subtests passed**였지만, 범위가 넓어서 최종 반영 대상에서 제외했다. 그 후보와 진단 기록은 별도로 보존하고 원격에 게시하지 않았다.

최종 이식은 다음처럼 main의 기존 계약으로 검증했다.

| 수정 | main에 적용한 방식 | 추가 PR 기능 |
| --- | --- | --- |
| 인용 검사와 출판 판정 연결 | 기존 editorial scanner의 숫자 인용 검사와 preflight/compliance 연결 | 없음 |
| 근거 인용문 재검사 | `impact()`에서 이미 읽은 원자료에 인용문과 줄 범위를 항상 대조 | 없음 |
| Git 환경 격리 | 기존 branch/default/tag 캡처의 하위 프로세스에서 저장소 경로 변수 제거 | full-SHA 지원은 추가하지 않음 |
| 그림 원본 보존 | 기존 native Word export에서 상대경로 그림을 보존하고 보존본을 변환 | DOCX-only 모드는 추가하지 않음 |

`export()`의 인자와 최종 반환값, `preflight()`, exporter CLI, `capture_repository()`, research CLI가 main과 동일함을 AST로 확인했다. Git 회귀는 기존 default branch/tag × 두 환경 오염 모드로 바꿨고, 타 저장소 전체 바이트·부모 환경·인증/통신 설정 보존 검사는 유지했다. PR 전용 DOCX-only/full-SHA 회귀는 기존 `154f400` 브랜치에 그대로 남아 있다.

## 그림 보존과 도구 연결

그림 수집 함수는 앞 회차와 동일하다. 실제 Pandoc과 실제 converter의 Markdown reader로 Image 노드를 읽고, 일반·참조형 그림의 경로와 원고 바이트를 다시 쓰지 않는다. 원고 디렉터리 또는 명시한 단일 resource directory에서 참조한 파일만 읽어 새 출력에 같은 상대경로로 보존한다.

이동 후 원래 원고·그림 디렉터리를 삭제한 상태에서도 보존된 원고와 그림으로 실제 Pandoc/DOCX 재변환을 실행했다. 명시적 제출 묶음에 원고·DOCX·그림만 넣고, 묶음을 이동한 뒤 원본과 중간 export를 삭제하는 회귀도 포함했다. 묶음은 계속 명시적으로 선택한 파일만 복사한다.

누락·빈 파일·손상 raster, 일반/참조형 경로, 한글·공백·괄호·percent/hash 파일명, traversal, symlink, 대소문자/파일-디렉터리 충돌, 생성 파일과의 충돌, Windows 비호환 파일명, 원본과 보존본의 변환 중 변경 감지를 검사한다. 같은 그림을 여러 번 참조해도 한 번 보존하고 코드 예제와 참조하지 않은 파일은 수집하지 않는다.

이식된 그림 테스트 41개는 main의 native export를 호출한다. Pandoc·DOCX·파일 입출력·이동·원본 삭제·manifest·bundle은 실제 동작이며, Microsoft Word/PDF와 native compliance 서비스만 명시적 테스트 대역이다. 테스트 대역은 content-format과 submission-ready를 false로 남기며, 실제 Word 실행이나 페이지 검수를 완료했다고 표현하지 않는다.

## 수정 전후 검증

| 검증 | 결과 | 해석 |
| --- | --- | --- |
| 최신 main 전체 기준선 | **365 passed, 63 subtests passed** | 이번 회차에 Pandoc 3.9로 다시 실행 |
| 기존 누적 패치를 main에 그대로 적용할 수 있는지 | **실패, exit 1** | 문맥 충돌; 파일 변경 없음 |
| main에서 원래 full-SHA 환경 회귀 | **2 failed, 2 passed, exit 1** | 기존 main에 없는 API 기능 확인; 통과로 계산하지 않음 |
| main export에 DOCX-only 인자 전달 | **TypeError 재현** | 원래 main의 미지원 인자; 출력/Word 실행 없음 |
| main 원본 + 새 native 그림 테스트 | **37 failed, 4 passed, exit 1** | 누락·이동 재변환·보호 조건을 실제 재현 |
| main 원본 + 새 연구 도구 회귀 | **8 failed, 55 deselected, exit 1** | Git 환경과 근거 witness 오류 재현 |
| 수정 후 그림 회귀 | **41 passed** | 실제 Pandoc/DOCX, Word/PDF 대역 |
| 수정 후 export 집중 회귀 | **71 passed** | gate·독립 설치·native 변경 감지 포함 |
| 수정 후 연구 도구 두 모듈 | **63 passed** | 실제 로컬 Git, 원자료/근거 연결 |
| 최종 main용 전체 pytest | **452 passed, 63 subtests passed** | 25.84초, 실패·error·skip 없음 |
| Pandoc 식별 | **통과: Pandoc 3.9** | 실제 실행 파일 식별 |
| 스크립트 컴파일 | **통과** | `python -m compileall -q scripts` |
| diff 검사 | **통과** | `git diff --check` |
| 이번 SHA의 원격 Windows CI | **게시 전 미실행** | 게시 후 실제 SHA의 실행을 별도로 확인 |
| 실제 Microsoft Word/PDF·전 페이지 육안 확인 | **미실행** | Linux 환경; 기존 CI에도 실제 Word 실행 단계 없음 |
| JOSS Inara/PDF | **미실행** | 소스 검사 문제만 별도 재현 |

최종 환경은 Linux, Python 3.12.14, pytest 9.2.0, Pandoc 3.9다. `CI=true`로 실제 Pandoc 검사를 필수화하고 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`로 무관한 플러그인 자동 로딩을 껐다. 프로젝트 의존성을 새로 추가하지 않았다.

앞 회차의 515/558 passed는 PR #2 기반 결과이며 이번 452 passed와 기준 코드가 다르다. main의 기존 테스트를 삭제하지 않았고, 이번 결함 회귀는 main이 제공하는 API로 검증한다. PR의 다른 기능과 관련 테스트를 함께 가져와 수치를 맞추지 않는다.

게시 전 읽기 조회에서 main의 해당 SHA check-run과 main workflow run 목록은 비어 있었다. PR #2의 [기존 Windows CI](https://github.com/andongmin94/paper-factory/actions/runs/42571671925/job/129010213844)는 `659fa818`의 success이며, 이번 변경이나 main의 성공 근거가 아니다. Windows 자동 회귀가 통과하더라도 실제 Word/PDF 렌더링과 페이지 검수 완료를 뜻하지 않는다.

### 재실행

프로젝트 의존성·pytest와 Pandoc이 준비된 환경에서 저장소 루트에서 실행한다.

```bash
export CI=true
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
python -m compileall -q scripts
python -m pytest -q tests/test_export_media.py tests/test_skill_export.py
python -m pytest -q tests/test_repository_snapshot.py tests/test_research_workspace.py
python -m pytest -q
git diff --check
```

이번 실패·성공 로그, JUnit XML, 실행 명령, 기존 산출물 SHA-256 대조, main API 불변 검사는 별도 `paper-factory-verification/round3/`에 보존한다. 기존 패치와 로그는 덮어쓰지 않는다.

## 이번에 포함하지 않은 PR 기능

DOCX-only, full-SHA capture, Claude/runtime 안내, EMSE/MLOSS 매체, host conversion 기록, canonical Markdown/finalizer 변경, grouped citation의 DOCX 조판 변경, DOI/URL 개선, CI ZIP 배포 단계를 가져오지 않았다. 기존 `SKILL.md`, requirements, CI, venue/template/text/JOSS/bundle/finalizer 구현은 main과 같다. 이 범위에서 PR #2의 나머지 문제를 해결했다고 주장하지 않는다.

## 다음 실제 문제

앞 회차의 JOSS YAML metadata Image 누락을 이번 main용 수정본에서도 다시 재현했다. 제목에 `![Logo](missing-logo.png)`가 있고 실제 파일은 없을 때, Pandoc 전체 AST의 metadata에는 Image가 있으나 JOSS 소스 수집은 body blocks만 읽는다.

```text
input_image_exists: false
metadata_image_targets: [missing-logo.png]
body_image_targets: []
preflight_passed: true
reported_image_count: 0
source_package_passed: true
retained_image_exists: false
```

이는 소스 검사 탐지 누락이다. 실제 Inara/PDF 실패를 확인한 것은 아니다. 이번 원격 반영 범위를 두 회차 수정으로 한정하기 위해 JOSS 구현과 테스트는 변경하지 않았다. 다음 회차에는 metadata 그림을 현재 계약에 맞게 수집할지 명확하게 거부할지를 정하고, 소스 검사·패키징 경로를 함께 수정하는 것이 다음 후보이다.

## 변경 파일

- 구현 6개: `_publication_checks.py`, `_publication_convert.py`, `_repository_snapshot.py`, `editorial_checks.py`, `export_manuscript.py`, `research_workspace.py`
- 회귀 5개: `test_editorial_checks.py`, `test_export_media.py`, `test_repository_snapshot.py`, `test_research_workspace.py`, `test_skill_export.py`
- 현재 계약 문서 3개: README, `references/tools.md`, `references/researcher-convenience.md`
- 검증 기록 3개: 이전 두 회차 문서 원본과 이 문서

main은 새 이식 커밋으로 반영하고, `91ecd79`와 `154f400`의 이력은 다시 쓰지 않는다. Draft PR 생성, PR #2 병합, 릴리스·배포·권한/보안 설정 변경은 이번 작업에 포함하지 않는다.
