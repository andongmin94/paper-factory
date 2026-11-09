# 도구 연결과 판정 오류 개선 검증

2026-11-09. 최신 `main`과 열린 PR을 대조한 뒤, PR #2에도 남아 있는 세 문제를 실패하는 회귀 테스트로 재현하고 수정했다. 이 문서의 결과는 로컬 구현과 검증이다.

## 기준 상태와 중복 방지

| 구분 | 확인한 상태 |
| --- | --- |
| 원격 `main` | `1aff3b7d1df45c2d7b9505c4d1be1761ba08b030` |
| 유일한 열린 PR | Draft [#2](https://github.com/andongmin94/paper-factory/pull/2), `feat/claude-skill` → `main` |
| PR 기준 커밋 | `659fa818fab67fae2259d758c4472e423fa157ed` |
| 로컬 작업 브랜치 | `fix/verified-tool-handoff`, 위 PR 커밋에서 분기한 별도 worktree |
| 개발 지침 | 두 커밋의 추적 파일과 로컬 상위 경로에서 `AGENTS.md`를 찾지 못했다. 사용자가 제공한 단순한 구현, 모듈 분리, 기존 의존성 활용, 호환 계층 금지 지침을 적용했다 |

마지막 원격 조회에서도 위 SHA와 유일한 열린 PR 상태가 같았다. 원격 브랜치 게시, PR 작성/수정, 병합, 배포, 릴리스, 계정·권한·보안 설정 변경은 수행하지 않았다. `main` worktree는 변경 없이 유지했다.

이전 분석에서 지적한 Markdown/DOCX 근거 해시 역할 불일치와 묶음·범위 인용의 DOCX 변환 문제는 PR #2에 이미 수정되어 있었다. 해당 구현을 다시 작성하지 않았다. 이번 변경은 PR #2에 추가되는 수정이며 아직 `main`에 포함된 결과가 아니다.

## 1. 인용 검사 결과를 출판 판정에 연결

**재현한 사실:** 문헌 목록이 1–3번일 때 `[1, 4]` 같은 미정의 인용이 PR 기준 코드의 preflight를 통과했다. `[1–999999999]`, `[3-1]`, `[1,,2]` 같은 검사할 수 없는 숫자 그룹도 명확한 실패로 처리되지 않았다. 실제 Pandoc/DOCX를 사용하는 compliance 경로에서도 누락 인용이 성공으로 남았다. 이때 Word 계수와 PDF 래스터화만 테스트 대역으로 공급했으므로 실제 Word/PDF 품질을 검증한 결과는 아니다.

**수정:** 기존 `editorial_checks.check_manuscript()` 결과 중 `citation_without_reference`와 새 `invalid_numeric_citation`만 `citation_references` 필수 검사에 연결했다. 형식이 잘못된 그룹, 역순 범위, 기존의 제한인 1,001개 항목을 초과하는 범위는 조용히 무시하지 않고 실패한다. 강조된 숫자와 한 문단 안의 줄바꿈도 검사한다. 숫자 사이의 `*`나 `_`를 제거해 다른 번호로 합치는 일은 허용하지 않는다.

정상 인용, 코드 예제, Markdown 링크 및 링크 정의, References 뒤의 부록을 각각 검증했다. 다른 편집 제안은 새 필수 검사로 승격하지 않았다. preflight 자체에 Pandoc 의존성을 추가하지 않았고 입력 원고를 변경하지 않는다. 독립 설치본 테스트에는 새로 직접 사용되는 기존 `editorial_checks.py`를 포함했다.

초기 회귀 선택 실행은 **18 failed, 2 passed**였다. 후속 강조·줄바꿈 검증은 첫 수정에서 남은 실패 **14개**를 발견했고 추가 수정했다. 최종 관련 네 모듈 실행은 **171 passed**였다.

## 2. 원자료 해시가 같아도 인용문과 줄 범위를 재검사

**재현한 사실:** `research_workspace.py impact`는 원자료 해시와 이전 성공 표시가 같으면 이전 보고서의 인용문을 실제 원자료와 다시 비교하지 않았다. 원자료를 그대로 둔 채 이전 보고서의 인용문 또는 줄 범위만 잘못 바꾸어도 재사용 가능한 연결로 표시했다.

**수정:** 이미 읽어 캐시한 원자료 바이트에 각 인용문과 줄 범위를 항상 대조한다. 변경·누락 파일, 이전 미검증 상태, 새 질문의 명시적 선택, 처리 종료 시 입력 재해시 검사는 유지했다. 이 검사는 제공된 근거 기록의 내부 일관성을 확인하며 출처의 진위나 과학적 타당성을 인증하지 않는다.

잘못된 인용문, 시작 줄, 끝 줄, 파일 밖의 끝 줄을 각각 재현했다. 변경 전 **4 failed**, 수정 후 해당 모듈 **49 passed**였다. 같은 파일을 사용하는 정상 주장과 다른 파일의 정상 주장은 계속 재사용 대상으로 남으며 원자료와 이전 보고서 바이트는 유지된다.

## 3. 저장소 캡처에서 호출자의 Git 저장소 경로 분리

**재현한 사실:** 별도 임시 Git 저장소를 가리키는 `GIT_DIR` 환경을 상속하면, 고정 커밋 캡처가 해당 저장소의 `.git`에 fetch 산출물을 기록했다. 실제 로컬 Git 저장소 두 개와 URL 치환을 사용해 외부 네트워크 없이 재현했다.

**수정:** 캡처 하위 프로세스에 전달하는 환경 복사본에서 저장소 경로와 문맥을 지정하는 Git 변수만 제거했다. 부모 프로세스 환경과 전역 Git 설정은 수정하지 않는다. 인증, proxy, CA, `GIT_CONFIG_*` 전달은 유지한다.

초기 회귀는 **1 failed**였다. 최종 테스트는 고정 커밋/tag와 단일 `GIT_DIR`/여러 경로 변수의 네 조합을 검사한다. 다른 저장소의 작업 파일과 `.git` 전체 바이트, 부모 환경, 전달해야 하는 인증·통신 설정이 유지됨을 확인했다. 해당 모듈은 **25 passed**였다.

## 검증 결과

| 검증 | 결과 | 조건과 한계 |
| --- | --- | --- |
| 수정 전 `main` 전체 테스트 | **365 passed, 63 subtests passed** | 별도 worktree, Pandoc 3.1.11.1 |
| 수정 전 PR #2 전체 테스트 | **470 passed, 69 subtests passed** | 별도 worktree, Pandoc 3.1.11.1 |
| 최종 전체 테스트 | **515 passed, 69 subtests passed** | Python 3.12.14, Pandoc 3.9, `CI=true`; 실패/skip 없음 |
| standalone 스크립트 컴파일 | **통과** | `python -m compileall -q scripts` |
| 변경분 공백·패치 검사 | **통과** | `git diff --check` 및 staged diff 검사 |
| CI와 같은 파일 선택으로 ZIP 구성 | **통과** | 스테이징된 코드 트리의 41개 파일; 작업 파일과 압축 내부 바이트 모두 일치 |
| 압축 해제 후 독립 preflight 실행 | **통과** | 정상 원고 exit 0, 미정의 인용 원고 exit 1; `citation_references` 결과와 입력 보존 확인 |
| 실제 Word 자동화와 PDF 렌더링·페이지 육안 확인 | **미실행** | Linux 환경에 Microsoft Word가 없음 |
| 이번 변경의 원격 Windows CI | **미실행** | 아직 원격에 게시하지 않음 |
| 외부 저널 서비스, Inara 전체 렌더링, 실제 투고 | **미실행** | 이번 세 수정의 로컬 검증 범위 밖 |

최종 전체 실행은 17.16초였다. pytest 9.2.0, python-docx 1.2.0, Pillow 12.3.0, pypdfium2 5.14.0, pypandoc_binary 1.17, pyparsing 3.3.2를 사용했다. 저장소의 의존성 목록은 변경하지 않았다. 최종 실행에서는 환경의 무관한 pytest 플러그인 자동 로딩을 껐다.

워크플로 파일 `.github/workflows/skill.yml`의 컴파일, 실제 Pandoc 식별, pytest, 스킬 ZIP 구성 단계를 로컬에서 확인했다. 원격 워크플로의 Windows/Python 3.11 환경과 이 로컬 Linux/Python 3.12 환경은 다르다. 기존 PR의 [Windows CI 실행](https://github.com/andongmin94/paper-factory/actions/runs/42571671925)은 이 수정 전 커밋의 결과이므로 이번 변경의 원격 통과 근거로 사용하지 않는다.

### 재실행 명령

저장소 루트에서 설치된 프로젝트 의존성과 pytest를 갖춘 Python을 사용한다. 이번 검증에서는 별도 가상환경을 사용했다. 아래 Pandoc 경로 설정은 셸 프로세스에만 적용한다.

```bash
PF_PANDOC_DIR="$(python -c 'from pathlib import Path; import pypandoc; print(Path(pypandoc.__file__).resolve().parent / "files")')"
export PATH="$PF_PANDOC_DIR:$PATH"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
export CI=true
python -c "import sys; sys.path.insert(0, 'scripts'); from _publication_convert import pandoc_binary, pandoc_version; print(pandoc_version(pandoc_binary()))"
python -m compileall -q scripts
python -m pytest -q
git diff --check
```

세 변경의 집중 회귀를 실행하려면 다음 모듈을 선택한다. 전체 실행에는 이 모듈들도 포함된다.

```bash
python -m pytest -q tests/test_editorial_checks.py tests/test_skill_export.py tests/test_publication_content.py tests/test_venue_selection.py
python -m pytest -q tests/test_research_workspace.py tests/test_repository_snapshot.py
```

ZIP 검증은 CI와 동일하게 `SKILL.md LICENSE requirements.txt scripts references assets`만 `git archive`에 전달하고, 압축 내부 파일을 원본 바이트와 대조했다. 새 디렉터리에 압축을 해제한 다음 `scripts/export_manuscript.py preflight`를 정상 원고와 `[999]`를 넣은 원고에 각각 실행했다. 원본 checkout의 스크립트를 import하도록 추가하지 않았다.

## 도구 사이의 연결 재점검

- `editorial_checks` → `validate_manuscript` → CLI preflight → compliance: 미정의·잘못된 숫자 인용 실패가 소비 단계까지 도달한다. 실제 Pandoc/DOCX를 쓰는 compliance 회귀가 포함되며, Word 계수/PDF 래스터화 대역은 테스트에 명시되어 있다.
- `research_workspace.evidence` → `impact`: 실제 생성된 근거 기록을 사용한다. 잘못된 인용 기록만 재검토 대상이 되고 정상 연결은 유지된다.
- 저장소 캡처 → 고정 커밋/태그 → 보존 source: 실제 로컬 Git 객체로 캡처하며 호출자의 다른 저장소에 기록하지 않는다.
- `research_workspace.evidence` → `submission_support.prepare_bundle` → `finalize_submission.check`: PR #2에 있던 통합 회귀도 전체 테스트에서 통과했다. 이 테스트는 근거와 묶음을 실제 도구로 생성하지만 Word/PDF 및 사람 확인은 합성 기록이다. 실제 투고나 사람 승인으로 해석하지 않는다.
- ZIP → 독립 설치본 preflight: 새 기존 모듈 의존성이 패키지에 포함되고 원래 checkout 없이도 검사한다.

## 남은 문제와 다음 후보

### 우선 후보: 내보낸 원고를 재변환할 때 필요한 그림 원본

**추가 재현에서 확인한 사실:** `figures/diagram.png`를 상대 경로로 참조하는 유효한 원고를 `docx_only=True`로 내보내면 DOCX 생성은 성공한다. 출력 폴더를 다른 위치로 옮기고 원래 임시 원고 폴더를 제거하면, 복사된 `manuscript.md`를 다시 DOCX로 변환할 때 그림을 찾지 못해 Pandoc이 실패한다. 사용한 Pandoc은 3.9다.

```text
initial_docx_created: true
media_retained: false
rebuild: failed
Could not fetch resource figures/diagram.png: replacing image with description
Failing because there were warnings.
```

이것은 모든 DOCX 내보내기의 실패나 명시적으로 그림을 포함한 제출 묶음의 실패를 뜻하지 않는다. 확인한 범위는 **원고와 그림이 있는 원래 폴더 없이 내보내기 출력만으로 재변환하는 경우**다. 다음 회차에는 export 출력과 제출 묶음의 책임을 먼저 비교한 뒤, 참조하는 원본 자료의 포함 여부와 누락 진단을 재현 가능한 이동·재변환 테스트로 정의하는 것이 좋다. 이번 회차에서는 이 경로를 변경하지 않았다.

### 남은 검증

원격 게시 승인을 받은 뒤 변경 커밋을 대상으로 Windows/Python 3.11 CI를 확인해야 한다. 실제 Word→PDF 출력과 전 페이지 확인은 Word가 있는 환경에서 별도 수행해야 한다. 현재 통과한 합성 기록·테스트 대역을 그 검증의 대체물로 간주하지 않는다.

## 변경 파일

- 구현: `scripts/_publication_checks.py`, `scripts/editorial_checks.py`, `scripts/research_workspace.py`, `scripts/_repository_snapshot.py`
- 회귀: `tests/test_editorial_checks.py`, `tests/test_skill_export.py`, `tests/test_research_workspace.py`, `tests/test_repository_snapshot.py`
- 기록: 이 문서

새 패키지, 호환 계층, 상태 저장소, 설정 체계는 추가하지 않았다. 마지막 독립 변경 검토에서 이번 범위의 커밋을 막을 문제는 발견되지 않았다. 다음 작업은 위 PR 기준 SHA를 다시 확인한 뒤 이 로컬 브랜치의 변경만 이어받아야 한다.
