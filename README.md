# Paper Factory

GitHub 저장소와 1차 문헌을 바탕으로 **IEEE Software** 또는 **IEEE Security & Privacy**의 영문 논문을 작성하는 Codex 스킬입니다. 에이전트가 연구 질문 선정부터 기존 연구 비교·집필·평가까지 직접 조율하고, 파일 도구가 공식 템플릿 출력과 투고 준비를 돕습니다.

## 빠른 시작

새 PC에서는 이 저장소를 Codex의 스킬 폴더에 설치합니다.

```powershell
git clone https://github.com/andongmin94/paper-factory.git "$env:USERPROFILE/.codex/skills/paper-factory"
Set-Location "$env:USERPROFILE/.codex/skills/paper-factory"
```

Codex에서 `$paper-factory`와 대상 저장소를 지정하세요.

```text
$paper-factory https://github.com/owner/repository

저장소와 관련 원문을 읽고, 프로젝트의 근거로 뒷받침할 수 있는 가장 유용한 논문을 작성해.
적합한 IEEE 매체를 선택하고, 공식 템플릿 Word/PDF와 한 번의 독립 평가까지 제공해.
프로젝트 코드는 실행하지 말고, 기존 자료와 횟수는 유지해.
```

기존 연구를 이어갈 때는 보존 자료의 위치와 원하는 작업을 함께 알려주면 됩니다. 필요한 명령과 입력 파일은 에이전트가 준비합니다.

## 주요 기능

| 기능 | 제공 내용 |
| --- | --- |
| 연구·집필 | 저장소 분석, 연구 질문 선정, 1차 문헌 비교, 근거에 맞는 기여와 한계 정리 |
| 공식 원고 출력 | 매체별 공식 템플릿을 적용한 Word/PDF, 분량·형식 검사, 전체 페이지 확인 |
| 문헌·근거 관리 | BibTeX/RIS 메타데이터 가져오기, 읽은 범위를 명시한 문헌 카드, 주장별 소스 위치·인용·해시 연결, 변경된 근거의 영향 표시 |
| 연구 이어가기 | 자료와 결정의 포터블 저장, 현재·과거 버전 현황표, 필요한 주장만 재검토, 새 PC 환경 진단 |
| 저자 정보 준비 | 공개 ORCID 조회, 재사용 가능한 공저자 프로필, 저자별 누락 정보, 익명 사본·메타데이터 점검 |
| 검토·투고 준비 | 편집 검사와 답변서, 커버레터를 포함한 파일별 확인 기록, 기존 평가·형식·페이지·저자 기록의 최종 준비 상태 연결 |

[IEEE Software](references/ieee-software.md)는 실무자의 엔지니어링 판단과 교훈을, [IEEE Security & Privacy](references/ieee-security-privacy.md)는 실질적인 보안·프라이버시 기여를 중심으로 다룹니다. 완성된 기여에 맞는 매체를 선택합니다.

## 결과물과 작업 원칙

- **원고와 근거:** 영문 원고, 소스·문헌의 출처와 해시, 주장과 근거의 연결, 필요한 보충자료를 남깁니다.
- **품질 평가:** 고정 점수 목표 없이 프로젝트와 1차 근거가 뒷받침하는 최선의 원고, 선택한 매체에 실제 투고를 검토할 만한 기여·논리·근거를 기준으로 판단합니다. 독립 전체 평가는 요청당 최대 한 번이며, 점수는 필요할 때의 보조 지표로만 사용합니다. 점수를 높이기 위한 자동 반복은 하지 않습니다.
- **기존 연구 보존:** 원자료·원고·평가·실패·횟수를 유지하고 새 작업은 별도 폴더에 저장합니다. 프로젝트 코드 실행은 사용자 요청 범위에 따릅니다.
- **투고 준비:** 내용 평가, 형식 검사, 페이지 확인과 실제 저자 승인을 구분합니다. ORCID에 없는 사실이나 승인 여부는 실제 확인이 필요하며, 업로드·투고는 별도 요청으로 진행합니다.

## 실행 환경

| 작업 | 필요한 환경 |
| --- | --- |
| 연구·집필 | Codex와 대상 저장소·문헌에 대한 접근 |
| 파일 도구 | Python 3.11 이상. 문서 처리 의존성은 [requirements.txt](requirements.txt) 참조 |
| 공식 Word/PDF 출력 | Windows, 설치된 Microsoft Word, Pandoc, 문서 처리 의존성 |

문서 출력이 필요한 환경에서 의존성을 설치합니다. Codex에서는 제공되는 문서 런타임과 이미 설치된 도구를 먼저 확인합니다.

```powershell
python -m pip install -r requirements.txt
```

`pypandoc_binary`가 Pandoc을 제공하며, 기존 실행 파일을 직접 지정할 수도 있습니다. Microsoft Word와 출판사의 전용 글꼴은 별도로 준비해야 합니다. 환경 진단은 설치 상태를 확인하며, 실제 출력과 글꼴 대체 여부는 최종 페이지에서 검수합니다.

## 개발과 상세 문서

```powershell
python -m pip install -r requirements.txt "pytest>=8,<10"
python -m pytest -q
```

Windows CI에서 실제 Pandoc 식별과 문서 변환을 필수로 검사합니다. 최근 로컬 검증에서는 **224개 테스트**를 통과했습니다. 누락·손상된 그림의 정상 출력 처리, 확인 도중 바뀐 근거, 과거 출력 파일의 평가 재사용과 저자 검사 누락을 방지합니다. Garak·REA의 기존 질문·기여 선택 기록과 프론트론의 공식 원고·평가·횟수는 유지합니다.

- [스킬 지침](SKILL.md)
- [연구·평가 기준](references/research-and-review.md)
- [연구 질문과 기여 선택](references/contribution-selection.md)
- [공식 출력·ORCID 도구](references/tools.md)
- [연구자 편의기능과 입력 형식](references/researcher-convenience.md)
- [최신 구현·검증 기록](docs/skill-refinements-verification-20261030.md)

연구 자료·저자 프로필·출력 파일은 스킬 설치 폴더 밖에 보관합니다. 로컬 연구 자료와 생성 결과는 Git에 포함하지 않습니다.

[MIT License](LICENSE)
