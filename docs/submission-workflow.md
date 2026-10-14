# IEEE 매체 투고 흐름

원고 생산 이후 앱에서 한 학술지를 선택하고, 실제 저자 정보가 포함된 제출 파일을 준비·확인해 공식 포털로 이어간다. 연구 원자료·채택 분석·과학 본문·독립 심사·모델 요청 횟수는 이 과정에서 변경하지 않는다.

## 파일 준비와 최종 확인

1. IEEE Software와 IEEE Security & Privacy 대안 중 한 곳을 선택한다. 현재 분석과 원고·독립 심사가 통과하고, 현재 저자 정보가 들어간 Word·PDF가 있어야 한다.
2. 저자가 영문 약력·키워드·지원 및 이해관계 선언을 입력한다. Software 저자 사진도 선택한다. 앱은 기존 Markdown의 모든 바이트를 복원할 수 있는 방식으로 키워드와 약력만 추가하고 **새 제출용 Word·PDF**를 생성한다. 기존 심사 본문과 파일은 보존한다.
3. 저자는 이 새 파일의 실제 Word 단어 수·전체 페이지·표·그림 수를 확인한다. 원고 변경 전의 검수 결과를 새 파일에 적용하지 않는다. 앱은 실제 Word XML의 표·그림 수, 초록·참고문헌과 현재 투고 분량을 점검한다. S&P는 전체 단어 수에 표·그림당 250단어를 더한다. Software는 참고문헌·약력을 포함한 전체 Word 단어 수와 시각 자료 환산을 사용해 상한을 보수적으로 확인한다.
4. 신원과 저자 정보, 모든 저자의 원고·투고 승인, 독창성·동시 심사 없음, 사용 권리·허가, AI 사용 공시, 최신 학술지·포털 요건, 새 파일 전체 페이지를 저자가 명시적으로 확인한다. 체크박스는 모두 미확인 상태로 시작한다. 지원·이해관계가 미정인 상태에서는 최종 묶음을 만들지 않는다.
5. 앱이 정확한 새 파일·현재 저자·원고·심사와 최종 확인에 결속한 ZIP, manifest, 투고 편지와 포털 입력 정보를 만든다. 파일 생성만 마친 상태는 `awaiting_file_check`, 확인을 마친 묶음은 `prepared`다. 정보나 원고가 달라지면 기존 묶음은 `stale`이 되며 이전 기록은 유지한다.

같은 연구의 활성 투고처는 한 곳이다. 포털 제출을 기록한 뒤에는 철회 또는 불채택을 명시적으로 기록하기 전까지 다른 곳의 새 투고를 준비하지 않는다. 제출 후 원고가 바뀌더라도 접수 기록은 제출 당시 파일에 연결한 채 유지한다.

## 공식 포털과 접수 기록

공식 CFP가 연결하는 투고 경로는 [IEEE Software Author Portal](https://ieee.atyponrex.com/journal/sw-cs)과 [IEEE Security & Privacy Author Portal](https://ieee.atyponrex.com/journal/sp-cs)이다. 2026-10-15 확인에서 각각 IEEE Research Exchange의 `siteName=sw-cs`, `sp-cs` 대시보드로 이동했다. 일반 안내의 과거 ScholarOne 링크 대신 해당 매체의 현재 링크를 사용한다.

앱의 **공식 안내**·**공식 투고 사이트** 버튼은 이 고정 주소만 연다. IEEE 계정 로그인과 실제 원고 유형·업로드 파일·포털 질문의 확인은 공식 사이트에서 진행한다. 앱의 연구 모델 계정과 IEEE 계정은 별개이며 IEEE 인증 정보는 앱이 수집하지 않는다. 투고 편지는 앱이 준비하는 보조 문서이며 모든 투고에 필수라고 단정하지 않는다.

저자는 포털에 제출 파일을 올리고 최종 제출을 완료한 뒤, 발급된 접수번호와 실제 제출 시각을 앱에 기록한다. 앱에서 `submitted`는 **사용자 확인 접수 기록**이며 출판사가 접수를 검증했거나 논문을 채택했다는 뜻이 아니다. 포털을 열거나 파일을 저장하는 동작으로 접수 상태를 만들지 않는다. 철회·불채택도 명시적인 사용자 기록으로 남긴다. 앱은 포털에 자동 업로드하거나 최종 제출 버튼을 누르지 않는다.

## 공식 요건의 확인 범위

[Computer Society 저자 안내](https://www.computer.org/publications/author-resources)는 키워드·소속·저자 약력을 포함한 완전한 원고와 필요한 보충자료를 안내한다. [Software 일반 CFP](https://www.computer.org/digital-library/magazines/so/cfp-ieee-software)는 실무 시사점 3개와 저자 사진을 명시한다. S&P 사진 필수 여부와 로그인 이후의 정확한 업로드 명칭·원고 유형·지원/이해관계 질문은 현재 공개 자료로 확인하지 못했으므로 저자가 포털에서 확인한다.

[IEEE 저자 윤리](https://journals.ieeeauthorcenter.ieee.org/become-an-ieee-journal-author/publishing-ethics/ethical-requirements/)와 [투고·심사 정책](https://journals.ieeeauthorcenter.ieee.org/become-an-ieee-journal-author/publishing-ethics/guidelines-and-policies/submission-and-peer-review-policies/)에 따른 저자 승인·권리·동시 심사·실제 AI 사용 공시를 확인한다. 저작권 양식 작성은 게재 승인 후 절차와 구분한다. 모델이나 앱의 내용 PASS가 이 사람의 확인을 대신하지 않는다.

준비·검수 확인·접수 기록은 별도 네이티브 제출 모듈에 보존하며 새 모델 요청을 만들지 않는다. 원고 생성 경로와 제출 행정 경로를 분리해 기존 과학적 판정과 횟수를 유지한다.
