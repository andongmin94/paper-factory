# BibTeX 오류 위치 진단 개선

2026-11-10. “남은거도 진행해” 요청에 따라 이전 회차에 재현해 둔 malformed BibTeX의 부정확한 오류 위치를 개선했다. 실행 코드 변경은 기존 pyparsing 문법 연결 두 곳이다. 새 변경은 최신 main 위의 `fix/bibtex-error-locations` 브랜치에 로컬로 보존한다.

## 시작점과 보존 한계

GitHub에서 최신 main, 열린 PR, 실제 CI 실행을 다시 읽었다.

| 대상 | 확인한 사실 |
| --- | --- |
| 원격 main | `fdbc0d52e5466fc1ea0f4ab73c8f2dd0e138d962` |
| main tree | `814ce3863d0321f556ec25d8c48219de137450db` |
| main parent | `1a0b33ac0a350850d011a44d725a66a2c78ac42e` |
| main의 새 게시 내용 | JOSS metadata 그림·인용/nocite와 BibTeX 필드 주석 수정 |
| 열린 PR | Draft #2 한 개, head `659fa818fab67fae2259d758c4472e423fa157ed` |
| PR 상태 | `merged=false`, `mergeable=false`, `mergeable_state=dirty` |

현재 main tree는 이전 회차에 기록된 최종 `245f8c1` tree 값과 같다. 따라서 앞선 세 수정을 중복 적용하지 않았다. 이번 세션에서 main 게시를 수행한 것은 아니다.

**이전 로컬 이력의 복원 한계가 있다.** 재개된 작업 공간에는 이전 checkout과 외부 패치·ZIP·bundle·검증 로그가 없었다. 기존 복원 ZIP과 bundle의 정확한 이름 검색도 결과가 없었고, 원격은 원래의 `245f8c1` commit 객체를 제공하지 않았다. 새 clone에서 `91ecd79`, `154f400`, `88c705d`, `813c98c`, `5b44535`, `0d64576`, `245f8c1` 객체가 없음을 확인했다. 원격의 `1a0b33a`, `fdbc0d5`, PR head는 존재한다.

최신 main에서 코드와 추적된 과거 검증 문서를 확보했지만, 이전의 원래 로컬 commit 객체와 외부 산출물 228개를 복원하거나 다시 해시 검증했다고 주장하지 않는다. 과거 문서에 적힌 결과는 당시 관측 기록으로 유지한다. 모든 이전 객체까지 복원하려면 앞서 내려받은 bundle/복원 ZIP이 필요하다. 이번 산출물은 **현재 확보 가능한 이력과 이번 검증 증거**를 보존하며, 이전 산출물을 덮어쓰지 않는다.

저장소 전체 트리에서 추가 `AGENTS.md`, `QUALITY.md`, `CONTRIBUTING` 지침은 발견하지 못했다. README, SKILL.md, requirements, 실제 workflow와 사용자가 제공한 최소 구현 원칙을 확인했다.

## 원인과 최소 수정

예를 들어 다음 입력은 여전히 잘못된 BibTeX이며, 반드시 거부해야 한다.

```bibtex
% retained annotation
@string{prefix={Retained}}
@article{retained,
 title={Retained}
 year=2024
}
```

main의 import, JOSS preflight, JOSS export는 모두 `line 3, column 1: Expected end of text`를 반환했다. 실제 누락 쉼표 다음 필드는 5행에 있다. 기존 optional/repetition 표현식이 내부 구문 실패를 되돌리고, 최상위 전체 입력 검사가 entry의 `@`에서 실패하기 때문이다.

`scripts/import_references.py`에서 다음 두 연결만 `+`에서 `-`로 바꿨다.

1. 필드 이름과 경계 주석을 읽은 다음, 필수 `=` 및 값을 읽는 연결.
2. entry 시작인 `@`를 읽은 다음, 기존 정의·preamble·comment·entry 문법으로 이어지는 연결.

[pyparsing의 `-` 연산자](https://pyparsing-docs.readthedocs.io/en/stable/HowToUsePyparsing.html)는 이후 구문 실패의 backtracking을 중단한다. 기존 `ParseBaseException` 처리 안에서 같은 `ValueError`와 JSON CLI 오류로 전달된다. 위 입력은 세 CLI에서 모두 **5행 2열**로 보고되며 exit 2, 출력 미생성은 유지된다.

literal·중첩 괄호·이스케이프·주석의 소비 위치, macro 확장, `Located`, `original_text_for`, `parse_with_tabs`, `source.raw` 슬라이싱은 바꾸지 않았다. 입력 전체 전처리, 새 파서, 새 의존성, PR #2 기능은 추가하지 않았다. 빈 필드와 마지막 쉼표의 정상 종료는 필드 이름 매칭이 cut 전에 실패하므로 유지된다.

오류 위치는 **1부터 시작하는 원본 문자 위치**다. UTF-8 BOM은 제외하고 탭·한글도 각 한 문자로 센다. [pyparsing의 tab 처리 설명](https://pyparsing-docs.readthedocs.io/en/stable/pyparsing.html#pyparsing.ParserElement.parse_with_tabs)과 기존 구현을 유지한다. 위치는 파서가 멈춘 곳이며 누락 토큰 뒤일 수 있다. 예를 들어 미완성 `#` 연결은 `#` 위치를 보고하지만 기대 토큰 설명은 `}`일 수 있다. 모든 문법 오류의 원인을 분류하는 새 진단 계약은 아니다.

## 수정 전후 회귀

새 회귀 24개를 production 변경 전에 실행했다. 기존 주석·리터럴 보호 40개와 함께 **24 failed, 40 passed**를 관측했다.

최초 두-cut 수정 뒤에는 **62 passed, 2 failed**였다. 두 실패는 닫히지 않은 braced 값의 마지막 줄바꿈 처리에 대한 테스트 기대값이었다. 실제 비교에서 pyparsing 3.2.0은 마지막 공백을 소비해 다음 행 EOF를 보고하고, 3.3.3은 마지막 성공 위치인 줄바꿈 직전을 보고했다. 두 위치 모두 해당 버전의 실제 파서 실패 위치다.

같은 unclosed-value fixture에서 끝의 선택적 줄바꿈만 제거해 명확한 EOF **4행 26열**을 검사하도록 정정했다. production은 더 바꾸지 않았다. 최초 테스트 파일, 실패 로그, 두 버전의 공백 처리 probe를 보존했다. 최종 테스트 파일의 SHA-256이 같은 것을 확인하고, 별도로 추출한 main 코드와 수정 코드에 다시 실행했다.

| 검증 | 실제 결과 | 판정 |
| --- | --- | --- |
| 최초 main + 신규 회귀·기존 주석 회귀 | 24 failed, 40 passed | 결함 재현 |
| 최초 수정 + 최초 EOF 기대값 | 62 passed, 2 failed | 중간 실패 보존 |
| 최종 동일 테스트 + main | 24 failed, 40 passed | 결함 재현 |
| 최종 동일 테스트 + 수정 코드, pyparsing 3.3.3 | 64 passed | 통과 |
| 최종 동일 테스트 + 수정 코드, 최소 허용 pyparsing 3.2.0 | 64 passed | 통과 |
| 전체 회귀, Python 3.12.14 / Pandoc 3.9 | 601 passed, 63 subtests passed | 통과 |
| standalone scripts compileall | exit 0 | 통과 |
| main 기준 전체 변경 diff 검사 | exit 0 | 통과 |

신규 importer 18개는 쉼표·등호·값 누락, 끝나지 않은 `#`, 닫히지 않은 braced/quoted 값과 entry의 두 괄호 형식, LF·CRLF/BOM을 검사한다. 정상 첫 entry 다음의 두 번째 entry에서는 탭·한글 앞뒤의 정확한 **8행 13열**을 확인한다. 모두 입력 바이트 불변과 출력 미생성을 검사한다.

JOSS 통합 6개는 3종 오류 × LF/CRLF이며, BOM을 포함한다. 각 사례에서 실제 import/preflight/export subprocess를 모두 실행한 다음 동일한 JSON 오류, exit 2, stdout 없음, 원고·서지 바이트 불변과 출력 미생성을 비교한다. 즉 테스트 내부 CLI 호출은 18회다.

추가로 정상 입력 11종을 main 함수와 수정 함수에 직접 넣어 반환 tuple과 raw 문자열 전체가 같은지 비교했다. 주석·리터럴·macro·undefined macro·빈 필드·마지막 쉼표·comment·preamble·LF/CRLF·한글·탭을 포함했다. 이 결과는 pytest 건수나 Pandoc 실행 건수에 합산하지 않는다.

전체 회귀에는 metadata Image, metadata Cite·nocite·`@*`, 누락/중복 그림·경로 이탈·심볼릭 링크·이름 충돌 보호, Word 출력 입력과 DOCX 변환, 근거 묶음·문헌·편집 도구, Git 환경 격리와 저장소 자료 보존이 포함된다. Word/PDF 서비스를 stub으로 대체하는 기존 테스트의 성격은 그대로다.

재현 명령은 다음과 같다. Pandoc 3.9가 PATH에서 먼저 선택되도록 하고 CI=true로 실행했으며, 실제 argv·환경·입력 SHA-256과 JUnit XML을 `round7` 증거에 보존한다.

```sh
python -m pytest -q tests/test_import_references.py tests/test_joss_export.py \
  -k 'bibtex_error_location or bibtex_entry_comments or bibtex_field_comments'
python -m pytest -q
python -m compileall -q scripts
git diff fdbc0d52e5466fc1ea0f4ab73c8f2dd0e138d962 --check
```

## 독립 설치 확인

설치 대상은 `SKILL.md LICENSE requirements.txt scripts references assets`의 38개 파일이다. 후보 Git tree에서 만든 ZIP을 checkout 밖에 풀고 PYTHONPATH를 제거, user site를 비활성화해 실제 CLI를 호출한다. 실행 Python은 이번 재개 세션에서 requirements와 pytest를 새로 설치한 독립 venv다.

**21회 CLI 호출 모두 기대한 결과를 확인했다.** 정상 수용 exit 0은 5회, 의도된 거부는 16회(exit 1 한 번, exit 2 열다섯 번)다. 예상 거부를 정상 출력 성공으로 세지 않는다. Python/Pandoc 버전 식별 명령 2회는 CLI 검증 건수와 별도다.

| 독립 설치 시나리오 | 호출 수 | 결과 |
| --- | --- | --- |
| 잘못된 BibTeX 4종 × import/preflight/export | 12 | 정확한 위치·동일 오류 JSON, exit 2, 출력 미생성 |
| 정상 복합 입력 import/preflight/export | 3 | exit 0, 원문·해시·metrics 확인 |
| 출력 이동·생성 원본 폴더 삭제 후 preflight/export | 2 | exit 0, 재출력 묶음의 모든 바이트 일치 |
| 없는 metadata Cite | 2 | preflight exit 1, export exit 2 |
| 없는 metadata Image | 2 | preflight/export exit 2 |

정상 입력은 BOM·CRLF, 필드 주석, braced/quoted `%`, escaped `\\%`, URL `%20`·`%25`, 중첩 값, macro·`#` 연결, metadata Image/Cite, 명시적 nocite와 `@*`를 함께 포함한다. 본문과 metadata가 공유하는 그림은 중복 수집하지 않았고, 공백·한글 파일명의 그림 두 개를 유지했다. `source.raw`는 각 원본 entry와 일치하고, bibliography 전체 바이트·입력 해시·manifest의 파일별 바이트 수와 SHA-256도 일치했다. 원본 폴더가 없는 이동 경로에서 재검사·재출력한 6개 묶음 파일은 최초 출력과 모두 같았다.

설치 payload 38개와 ZIP 바이트는 실행 전후 동일하다. 사용한 스크립트 `round7/installed-cli-check.py`, 각 호출의 argv·stdout/stderr·JSON, 생성 출력과 fixture, 최종 `installed-cli-result/verification.json`을 보존한다. 검증 스크립트 검토 중 venv Python symlink를 해석하면 system Python을 실행하게 되는 문제를 발견해 실행 전에 경로를 유지하도록 수정했다. 이 수정은 검증 harness에만 해당하며 제품 코드에는 포함되지 않는다.

## 최신 Windows CI와 미실행 범위

[main fdbc0d5의 실제 Windows CI](https://github.com/andongmin94/paper-factory/actions/runs/42629800860)는 completed/success다. Windows Server 2025, Python 3.11.9, Pandoc 3.9, pyparsing 3.3.3에서 **576 passed, 1 skipped, 63 subtests passed**를 실제 job 로그로 확인했다. 2026-11-09 13:55–13:57 UTC 실행이며 한국 시각으로 같은 날 22:55–22:57이다. 이제 앞선 JOSS·BibTeX 주석 변경의 Windows 결과는 확인된 상태다.

이 결과는 이번 새 오류 위치 수정의 Windows 검증이 아니다. quiet 로그에는 skip의 node와 이유가 없다. 소스상 대소문자 file/directory 충돌 fixture의 조건부 skip이 후보이지만 정확한 대응은 추정이다. 그 보호 조건을 Windows에서 실행해 통과했다고 단정하지 않는다.

| 항목 | 상태 |
| --- | --- |
| 이번 새 commit의 Windows/Python 3.11 실행 | 미실행; 로컬 Linux 결과와 구분 |
| 실제 Microsoft Word 자동화·PDF 렌더링 | 미실행; 기존 테스트에는 명시적 Word/PDF stub이 있음 |
| JOSS 공식 Inara/PDF와 전 페이지 시각 검수 | 미실행; 실제 Pandoc AST 및 소스 패키지 검사와 구분 |
| 고전 BibTeX/Biber 실행 | 이번 범위 미실행 |
| 원격 push·PR 변경·병합·배포·릴리스 | 미실행 |

현재 환경에는 Windows/Word와 Docker/Podman이 없다. 다른 로컬 TeX 또는 문서 변환기를 실행해 공식 Inara/Word 검증으로 대체하지 않았다. workflow에도 설치 ZIP 검증 단계는 없으며, 이번 ZIP 검증은 로컬에서 별도로 수행한 것이다.

## PR 충돌과 다음 후보

실제 main과 그대로인 PR head를 읽기 전용 `git merge-tree --write-tree`로 비교했다. 예상된 충돌 exit 1이며 **7개 파일**에서 충돌한다.

- README.md
- references/joss.md
- references/tools.md
- scripts/editorial_checks.py
- scripts/export_manuscript.py
- tests/test_repository_snapshot.py
- tests/test_skill_export.py

진단 전후 HEAD와 모든 refs가 같았다. 실제 병합이나 충돌 해결을 하지 않았다. 이전 main에서 기록한 6개 충돌과 현재 7개 충돌을 혼동하지 않는다.

다음 후보는 **위치를 넘어선 오류 원인 설명**이다. 이번 회귀에서 미완성 `#` 연결은 올바른 `#` 위치를 보고하되 `Expected '}'`로 설명할 수 있음을 확인했다. 현재도 잘못된 입력은 차단된다. 이 문구 개선은 필요성과 범위를 별도로 정할 항목으로만 기록하며 추가 구현을 시작하지 않는다.

## 변경 파일과 복원 자료

| 파일 | 변경 |
| --- | --- |
| scripts/import_references.py | 문법 연결 두 곳의 cut와 설명 주석 |
| tests/test_import_references.py | 신규 위치·원문·무출력 회귀 18개 |
| tests/test_joss_export.py | 실제 3 CLI 연결 회귀 6개 |
| references/researcher-convenience.md | 원본 문자 위치와 진단 범위 명시 |
| 이 문서 | 최신 원격 상태, 수정·검증·보존 한계 기록 |

새 이름의 baseline 이후 patch, 설치 ZIP, 확보 가능한 모든 refs의 bundle 및 이번 검증 증거를 제공한다. 최종 commit/tree, 파일별 SHA-256, offline bundle verify·clone·fsck, patch 적용 tree 일치, 설치 ZIP과 검증 후보 ZIP/Git blob의 바이트 비교 결과는 commit 작성 후 생성하는 `recovery-verification.json`과 인계 자료에 기록한다. 이전에 사라진 로컬 객체까지 들어 있는 “완전 복원”으로 표시하지 않는다.
