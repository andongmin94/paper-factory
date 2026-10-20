# 2026-10-20 정리 전 인계 기록

이 문서는 당시 누적 기록의 보존본이다. 과거의 초기화·진행 중·투고 권고 문구를 현재 지시나 평가로 사용하지 않는다. 현재 상태는 [다음 세션](../next-session.md)과 [검증 기록](../standalone-verification.md)을 따른다. 상대 문서 링크만 이동 위치에 맞췄으며 연구 자료·횟수는 변경하지 않았다.

---

# 2026-10-20 연구 질문·가까운 방법 비교·실제 근거 확보 흐름 개선

이 항목이 최신 지시와 구현 상태다. 사용자는 연구 설계 능력을 개선하되 기존 자료·횟수를 유지하고 검증만 늘리지 말라고 요청했다. 이번에는 연구 설계 코드를 개선하고 합성 자료로 내용이 집필까지 전달되는 경로를 확인했다. **실제 Frontron의 추가 모델 요청·연구 재개·새 원고 생성·재심사는0이며, 기존 원고의 점수나 투고 권고가 개선됐다고 주장하지 않는다.** 아래2026-10-18 기록은 마지막 실제 원고 생산과 평가의 결과다.

새 연구의 기존 문헌 계획 요청은 소스에 근거한 서로 다른 질문2~3개와 가까운 기존 접근, 반박 조건, 근거 요구·검색 계획을 함께 만든다. 실제 원문 수집 뒤 공통 분석에서 원래 후보 전부를 비교하고 가장 답할 수 있는 질문을 선택한다. 기존 방법이 이미 해결하는 부분, 같은 조건에서의 실제 차이, 완료한 발견·대안 비교표·비용·반례를 집필 근거로 보존한다. 초기 질문은 수집 결과에 따라 바뀔 수 있으며, 문헌 계획과 공통 분석의 기존 모델 요청 안에서 처리한다.

새로 명시적으로 시작하는 연구 보완 회차는 contract3이다. **질문 후보→앱의 실제 가까운 원문 확보→질문 선정·비교·분석 완성→필요시 한 번 내용 강화→독립 방법 검토→두 매체 집필→독립 평가** 순서다. 모델은 기본5회·내용 강화 포함 최대6회다. 네이티브 수집은 별도 모델 요청이 아니며 최초 검색어 최대4개/후속 최대2개·각 결과 최대6개·두 수집을 합친 PDF 예약2회로 제한한다. 수집한 전문과 기존 원문을 함께 읽어 빈 비교를 채우고 실제 결과를 바꾸며, 수집 실패·아직 필요한 자료·부정적 결과는 보존한다. 강화나 재심사를 자동 반복하지 않는다.

일반 저장소는 `source_comparison`이 기본이고 유한 모형 없이도 분석·감사·집필이 가능하다. 선택 질문이 실제 시간·절차 문제일 때만 유한 규칙과 프로토콜 산출물을 쓴다. writer는 실제 `writer_brief`의 선택 질문·가까운 방법의 정확한 인용·완료한 발견과 비교 산출물을 받는다. 새로 확보한 문헌은 분석 문맥뿐 아니라 원고 수락·참고문헌·공식 출력에도 연결한다. 새로운 용어나 검사 통과를 추가 기여로 간주하지 않으며, 내부 감사 허가를 원고의 학술적 지지로 쓰지 않는다. 상세 동작은 [연구 설계와 근거 보완](../research-development.md)을 따른다.

기존 Frontron `research-7008ca97102a`는 **SDK35·영구 예약24/24·품질 심사10·수정8·작업9·형식 보완2**, contract2의 종료된 round2와 이전 회차 이력1개를 유지한다. 계획/문헌/분석은1/1/2, 프로그램·실험 실행은0이다. 일반 조회·재개로 contract3 전환·한도 추가·새 모델 요청을 만들지 않는다. 저자 정보·투고 준비2·사람 확인·포털 상태, 모든 기존 원고·점수·실패·원 응답·인계 자료·ZIP/manifest도 유지한다.

이번 보존·조회 증거는 `output/playwright/research-design-20261020/`에 있다.

- `checks.json`: **passed**, SHA `bde8eec8832b220d5e47e3e446d40b7c972ad9ec2dee6892a006912c747abdcc`. 최종 native31개와 Desktop134개의 로그·생산 소스15개·조회/보존 증거를 결속했다. native에는 보완 회차의5/6회 전체 경로2개, 최초 포트폴리오4개, 공통 설계·수집·한도25개가 포함된다. 합성 모델 응답과 HTTP 자료로 선택 질문 변경, 추가 원문의 실제 비교 반영, 바뀐 발견의 두 원고 본문·참고문헌 전달을 확인했다. 입력 저장소나 실제 모델을 실행하지 않았고 Word/PDF 변환은 해당 합성 흐름에서 대체했다.
- `preservation-baseline.json`: SHA `067adbdeaf536d21d8383d783148faf250132522f025717d523263aa14d004e8`. workflow1,176개(실제DB 포함), 원자료161개/1,121,077bytes, SDK수신70개·dispatch35개, 이전15개 납품/증거 디렉터리와 ZIP·공식 템플릿을 보호한다.
- `preservation-final.json`: **passed**, SHA `71fa99ffef76915e91aceaf69287640f31725cf47fe8d6967da09cd861d5dd69`. 원본 jobs·원자료·원고·심사·전체 보호 파일의 바이트와 누적 횟수가 baseline과 같다. 추가 SDK·예약·실제 연구 실행0이다.
- `closed-study-current-source.json`: **passed**, SHA `b6f9c9dc85d4a341636ea85c6bb9ad9adc60d96474baef19969b52090c5f1b4d`. 새 소스로 전체 workflow의 독립 일반 파일 복제본에서 새 서비스2개를 차례로 열고 각각 `status`와 IPC `workflow.list`를 조회했다. 실제 보존 품질 객체 전체가 같고 contract2·종료round2·24/24·심사10·다음 작업없음을 확인했다. 네트워크·문헌 수집·runner·runtime 요청 시도0, 원본 서비스 생성·재개0이다.
- `readonly-clone-preparation.json`: SHA `cbe33470b4fba32f13ef62c8a3ba5b7f9e4c46c73aacaae67813680f1d1bfb39`. 1,176개/1,123,017,705bytes를 독립 일반 파일로 복사하고 서로 다른 파일 ID·모든 바이트 일치를 확인했다. 계정이나 외부 SDK dispatch를 복사하지 않았다.
- `question-design-ui-proof.json`: **30/30 passed**, SHA `c0d61dfa5d439884e695bcc6057e00fea454f820a45831657e344ddabe714d4c`. 기존25개와 신규5개의 production React 합성 상태 검증이다. 단계 순서, 선택 질문·실제 확보 원문0/2개, 정확한 artifact 저장, 강화1회와 생략, 기존 회차·횟수·추가grant 없음과 렌더 전후 상태 불변을 확인했다. 실제 앱이나 모델 실행의 증거는 아니다.

미배포 로컬 패키지도 한 번 빌드하고 정적 검증했다. 실행 파일은 `desktop/release/research-design-20261020/win-unpacked/Paper Factory.exe`, SHA `1889ab05b39f9726ef466acbb5cdf8cabb6b2b8d06095f52f53d6b7b6a42b693`다. `build-proof.json`은 **passed**, SHA `a6155df1a11da84bbf858b8915730f27727b43bc3bc8517e49e3f6ada41ccdb7`이며 source123개·native54개·runtime2,443개와 공식 템플릿을 바이트/SHA로 결속한다. source binding은 `108681ae30845021c6e1da0a8ed97308befe0827bbdac34c9b607d7a2d38c953`이다. 새3개 모듈의 소스·패키지 Python 문법 검사6개도 통과했다. **이 패키지를 실제 기동하거나 계정 연결·모델 요청·연구 재개하지 않았다.** 공개 배포·commit·push도 하지 않았다.

이번 코드 변경으로 실제 논문 품질이 얼마나 개선됐는지는 아직 측정하지 않았다. 마지막 실제 새 후보의 점수는 Software **6/8/7/6/7/8/8/7/9**, S&P **6/8/7/7/7/8/6/5/9**, 모두 `revise_before_submission` 그대로다. 9점 목표와 현재 투고 권고 수준을 달성했다고 설명하지 않는다. 코드 검증·읽기 조회·공식 양식 출력·독립 학술 평가·사람의 투고 승인은 각각 다른 결과다.

아래는 앞선 실제 원고 생산의 보존 기록이다.

---

# 2026-10-18 최종 완료 체크포인트: 새 공식 원고 2편과 독립 평가

이 항목이 최신 상태다. 아래의 ‘진행 중’, ‘수락 전’, 과거 투고 권장·초기화 문구는 해당 시점의 보존 기록이며 현재 지시나 판정으로 사용하지 않는다.

같은 Frontron 연구 `research-7008ca97102a`, commit `3a7da2822721801db88ea059d204c8c6c622fab4`를 Windows의 숨김 packaged Electron·Playwright·공식 계정으로 이어갔다. round2는 설계+근거→독립 방법 감사→한 번 보완→현재 근거 독립 재감사→두 매체 집필→독립 평가의 **추가 실제 요청 6/6회, 총 SDK35, 영구 예약24/24**를 사용했다. 마지막 일반 재개는1회·연장0·모델 목록 확인1회·추가 SDK0·추가 예약0이며 정상 종료0이다. 현재 종료 상태는 `manuscripts_assessed` / `bounded_manuscripts_independently_assessed`다. **새 모델 호출 권한은 없으며 재집필·재심사·한도 재부여를 자동으로 하지 않는다.** Frontron/Madi 실행·실험·횟수 초기화·Docker·실제 투고는0이다.

새 후보 두 편의 기여/근거/방법/비교/실무/논리/표현/매체 적합성/한계 점수는 Software **6/8/7/6/7/8/8/7/9**, S&P **6/8/7/7/7/8/6/5/9**이며 둘 다 `revise_before_submission`이다. **모든 항목9점 목표와 투고를 권할 수준은 미달성**이다. 앱에 공개한 대체9개 기준의 독립 모델 평가이며 출판사 심사 결과가 아니다. 새 후보는 양쪽 모두 최선 원고로 선택되지 않아 기존 최선 원고를 유지했고, 이번 새 두 후보와 각각의 평가도 별도로 보존·전달했다.

집필 전 실제 연구 작업 산출물·동일 자원의 다른 요청·공통 서비스 계약·대안 비교·소스/완전한1차 문헌 대응·유한규칙 검사·부정 대조군·독립 재감사를 생성했다. 현재 근거 SHA에 결속된 재감사는 집필 가능한 범위를 인정했지만 이는 게재 가치나 전체 서비스 보장의 승인과 다르다. 새 최종 심사는 가장 가까운 비동기 서비스/큐 설계 방법 대비 추가 가치, 명시적인 최신 상태 서비스 수락 조건과 완결된 결과 비교, S&P의 과도한 내부 검사 설명을 주요 보완점으로 남겼다. 예산 종료를 프로젝트의 영구적인 품질 상한 확인으로 해석하지 않는다. 실제 프로젝트를 실행한 보호 효과·사용성·운영 성능 실험은 없다.

마지막 심사 원 응답의 SHA 역할 혼동은 정확히 같은 current version의 draft SHA→Markdown SHA 두 건으로 연결했고, S&P의 유일한 본문 locator는 첫 ASCII 문자의 대소문자 차이 한 건만 현재의 유일한 literal 위치에 맞췄다. 역복원하면 원 응답 객체와 완전히 같다. **과학 본문·점수·이유·비판·권고·원 응답·원 거절/error는 바꾸지 않았다.** 같은 완료 응답으로 새 review-5 두 건을 append했고 전체 품질 심사는8→10으로 누적됐다. 실제 일반 재개에서 추가 모델 요청 없이 수락·기록 재조회·23개 정상 UI 저장을 확인했다.

Software 공식 `CS_Mag_7_22.docx`, S&P 공식 `CS-Mag-template.docx`를 사용했다. 이번 새 후보의 실제 Word 수치는 Software **5쪽·환산2,650단어·초록99·참고문헌4·표2**, S&P **8쪽·환산5,376단어·초록44·참고문헌5·표3**이며 native 형식 검사를 통과했다. 정확한 Word/PDF에 결속된 **총13개 페이지 PNG를 전부 직접 검수**했고 심각한 잘림·겹침·표 행/헤더 분리는 없었다. Software의 Helvetica-Light/Cheltenham-Book 대체 글꼴, LibreOffice canonical renderer 부재의 실패 로그와 숨김 read-only Microsoft Word fallback을 보존했다. 형식 통과·학술적 투고 권고·실제 저자 승인·투고 완료는 각각 별개다.

재개 전 frozen1,169개 파일과 원고 관련153개 파일, 원자료161개·모든 기존 원 응답/dispatch·심사/점수·실패 실행·닫힌 이전 회차·ZIP/manifest·누적 횟수·저자/투고 상태를 SHA와 원 객체로 대조했다. 새 기록만 추가했고 기존 파일을 덮어쓰지 않았다. ORCID는 저자 동의가 아니며 약력/사진·연구비/이해충돌·권리·AI 공시 확인·최종 승인·제출 파일 QA/포털/접수는 여전히 별도 사람 확인 단계다.

최종 실행 증거는 `output/playwright/frontron-renewed-20261018/`에 있다.

- `actual-app-3/proof.json`: passed/exit0, SHA `b5927d0f9332c722309640dc0ed7911c9e28e9396add3ec46441d309f242845f`. 추가 SDK/예약0, 기존 자료·원 점수/권고 보존.
- `actual-app-3/native-save-proof.json`: 정상 UI 저장23개, SHA `fa591c9a6ff7ec84295cf74326f35cbba271977946690a0a01b2dfd4fd8a318d`. 새 후보와 기존 최선 출력의 ID를 구분했다.
- 최종 `manuscript-improvement-quality-report-15`: SHA `868a1bce39f5f3796b057873daa70571fa2c73228a7d9deca842056116c046ff`.
- `readonly-before-review/proof.json`: SDK/원자료 변경 없는 실제 읽기 전용 기동 passed, SHA `5afbcab59112b1672e3308c7ab20f2562cb9f0dbcfa7decfb7d687b200b6c85a`.
- `build-proof-v3.json`: SHA `6d2295fbd027a31262b5821b929080588ad8ef89c8fbd8b98f71256a0b4df1b7`. 최종 미배포 로컬 패키지 `desktop/release/frontron-renewed-reviewed-20261018/win-unpacked/Paper Factory.exe`의 소스·native 자산·런타임·공식 템플릿을 결속한다.
- `review-transport-fix/manifest.json`: SHA `118c0ffcc6f2d7870b3e609b67db67bbdb117b479e13accb7114e5db64d5f324`. 순수38개·워크플로2개 회귀 및 실제 전체 복제본에서의 멱등·새 서비스 status/list 재기동 검증을 해당 소스와 결속했다.
- `independent-renewed-replay/proof.json`: UI 저장 재현 ZIP의 전체 manifest·정확한 checker·생성 그래프 독립 재실행 일치. 이는 유한 모델 재현이며 Frontron 실행이 아니다.

최종 검토용 납품은 `output/pdf/frontron-renewed-20261018/`와 `output/pdf/frontron-renewed-20261018.zip`이다. ZIP은 **5,063,842 bytes·45 entries·SHA `ee39abcfb20e3d69494a1d4c3159bbccb02482697696a35ce3cf32d2691a67a0`**, 폴더 `manifest.json` SHA는 `78cf3e3e53e4d35c8da475fdf5c7bef671fc78fd52e45b8bbe2899162fef419e`다. 외부 `output/pdf/frontron-renewed-20261018-receipt.json` SHA `18dd9faf45df75425797ba5896b9a32e9b010310582b2177c475c5c6a64f0bff`가 ZIP CRC·정확한 멤버 집합·바이트/해시·23개 원 UI 저장본 불변을 검증해 passed다. 이번 새 원고6파일·새 review-5 두 개·최종 report-15는 정확한 UI artifact ID/예상 SHA와 일치하며, 재현 ZIP·현재 상태 구분표·평가·13개 PNG와 QA/실행 증거를 포함한다. 이전 스테이징26개 파일도 `output/pdf/frontron-renewed-20261018-staging-history/`에 별도로 보존했다. 검토용 로컬 묶음이며 공개 기탁·게재 승인·실제 투고가 아니다.

아래는 앞선 단계의 원래 기록이다.

---

# 2026-10-18 추가 6회 전부 사용: 새 공식 원고 2편, 평가 연결 복구 중

최신 실제 실행 `actual-app-2/proof.json`은 운영/보존 passed·정상종료0이며 **추가6/6회·총 SDK35·영구 예약24/24를 모두 사용했다. 새 모델 호출 권한은 없다.** 같은 원 응답 무호출 재수락→새 근거 독립 재감사→새2원고 집필→마지막 독립 평가까지 실제 수행했다. Software 새 원고는5쪽·환산2650단어·초록99·참고문헌4·표2, S&P는8쪽·환산5376·초록44·참고문헌5·표3이며 두 공식 Word/PDF가 생성되고 native 형식 검사를 통과했다.

마지막 심사 `43887ed6-dbf5-4919-b806-7bdbed6e05a5`는 양쪽 SHA 필드에 정확히 같은 current version의 draft JSON SHA를 넣어 Markdown SHA 요구와 충돌했다. SP anchor 하나도 실제 fragment 첫 소문자 l을 대문자 L로 시작한 locator 차이가 있었다. 모든 다른 원문·점수·이유는 유지한 채, 정확한 같은 버전과 유일한 현재 본문 위치에만 연결하는 무호출 메타데이터 재수락 수정 중이다. 새 리뷰를 호출하거나 평가 내용을 고치지 않는다. 원 평가의 기여/근거/방법/비교/실무/논리/표현/적합성/한계는 SW **6/8/7/6/7/8/8/7/9**, SP **6/8/7/7/7/8/6/5/9**, 둘 다 `revise_before_submission`이며 아직 app-native 수락 전이다. 9점 목표 및 현재 투고 권고 수준은 미달성이다.

새 원고 경로는 같은 workflow의 `research/manuscript-improvement/research-development/round-2/preflight/{venue}/paper.{md,docx,pdf}`다. root가 Software5쪽, 독립 에이전트가 SP8쪽을 모두 직접 봤고 심각한 잘림/겹침은 없었다. 미설치 공식폰트2종은 경고로 보존했다. LibreOffice canonical render 실패 로그와 실제 Microsoft Word read-only PDF fallback도 보존했다. `independent-renewed-replay/proof.json`은 UI 저장 재현ZIP 전체manifest/정확checker/생성graph 독립 재실행 일치·자료0변경으로 passed다. 독립 메리트 검토도 두 편 모두 투고 전 수정 권고다. 현재 납품 스테이징은 `output/pdf/frontron-renewed-20261018/`, 최종 복구/패키지/0호출 실제 재개·평가보고서/ZIP 검증은 아직 완료 전이다. 아래는 이번 실행 경위다.

재감사4회는 현재 근거에 대해 `ready_to_write=true/repair_required=false`로 수락됐고 SHA는 `3d76f5e1e87fd7fb3b50970a8f140d56274753a4ffad0d591b5a7d243fbaa7c5`다. 추가5/6회·총 SDK34·예약23/24인 `d2aa85f4-90e9-4050-a5c9-a352332a3b5c`가 두 매체 집필 중이다(13:28:06 UTC 시작). 완료 여부가 불명확한 이 요청을 재전송하지 않는다. 완료·수락 후 최종 독립 평가1회만 남는다. 아래의4회 진행 표시는 앞 단계 기록이다.

현재 새 contract 패키지의 숨김 실제 앱 일반 재개1회·연장0으로 동일 수정 응답을 **추가 모델 요청 없이 재수락**했다. 새 evidence-1 SHA는 `f6412883db4e7144441acc9bb8eb099827b7bde512a80679be7ee063ce0cd1a3`이며 current checker/work-product/supplement도 실제로 생성됐다. 원3번 거절과 원 응답은 유지된다. 현재 추가4/6회·총 SDK33·영구 예약22/24로, `7910fbc2-2b22-47b3-a96e-bc8da7a9cd4d`가 새 근거의 독립 재감사 중이다. 아직 새 원고나 최종 점수는 없다. 실행 증거는 같은 proof root의 `actual-app-2/`, 패키지는 `desktop/release/frontron-renewed-contract-20261018/win-unpacked/Paper Factory.exe`, build는 `build-proof-v2.json`이다. 새 읽기 전용 기동도 `readonly-before-resume/proof.json`에서 passed/정상종료0·SDK32/native21 불변을 확인한 뒤 시작했다. 아래는 첫 실제 실행과 복구 경위다.

현재 사용자는 기존 자료·횟수를 보존하며 같은 Frontron을 개선된 실제 앱에서 추가 최대6회 실행하고 공식 템플릿 원고와 독립 평가를 요구했다. 별도 명시 승인으로 round2를 만들었으며 round1은 원 객체 그대로 이력/동결 파일에 보존했다. 누적 예약 상한은18→24, 실제 SDK 상한은29→35다. 일반 재개로 한도를 새로 부여하지 않는다.

`output/playwright/frontron-renewed-20261018/actual-app/proof.json`은 실제 숨김 packaged Electron·Playwright·공식 연결의 운영/보존 검사 passed·정상종료0이다. 현재 추가 실제 요청은 **3회**, 총 SDK32·영구 예약21/24다. 설계1→방법 감사1→수정1을 완료했지만 새 원고는0이다. 초기 모델은 Cartesian6,291,456개로5,000개 한도를 넘었다. 수정 응답은4,096개로 줄였고, 없는 대입 교체와 guard/effect 매핑도 고쳤으나 실제 문헌 `focused-document-1`을 규칙 근거에 포함해 repository-only 내부 검사에서 거절됐다. 두 거절과 원 응답은 보존했다. 현재 상태는 bounded research report이며 이 상태를 투고 가능 또는 연구 완료로 설명하지 않는다.

수정 응답에는 실제 존재하는 소스·문헌·모델 참조만 있지만 공개 스키마와 내부 검사 사이의 지원 불일치도 있었다. 비교표의 계산 결과 결속, 공통 규칙의 설명문 차이, 동일 원자 전이의 역할별 설명, 도달 가능한 특정 요청의 phase 인스턴스를 다루는 수정안을 `tmp/renewed-contract-fix/`에서 준비·검증했다. 원 응답을 수정하거나 과학적 한계를 제거하는 작업이 아니다. staged 전체 source/doc literal 검증·finite 재계산·work-product 검사에서 같은 수정 응답이 통과했고, 정확한 edge/상태와 근거 종류를 보고서에 결속한다. 구현/효과/보편적 phase 보장으로 승격하지 않는다.

이어서 root 검토와 별도 증명 범위 검토, 순수82개·재수락10개 staged 검사, 실제0.94GB 복제본의 재수락/멱등/기록 보존/용량 검사를 완료했다. source5+test2와 UI3파일을 SHA 검증 후 생산 적용했고, 생산 순수82개·Desktop68+deadline3 검사가 통과했다. 실제 자료 변경·재수락·추가SDK는 아직0이다. 생산 적용 증거는 `contract-fix/production-apply/apply-receipt.json`, 복제본은 `contract-fix/isolated-clone-resume-proof.json`에 있다. 현재 새 패키지와 읽기 전용 기동 검증을 준비 중이다. 실제 앱의 일반 재개로 **같은 원 응답만 무호출 재수락**하고, 남은 최대3회로 새 근거 SHA에 대한 독립 재감사→두 매체 집필→독립 평가를 진행한다. 기존 호출의 거절 outcome/error·실패 파일·이전 closure·자료·점수는 변경하지 않는다. 재감사가 집필 불가이면 이를 우회하지 않는다. 연구/모형/문헌/점수를 수동으로 고치거나 새 한도를 부여하지 않는다.

후속 실행 baseline은 `output/playwright/frontron-renewed-20261018/resume-after-evidence-baseline/baseline.json`이다. 현재1064개 frozen workflow 파일·source161·이전 모든 실행과4개 납품·32개 SDK/dispatch·21개 예약·저자/투고 상태를 보호한다. 재개 harness는 `tmp/final-frontron-renewed-resume-20261018.mjs`, 새로운 증거 경로는 `actual-app-2/`이며, 최종 source/package 동결과 root GO 전에는 실행하지 않는다. 이전 앱/납품 폴더를 덮어쓰지 않는다. 이 항목 아래는 이번 실행 전의 검증 기록이다.

---

# 2026-10-18 집필 전 연구 작업 생성·재감사 교정

사용자의 현재 목표는 앱이 처음부터 투고를 검토할 실제 원고를 생산하는 것이다. 약한 원고를 만든 뒤 점수만 반복해서 매기는 흐름으로는 이 목표를 달성하지 못했다. 실제 방법 감사가 `ready_to_write=false`여도 보완 뒤 집필로 넘어가던 결함을 확인했다. 이전 Frontron 원고의 점수·실제 감사·한계와 결과는 수정하지 않는다.

새 저장소 연구는 첫 공통 분석에서 실제 대안의 구현 단계·비용·적용 조건, 공통 요건/전제, 전체 비교표, 기존 판단과 추가 분석 후 판단을 `work_products`로 생성한다. 네이티브 보고서를 분석 원본에 동결하고 첫 집필·심사 전에 정확한 SHA·전체 본문·페이지/EOF를 검증한다. 초기 분석은 `source_comparison`만 받는다. 유한 프로토콜은 별도 보완 단계에서 실제 규칙·사례와 함께 다룬다.

새 보완 회차(contract 2)는 **설계+근거 → 독립 감사 → 필요시 한 번 보완+독립 재감사 → 두 원고 집필 → 독립 평가**, 최대6회다. 현재 근거 SHA에 결속된 감사가 집필 가능이고 필요한 보완이 없을 때만 집필한다. 현재 산출물/검사 보고서·감사 원본의 실제 결속도 확인한다. 불충분하면 완료한 연구 보고서와 정확한 종료 사유를 남긴다. 이전 closed contract 1 회차는 새 계약으로 바꾸거나 다시 열지 않는다.

프로토콜 산출물은 동일 자원의 서로 다른 세 요청, 주체별 상태와 실제 유한 단계, 공통 작업·서비스 계약, 거절/보존/최신 상태 병합과 기존 지침 대비 판단을 연결한다. 내부 일관성 검사는 정책-규칙의 의미 대응·실제 구현 원자성·게재 가치를 입증하지 않는다. 독립 감사가 실제 guard/effect와 원문을 판단한다. 같은 판단을 확인하는 부정 결과도 허용하며 추가 기여 미입증 한계를 남긴다. 9점 목표 달성은 모든 점수뿐 아니라 오류 부재와 `consider_submission`을 함께 요구한다.

이번 변경에서 새 과학 모델 요청이나 원고 생성은 하지 않는다. 기존 Frontron **SDK29·영구 예약18/18·닫힌6/6**, 자료·원 응답·심사·실패·횟수·저자 승인 상태를 유지한다. 새 흐름으로 Frontron 논문이9점이나 투고 가능 품질에 도달했다고 주장하지 않는다. 공식 템플릿 사용·저자 확인·권리/투고 선언도 그대로 별도 단계다. 변경된 흐름은 [연구 설계·근거 보완](../research-development.md)에 정리했다.

첫 실제 읽기 전용 시작은 실패했고 `output/playwright/frontron-method-20261018/actual-app-readonly/`에 보존했다. 원인은 기존 분석 거절의 오류 위치 `['analysis']`가 새 코드에서 `[]`로 계산되어 원 schema-repair 증빙을 변조로 오인한 것이었다. 원자료가 달라진 것은 아니다. 오류 위치 계약을 복구했으며 원 응답·오류·수락 검증을 완화하거나 보존 파일을 고치지 않았다. 시작 실패 때 비워진 jobs.json의 파생 화면 캐시도 수동 복원하지 않는다. 수정 소스로 실제 packaged Python의 읽기 전용 조회3종과 파일1,038개 해시 불변 검사를 통과했다. `current-source-native-readonly-status-fixed.json`과 원 실패/정확한 차이 진단은 같은 증거 폴더에 있다.

새 작업 산출물의 합법적인 선택 필드 생략도 회귀로 확인했다. 타입 기본값 `[]`를 원 응답에 없던 키로 삽입해 `PORTFOLIO_RESPONSE_CHANGED`로 거절하던 문제를 재현했고, 첫 분석/분석 보완의 원 응답 비교에서 실제 입력된 필드만 직렬화하도록 두 곳을 교정했다. 원 응답은 그대로이며 전체 구조·실제 소스·근거 검증은 유지한다. 최종 첫 경로7개 검사가 통과했고 `portfolio-optional-fields-proof.json`에 실패 재현과 최종 소스/검사 SHA를 보존했다.

최종 검증은 **passed**다. 패키지 `desktop/release/frontron-method-verified-20261018/win-unpacked/Paper Factory.exe`를 실제 숨김 Electron·Playwright로 실행하고 결과 탭만1회 열었다. 시작 실패 때 비워졌던 파생 캐시는 정상 verified engine listing으로 복구됐으며 수동 파일 복사·연구 재개·모델 새로고침·한도 부여·추가 SDK 요청은0이다. 기존 frozen1,037개/source161개·SDK raw58/dispatch29·모든 이전 실행과 납품/실패 증거의 SHA, 기존 원고/심사/점수/저자/투고 상태를 확인했다. SDK29·예약18/18·닫힌6/6 유지, 정상 종료0이다.

종합 증거는 `output/playwright/frontron-method-20261018/checks.json`, `build-proof-v3.json`, `actual-app-readonly-2/proof.json`이다. source118/native51/runtime2440개를 결속하며 source binding은 `0454a1a777342d69db11d872ee2b09e5142441e6f03ab9940df9f0e96a792db1`이다. Desktop52+마지막 문구1, 초기 경로140개/수정 후6·최종7, 연구 계약50, 순수 산출물33 검사를 각각의 소스·범위로 연결했고 중복 합산하지 않았다. 첫 실패와 중간 패키지도 덮어쓰지 않았다. 새 흐름으로 실제 새 원고나 점수를 생성한 검증은 아니다. commit·push·실제 투고는 하지 않았다.

아래는 직전 실제 원고 생산 회차의 보존 기록이다.

---

# 2026-10-18 연구 설계·근거 보완 완료 기록

현재 지시는 **기존 자료·횟수 유지**다. 같은 Frontron 연구 `research-7008ca97102a`, commit `3a7da2822721801db88ea059d204c8c6c622fab4`를 실제 숨김 packaged Electron·Playwright·공식 계정에서 이어갔다. 설계→근거→별도 방법 감사→한 번 보완→두 원고 집필→독립 평가의 실제 추가 요청은 정확히 **6회**, 총 SDK23→29, 영구 예약12→18/18이다. 한도를 다시 부여하지 않는다. 계획/문헌/분석1/1/2·기존 두 매체 draft/review/admitted·원자료161개·저자/준비2·선언/승인/포털 상태는 유지했다. Frontron/Madi 재실행·실험 횟수 초기화·Docker·실제 투고는 없다.

새 두 후보는 **모든 항목9점 목표 미달, 투고 전 보완 필요**다. 기여/근거/방법/비교/실무/논리/표현/적합성/한계 순으로 Software **7/8/7/8/8/8/8/8/9**, S&P **7/8/7/8/8/8/6/7/9**다. 앱의 명시된 9개 대체 기준이며 외부 GPT의 전체 평가표나 편집자 심사는 아니다. Software는 새 후보가 최선으로 선택됐고 S&P는 이전 최선 원고를 유지했다. 새 S&P도 별도 보존·전달했다. 점수·원 평가·기여 주장을 수동으로 올리지 않았다.

단순 재서술을 넘어 생성 규칙에서 상태를 만드는 네이티브 검사, 소스/선행 원문 대응 감사, 부정 대조군, 조건 변화, 한 번의 실질 보완을 추가했다. E2는2사례/5대안/141도달 상태/356전이/531불변식 검사/6대조군 탐지를 기록한다. 기존 overflow 표식 검사로 놓치던 a→b 대기 요청 교체를 관계 불변식이 탐지한다. 원래 두 실패 조건 변화·vacuity·dead rule·기존 기본 그래프 반례를 유지했다. 추가 조건 변화2개는 작업 도달성 차이이며 전체 보안 우열의 역전이 아니다. 이는 선언한 유한 모델의 결과이지 프로젝트 실행·보호 효과·사용성 실험이 아니다.

중심 한계는 실제 신뢰 입력·문서 세대·원자적인 시작 경계와 모델의 대응, 동일 경로의 서로 다른 요청 구별, Autosave 보존/거절 정책의 이유와 기존 방법 대비 추가 실무 가치다. S&P는 내부 검사 상세가 많다. 현재 자료·이번 한도에서의 판단이며 프로젝트의 영구적인 품질 상한이 확인된 것은 아니다.

원 감사의 대상 필드와 실제 모델 ID, 집필의 계산 근거 ID/인용 구분자 계약을 엄격한 무호출 수락 복구로 해결했다. 원 응답·거절·오류·실패 실행·사용량은 그대로다. 소스/문헌/이전 원고/검사기·입력 해시·미등록 ID 검증을 유지한다. 형식 검사의 인사이트 제목/GPT 공시/과학 용어 placeholder 오탐도 고쳤다. 후속 실행은 과학 본문·심사·횟수를 바꾸지 않고 변환기 해시에 따라 출력 세대만 갱신한다.

공식 Software `CS_Mag_7_22.docx`, S&P `CS-Mag-template.docx`를 사용했다. 새 후보 실제 Word 수치는 Software **5쪽·환산2,887단어·초록93·참고문헌5**, S&P **9쪽·환산5,506단어·초록45·참고문헌6**이다. 새 두 원고의14쪽을 직접 본 이미지와 해시 대조했다. 행 분할·셀 정렬·헤더/캡션 설정을 다뤘으며 이전 최선 원고까지 시각 검수가 완료됐다고 주장하지 않는다. Software의 Helvetica-Light/Cheltenham-Book 대체 글꼴은 기록에 남는다. LibreOffice 부재로 bundled render_docx는 실패 로그를 보존했고, 실제 앱의 read-only Microsoft Word 변환·통계와 해당 PDF의 PDFium 페이지를 검수했다. 저자 약력·사진·권리·AI 공시 확인·최종 승인·실제 제출 파일 QA는 사람의 입력 대기이며 ORCID를 동의로 취급하지 않는다.

재현 ZIP은 manifest 포함22개 파일을 확인했고, 정확한 checker SHA와 입력으로 `Python -I -S` 독립 재실행한 전체 생성 그래프가 일치했다. 공개 DOI/기탁을 주장하지 않는다. 원자료·이전 ZIP/manifest·실패 실행·모든 원 응답/dispatch·카운터의 불변 검사를 통과했다.

최종 전달은 `output/pdf/frontron-new-manuscripts-20261018/`다. 새 두 후보 Markdown/Word/PDF6개·원 평가2개·quality report·재현 ZIP의 실제 UI 저장10개와 평가/QA/재현·독립 검토를 묶었다. `Frontron-IEEE-research-development.zip` **1,095,186bytes/17members/SHA a184d47ef08e75b11b27b578dc90a0a747f0a1c990bc39001b4b591ee2920f19**, 원 UI manifest SHA `0b26a09b26b6134e3c91e5c39f8df2617b721fea10aa4d7b5114e98aa298c831`, delivery manifest SHA `81269f5bd013ea2e89d9ad4983e14ff57e703f6cdfa6976717af31281ebbb448`. 외부 `bundle-receipt.json`의 모든 멤버/CRC/바이트/해시 검증이 passed다. 초기 묶음 검사의 Windows 대소문자 정렬 비교 오류를 수정해 검증했으며 ZIP/원고/평가 바이트는 바꾸지 않았다. 중간 복사 폴더 `frontron-development-20261018/`, `frontron-development-final-20261018/`도 덮어쓰지 않고 보존했다.

증거는 `output/playwright/frontron-development-20261018/`에 있다. `actual-app/`·`actual-app-2/`·`actual-app-3/`의 실패를 보존했다. `actual-app-4/proof.json`은 원고/최종 평가를 포함해 passed, 추가6/SDK29/native18/저장16/정상 종료0이다. `actual-app-5/`와 **`actual-app-6/proof.json`**도 일반 재개1/grant0/새 SDK0/동일 점수·원고·횟수/저장16/정상 종료0으로 passed다. 마지막 시작 전971개 파일과 모든 이전 실행을 보호했다. 최종 실행 패키지는 `desktop/release/frontron-development-final-20261018/win-unpacked/Paper Factory.exe`; `build-proof-v6.json`이 생산 소스117개/native자산50개/런타임2439개 및 공식 템플릿을 결속한다. 공개 배포·commit·push는 하지 않았다.

설계와 동작은 [연구 설계·근거 보완](../research-development.md)을 따른다. 아래는 이전 보완 회차의 기록이다. 새 요청 없이 추가 과학 호출/재집필/재심사하지 않는다.

---

# 다음 세션: Frontron 품질 보완 결과

## 2026-10-18 추가 4회 한도 보완 완료

현재 지시는 **기존 자료·횟수 유지**다. 같은 Frontron 연구 `research-7008ca97102a`, commit `3a7da2822721801db88ea059d204c8c6c622fab4`를 실제 숨김 packaged Electron·Playwright·공식 계정으로 이어갔다. 선택·분석·두 원고 집필·독립 평가 각 1회로 추가 실제 모델 요청은 정확히 **4회**, 총 SDK 19→23이다. 전송 전 취소 예약을 포함한 영구 예약은 8→12/12다. 연구 초기화·Frontron 코드 실행·다섯 번째 요청은 없으며 예산 종료로 멈췄다. 이 한도를 재부여하지 않는다.

원 응답의 학술 PDF 인용 분류 불일치로 분석/집필이 거절됐다. 실제 원문 ID·SHA·정확한 인용과 모든 소스를 검증한 결정적 분류 복구로 같은 응답을 수락했다. 복구 추가 요청은0이며 원 응답·거절·실패한 첫 두 실제 앱 실행 증거는 그대로다. 세 번째 실행은 정상 UI 재개1회·새 요청1회만 사용해 공식 Word/PDF·Markdown6개와 보고서를 저장하고 정상 종료했다.

**두 원고 모두 투고 전 보완 필요이며 모든 항목 9점 목표는 미달성**이다. 앱이 명시한 9개 대체 기준은 기여/근거/방법/비교/실무/논리/표현/적합성/한계 순으로 Software **7/8/7/8/8/8/7/8/9**, S&P **7/8/7/9/8/8/6/7/9**다. 원래 외부 GPT의 전체 평가표는 제공되지 않았다. 별도 심사의 빈 `literature_evidence` 지적은 실제 PDF가 검증된 `document_evidence`에 저장되는 분류 오인이다. 수동 재채점하지 않았고 나머지 검사 범위·기여·재현성 지적은 남긴다. 향후 심사 지침의 잘못된 필드 요구와 집필 전용 References 금지 지침 전달을 수정했고 합성 회귀 검사로 확인했다. 수정 후 실제 모델 평가를 다시 호출하지 않았다.

완전한 1차 논문3편 비교, Paste·Autosave 결정표와 네 유한 상태 그래프를 추가했다. 불변식 검사50회·추상 반례4개는 Frontron 실행 실험이 아니다. JSON에는 전체 상태·가드·갱신·불변식이 있으나 공개 재현 묶음/실행 안내/검사기 버전 결속을 원고에 연결하는 일은 남는다. 자원 동일성·현재 수신자·동시에 실행/대기하는 작업의 전체 관계는 검사하지 못한다. 단일 템플릿·미구현 제안·모델 가정이 한계이며 이번 예산 종료를 프로젝트의 영구적인 품질 상한 확인으로 해석하지 않는다.

Software 공식 `CS_Mag_7_22.docx`와 S&P `CS-Mag-template.docx`를 사용했다. 실제 Word 수치는 Software **6쪽·환산3,101단어·초록104·참고문헌5**, S&P **9쪽·환산5,940단어·초록47·참고문헌6**으로 두 원고의 자동 형식 검사를 통과했다. 최종15쪽 PNG·텍스트 SHA가 직접 확인한 페이지와 모두 같다. Word의 proprietary font 대체도 기록했다. **형식 통과·투고 권고·저자 승인은 별개**다.

약력의 실제 직위·소재지·관심 분야·최종 학위·학위 기관·학회 회원 여부, 연구비·이해충돌, Software용 사진, 저자 확인·권리·AI 공시·최종 승인과 새 파일 직접 검수는 입력 대기다. ORCID는 동의가 아니다. 앱은 누락 정보 입력→새 제출용 Word/PDF→실제 분량/전페이지 검사→실제 저자 확인→제출 묶음으로 처리한다. 기존 준비2·선언false·파일 QA 빈 값·포털0·접수0은 보존됐고 실제 투고는 하지 않았다.

현재 결과와 증거(로컬 자료, Git 제외):

- `output/pdf/frontron-focused-20261018/evaluation.md`: 새 원고·항목별 점수·형식/과학적 한계·평가 분류 오인.
- 같은 폴더의 `IEEE-Software.*`, `IEEE-Security-and-Privacy.*`, 두 원 심사·quality-report·분석/검사 결과·visual-review·manifest.
- `Frontron-IEEE-focused-manuscripts.zip`: 942,501 bytes,17 members,SHA `ff3bde2411dfcac39c51a2fdf20ff3220166b9e395eaf49e6c87eda7d2002e95`; manifest SHA `0b71d5dfa39204f31de05e8986578f78a42686f786db167f75214b813e3bf9e8`. ZIP 외부 `bundle-receipt.json`으로 모든 멤버를 검증했다.
- `output/playwright/frontron-focused-20261018/actual-app-3/proof.json`: **passed**,추가4/총23,저장7,보존 검사 통과,정상 종료0. 첫 두 `actual-app/`, `actual-app-2/`의 failed 증거를 덮어쓰지 않았다.
- 같은 실행의 `resumption-preservation-final.json`: 재개 전655개 파일과 앞선 실패 실행 전체·원 응답/dispatch 불변. 최초541개 파일·원자료161개·이전 요청19개·예전 ZIP/manifest·저자·카운터·준비2도 보존했다.
- `build-proof-v3.json`: 실제 실행 패키지의 생산 소스113개·native자산47개·런타임2436개·공식 템플릿 결속. 실행 패키지는 `desktop/release/frontron-focused-final-20261018/win-unpacked/Paper Factory.exe`.
- `native-review-evidence-discrepancy.json`: 실제 심사 분류 오인 확인. 수정 후 로컬 패키지는 `desktop/release/frontron-focused-reviewed-20261018/win-unpacked/Paper Factory.exe`; `build-proof-v4.json`은 이 후속 패키지를 따로 결속하며 새 모델 평가의 증거가 아니다. 공개 배포나 push는 하지 않았다.

최종 수정 패키지의 숨김 읽기 전용 시작 검증도 `actual-app-4-readonly/proof.json`에서 passed·정상 종료0이다. 결과 탭 선택 외 동작 없이 SDK23/native12·두 원고의 9개 점수와 권고·전체 기존 자료가 동일하며 추가 모델 요청0이다.

아래는 앞선 세션의 보존 기록이며 이 체크포인트보다 오래됐다.


2026-10-18 최신 체크포인트. **기존 자료·원고·심사·횟수 유지**가 현재 지시다. 아래 과거 기록의 초기화·투고 권장 문구를 현재 지시나 현재 판정으로 사용하지 않는다.

같은 Frontron 연구 `research-7008ca97102a`와 commit `3a7da2822721801db88ea059d204c8c6c622fab4`를 앱의 항목별 품질 보완으로 이어갔다. 현재 권고는 **Software·S&P 모두 투고 전 보완 필요**이며 9개 항목 각각 9점 목표는 미달성이다. 기여 6·근거 8·방법 7·비교 5·실무 가치 8·논리 8·표현 6·매체 적합성 7, 한계는 Software 8/S&P 9다. 과거 내부 PASS는 이력으로만 보존한다.

기존 설계/문헌/분석 1/1/2, Software 집필/심사 1/1, S&P 2/2, 코드/실험 0은 그대로다. 별도 품질 보완에 실제 모델 요청 7개(초기 평가 2·계획 1·집필 2·수정 평가 2)를 추가했다. 전송 전 중단 예약 1개도 포함해 영구 예약 예산 8/8을 사용했고 `budget_exhausted`로 종료했다. 요청 UUID 총수는 기존 12+추가 7=19다. 추가 수정본 2·평가 4·참고문헌 형식 복구 2이며 복구·재출력은 추가 모델 호출 0이다. 예산을 새로 만들려고 연구를 초기화하거나 같은 응답을 재평가하지 않는다.

흐름은 독립 평가→방향 비교→필요한 완전한 소스/공식 문서 확보→실질적 원고 보완→독립 평가→최선 원고 선택→공식 템플릿 Word와 정확한 Word에서 렌더링한 PDF→별도 분량·전체 페이지 검수다. 계획은 가까운 선행 방법의 전문 확보를 우선하고 연구 관리 이력·자기 점수·참고문헌 수 자기 선언은 본문에 늘리지 않도록 개선했다. [품질 보완 흐름](../manuscript-improvement.md), [공식 템플릿](../official-templates.md)을 확인한다.

두 수정본은 붙여넣기·자동 저장 정책, 생명주기 반례, 기존 지침과의 공정한 비교와 구현 책임을 추가했다. 그러나 가까운 학술 방법의 본문 비교·완성된 공통 검토표·정확한 상태 전이와 체계적 반례 점검이 부족하다. 이는 전부 프로젝트의 영구적 한계가 아니다. 단일 정적 템플릿으로 실제 보호 효과나 넓은 일반화를 입증할 수도 없다. 이번 예산 종료를 프로젝트의 절대적인 품질 상한 확인으로 해석하지 않는다.

Software 본문의 “12 reference entries”는 실제 5개와 다르다. S&P는 전체 분량 최소 4,900·초록 최대 50 규정을 충족하지 못한다. 최종 수치는 아래 최신 전달 평가를 확인한다. 서지 정보·편집·저자/제출 자료도 남아 있다. 원고 본문이나 심사를 임의 수정하지 않았고 투고는 하지 않았다.

현재 미배포 로컬 패키지는 `desktop/release/magazine-layout-final-20261018/win-unpacked/Paper Factory.exe`다. Windows·설치된 Microsoft Word를 사용하며 Docker는 없다. 공식 템플릿 원본 SHA는 provenance에 고정했고 PDF는 exact DOCX SHA에 결속한다. proprietary font 부재 시 Word 대체 글꼴을 기록하며 완전한 편집 규정 준수나 채택을 주장하지 않는다. 공개 0.14.20 설치본을 갱신하지 않았다.

최신 검증/전달 경로(로컬 자료, Git 제외):

- `output/playwright/frontron-quality-20261018/layout-checks.json`: 핵심 테스트 100개, typecheck/build 및 native host 검증.
- `output/playwright/frontron-quality-20261018/layout-build-proof.json`: 실제 패키지·모든 포함 런타임·현재 생산 소스와 공식 템플릿 해시 결속.
- `output/playwright/frontron-quality-20261018/actual-app-7/`: 숨김 packaged Electron·Playwright·실제 공식 계정·정상 UI 저장. SDK/engine/model mock 없음.
- `output/playwright/frontron-quality-20261018/final-preservation-after-layout.json`: 원 381개 파일·원자료 161개·기존 12개 요청·옛 ZIP/manifest·카운터·저자·준비 2 보존. 이후 품질 기록과 실패 증거도 유지.
- `output/playwright/frontron-quality-20261018/official-qa-final-v2/`: 실제 Word 통계, exact Word/PDF 결속과 전체 페이지 검수.
- `output/pdf/frontron-quality-20261018/evaluation.md`: 한국어 최종 평가; 같은 폴더의 6개 원고·2개 심사·보고서·새 ZIP/manifest가 최신 검토용 전달본.

기존 전달 루트 `output/pdf/frontron-fresh-20261014/`와 ZIP SHA `3468916fe6b0568d11646684220540ea4bbe0c31e454505296bc545ed4301fe4`, manifest SHA `af75d68e68db703ebc135e824f77e14a42e99f47663ebf8fc25b9766e728db42`는 불변이다. 이전 실패한 앱 검증 증거를 새 성공으로 덮어쓰지 않는다. 기존 S&P 준비 2는 원문과 저자 확인 7개 false·파일 QA 5개 빈 값이 보존되며 최신 원고/평가에 대한 제출 준비로 재사용하지 않는다.

최종 실제 Word 수치는 Software 5쪽·환산 본문 3,032단어·초록 121단어·참고문헌 5개, S&P 8쪽·전체 4,821단어·초록 51단어·참고문헌 5개다. S&P는 최소보다 79단어 부족하고 초록은 1단어 초과한다. 최종 13쪽 시각 검수는 정확히 동일한 기존 11쪽과 새로 확인한 마지막 2쪽으로 결속했다. 새 검토 묶음 `Frontron-IEEE-review-manuscripts.zip`은 804,424 bytes·12 members, SHA `55eb060e8471f8aa58f6fa19de3221f826ec718e07b6e75a50afbff01d991ad5`; 새 manifest SHA는 `4c096ca3cc8bf43dd570c05879bd4eac547f904ace302afc487cbddb682d4d61`이다. 이 자료는 검토용이며 제출 완료가 아니다.

## 보존된 이전 실행 기록


2026-10-18 평가 정정: IEEE Software 원고의 기존 **투고 검토 권장**을 철회한다. 현재 판단은 **유효한 기술 분석 초안이나 기여와 근거의 실질적 보완이 필요함**이다. 사용자 제공 외부 평가와 실제 원고·원 심사·감사를 대조했다. 단일 템플릿 5개 경로와 공식 문서 3개의 정확한 설명, 한계 고지와 페이지 QA가 충분한 게재 가치를 입증하지는 않는다. 기존 지침보다 추가로 제공하는 판단·적용 가치가 확인되지 않았고, scoped grant는 제안이며 클립보드 완료 계약의 버전 일치도 미확인이다. 과거 내부 PASS와 출력·원고·심사·자료·횟수는 보존한다. 이번 재평가는 Software에 한정하며 S&P의 게재 가치를 새로 확인한 것은 아니다. 아래 10월 15일 실행·검수 기록과 현재 권고를 구분한다.

2026-10-15 KST 체크포인트. 목표는 공개 GitHub 저장소에서 **IEEE Software·IEEE Security & Privacy의 적합한 Feature Article을 실제 앱으로 작성·평가하고, ORCID 공개 정보로 저자 입력을 보완해 제출 파일·저자 확인·공식 포털·접수 기록까지 연결하는 것**이다. 실제 외부 투고 승인은 아직 없으며 두 매체의 범위에 맞지 않는 프로젝트를 억지로 두 원고로 만들지 않는다.

사용자의 최신 전체 삭제 요청에 따라 이전 연구·원고·원자료·심사·횟수·전달 ZIP을 다시 삭제했다. 예전 연구의 통과 판정이나 원고는 현재 실행의 결과가 아니다. 과거 JIZURA·9곳 포트폴리오·인계 ZIP을 복원하지 않는다. [현재 검증 기록](../standalone-verification.md), [두 매체 설계](../ieee-magazine-redesign.md), [실제 투고 흐름](../submission-workflow.md)을 함께 확인한다.

아래 `output/`와 `.paper-factory/`는 이 Windows PC의 로컬 자료이며 Git에는 원고·계정 자료·실행 증빙을 포함하지 않는다. 새 복제본에는 이 경로가 없다. 상대 경로는 저장소 루트 기준이다.

## 현재 실제 실행

- 입력: `https://github.com/andongmin94/frontron`
- 새 연구: `research-7008ca97102a`
- 고정 Frontron commit: `3a7da2822721801db88ea059d204c8c6c622fab4`
- 작업공간: `C:/Users/Andongmin/Desktop/repository/paper-factory`
- 실제 데이터: `.paper-factory/jizura-new-01420-20261008-04e3b1a0-4ee/app-data` — 과거 디렉터리 이름이며 내용은 이번에 초기화한 새 연구다.
- 현재 패키지: `desktop/release/orcid-autofill-20261015/win-unpacked/Paper Factory.exe` — ORCID 자동채움을 포함한 미배포 로컬 빌드, 버전 0.14.20. 소스·포함 파일 결속과 실제 ORCID UI 검증이 통과했다.
- 원고 생성 증빙: `output/playwright/frontron-fresh-20261014/`
- 새 투고 준비 증빙: `output/submission-design/actual-app-20261015/`
- ORCID 패키지·실제 앱 증빙: `output/playwright/orcid-autofill-20261015/`

2026-10-14 14:06:17 UTC 초기화에서 760개 파일·60,455,815 bytes를 삭제했다. 설치 앱과 실제 검증 데이터 양쪽 모두 연구·워크플로가 없는 상태를 확인했다. 자체 계정 연결·설정·소스·런타임·설치 파일은 유지했다. `reset-verification.json`, `empty-stores-before-app.json`, `empty-app-before-start.json`이 새 연구 시작 전 증거다.

2026-10-14 14:09:19 UTC 실제 packaged 앱의 정상 UI에서 저장소·목표·모델을 입력하고 **연구 시작**을 한 번 눌렀다. 공식 자체 계정의 `connected=true`, `sharing=true`, 실제 모델 목록과 작성·검토 `gpt-6.1-sol`을 확인했다. SDK mock, 이전 연구 가져오기, 직접 원고·심사 입력은 없다. 창만 숨김/offscreen으로 운영하며 Docker를 사용하지 않는다.

첫 분석 응답은 스키마와 근거 ID 계약의 불일치로 수락되지 않았고, 첫 정상 재개는 같은 완료 응답을 다시 확인해 추가 모델 호출·횟수 증가 없이 종료했다. 원 응답과 분석 1회를 그대로 보존한 채 계약을 수정하고 엄격한 native 검증을 통과해야 하는 보정 요청을 한 번 허용했다. 수정한 실제 로컬 패키지에서 같은 연구의 정상 **IEEE 매체별 미완료 투고본 재개**를 한 번 눌러 분석 2를 수락하고 두 원고를 생성했다. 실패를 승인으로 바꾸거나 검증 조건을 낮추지 않았다.

2026-10-14 15:03:34 UTC / 10-15 00:03:34 KST 원고 생성·독립 평가와 정상 종료 exit 0을 확인했다. 설계 1·문헌 1·분석 요청 2·채택 분석 1, 공통 원고·코드/실험 0이다. 매체별 실제 원고 1·독립 심사 1이 있으며 두 심사의 7개 기준·비교·기여가 모두 통과하고 차단 문제와 후속 작업이 없다. native `allContentReady=true`다. 실제 Word·PDF·Markdown 6개를 정상 저장 버튼으로 내보내 해시를 대조했고, 재개 전 원 파일의 변경·누락은 0이다.

| 실제 원고 | 제목 | 현재 별도 검수 |
| --- | --- | --- |
| IEEE Software | Authorize the Operation, Not Just the Renderer: Maintaining Native Bridges in Frontron | 독립 내용 감사·최종 Word 10쪽/PDF 8쪽 검수 통과 |
| IEEE Security & Privacy | What a Compromised Renderer Can Still Ask For: Authorizing Native Operations in Electron Bridges | 원고 2·심사 2, 별도 내용·수치·Word 14쪽/PDF 12쪽 검수 통과 |

첫 두 원고 생성 증거는 `resume-2/final-summary.json`, 정상 UI·저장·종료는 `resume-2/proof.json`, 원 파일 보존은 `resume-2/immutable-research-final.json`이다. 정상 저자 정보 UI로 후보 정보를 반영한 `author-2/proof.json`은 6개 실제 저장·정상 종료와 추가 모델 호출 0을 확인한다. Software의 실제 Word는 3,199단어에 표 allowance 250을 더해 분량 범위 안이고, Word 10쪽·native PDF 8쪽의 모든 페이지를 확인했다. 전달본 `output/pdf/frontron-fresh-20261014/IEEE-Software.docx`, `.pdf`, `.md`는 앱 native bytes와 일치한다. 검수 기록은 `output/word-qa/frontron-fresh-20261014/author-2/visual-qa-report.json`이다.

S&P 첫 저자 Word는 4,455단어·표 1개 allowance 250으로 4,705단어다. 일반 최소 4,900단어보다 195단어 부족해 내용 PASS만으로 최종 투고 준비 완료가 아니다. 공식 CFP 두 곳의 일반 Author Information 재명시를 확인한 수치는 `official-sp-numeric-verification.json`에 기록했다. 이 확인은 특정 특별호 선택이나 기존 연구의 동결 catalog 변경이 아니다.

정상 앱의 외부 검수 보완 입력에 `sp-external-feedback.txt`를 한 번 제출해 같은 분석·원자료에서 S&P만 보완했다. 2026-10-14 15:43:32 UTC / 10-15 00:43:32 KST `sp-revision-1/proof.json`은 새 집필·독립 심사 각 1회와 정상 종료 exit 0, 기존 과학 자료·Software·후보 저자 정보의 불변을 확인한다. S&P 누적 원고 2·심사 2·채택 원고 2, Software 1/1, 공통 분석 요청 2·코드/실험 0이다. 새 심사의 7개 기준·비교·기여는 모두 통과하고 차단 문제·후속 작업은 없다. 후보 저자 출력에는 추가 모델 호출 0이며 기존 정상 입력 정보를 재사용해 새 Word·PDF·Markdown 3개를 저장했다.

S&P 수정 저자본의 실제 Word는 5,192단어·표 1개 allowance 250으로 5,442단어이며 4,900–7,200 범위를 충족한다. 별도 최종 내용 감사 `quality-sp-revision-audit.json`과 `.md`는 차단 결함·근거 없는 주장 0, 소스 근거 13개·문서 근거 7개 일치와 초록 50단어·참고문헌 8개를 확인했다. Word 14쪽·native PDF 12쪽을 각각 전페이지 시각 검수했고 원 파일 SHA는 불변이다. Software까지 총 44쪽의 잘림·겹침·글리프·표·캡션을 확인했다. S&P 기록은 `output/word-qa/frontron-fresh-20261014/sp-revision-1/word-render-proof.json`과 `visual-qa-report.json`이다.

두 대안 원고 모두 내용·확인한 수치·페이지 기준에서 **저자 최종 검토와 투고 검토를 권할 수준**이다. 같은 연구이므로 두 매체에 동시에 독립 논문으로 제출하지 않는다. 후보 저자 정보는 출력에 반영됐지만 신원·저자 해석·권리·지원/이해관계·최종 제출 승인과 필요한 약력·사진은 확인해야 한다. 실제 투고나 학술지 채택을 완료·예측하지 않았다. 공개 0.14.20 설치본에는 이번 앱 수정이 없으며 기존 공개 릴리스는 보존했다.

전달 루트는 `output/pdf/frontron-fresh-20261014/`다. 두 매체의 Word·PDF·Markdown 6개와 최종 native 독립 심사 2개는 앱 bytes 그대로이고 최종 manifest에 결속한다. 정상 저장은 `author-2/proof.json`과 `sp-revision-1/proof.json`, S&P 전달 복사는 `native-delivery-copy-proof.json`이 확인한다. 전달 ZIP `Frontron-IEEE-manuscripts.zip`은 259,316 bytes, 16개 member의 모든 해시를 대조해 `bundle-verification.json` status passed다. ZIP SHA256은 `3468916fe6b0568d11646684220540ea4bbe0c31e454505296bc545ed4301fe4`, `manifest.json` SHA256은 `af75d68e68db703ebc135e824f77e14a42e99f47663ebf8fc25b9766e728db42`다. 별도 감사·QA·공식 수치 확인은 원고와 구분하며 SDK 원 응답·인증은 묶음에 포함하지 않는다.

## 현재 앱 흐름

저장소 가져오기→범위와 기여 설계→적합한 매체 선정→관련 문헌과 완전한 비교 문서 확보→공통 정적 분석→매체별 Feature Article→실제 Word/PDF와 형식 선검사→독립 내용 심사→실제 지적에 연결된 보완이다. 내용 PASS 후에도 실제 출력의 외부 검수 지적을 해당 매체의 현재 원고·심사에 결속해 정상 UI로 보완할 수 있다. 원 심사를 고치지 않고 새 원고·독립 심사를 추가하며 남은 예산을 사용한다. 범용 첫 원고·첫 심사는 중복 생성하지 않는다. 프로젝트 실행은 필수 조건이 아니며 정적 근거만으로 효과·성능·배포 결과를 주장하지 않는다.

완료 응답과 검증을 통과한 분석·원고를 구분한다. 미완료 출력·원고·심사를 먼저 수락하고, 실제 현재 심사의 지적이 있을 때 필요한 문서를 확보하거나 원고를 수정한다. 문헌·분석·집필·심사·문서 보완의 실패·중단도 횟수에 남긴다. 이번 새 연구의 횟수를 다시 초기화하지 않는다.

## 실제 앱의 투고 준비 상태

새 제출 행정 흐름은 한 매체 선택→약력·키워드·지원/이해관계 입력→새 제출용 Word/PDF 생성→그 새 파일의 분량·페이지와 저자 확인→제출 ZIP·manifest·편지·포털 입력 정보→공식 포털→사용자 확인 접수 기록이다. 과학 본문·원 심사·연구 횟수는 보존한다. 현재 실제 S&P `preparation-2`는 `awaiting_file_check`이며 최종 제출 묶음이나 접수 기록은 없다.

2026-10-14 16:45:12 UTC / 10-15 01:45:12 KST `ui-run-3/proof.json`은 이미 생성된 준비 2를 재생성하지 않고 정상 저장한 검증의 passed·정상 종료 exit 0을 확인한다. 새 Word·PDF·Markdown 3개는 native descriptor SHA와 일치한다. 연구 재시작·횟수 초기화·추가 모델 호출·새 행정 산출물·저자 승인·공식 사이트 열기·투고 이벤트는 0이며 두 이전 준비·실패·원자료·12개 모델 요청과 기존 원고 ZIP/manifest·build 결속은 불변이다.

준비 1의 provenance 검증 실패와 준비 2 저장 검증의 임시 파일 조회 실패는 `first-run-diagnosis.json`, `run-2-diagnosis.json` 및 원 failed proof에 보존했다. 준비 2는 정상 생성된 10개 등록 산출물을 유지하고 이후 저장만 확인했다. 새 제출 파일의 모든 변환 입력을 동결했고 과거 실패를 성공으로 덮어쓰지 않았다.

새 제출용 Word는 5,217단어·표 1개 allowance 250으로 5,467단어이며 Word 14쪽·native PDF 12쪽의 모든 26페이지 시각 검수를 통과했다. 키워드·후보 약력은 새 제출 파일에 포함되고 과학 본문은 보존한다. 이 결과는 앞선 원고 44페이지 검수와 별도다. 새 QA는 `output/word-qa/submission-flow-20261015/preparation-2/word-render-proof.json`, `visual-qa-report.json`이며 저장 파일은 `output/submission-design/actual-app-20261015/ui-run-3/saved/`에 있다.

저자 확인 7개는 모두 false이고 앱의 파일 QA 입력 5개는 빈 값이다. 지원·이해관계는 `저자 확인 대기`, 약력은 기존 후보 정보에 근거한 확인 전 초안이며 사진·실제 신원·권리·최종 승인도 확인되지 않았다. 페이지 검수를 저자 승인으로 사용하지 않았고 앱의 최종 확인 버튼은 비활성이다. 전체 준비·확인·접수 기록 흐름은 합성 자료로 검사했으며 실제 연구에서 사람의 승인이나 IEEE 접수를 만들지 않았다.

앞선 제출 패키지의 `ready-build-proof.json`과 2026-10-14 16:55:53 UTC / 10-15 01:55:53 KST `ui-run-5-readonly/proof.json`은 숨김 Playwright 읽기 전용 실행 passed·정상 종료 exit 0을 확인한다. 기존 준비 2·7개 미확인·QA 5개 빈 값과 공식 계정·보안 설정을 확인했으며 준비·저장·모델·포털·확인·접수 동작은 모두 0이다. 전체 workflow·12개 모델 요청·기존 ZIP/manifest는 불변이다. 앞선 `ui-run-4-readonly`의 entry 실행 전 검증 prelude 이름 오류는 별도 실패로 보존했다. 실제 준비 생성·저장과 새 제출 파일 26페이지 QA 증거는 해당 패키지에서 얻은 그대로 유지하며 새 ORCID 패키지의 실제 실행 증거와 구분한다.

## 다음 작업

ORCID 자동채움은 번호·공식 프로필 주소에서 공개 정보를 조회해 빈 이름·소속·이메일·공개 약력만 입력 초안에 반영한다. 기존 값은 유지하고 복수 현재 소속·이메일은 선택하며 공개하지 않은 항목만 직접 입력한다. 공개 약력이 없으면 직위·학력으로 만들지 않는다. 조회는 본인 인증·동의·저장이나 모델 호출이 아니다. `output/playwright/orcid-autofill-20261015/build-proof.json`과 `actual-app/proof.json`이 각각 패키지 결속과 실제 앱 검증 통과를 확인한다.

2026-10-15 12:17:57 UTC / 21:17:57 KST 실제 숨김 packaged 앱에서 사용자가 제공한 ORCID의 공개 이름·현재 기관을 자동으로 채웠다. 공개되지 않은 이메일·약력은 빈 편집 항목으로 남았고, 저장 전 수기 값 4개는 재조회해도 유지됐다. 화면을 다시 열어 저장 전 변경을 버리고 기존 저장 프로필이 그대로 복원되는 것을 확인했다. 정상 종료 exit 0이며 workflow 381개 파일의 변경·추가 0, 모델 요청 12개·기존 ZIP/manifest와 준비 2의 `awaiting_file_check`·저자 확인 7개 false·QA 5개 빈 값은 유지했다. 새 모델 요청·저자 저장·원고 출력·준비·포털·승인·접수 동작은 모두 0이다. 이미 검증한 기능을 다시 실행하려고 연구를 재시작하거나 횟수를 초기화하지 않는다.

1. 기존 과학 원고의 생성·독립 평가·검수와 전달 ZIP은 완료됐다. 실제 새 지적 없이 연구·집필·심사를 재실행하거나 초기화하지 않는다. 현재 제출 준비 2의 새 파일과 별도 QA를 저자가 직접 검토한다.
2. ORCID 공개 정보와 기존 저자 입력을 확인하고 누락된 연락 이메일·약력 등만 입력한다. 실제 키워드·지원/이해관계와 신원·권리·해석·AI 공시도 확인한다. Software를 선택할 때 필요한 사진을 준비한다. 현재 활성 S&P 준비에서 다른 매체로 바꾸려면 미제출 준비를 취소해 선택을 해제하며 이를 실제 학술지 철회로 기록하지 않는다.
3. 저자가 앱의 새 파일 QA 5개와 확인 7개를 명시적으로 입력하고 승인한 뒤 정상 기능으로 정확한 제출 묶음·manifest·편지·포털 입력 정보를 만든다. 정보가 바뀌면 새 제출 파일을 만들고 전체 페이지·분량·SHA를 다시 검수한다. 승인 값을 자동으로 채우지 않는다.
4. 선택한 매체의 고정 공식 Author Portal에서 저자가 로그인·업로드·최종 제출한다. 실제 접수번호·제출 시각을 받은 뒤 앱에 기록하며 이 기록은 사용자 확인이고 출판사 검증·채택이 아니다. 포털 열기나 파일 저장을 제출 완료로 설명하지 않는다.
5. 코드 변경이 필요하면 앱을 정상 종료하고 집중 회귀→Windows runtime/desktop 빌드→소스와 포함 bytes 결속→숨김 packaged Electron·Playwright 정상 UI 순서로 검증한다. 같은 연구 ID·원자료·실패·횟수와 제출 행정 이력을 유지한다.

다른 PC에서는 절대 경로·공식 계정 연결·포함 런타임 SHA를 다시 확인한다. 이 PC의 경로나 로컬 자료가 새 복제본에 있다고 가정하지 않는다.
