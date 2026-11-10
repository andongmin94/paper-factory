# 로컬 그림 원본 보존과 이동 후 재변환 검증

2026-11-09, 추가 지시 1/5. 첫 회차의 로컬 커밋 `91ecd792fba0456a424a859dd56e55e74adb8712` 위에서 Word export의 그림 원본 누락을 개선했다. 이전 [검증 문서](tool-handoff-verification-20261109.md), 테스트 로그, 패치와 ZIP은 덮어쓰지 않았다. 이번 결과는 로컬 구현·검증이며 원격 게시나 PR 생성을 포함하지 않는다.

## 기준 상태와 개발 지침

작업 시작과 전체 회귀 시점에 GitHub를 읽어 대조했다.

| 구분 | 확인한 상태 |
| --- | --- |
| 원격 `main` | `1aff3b7d1df45c2d7b9505c4d1be1761ba08b030` 유지 |
| 열린 PR | Draft [#2](https://github.com/andongmin94/paper-factory/pull/2) 하나, `feat/claude-skill` → `main` |
| PR head | `659fa818fab67fae2259d758c4472e423fa157ed` 유지 |
| 로컬 작업 | `fix/verified-tool-handoff`, 첫 회차 `91ecd79`의 후속 커밋 |

새 원격 변경과 중복되지 않는 것을 확인했다. 별도의 저장소 `AGENTS.md`와 상위 경로 지침은 발견되지 않았으며 사용자가 제공한 개발 지침을 적용했다. 원격 push·PR 작성/수정·병합·배포·릴리스 및 권한·보안 설정 변경은 수행하지 않았다.

## 현재 계약과 구현의 차이

이전 문서의 Word export 계약은 정확한 Markdown 바이트, DOCX/native 출력과 보고서 보존이었다. 모든 원본 의존성을 자동으로 모은 독립 패키지라는 명시적인 보장은 없었다. 한편 README와 `SKILL.md`의 전달 원칙에는 필요한 그림을 포함하고, 저자 준비 문서는 원래 그림 디렉터리를 `--resource-dir`으로 지정하도록 설명했다.

기존 Word export는 원래 원고 또는 지정 resource directory에서 그림을 읽어 DOCX에 삽입했지만, 출력 폴더에는 그림 원본을 복사하지 않았다. 따라서 최초 DOCX 생성은 성공해도 그 출력 폴더만 이동해 재변환할 때는 그림이 누락됐다. 이번 수정은 이 전달상의 공백을 **참조한 로컬 상대경로 Markdown 그림** 범위에서 해결하고 그 동작을 명시한다.

| 경로 | 이번에 적용한 범위 |
| --- | --- |
| Word native export / `--docx-only` | 실제 converter가 읽는 Markdown 그림 원본을 같은 상대경로와 바이트로 보존하고, 보존본으로 변환 |
| Word `preflight` | 기존의 원고·템플릿 검사 유지. 그림 수집 때문에 Pandoc 실행을 새 필수 조건으로 만들지 않음 |
| JOSS export | 기존 `paper.md`·`paper.bib`·로컬 그림 소스 패키지 경로 유지. 이번 구현 변경 대상 아님 |
| `submission_support.py bundle` | 명시한 파일 allowlist만 복사. 그림을 자동 탐색·추가하지 않음 |
| EMSE / MLOSS | 기존 호스트 변환과 명시적 입력 기록·묶음 경로 유지 |

공식 템플릿·Pandoc·Word·글꼴·외부 URL·raw HTML/TeX 자산을 수집하거나 완전한 렌더링 환경을 제공한다고 약속하지 않는다. 이동 후에도 선택한 출력 방식에 필요한 같은 변환기와 공식 템플릿 등은 별도로 필요하다. Access/JORS 템플릿의 배포 범위도 변경하지 않았다.

## 구현

- `_publication_convert.py`의 `image_sources()`가 기존 Pandoc으로 Image 노드를 읽는다. 정규식으로 Markdown 문법을 재구현하지 않았다. 실제 Word 변환과 동일한 `markdown-smart-raw_tex-raw_html` reader 상수를 공유한다.
- 기본 그림 기준은 원고의 부모 폴더이며 `--resource-dir`이 있으면 그 디렉터리만 사용한다. 이 선택은 [Pandoc resource-path 동작](https://pandoc.org/MANUAL.html#option--resource-path)과 일치한다.
- 일반·참조형 그림을 수집하고 URL 인코딩은 한 번만 해석한다. 같은 그림의 반복 참조와 `./` 표기는 같은 보존 파일로 모은다. 코드 예제와 참조되지 않은 파일은 복사하지 않는다.
- 원고 바이트와 그림 파일명·상대경로는 다시 쓰지 않는다. 새 출력에 exclusive create로 복사하고, `convert_docx()`가 그 보존된 원고와 그림을 사용한다.
- 원본과 복사본의 이미지 바이트를 변환 후 다시 대조하고 기존 manifest에 그림 해시를 포함한다. 원고·저자·템플릿의 기존 변경 검사도 유지한다.
- 누락/비파일/빈 그림, 경로 이탈, symlink/junction, 외부 URL·절대경로, 생성 파일과의 충돌, 대소문자를 무시했을 때의 파일·디렉터리 충돌을 거부한다. 손상 raster는 기존 실제 embedded-image 검사에서 거부한다.
- Windows에서 같은 이름으로 보존할 수 없는 문자·장치 이름·끝의 점/공백도 명확히 거부한다. 이름을 바꾸는 fallback은 없다. [Microsoft의 파일명 규칙](https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file)을 확인했다. Python 3.11 지원 범위를 유지하며 제거된 `PurePath.is_reserved()` API나 새 의존성을 추가하지 않았다.

## 실패 재현에서 통과까지

### 처음 재현한 누락

새 `tests/test_export_media.py`의 첫 32개 경우를 구현 전 `91ecd79`에서 실제 Pandoc 3.9로 실행했다.

```text
28 failed, 4 passed in 14.02s
```

일반·참조형 그림과 공백·한글·괄호·URL 인코딩을 사용하는 원고는 원래 폴더에서 DOCX 생성에 성공했다. 출력 폴더를 이동하고 임시 원본 폴더를 삭제한 뒤 보존된 원고로 다시 export하면 그림 누락으로 실패했다. 기본 이미지 경로와 별도의 `--resource-dir` 경로 모두 재현했다.

4개 이미 통과한 경우는 기존의 누락 파일·디렉터리·빈 파일·손상 PNG 거부였다. 이를 새로 발견한 회귀로 오인하지 않고 기존 보호 조건으로 유지했다. 새 누락 진단은 `figure.png`처럼 실패한 원래 경로를 포함한다.

첫 수정 후에는 실제 `%20`을 포함하는 파일명을 `%2520`으로 참조하는 경우까지 포함해 **33 passed**였다.

### 경계 재점검과 추가 수정

재점검에서 Linux의 `plot?.png`, `CON.png`, `figures./plot.png`가 실제 export와 manifest 생성을 통과하는 것을 확인했다. Windows에 같은 경로를 보존할 수 없는 파일명이므로 해당 검사를 추가했다. 추가 경계 테스트의 수정 전 결과는 다음과 같다.

```text
6 failed, 1 passed, 33 deselected
```

실패 6개는 인코딩된 `?`·`*`, 예약 장치 이름, 끝의 점·공백이었다. 정상적인 `#` 파일명을 `%23`으로 참조하는 이동·재변환은 통과했다. 거부는 파일 조회와 변환 전에 이루어지며 오류 이유를 명시한다. 이 보완 후 그림 테스트 **40 passed**였다.

### 제출 묶음과의 연결

마지막으로 한 개의 통합 회귀를 추가했다.

1. 한글·공백·괄호가 있는 참조형 그림으로 실제 DOCX export.
2. `manuscript.md`, `editable_docx`, 그림 파일 세 개만 명시해 실제 `prepare_bundle()` 실행.
3. 묶음을 이동하고 임시 원본 및 중간 export 폴더 삭제.
4. `files/manuscript.md`에서 원래 `--resource-dir` 없이 다시 실제 DOCX export.

명시한 파일만 보존되고, 원고·그림·기존 DOCX 바이트 및 manifest 해시가 유지되며 새 DOCX에 같은 그림이 삽입되는 것을 확인했다. 사람 확인과 투고 준비 상태는 미완료로 남는다. 해당 통합 회귀는 **1 passed**였다.

## 최종 검증 결과

| 검사 | 결과 | 범위 |
| --- | --- | --- |
| 첫 회차 기준 전체 결과 | **515 passed, 69 subtests passed** | 이전 로그와 커밋 보존 |
| 이번 전체 pytest | **558 passed, 69 subtests passed** | 40.66초, 실패·skip 없음 |
| 새 그림 회귀 | **41개 전체 suite에 포함되어 통과** | 이동·재변환, 경로·파일명·변경 감지, native 대역, 묶음 연결 |
| 기존 원고 변경 감지 | **통과** | 원본/보존본 × native/docx-only 네 경우로 확장 |
| 기존 export/JOSS/bundle 소비 경로 | **167 passed** | 별도 집중 실행, 이후 전체 회귀에도 포함 |
| 스크립트 컴파일 | **통과** | `python -m compileall -q scripts` |
| 변경분 검사 | **통과** | working/staged `git diff --check` |
| CI와 같은 스킬 ZIP 구성 | **통과** | 41개 설치 파일, 검증한 작업 파일과 payload 바이트 일치 |
| 독립 ZIP의 실제 CLI export | **통과** | 원래 checkout을 import하지 않고 실제 Pandoc/DOCX 사용 |
| 독립 ZIP의 이동·원본 삭제 후 재export | **통과** | 한글·공백 참조형 그림, 정확한 바이트·manifest·embedded image 확인 |
| 실제 Windows/Python 3.11 CI | **미실행** | 원격 게시하지 않음 |
| 실제 Microsoft Word/PDF 렌더링·페이지 육안 확인 | **미실행** | Linux 환경; native 분기의 Word/PDF/compliance는 명시한 테스트 대역 |
| JOSS 공식 Inara/PDF | **미실행** | 별도 소스 검사 문제의 재현만 수행 |

최종 환경은 Linux, Python 3.12.14, Pandoc 3.9, pytest 9.2.0이다. 기존 가상환경과 저장소 의존성 목록을 사용했다. `CI=true`로 실제 Pandoc 검사를 필수화했고 무관한 pytest 플러그인 자동 로딩을 껐다.

### 재실행

프로젝트 의존성과 pytest가 설치된 Python으로 저장소 루트에서 실행한다.

```bash
PF_PANDOC_DIR="$(python -c 'from pathlib import Path; import pypandoc; print(Path(pypandoc.__file__).resolve().parent / "files")')"
export PATH="$PF_PANDOC_DIR:$PATH"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
export CI=true
python -m pytest -q tests/test_export_media.py tests/test_skill_export.py
python -m compileall -q scripts
python -m pytest -q
git diff --check
```

이전 출력과 로그를 지우지 않았다. 이번 실패·성공 로그와 패키징 결과는 별도 `paper-factory-verification/round2/`에 보관했다. 첫 회차 패치와 ZIP은 기존 handoff SHA-256과 일치하고, 이전 검증 문서도 `91ecd79`의 바이트와 일치한다.

## 재점검에서 확인한 다음 실제 문제

**JOSS의 YAML metadata Image가 소스 수집에서 누락된다.** `_publication_joss.py`는 이미지 탐지 시 `document["blocks"]`만 순회한다. 정상 JOSS 원고의 제목을 다음처럼 하고 이미지 파일을 만들지 않은 상태에서 Pandoc 3.9로 재현했다.

```yaml
title: 'Research tool ![Logo](missing-logo.png)'
```

전체 Pandoc AST와 metadata에는 `missing-logo.png` Image가 존재하지만 결과는 다음과 같다.

```text
input_image_exists: false
metadata_image_targets: [missing-logo.png]
body_image_targets: []
preflight_passed: true
reported_image_count: 0
source_package_passed: true
retained_image_exists: false
```

이것은 소스 패키지 검사의 탐지 누락이며 실제 Inara/PDF 실패를 확인한 결과는 아니다. JOSS metadata에서 그림을 허용해 수집할지, 지원하지 않는 metadata로 명확히 거부할지를 현재 계약에 맞춰 정해야 한다. 이번 Word 경로의 범위를 넓혀 임의로 바꾸지 않았다. JOSS 구현과 테스트 파일은 그대로 유지했다.

재현 스크립트 `probe_joss_metadata_image.py`와 결과 `joss-metadata-image-pandoc39.json`을 이번 검증 폴더에 보존했다. 스크립트는 지정한 checkout과 Pandoc 3.9를 사용하고 새 결과 경로만 허용하며 입력·출력 자료는 임시 디렉터리에 생성한다. 원자료·원격 리소스를 변경하지 않는다.

## 변경 파일과 인계

- 구현: `scripts/_publication_convert.py`, `scripts/export_manuscript.py`
- 회귀: `tests/test_export_media.py`, `tests/test_skill_export.py`
- 현재 계약 설명: `README.md`, `references/tools.md`, `references/researcher-convenience.md`
- 이번 결과 기록: 이 문서

첫 회차 커밋을 다시 쓰지 않고 후속 로컬 커밋을 작성한다. 이번 회차 증분 패치, PR #2의 `659fa81` 이후 두 회차를 합친 누적 패치, 검증한 스킬 ZIP은 새 파일명으로 보존한다. 다음 작업은 원격 main/PR 상태를 다시 확인하고 이 후속 커밋에서 이어가면 된다. 원격 작업에 대한 승인은 아직 없다.
