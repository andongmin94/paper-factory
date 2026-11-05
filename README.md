# Paper Factory

GitHub 저장소와 1차 문헌을 바탕으로 영문 논문을 작성하는 Agent Skills 형식의 스킬입니다. **Claude Code·Claude.ai·Codex에서 같은 지침과 Python 도구를 재사용**합니다. **IEEE Software, IEEE Security & Privacy, IEEE Access, Journal of Open Research Software(JORS), Journal of Open Source Software(JOSS)**를 지원합니다. 에이전트가 연구 질문 선정부터 기존 연구 비교·집필·검토까지 직접 조율하고, 파일 도구가 매체별 원고 출력과 투고 준비를 돕습니다.

## 빠른 시작

### Claude Code

개인용 스킬 디렉터리에 설치하거나, 아래 Claude.ai용 ZIP의 `paper-factory/` 폴더를 `~/.claude/skills/`에 풉니다. 한 프로젝트에서만 쓸 때는 `.claude/skills/`에 넣습니다.

```sh
git clone https://github.com/andongmin94/paper-factory.git "$HOME/.claude/skills/paper-factory"
```

Windows PowerShell에서는 `$HOME` 대신 `$env:USERPROFILE`을 사용할 수 있습니다. Claude Code에서 `/paper-factory https://github.com/owner/repository`로 호출합니다. 기존 설치본이 있으면 덮어쓰지 말고 변경 상태를 먼저 확인하세요.

### Claude.ai

코드 실행·파일 생성을 활성화한 뒤 **Customize > Skills > + > Create skill > Upload a skill**에서 `paper-factory.zip`을 업로드하고 켭니다. [Skill tools CI](https://github.com/andongmin94/paper-factory/actions/workflows/skill.yml)의 해당 커밋 실행에서 `paper-factory-skill` artifact를 받으면 안에 설치용 ZIP이 있습니다. GitHub의 바깥 artifact ZIP을 한 번 풀고 **안쪽 `paper-factory.zip`**을 업로드합니다.

ZIP에는 `paper-factory/SKILL.md`와 기존 스크립트·참조·에셋만 들어갑니다. 별도 Claude 전용 프롬프트나 API 키는 필요하지 않습니다. **업로드 형식 지원과 실제 Claude 실행 검증은 별개**이며, Word가 없는 환경에서는 원고 소스·서지·그림·checklist를 전달합니다. Pandoc과 문서 의존성이 있으면 `export --docx-only`로 편집 가능한 DOCX와 변환 기록도 만들 수 있고, Word/PDF 검증은 미완료로 남깁니다.

### Codex

기존 설치와 호출 방법은 그대로 유지합니다.

```powershell
git clone https://github.com/andongmin94/paper-factory.git "$env:USERPROFILE/.codex/skills/paper-factory"
Set-Location "$env:USERPROFILE/.codex/skills/paper-factory"
```

Codex에서는 `$paper-factory`, Claude Code에서는 `/paper-factory`를 사용합니다. Claude.ai에서는 활성화한 뒤 “paper-factory 스킬을 사용해”라고 요청하세요. 다음은 Codex 호출 예이며 본문 요청은 공통입니다.

```text
$paper-factory https://github.com/owner/repository

저장소와 관련 원문을 읽고, 현재 지원하는 매체 중 정확히 세 후보의 근거 적합성과 article type을 비교해.
한 곳을 조건부로 추천한 뒤 실제 근거로 뒷받침할 수 있는 영문 초안 한 편을 작성해.
초안 소스, 서지, 짧은 선정·근거·공식 지침 기록과 미확인 항목 checklist를 하나의 묶음으로 제공해.
평가는 단순 투고 적합성보다 원고 그대로 게재를 권고할 수 있는지를 기준으로 해.
프로젝트 코드는 실행하지 말고, 기존 자료와 횟수는 유지해.
```

기존 연구를 이어갈 때는 보존 자료의 위치와 원하는 작업을 함께 알려주면 됩니다. 필요한 명령과 입력 파일은 에이전트가 준비합니다.

## 저장소 URL에서 초안 묶음까지

에이전트가 실제 파일 트리를 확인하고 README·구현·테스트·기존 실험 자료를 읽습니다. `research_workspace.py repository`는 선택한 원본 파일과 저장소 커밋·해시를 새 작업 폴더에 보존합니다. 파일명이나 README의 설명만으로 프로젝트 분야·성능·연구소프트웨어 적격성을 판정하지 않습니다.

현재 구현된 다섯 지원 매체 안에서 **후보 세 곳을 비교하고 한 곳을 조건부 추천한 다음, 초안 한 편을 직접 작성**합니다. 정적 소스 관찰, 실제 측정, 추론과 미확인 근거를 구분하며 저널의 현재 공식 지침과 article type을 확인합니다. 기존 서지 가져오기·근거 ledger·preflight·export·bundle 경로를 이어 사용합니다. [URL에서 초안까지 실행 절차](references/repository-to-draft.md)에 명령과 최소 결과물을 정리했습니다.

저자 정보나 근거가 부족하면 이를 보완 과제로 남긴 소스 초안을 전달합니다. Word/PDF 또는 JOSS Inara 렌더링을 수행하지 못했으면 미검증으로 기록하며, 형식 검사를 통과시키기 위해 이름·결과·승인을 만들지 않습니다. 사용자 저장소 수정·코드 실행은 별도 허용 범위를 따르고, 한 사례의 초안 묶음을 전달하면 이번 작업을 마칩니다.

## 주요 기능

| 기능 | 제공 내용 |
| --- | --- |
| 연구·집필 | 저장소 분석, 연구 질문 선정, 1차 문헌 비교, 근거에 맞는 기여와 한계 정리 |
| 원고 출력 | IEEE·JORS 공식 템플릿 Word/PDF와 형식·페이지 검사, JOSS 공식 형식의 Markdown·BibTeX·그림 소스 묶음 |
| 문헌·근거 관리 | BibTeX/RIS/CSL-JSON 메타데이터 가져오기, 읽은 범위를 명시한 문헌 카드, 주장별 소스 위치·인용·해시 연결, 변경된 근거의 영향 표시 |
| 연구 이어가기 | 자료와 결정의 포터블 저장, 현재·과거 버전 현황표, 필요한 주장만 재검토, 새 PC 환경 진단 |
| 저자 정보 준비 | 공개 ORCID 조회, 재사용 가능한 공저자 프로필, 저자별 누락 정보, 익명 사본·메타데이터 점검 |
| 검토·투고 준비 | 편집 검사와 답변서, 커버레터를 포함한 파일별 확인 기록, 기존 평가·형식·페이지·저자 기록의 최종 준비 상태 연결 |

## 지원 매체와 출력 범위

| 매체 / `--venue` | 근거에 맞는 선택 기준 | 연결된 출력 |
| --- | --- | --- |
| [IEEE Software](references/ieee-software.md) / `ieee-software` | 실무자의 엔지니어링 판단·대안·교훈 | 보관된 공식 DOCX → Word PDF |
| [IEEE Security & Privacy](references/ieee-security-privacy.md) / `ieee-security-privacy` | 실질적인 보안·프라이버시 기여 | 보관된 공식 DOCX → Word PDF |
| [IEEE Access](references/ieee-access.md) / `ieee-access` | 완성된 공학 연구와 검증된 결과 | 지정한 공식 DOCX → Word PDF |
| [JORS](references/jors.md) / `jors` | 재사용 가능한 공개 연구 소프트웨어의 Software Metapaper | 지정한 공식 DOCX → Word PDF |
| [JOSS](references/joss.md) / `joss` | 실제 연구 활용과 공개 개발 이력이 있는 연구 소프트웨어 | `paper.md` + `paper.bib` + 로컬 그림 |

신규 세 매체는 2026-11-02에 공식 지침과 템플릿 원문을 확인했습니다. Access·JORS 템플릿은 재배포 허가를 확인하지 못해 포함하지 않으며, 각 매체 문서의 공식 원본을 내려받아 `--template`으로 지정합니다. 도구는 확인된 SHA-256과 일치하는 파일을 사용합니다. JOSS는 YAML·인용·서지·그림 경로를 검사해 실제 제출 소스를 보존하며, Inara PDF 렌더링은 수행하지 않습니다.

이번 확대는 저장소 기반 집필 목적과 공식 자료 접근성에 따라 세 곳으로 한정했습니다. Computer·Internet Computing·Pervasive Computing·Intelligent Systems는 매체별 공식 지침 직접 접근이 HTTP 403으로 막혀 제외했고, [JOSE는 현재 신규 투고 중단](https://jose.theoj.org/)으로 제외했습니다. 매체 지원은 특정 사용자의 투고 목표나 개별 프로젝트의 적합성을 뜻하지 않습니다.

## 결과물과 작업 원칙

- **원고와 근거:** 영문 원고, 소스·문헌의 출처와 해시, 주장과 근거의 연결, 필요한 보충자료를 남깁니다.
- **품질 평가:** 고정 점수 목표 없이 프로젝트와 1차 근거가 뒷받침하는 최선의 원고를 작성하고, **원고 그대로 게재를 권고할 수 있는지** 평가합니다. 내부 게재 권고(`accept`·`minor_revision`·`major_revision`·`reject`)와 기존 투고 적합성 판단을 구분합니다. 엄격한 목표 달성은 내부 `accept` 판단일 때만 기록하며, `minor_revision`은 준비에 가까워도 목표 미달성으로 남기고 필요한 수정을 명시합니다. 큰 수정이 필요한지는 별도 진단으로 보존합니다. 이는 실제 저널의 원패스 통과 보장이나 채택 확률 예측이 아닙니다. 독립 전체 평가는 요청당 최대 한 번이며, 불리한 결과를 바꾸기 위한 자동 반복은 하지 않습니다. 과거의 ‘투고 고려 가능’ 평가를 새 기준 통과로 바꿔 기록하지 않습니다. JOSS에서는 자동 검토를 저자 측 진단으로 제한하고 공식 심사 판정은 사람이 수행합니다. 번역을 제외한 저자–편집자·심사위원 대화의 AI 작성 제한도 따릅니다.
- **기존 연구 보존:** 원자료·원고·평가·실패·횟수를 유지하고 새 작업은 별도 폴더에 저장합니다. 프로젝트 코드 실행은 사용자 요청 범위에 따릅니다.
- **투고 준비:** 내용 평가, 형식 검사, 페이지 확인과 실제 저자 승인을 구분합니다. ORCID에 없는 사실이나 승인 여부는 실제 확인이 필요하며, 업로드·투고는 별도 요청으로 진행합니다.

## 실행 환경

| 작업 | 필요한 환경 |
| --- | --- |
| 연구·집필 | Claude 또는 Codex와 대상 저장소·문헌에 대한 접근 |
| 저장소 URL 자료 보존 | 설치된 Git과 대상 GitHub 저장소 읽기 권한; 프로젝트 코드 실행 없음 |
| 파일 도구 | Python 3.11 이상. 문서 처리 의존성은 [requirements.txt](requirements.txt) 참조 |
| DOCX 생성 (`export --docx-only`) | Pandoc, 문서 처리 의존성, 해당 공식 템플릿. Word 불필요; native Word/PDF 검증은 미완료 |
| 공식 Word/PDF 출력 | Windows, 설치된 Microsoft Word, Pandoc, 문서 처리 의존성 |
| JOSS 소스 검사·출력 | Python, Pandoc, 기존 서지 파서. Word 불필요; 공식 PDF는 별도 Inara 환경에서 검증 |

문서 출력에 필요한 패키지가 없을 때만 호스트의 관리 환경 또는 작업용 가상환경에 의존성을 설치합니다. 제공되는 런타임과 기존 도구를 먼저 확인하고, 전역 설치나 Word 설치를 자동으로 수행하지 않습니다. Claude.ai의 네트워크·설치 권한은 계정 설정에 따라 다릅니다. [호스트별 설치·실행 범위](references/runtime.md)를 확인하세요.

```powershell
python -m pip install -r requirements.txt
```

`pypandoc_binary`가 Pandoc을 제공하며, 기존 실행 파일을 직접 지정할 수도 있습니다. Microsoft Word와 출판사의 전용 글꼴은 별도로 준비해야 합니다. 환경 진단은 설치 상태를 확인하며, 실제 출력과 글꼴 대체 여부는 최종 페이지에서 검수합니다. DOCX 생성·구조 검사만 실행했으면 Word/PDF 렌더링과 시각 검수는 미검증으로 남깁니다.

## 개발과 상세 문서

```powershell
python -m pip install -r requirements.txt "pytest>=8,<10"
python -m pytest -q
```

Windows CI에서 실제 Pandoc 식별과 문서 변환을 필수로 검사합니다. 현재 변경 사항과 테스트 결과는 [커밋 이력](https://github.com/andongmin94/paper-factory/commits/main/)과 [GitHub Actions](https://github.com/andongmin94/paper-factory/actions/workflows/skill.yml)에서 확인할 수 있습니다. 누락·손상된 그림의 정상 출력 처리, 확인 도중 바뀐 근거, 과거 출력 파일의 평가 재사용과 저자 검사 누락을 방지합니다. Garak·REA의 기존 질문·기여 선택 기록과 프론트론의 공식 원고·평가·횟수는 유지합니다.

- [스킬 지침](SKILL.md)
- [Claude 설치와 실행 환경](references/runtime.md)
- [연구·평가 기준](references/research-and-review.md)
- [연구 질문과 기여 선택](references/contribution-selection.md)
- [저장소 URL에서 초안 묶음까지](references/repository-to-draft.md)
- [공식 출력·ORCID 도구](references/tools.md)
- [연구자 편의기능과 입력 형식](references/researcher-convenience.md)
- [이전 구현·검증 기록](docs/skill-refinements-verification-20261030.md)

연구 자료·저자 프로필·출력 파일은 스킬 설치 폴더 밖에 보관합니다. 로컬 연구 자료와 생성 결과는 Git에 포함하지 않습니다.

[MIT License](LICENSE)
