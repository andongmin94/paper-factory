# 같은 연구의 실제 보완 자료

기존 원문·분석·원고·심사와 사용 횟수를 유지하면서, 매체별 2차 심사가 요구한 실제 비교 자료를 추가하는 경로다. 현재 대상은 IEEE Software와 IEEE Security & Privacy다. 보완 자료 등록은 문헌 수집이나 공통 분석 재실행이 아니다. 네트워크 수집·모델 호출·코드 실행 없이 입력 bytes를 보존하며, 기존 내용 평가나 승인도 변경하지 않는다.

## 앱에서 사용하기

결과 화면의 **실제 보완 연구자료 패키지**에 JSON 파일을 선택한다. 패키지는 `value` manifest와 `files` 원문을 함께 담는다. 원문은 1–32개이며 일반 텍스트는 파일마다 128 KiB, 정확한 GitHub commit·전체 소스 경로·SHA에 결속된 `case_source`는 파일마다 256 KiB, 텍스트 합계는 512 KiB다. 여러 파일에 걸친 실제 비교 구현과 완전한 선행 본문·proof를 함께 보존하기 위한 한도다. 정확한 공식 출판사 원 증명에 결속된 raw PDF만 별도로 합계 1 MiB까지 지원하며 전체 IPC 요청은 기존 2 MiB 한도를 따른다. 큰 자료를 잘라서 전체 원문으로 표시하거나 PDF를 텍스트 파일로 이름만 바꿔 가져올 수 없다.

등록 가능 조건은 현재 공통 분석·문헌 SHA, 실제 부정적인 2차 원고·심사 SHA, 남은 3차 작성·심사 예산, 다른 미완료 요청이 없는 상태다. 등록을 완료한 뒤 필요한 매체별 미완료 투고본을 재개하면 새 원문과 전체 등록 영수증이 해당 원고 작성·독립 심사에 전달된다. 기존 문헌·공통 분석 사용 수와 PDF 예약·모델 요청은 그대로 유지한다. 남은 횟수를 늘리지 않는다.

등록은 1회다. 구조·입력 SHA·literal 인용 오류는 예약 전에 거부한다. 원 파일을 보존하기 시작한 뒤 primary proof 검증 또는 저장이 실패하면 실패·원 bytes·사용 횟수를 보존한다. 완료한 동일 입력의 native 재확인은 덮어쓰지 않는다. 실패·중단 뒤 새로운 자료를 같은 슬롯에 덮어쓸 수 없다.

## 입력 계약

`value`는 다음 정보를 담는다. 정확한 필드와 제한은 [repository_supplement.py](../src/paper_factory/autonomous/repository_supplement.py)를 따른다.

- `prior_analysis_sha256`, `prior_literature_sha256`: 현재 공통 근거의 해시.
- `reviews`: 관련 학술지의 `venue_id`, `draft_artifact_id`, `draft_sha256`, `review_artifact_id`, `review_sha256`.
- `members`: 원 파일의 `name`, `sha256`, `size`, 원 primary proof가 필요할 때 `original_path`.
- `materials`: 실제 과학 근거의 `id`, `kind`, `name`, `sha256`, `title`, `url`, `provenance`와 유형별 출처 정보.
- `selection`: 선정 이유 `rationale`과 동일 저자·공유 구현·원 획득 기록 등을 밝히는 `lineage`.
- `comparison`: 수행한 정적 비교의 `protocol`, 원문 literal `witnesses`, 그 근거에 연결한 `results`와 각 `limitations`. `provenance`는 `supplied_interpretation`이다.

`files`는 각 member의 원 bytes를 `{name, contentBase64}`로 담는다. canonical Base64, 전체 크기·SHA와 manifest가 정확히 일치해야 한다. 일반 과학 본문과 identity JSON은 완전한 UTF-8이어야 한다. 원 수집 proof에 바인딩된 raw HTML은 원 인코딩과 bytes를 그대로 유지하며 기존 scholarly HTML verifier가 다시 확인한다.

자료 유형은 다음과 같다.

| 유형 | 보존하는 근거 | 인용 경로 |
|---|---|---|
| `case_source` | 별도 GitHub 사례의 정확한 URL·소스 경로·40자리 commit과 전체 파일 | `document_evidence` |
| `requirement` | 실제 문서에 선언된 요구와 출처 | `document_evidence` |
| `primary_body` | 보존한 완전한 scholarly HTML 또는 공식 출판사 PDF 본문과 원 identity/discovery/raw/metadata proof | `literature_evidence` |
| `supplied_result` | 제공한 분석 결과와 한계 | `document_evidence` |

해석·프로토콜 문서만으로 등록하거나 기존 Frontron bytes를 새 사례로 다시 등록할 수 없다. 모든 과학 자료에는 실제 literal witness와 그에 연결한 제한된 비교 결과가 있어야 한다. 제안한 정책은 소스에 선언된 요구나 관측한 실행 결과와 구분해야 한다. 별도 사례는 그 사례의 URL·경로·commit으로 인용하며 Frontron의 소스로 렌더하지 않는다.

공식 출판사 PDF는 원 `repository_copy` source와 `publisher_public_pdf` identity, 정확한 단일 `pdf_hint_attempts`, 서로 다른 원 파일 5개를 유지한다. 원 raw PDF에서 전체 페이지 텍스트를 다시 추출해 보존된 완전본문과 비교하고 기존 출판사 메타데이터·첫 페이지 identity·body range를 재검증한다. 일반 PDF 업로드, arXiv·저자 복사본의 새 입고나 출처 증명이 없는 추출 텍스트는 이 경로의 대상이 아니다. 과거 별도 preflight에서 보존한 출판사 자료는 제공한 복사본이며, 다른 실제 연구의 native 문헌 등록으로 표시하지 않는다. 입고는 현재 문헌 수집·PDF 예약을 늘리거나 과거 실패를 지우지 않는다.

## 평가와 보존

원 manifest는 동결된 intent에 한 번 보관한다. receipt는 intent SHA와 실제 등록 상태·근거·비교를 보존하며, 원 intent 및 원 심사·원고·등록 metadata를 해시 검증해 읽는다. 여러 심사 본문이나 전체 manifest를 receipt에 중복 복제하지 않는다. 집필·심사에는 전체 receipt와 모든 과학 본문, 해당 원고의 전체 Markdown과 전체 직전 심사를 전달한다. Markdown은 structured 원고 객체와 중복 전달하지 않으며 artifact ID·SHA·전체 페이지·EOF로 원 출력에 결속한다.

모델은 정확히 바인딩된 receipt와 과학 본문의 SHA·전체 페이지·EOF를 모두 읽어야 한다. 3차 원고는 실제 새 primary body 또는 사례 소스를 인용해야 한다. 최종 모델 요청은 일반 단계·다른 모델의 기존 700k 문자 한도를 유지한다. 정확히 등록된 보완 자료 SHA와 native 학술지별 집필·심사·누락 구간 보완 binding이 결속된 `gpt-6.1-sol` 요청만 전체 UTF-8 900,000 bytes를 허용한다. [공식 모델 규격](https://developers.openai.com/api/docs/models/gpt-6.1-sol)의 1,050,000 token 문맥에서 최대 출력 128,000과 별도 framing 여유 22,000을 예약한 보수적인 bytes 기준이며 실제 token count나 계정별 문맥 조회가 아니다. 완성된 요청이 한도를 넘으면 UUID·예약·SDK 호출 전에 거부하고 근거를 생략하지 않는다. 모델·집필·심사 횟수는 변경하지 않는다.

입고 성공은 원 bytes와 출처 계약 확인이다. 의미 있는 기여, 외부 사례의 대표성, 사람 검증, 코드 실행, 현재 심사의 지적 해결이나 투고 권고를 자동 확인하지 않는다. 새 원고와 독립 심사가 실제 내용을 평가한다. 같은 저자의 다른 프로젝트는 별도 사례가 될 수 있으나 독립적인 검증자가 평가한 연구로 표시할 수 없다.

보완 자료 등록 자체로 준비도가 통과하지 않는다. 기존 부정 심사와 출력 보완 결과를 각각 보존하고, 새 원고·출력·독립 심사의 결과로 현재 상태를 판단한다. 현재 Frontron의 두 매체 원고는 2차 내용 평가를 완료했으므로 이 기능을 실행할 보완 요구가 없다. 실제 상태는 [현재 검증 기록](standalone-verification.md)을 따른다.
