# 2026-10-20 정리 전 인계 기록

이 문서는 당시 누적 기록의 보존본이다. 과거의 초기화·진행 중·투고 권고 문구를 현재 지시나 평가로 사용하지 않는다. 현재 상태는 [다음 세션](../next-session.md)과 [검증 기록](../standalone-verification.md)을 따른다. 상대 문서 링크만 이동 위치에 맞췄으며 연구 자료·횟수는 변경하지 않았다.

---

# 2026-10-20 연구 설계 코드 개선과 기존 연구 보존 검증

최신 변경은 질문 선정·가까운 기존 방법 비교·실제 원문 확보·완료한 발견을 집필까지 연결하는 코드다. 새 저장소는 기존 문헌 계획과 공통 분석의 요청 안에서 질문 후보와 실제 근거를 비교한다. 새 contract3 보완 회차는 질문→네이티브 원문 확보→설계·분석 완성→선택적 내용 강화1회→독립 검토→집필→평가의 기본5/최대6회다. 일반 소스 비교가 기본이며 유한 프로토콜은 질문에 필요할 때만 사용한다. 자세한 흐름은 [연구 설계와 근거 보완](../research-development.md)에 있다.

**이번 실제 Frontron 연구의 새 SDK·예약·집필·심사·앱 연구 재개는0이다.** 기존 SDK35·예약24/24·심사10·수정8·작업9·종료contract2 round2·이력1개를 그대로 유지했다. Software와 S&P의 기존 점수·원고·투고 전 수정 권고도 바꾸지 않았다. 합성 자료로 확인한 내용 전달 경로를 실제 논문의 품질 상승이나 게재 준비 완료로 설명하지 않는다.

검증 증거는 `output/playwright/research-design-20261020/`에 있다.

- `checks.json`: **passed**, SHA `bde8eec8832b220d5e47e3e446d40b7c972ad9ec2dee6892a006912c747abdcc`. 최종 native **31개**, Desktop **134개**를 해당 로그와 생산 소스15개에 결속했다. native의 합성 성공 경로는 잠정 질문 변경, 최초·후속 실제 수집기의 원문 증명, 완료 비교/발견의 두 원고 본문 및 참고문헌 전달, 기본5회/강화6회 종료를 검증한다. 모델 응답과 HTTP 자료를 주입했고 Word/PDF 변환도 해당 흐름에서 대체했다. 실제 SDK·논문 품질 점수를 측정하는 검증은 아니다.
- `question-design-ui-proof.json`: production React 합성 상태 **30/30 passed**. 새 질문·선정·실제 수집0/2본문·강화/생략·정확한 artifact 저장·기존 회차 보존과 추가grant 없음을 검증했다. 테스트/production UI4파일의 실행 전후 SHA와 TAP 로그를 결속한다.
- `readonly-clone-preparation.json`: 실제 workflow1,176개 전체를 새 일반 파일 복제본에 복사했다. 원본과 파일 ID가 다르고 모든 bytes가 같다. 계정·외부 SDK dispatch는 복사하지 않았다.
- `closed-study-current-source.json`: 새 생산 소스로 복제본의 새 서비스2개에서 각각 `status`와 IPC `workflow.list`를 조회해 **passed/정상 종료0**이다. 품질 객체 전체·24/24·심사10·종료contract2·이전 이력·다음 작업없음이 유지됐다. 네트워크·collector·runner·runtime 시도0, 원본 constructor/operation0이다. SHA `b6f9c9dc85d4a341636ea85c6bb9ad9adc60d96474baef19969b52090c5f1b4d`.
- `preservation-final.json`: **passed**, SHA `71fa99ffef76915e91aceaf69287640f31725cf47fe8d6967da09cd861d5dd69`. 실제DB 포함workflow1,176개·source161개·SDK raw70/dispatch35·이전15개 증거/납품 디렉터리·ZIP·공식 템플릿·원고/심사/점수·저자/투고 상태의 정확한 바이트와 횟수가 시작 baseline과 같다.

단일 새 로컬 패키지 `desktop/release/research-design-20261020/win-unpacked/Paper Factory.exe`도 빌드·정적 검증 **passed**다. 실행 파일 SHA는 `1889ab05b39f9726ef466acbb5cdf8cabb6b2b8d06095f52f53d6b7b6a42b693`, 같은 증거 폴더의 `build-proof.json` SHA는 `a6155df1a11da84bbf858b8915730f27727b43bc3bc8517e49e3f6ada41ccdb7`이다. source123/native54/runtime2,443개와 공식 템플릿의 모든 bytes/SHA, 새3개 모듈의 소스·패키지 문법 검사6개를 검증했다. source binding은 `108681ae30845021c6e1da0a8ed97308befe0827bbdac34c9b607d7a2d38c953`이다. 미배포 산출물이며 **앱 기동·계정 접근·실제 연구 재개·추가 SDK는0**이다. 이 빌드 증거를 실제 새 원고 생산이나 개선된 점수의 증거로 사용하지 않는다.

이번 검증은 Windows에서 Docker 없이 진행했으며, 실제 입력 저장소 프로그램·실험·추가 모델 요청·저자 승인·포털 제출은 없다. 코드 검증과 복제본의 읽기 전용 호환성 확인이며 새 Frontron 원고의 품질 평가를 수행한 실행이 아니다. 마지막 실제 숨김 Electron·Playwright 원고 생산과 독립 평가는 아래2026-10-18 기록을 따른다.

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

# 2026-10-18 추가 6회 실제 앱 실행: 진행 중 체크포인트

최신 상태: 새 패키지 `frontron-renewed-contract-20261018`의 실제 숨김 앱에서 동일 원응답 무호출 재수락과 현재 근거 독립 재감사가 통과했다. 현재 추가5/6회·SDK34·예약23/24로 두 매체 집필 요청 `d2aa85f4-90e9-4050-a5c9-a352332a3b5c` 진행 중이며, 아직 새 원고 출력·최종 평가는 완료 전이다. 이 요청의 완료가 불명확하면 재전송하지 않는다. 아래는 첫 실행과 복구 경위다.

현재 round2는 추가3/6회·총 SDK32·영구 예약21/24이며 새 원고0이다. 첫 숨김 실제 앱 실행은 운영/보존 검증 passed·정상종료0이지만 연구 근거 수락 실패로 닫혔다. 실제 연구 완료나 투고 품질 통과를 뜻하지 않는다. 증거는 `output/playwright/frontron-renewed-20261018/actual-app/proof.json`이다. 기존 모든 자료·원 응답·거절·심사·점수·누적 횟수·닫힌 round1·저자/투고 상태는 보존했다.

수정 원 응답을 변경하지 않고 공개 스키마와 내부 참조/phase 검사 사이의 불일치를 해결했다. 원 응답 전체 재계산과0.94GB 복제본의 재수락·멱등·원 기록 보존·남은3회·후속 prompt 용량 검사가 통과했다. SHA 확인 후 source5+test2/UI3파일을 생산 적용했고 생산 순수82개·Desktop68+deadline3 검사가 통과했다. 임의 근거·결과·점수 수정을 허용하지 않는다. 실제 원본의 무호출 재수락과 남은 최대3회의 독립 재감사→집필→평가는 아직 실행 전이다. 새 패키지·재개·원고·독립 평가 검증도 아직 완료되지 않았다. 정확한 중간 상태와 실행 경로는 [다음 세션 기록](../next-session.md)의 첫 항목을 따른다. 아래는 이번 추가 실행 전의 검증 기록이다.

---

# 2026-10-18 집필 전 연구 작업 생성·재감사 교정

새 기본 공통 분석은 구체적인 구현 단계·대안 비교·추가 분석 후 판단을 `work_products`로 생성하고 네이티브 보고서와 동결한다. 첫 집필·심사 전에 정확한 분석 원본의 SHA·전체 본문·페이지/EOF를 요구한다. 새 보완 계약은 설계+근거를 한 요청으로 합쳐 보완 후 독립 재감사까지 최대6회에 넣는다. `ready_to_write=false` 또는 수정 전 감사로 집필하던 결함을 교정했고, 현재 근거·산출물·실제 감사 원본의 결속을 집필 전과 수락 때 확인한다.

기존 Frontron **SDK29·영구 예약18/18·닫힌6/6**과 원자료·원고·점수·심사·실패·저자 확인 상태를 유지한다. 이번 코드 검증은 새 과학 호출·새 원고·재채점으로 품질을 증명하는 작업이 아니다. 새 흐름으로9점 또는 투고 가능 품질에 도달했다고 주장하지 않는다. 실제 규칙이 선언한 정책을 구현하는지와 게재 가치는 독립 평가 대상이다. 같은 판단을 확인하는 결과도 허용하며 추가 기여 미입증을 표시한다.

첫 새 packaged 읽기 전용 실행은 이전 분석 거절 오류 위치가 `['analysis']`에서 `[]`로 바뀐 탓에 `ARTIFACT_CHANGED`로 실패했다. 실제 원본 변경은 없었으며 실패 증거·null 파생 캐시는 `output/playwright/frontron-method-20261018/`에 별도 보존했다. 오류 위치 계약만 복구한 뒤 packaged Python + 수정 소스로 실제 읽기 전용 조회3종과 원본1,038개 SHA 불변을 확인했다. 원 응답·거절·strict 검증은 유지한다. 새 첫 경로 회귀6개(위치 계약 회귀 포함)도 통과했다. 캐시 수동 복사는 하지 않는다.

이어서 선택 필드 생략이 허용된 새 작업 산출물 응답을 원문 변경으로 오인하던 실패를 재현했다. 비교용 직렬화에 `exclude_unset=True`를 사용한 두 곳의 수정으로 해결했고 최종 첫 경로7개 검사가 통과했다. 원문과 검증 조건을 바꾸지 않았다. `portfolio-optional-fields-proof.json`은 재현 실패·최종 통과·실제 소스/검사 SHA를 구분한다.

최종 실제 실행은 **passed/정상 종료0**: `desktop/release/frontron-method-verified-20261018/win-unpacked/Paper Factory.exe`, 증거 `output/playwright/frontron-method-20261018/actual-app-readonly-2/proof.json`. 실제 숨김 Electron·Playwright, 결과 탭1회, 새로고침/재개/grant/save/포털/사람 승인0, 추가 SDK0이다. 원본 frozen1,037개/source161개·SDK raw58/dispatch29·기존 모든 실행/납품/실패 증거 SHA, 모든 기존 원고/심사/점수/저자/제출 상태를 보존했다. null 화면 캐시는 정상 verified listing으로 복구했고 수동 복원하지 않았다. SDK29/native18·closed6/6은 그대로다.

최종 `checks.json`은 중복 합산 없이 Desktop52(+문구1), 초기 경로140/후속6/최종7, 계약50, 순수33 검사를 해당 소스 SHA로 묶는다. `build-proof-v3.json`은 source118/native51/runtime2440개·최종 source binding `0454a1a777342d69db11d872ee2b09e5142441e6f03ab9940df9f0e96a792db1`을 결속한다. 이 실제 앱 검증은 기존 결과의 정상 표시와 보존을 확인했으며 새 과학 원고의9점·투고 권고를 입증한 것이 아니다.

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

# 실제 앱 품질 보완 검증

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


2026-10-18 재평가 정정: 아래 Software의 투고 권장 표현은 10월 15일 당시 판단이며 현재는 철회한다. 근거 인용·조건부 추론·분량·페이지 검사 통과와 충분한 게재 가치를 구분하지 못했다. 단일 사례에서 기존 보안 지침보다 제공하는 추가 판단 가치, 검토 가능한 개선 설계와 적용 근거를 실질적으로 보완해야 한다. 내부 심사의 기여 항목도 있었지만 공식 문서와 소스만으로 실무 교훈이 충분하다고 판단한 기준이 관대했다. 현재 권고는 **투고 전 실질 보완 필요**이며 점수나 출판사의 판정은 아니다. 원고·원 심사·자료·횟수·QA 기록은 변경하지 않았고, S&P의 현재 게재 가치는 이번에 재평가하지 않았다.

2026-10-15 KST 현재 체크포인트. 검증 대상은 Docker 없이 실행하는 실제 Electron 앱과 공식 계정 모델 호출이다. 합성 회귀·패키지 무결성·실제 원고 생성·투고 준비도는 각각의 증거로 기록한다. 이번 새 연구의 최신 상태는 [다음 세션](../next-session.md)과 함께 갱신한다.

`output/`·`.paper-factory/`와 빌드 경로는 이 Windows PC의 로컬 자료이며 Git에서 제외한다. 원고·개인정보·인증·실제 모델 요청을 저장소나 릴리스에 게시하지 않는다. 상대 경로는 저장소 루트 기준이고 새 복제본에는 증빙 파일이 없다.

## 초기화와 새 연구

사용자의 최신 전체 삭제 요청에 따라 2026-10-14 14:06:17 UTC 이전 연구·원자료·원고·심사·횟수·전달 ZIP 760개 파일, 60,455,815 bytes를 삭제했다. 대상은 설치 앱 `%APPDATA%/Paper Factory Standalone`과 실제 검증 앱 `.paper-factory/jizura-new-01420-20261008-04e3b1a0-4ee/app-data`의 연구·워크플로 및 과거 실제 출력이다. 자체 계정 저장소·연결 설정·소스·포함 런타임·설치 파일은 유지했다.

이번 증빙 루트는 `output/playwright/frontron-fresh-20261014/`다. `reset-verification.json`은 삭제 대상 없음과 보존 항목을, `empty-stores-before-app.json`은 두 저장소의 jobs/workflows 0을, `empty-app-before-start.json`은 실제 앱의 빈 연구·엔진 ready·오류 없음 상태를 확인한다. 연구 시작 후 저장소가 계속 비어 있다고 설명하지 않는다.

새 연구는 `research-7008ca97102a`, 입력은 `https://github.com/andongmin94/frontron`이다. 14:09:19 UTC 실제 앱의 정상 입력과 **연구 시작** 한 번으로 생성했다. 고정 commit `3a7da2822721801db88ea059d204c8c6c622fab4`에서 189개 파일을 내려받고 분석용 161개 파일, 1,121,077 bytes를 보존했으며 해시가 모두 일치한다. 이전 연구나 원고를 가져오지 않았다.

## 실제 패키지와 공식 연결

| 항목 | 이번 실행 경로/증거 |
| --- | --- |
| 작업공간 | `C:/Users/Andongmin/Desktop/repository/paper-factory` |
| 실제 데이터 | `.paper-factory/jizura-new-01420-20261008-04e3b1a0-4ee/app-data` |
| 최초 executable | `desktop/release/final-ready-0.14.20-20261014/win-unpacked/Paper Factory.exe` |
| 최초 executable SHA256 | `6a655a7f33264a75cbeb9841c58a162f08da0c2d23e5d5608ce58a6392726a3d` |
| 현재 executable | `desktop/release/orcid-autofill-20261015/win-unpacked/Paper Factory.exe` |
| 현재 executable SHA256 | `1d96593555e63505059d8fc767052d3f8a4af69ca8a4cfb9ef3a84592a0916ab` |
| 정상 입력 | `normal-user-input.json` |
| 공식 연결·모델 목록 | `official-connection-proof.json` |
| 숨김 packaged 창 | `window-launch-proof.json` |
| 첫 원고 생성 결과·정상 UI·저장·종료 | `resume-2/final-summary.json` / `resume-2/proof.json` |
| 후보 저자 출력·6개 저장·정상 종료 | `author-2/proof.json` |

증거 JSON은 위 이번 증빙 루트 기준이다. 공식 자체 계정의 `connected=true`, `sharing=true`, 실제 모델 목록과 작성·독립 평가 모델 `gpt-6.1-sol`을 확인했고 `sdkMocked=false`다. 계정 토큰이나 다른 앱 인증 파일을 읽거나 복사하지 않는다.

최초 실행은 공개 NSIS와 같은 unpacked payload, 완료 재개는 아래 계약 수정을 포함한 미배포 로컬 패키지다. 두 실행 모두 `isPackaged=true`, 버전 0.14.20과 runtime/repository analysis ready를 확인했다. 일회용 검증 prelude는 패키지 entry 실행 전 데이터 경로를 자체 연구 저장소로 매핑하고 창에 `show:false`, `offscreen:true`, `backgroundThrottling:false`를 적용했다. production controller·SDK·engine·모델·IPC와 native 변환을 사용했다. sandbox·context isolation·web security와 Node isolation을 유지하며 Playwright로 정상 입력·모델 선택·시작·재개를 조작했다. 원고·심사·모델 응답은 주입하지 않았다. PowerShell에서 숨김 helper를 시작할 때는 `-WindowStyle Hidden`을 사용한다.

## 새 원고 결과와 실제 외부 보완

첫 분석 응답은 `INVALID_ARGUMENT: Analysis observation evidence must bind unique existing identifiers`로 수락되지 않았다. 첫 정상 UI 재개는 같은 완료 응답을 재검증해 추가 모델 호출이나 횟수 증가 없이 정상 종료했다. 원인은 분석 스키마 계층과 근거 ID 계약의 불일치였다. 스키마를 수정하고 원 응답·원 자료·횟수를 보존한 채 엄격한 native 검증을 통과해야 하는 보정 요청을 한 번 허용했다. 보정도 실제 분석 요청 횟수에 포함하며 반복 보정이나 검증 조건 완화는 하지 않는다.

수정된 실제 패키지의 같은 연구에서 정상 **IEEE 매체별 미완료 투고본 재개**를 한 번 눌렀다. 2026-10-14 15:03:34 UTC / 10-15 00:03:34 KST 최종 생성 스냅샷은 `busy=false`, `error=null`, `phase=idle`, `pipeline=paused`다. 분석 보정 요청을 수락했고 두 매체 원고·독립 평가·실제 출력이 완료됐다.

| 실제 누적 요청/산출물 | S&P 보완 완료 시점 |
| --- | --- |
| 설계 / 문헌 | 1 / 1 |
| 공통 분석 요청 / 채택된 분석 | 2 / 1 |
| 공통 원고 / 코드 / 실제 실행 | 0 / 0 / 0 |
| Software 집필 / 독립 심사 / 채택 원고 | 1 / 1 / 1 |
| S&P 집필 / 독립 심사 / 채택 원고 | 2 / 2 / 2 |
| 실제 매체별 Word/PDF/Markdown | 생성·정상 저장 완료 |
| 앱 scientific/content ready | 두 매체 모두 true / true |
| 별도 내용·확인한 수치·전페이지 검수 | 두 매체 통과 |
| 최종 저자·권리·제출 승인 | 미확인, 실제 투고 없음 |

두 새 심사의 7개 기준·비교·기여는 모두 통과했고 차단 문제·후속 작업은 비어 있으며 native `allContentReady=true`다. Word·PDF·Markdown 6개를 정상 저장 버튼으로 내보내 bytes/SHA를 대조하고 앱 정상 종료 exit 0을 확인했다. 재개 전 원 파일의 변경·누락은 0이며 `resume-2/immutable-research-final.json`에 기록했다. 첫 실패와 분석 요청 1회를 삭제하거나 승인으로 바꾸지 않았다. 과거 삭제한 연구의 원고·심사·페이지 검수·저자 ZIP을 이번 결과로 사용하지 않는다.

정상 후보 저자 정보 출력 `author-2/proof.json`은 Word·PDF·Markdown 6개 저장·정상 종료 exit 0과 추가 모델 호출 0을 확인한다. 최종 저자·권리·선언 승인은 추정하지 않는다.

Software 제목은 *Authorize the Operation, Not Just the Renderer: Maintaining Native Bridges in Frontron*이다. 별도 내용 감사 `quality-software-audit.json`과 `.md`는 단일 사례의 근거·비교·실무 교훈과 확인한 수치 형식을 통과시켜 저자 최종 검토와 투고 결정을 권한다. 실제 Microsoft Word의 3,199단어에 표 1개 allowance 250을 더한 3,449단어는 한도 안이다. Word 10쪽·native PDF 8쪽을 각각 전페이지 시각 검수했고 잘림·겹침·누락 글리프·표 문제는 없다. 별도 숨김 Word read-only COM으로 렌더링하고 원 DOCX를 저장·변경하지 않았다. canonical renderer의 LibreOffice 미설치 실패도 기록하고 실제 Word 대안 검수를 사용했다. 증거는 `output/word-qa/frontron-fresh-20261014/author-2/word-render-proof.json`과 `visual-qa-report.json`이다. `output/pdf/frontron-fresh-20261014/IEEE-Software.docx`, `.pdf`, `.md`는 앱 native bytes와 일치한다.

S&P 제목은 *What a Compromised Renderer Can Still Ask For: Authorizing Native Operations in Electron Bridges*이다. 첫 원고의 앱 내용 평가는 통과했고 별도 내용 감사에서도 실질적인 근거 없는 보안 주장은 발견하지 않았다. 그러나 실제 저자 Word는 4,455단어·표 1개 allowance 250으로 4,705단어다. 일반 최소 4,900단어보다 195단어 부족해 최종 형식 검수에서 차단됐다. 앱의 내용 PASS를 최종 제출 준비 완료로 해석하지 않는다.

현재 공식 CFP [Real-world Security Impact](https://www.computer.org/digital-library/magazines/sp/cfp-real-world-security-impact)와 [One Decade of GDPR Challenges](https://www.computer.org/digital-library/magazines/sp/cfp-one-decade-gdpr-challenges)가 일반 Author Information을 명시적으로 재명시한 규정을 읽어 확인했다. 요구는 본문·초록·키워드·참고문헌·약력·표 텍스트를 포함한 4,900–7,200단어에 시각 자료당 250단어를 더하는 방식, 초록 최대 50단어·참고문헌 최대 15개다. 이번에 일반 Author Information 본문을 직접 다시 읽었다고 주장하지 않으며 특정 특별호를 투고처로 선택하지 않았다. 확인 기록은 `official-sp-numeric-verification.json`이다. 새 연구의 안내에는 확인한 일반 수치를 반영하지만 기존 연구의 동결 catalog는 바꾸지 않았다.

이 실제 분량 결함과 필요한 실질 보완을 `sp-external-feedback.txt`에 기록해 정상 앱의 외부 검수 보완 UI에 한 번 입력했다. 보완은 현재 S&P 원고·원 심사에 결속하고 같은 채택 분석과 원자료를 사용하며 기존 긍정 심사·원고·실패·횟수와 Software 1/1을 보존했다. 제안된 정책 사례·권한 만료·회수·비용·잔여 위험을 근거 범위 안에서 보완하는 새 집필·독립 평가를 각각 한 번 완료했다. 실험이나 구현 효과를 만들어 분량을 늘리지 않았다.

2026-10-14 15:43:32 UTC / 10-15 00:43:32 KST `sp-revision-1/proof.json`은 status passed·정상 종료 exit 0, 모든 이전 과학 자료·Software bytes·후보 저자 정보의 불변을 확인한다. 새 실제 모델 요청은 집필 `130e33f0-879f-4ee4-83dc-ff3f3ae078b8`과 독립 심사 `264b4046-25e3-46eb-ba7a-5f573cec67ca` 두 개다. 전체 연구는 journal의 별칭·상태 중복을 제외한 실제 UUID 12개이며, 후보 저자 출력 모델 호출은 0이다. 누적 S&P 집필·심사·채택 원고는 2/2/2, Software는 1/1/1, 공통 분석 요청은 2로 유지됐다. 새 심사의 7개 기준·비교·기여가 통과하고 차단 문제·후속 작업은 없다.

기존 정상 UI에서 저장한 후보 저자 정보를 재사용해 수정 원고의 Word·PDF·Markdown 3개를 정상 저장했다. 실제 Microsoft Word 16의 5,192단어에 표 1개 allowance 250을 더한 5,442단어는 4,900–7,200 범위 안이다. Word 14쪽·native PDF 12쪽을 각각 모든 페이지 시각 검수했고 잘림·겹침·누락 글리프·표·캡션 문제는 없다. read-only 렌더링 전후 원 DOCX와 native PDF SHA는 불변이다. Software까지 총 44쪽을 확인했다. S&P의 분량·렌더·전페이지 증거는 `output/word-qa/frontron-fresh-20261014/sp-revision-1/word-render-proof.json`과 `visual-qa-report.json`이다.

별도 수정본 내용 감사 `quality-sp-revision-audit.json`과 `.md`는 차단 결함·근거 없는 주장 0, 소스 근거 13개·문서 근거 7개 일치, 초록 50단어·참고문헌 8개를 확인했다. 내용과 확인한 수치 기준에서 저자 최종 검토와 투고 검토를 권한다. 두 원고 모두 이 수준에 도달했으며 학술지 채택은 예측하지 않는다. 후보 저자 정보는 정상 앱 출력에 반영됐지만 신원·저자 해석·권리·지원/이해관계·최종 제출 승인과 필요한 약력·사진은 남아 있다. 두 원고는 같은 연구의 대안 투고본으로 두 곳에 동시에 독립 논문으로 제출하지 않는다.

## 최종 전달 묶음

전달 루트는 `output/pdf/frontron-fresh-20261014/`다. 두 매체의 Word·PDF·Markdown 6개와 최종 native 독립 심사 2개는 bytes 그대로 전달하고 최종 manifest의 SHA와 대조했다. 정상 저장 증거는 `author-2/proof.json`과 `sp-revision-1/proof.json`, S&P 전달 복사는 `native-delivery-copy-proof.json`이다. 별도 내용 감사·QA·공식 수치 확인과 원고를 구분했다. 인증·SDK 원 응답은 묶음에 포함하지 않았다.

`Frontron-IEEE-manuscripts.zip`은 259,316 bytes, 16개 member의 모든 해시를 대조했으며 `bundle-verification.json` status passed다. ZIP SHA256은 `3468916fe6b0568d11646684220540ea4bbe0c31e454505296bc545ed4301fe4`, `manifest.json` SHA256은 `af75d68e68db703ebc135e824f77e14a42e99f47663ebf8fc25b9766e728db42`다. 이 ZIP은 전달 원고 묶음이며 앱 계정·전체 연구 저장소의 복원 패키지가 아니다.

앱 흐름은 저장소 확보→범위·기여 설계→적합한 매체 선정→문헌·완전한 비교 문서 확보→공통 정적 분석→매체별 원고→Word/PDF와 형식 선검사→독립 내용 심사→실제 지적에 따른 보완이다. 내용 PASS 이후에도 실제 출력의 외부 검수 지적을 정상 UI로 입력해 해당 매체의 원고·독립 심사를 추가할 수 있다. 원 심사와 이력을 고치지 않고 남은 매체별 예산을 사용한다. 프로젝트 코드 실행은 원고 생성의 필수 조건이 아니며 실행·효과·성능 근거를 꾸며내지 않는다. 완료 응답 수와 검증을 통과한 분석·원고 수를 구분한다.

## 실제 제출 파일 준비와 승인 경계

새 [투고 흐름](../submission-workflow.md)은 연구 원고 생성 이후의 제출 행정을 별도 native 모듈에 저장한다. 한 매체 선택·약력/키워드/지원/이해관계 입력→새 제출용 Word/PDF 생성→그 새 파일 QA와 저자 명시적 확인→제출 ZIP/manifest/편지/포털 입력 정보→고정 공식 Author Portal→사용자 확인 접수 기록 순서다. 파일 생성은 `awaiting_file_check`, 확인한 묶음은 `prepared`, 실제 접수번호·시각을 사용자가 기록해야 `submitted`다. 상태와 원고·저자·파일 SHA를 결속하며 포털 열기·파일 저장은 접수가 아니다. 준비 취소와 실제 학술지 철회를 구분하고 제출 후 원고가 바뀌어도 제출 당시 접수 기록은 유지한다.

이번 실제 연구는 S&P 준비 2의 `awaiting_file_check`까지 검증했다. 후보 약력·키워드를 새 제출 파일에 추가했으며 기존 과학 본문을 그대로 복원할 수 있다. 지원·이해관계는 `저자 확인 대기`, 저자 확인 7개는 모두 false, 앱의 파일 QA 입력 5개는 빈 값이고 최종 확인 버튼은 비활성이다. 최종 제출 ZIP·편지·확인·접수 기록은 생성하지 않았으며 공식 사이트 버튼도 누르지 않았다. IEEE 로그인·업로드·최종 제출과 저자 승인을 완료 처리하지 않는다.

증빙 루트는 `output/submission-design/actual-app-20261015/`다. 준비 1은 provenance 경계 검사에서 변환 helper 입력과 소스 경계 차이를 발견해 실패했고, 준비 2는 새 파일 생성은 완료했으나 저장 검증의 atomic temp 파일 조회가 실패했다. 원 두 failed proof와 `first-run-diagnosis.json`, `run-2-diagnosis.json`을 보존했다. 준비 2의 등록 산출물 10개와 이전 연구를 유지하고 새 생성 없이 저장만 다시 검증했다.

`ui-run-3/proof.json`은 2026-10-14 16:45:12 UTC / 10-15 01:45:12 KST passed·정상 종료 exit 0을 확인한다. 기존 준비 2의 실제 제출 Word·PDF·Markdown 3개를 정상 저장했고 native descriptor SHA와 일치한다. 재생성·새 행정 산출물·연구 초기화·추가 모델 요청·저자 승인·포털/접수 동작은 0이다. 이전 과학 자료·두 준비·실패·12개 모델 요청·기존 원고 ZIP/manifest와 실행 build 결속은 모두 불변이다.

새 제출 Word는 실제 Microsoft Word 16에서 5,217단어이며 표 1개 allowance 250을 더한 5,467단어가 S&P 4,900–7,200 범위 안이다. Word 14쪽·native PDF 12쪽, 모든 26페이지를 각각 시각 검수해 잘림·겹침·글리프·표·캡션·키워드·후보 약력 표시가 통과했다. 원 DOCX/PDF를 저장·변경하지 않았다. 이 QA는 앞선 과학 원고 44페이지 QA와 별도이며 신원·권리·실제 약력·저자 승인·투고 완료를 확인하지 않는다. 증거는 `output/word-qa/submission-flow-20261015/preparation-2/word-render-proof.json`, `visual-qa-report.json`이다.

실제 새 DOCX SHA256은 `a8d9fda6bf0b0dbf71e2a5d26b8096389b6b2a5c8d108ac89286d75f9c325b2f`, PDF SHA256은 `4961d1d11e366b3024d2e8d4a0a76319f4095be1a640b0d5a67192e28e705df3`이다. 저장본은 `output/submission-design/actual-app-20261015/ui-run-3/saved/`에 있다. 지원/이해관계와 실제 약력·사진·7개 저자 확인, 새 파일 QA 입력은 사람의 다음 작업이며 확인 값을 자동으로 만들지 않는다.

## ORCID 공개 정보 자동채움 구현

저자 입력에 ORCID 번호나 공식 프로필 주소를 넣으면 공개 이름·현재 소속·이메일·약력을 조회해 빈 항목에만 반영한다. 저장된 값·직접 입력한 값은 유지하며 복수 현재 소속·이메일은 사용자가 선택한다. 공개 약력이 없을 때 직위·학력으로 새 약력을 만들지 않는다. 조회 결과는 저장 전 초안이며 본인 인증·동의·저자 승인이나 제출 확인이 아니다. 조회만으로 연구·심사·횟수·원고·제출 준비를 바꾸지 않는다.

공개 API의 person/employments/educations 고정 경로를 인증 없이 읽는다. 요청은 20초·응답 1MiB 한도로 제한하고 프로필의 현재 기관을 중복 제거한다. 저자 약력은 선택 값이며 빈 약력을 추가해 기존 저자 해시를 바꾸지 않는다. ORCID 구현의 native 저자 64개·기존 저자 출력 10개, desktop 집중 81개(ORCID 9·저자 14·제출 5·publication 53)와 타입·빌드가 통과했다. 합성 검사 통과를 사용자의 실제 ORCID 조회나 새 패키지 실행 통과로 설명하지 않는다.

새 Windows 패키지에서 사용자가 제공한 ORCID의 실제 공개 API·정상 UI를 검증했다. `output/playwright/orcid-autofill-20261015/actual-app/proof.json`은 2026-10-15 12:17:57 UTC / 21:17:57 KST passed·정상 종료 exit 0이다. 실제 SDK·native·ORCID API를 사용했고 mock 없이 숨김/offscreen·sandbox·context isolation·Node integration off를 유지했다.

공개 이름·현재 기관은 빈 항목에 자동으로 채워졌고 중복 기관은 하나로 표시됐다. 공개 이메일·약력은 없어 빈 편집 항목으로 남았다. 저장 전 수기 값 4개를 넣고 재조회해도 보존됐으며 화면을 다시 열면 저장 전 변경을 버리고 기존 저장 저자 정보가 그대로 복원됐다. 이를 본인 인증이나 최종 저자 동의로 해석하지 않는다.

기존 workflow 381개 파일의 변경·추가 0, 모델 요청 12개·기존 원고 ZIP/manifest·저장 저자 정보·제출 준비 2와 실행 build는 불변이다. 새 모델 요청·저자 저장·출력·준비·포털·확인·접수는 모두 0이며 저자 확인 7개 false·QA 입력 5개 빈 값을 유지했다. 앞선 제출 패키지의 실제 준비·저장·26페이지 QA와 원고 생성·44페이지 QA 증거는 별도로 보존한다.

## 현재 미배포 로컬 패키지

공개 릴리스를 덮어쓰지 않고 ORCID 자동채움·분석 계약·외부 검수 보완·실제 투고 준비 흐름이 포함된 Windows 패키지를 `desktop/release/orcid-autofill-20261015/win-unpacked/`에 만들었다. 버전 표기는 0.14.20이지만 공개 설치본과 bytes가 다르며 아직 배포하지 않았다. 현재 결속 기록은 `output/playwright/orcid-autofill-20261015/build-proof.json`이다. 앞선 제출 패키지의 `output/submission-design/actual-app-20261015/ready-build-proof.json`, `final-build-proof.json`과 원고 생성 패키지의 증거도 보존한다.

| 로컬 패키지 결속 항목 | SHA256 |
| --- | --- |
| executable | `1d96593555e63505059d8fc767052d3f8a4af69ca8a4cfb9ef3a84592a0916ab` |
| ASAR | `961779f55649ba16a465e046e7c4285d48b916e25ece1a969b3a2698e5b52864` |
| runtime inventory | `da8e10d274b0de291b166daa1579808a730a530b30c976bb20dc66f67bf0cef8` |
| production 입력 121개 | `e88c6dd0b11209e2269af54e3e4a4fe6ea4b9242fd534a284f373dcfa1091261` |

runtime 2,231개 파일·474,654,303 bytes의 전체 SHA와 native 소스·데이터·폰트 결속 39개, production 입력 121개와 ASAR asset 결속이 일치한다. 이 패키지의 실제 ORCID UI 검증·정상 종료와 실행 전후 결속 불변을 확인했다. 기존 제출 준비 2·저장 파일·26페이지 QA와 앞선 패키지의 아래 읽기 전용 실행 증거도 유지하며 새 ORCID 검증과 구분한다.

앞선 `submission-ready` 패키지의 `output/submission-design/actual-app-20261015/ui-run-5-readonly/proof.json`은 2026-10-14 16:55:53 UTC / 10-15 01:55:53 KST passed·정상 종료 exit 0이다. 공식 계정 connected/sharing, 숨김 창·sandbox·context isolation·Node integration off와 기존 준비 2의 `awaiting_file_check`, 저자 확인 7개 false·QA 입력 5개 빈 값을 확인했다. 새 준비·행정 산출물·저장·모델 요청·공식 사이트·확인·접수 동작은 모두 0이며 전체 workflow·12개 모델 요청·기존 원고 ZIP/manifest를 유지했다. `ui-run-4-readonly`는 entry 실행 전 prelude 이름 allowlist 불일치로 실패했고 원 증거·exit 0·모델 0·자료 보존을 별도로 기록했다. 이 실패를 통과로 덮어쓰지 않았으며 새 ORCID 기능의 실행 증거로 사용하지 않는다.

## 보존한 공개 0.14.20 Windows 배포본

이번 초기화는 소프트웨어 배포·합성 검증 자료를 삭제하지 않았다. 최종 NSIS와 포함 파일의 무결성 기록은 `output/playwright/package-smoke-20261013-8e4bfa7/final-ready/`에 남아 있다.

| 패키지 항목 | 값 |
| --- | --- |
| NSIS | `desktop/release/final-ready-0.14.20-20261014/Paper Factory Setup 0.14.20.exe` |
| NSIS 크기 / SHA256 | 213,342,831 bytes / `968f7bd258858eccb5ecf45675099c3caa5851373fec2f9487fe2ec78c9c523e` |
| ASAR SHA256 | `518fc837a3c2e4f2226204f0a2ecab03bf6d5d2f6e631da6069d4da2e838b3bb` |
| runtime inventory SHA256 | `f5a2d7cf7fcbef5949ad613b7f1bc073bf4ca0becd25f279c5e85d40914ada77` |
| 최종 production 입력 114개 SHA256 | `f3e9ddca05ad03edf1748a263a470682907f5c927089cbc84a5d45f4fb259183` |

NSIS 압축 무결성과 핵심 payload 4개, ASAR 7,668 members, runtime 2,230개 파일·474,589,236 bytes의 전체 SHA, Python 소스 33개와 포함 bytes의 일치를 확인했다. 포함 Python·Node·Pandoc·Typst·폰트로 동작하며 시스템 Docker·TeX 설치를 요구하지 않는다. Setup과 unpacked 앱은 `NotSigned`다. 실제 시스템 설치·제거와 macOS 실행은 검증하지 않았다.

짧은 자체 데이터 경로 `tmp/ps14-2`에서 숨김 packaged 앱의 전체 runtime/repository analysis ready, 보안 설정, 빈 계정·모델·연구와 정상 종료 exit 0을 확인했다. 같은 binary/runtime의 긴 데이터 경로 검사에서 발생한 GPU cache 오류·Chromium 종료 시간 초과는 원 실패로 보존했고 짧은 경로의 통과로 덮어쓰지 않았다. 실제 패키지의 `app.asar` 물리 파일 SHA는 내장 `original-fs`로, ASAR 내부 runtime binding JSON은 기존 Electron 가상 fs로 확인한다.

검증한 설치 파일·blockmap·공개 checksum manifest는 [0.14.20 릴리스](https://github.com/andongmin94/paper-factory/releases/tag/v0.14.20)에 게시했다. 공개 태그 commit은 `aa75606c01772d8df45a48d90753bbaabc20f455`이며 익명 다운로드와 세 asset digest가 일치한다. 공개 checksum manifest SHA256은 `4ab81c9fba39b37553a0dc9707d5d219c157ec29d6aafcc18c7608c5840d6711`이다. 공개 확인 기록은 `output/releases/0.14.20/final-public-verification.json`이다. 연구 원고나 인증은 배포하지 않았다.

## 소프트웨어 회귀 검증 범위

현재 제출 흐름의 native 43개와 converter helper 1개, desktop 집중 159개·최종 guard 5개 부분집합, 숨김 합성 UI 1개가 통과했다. 합성 자료로 준비·파일 QA·저자 확인·ZIP/편지·사용자 확인 접수 기록의 전체 흐름을 검사했다. 실제 Frontron 연구는 파일 생성·정상 저장·별도 시각 검수까지만 진행했으며 사람의 승인·공식 포털 접수는 검증하지 않았다.

마지막 사진 입력 수정은 한글·`.JPG` 파일명을 MIME에 맞는 `author-photo.jpg`/`.png`로 정규화하며 파일 bytes를 유지한다. 기존 합성 UI 시나리오를 이 JPEG 경우까지 확장해 1/1 통과(11.1초)와 TypeScript 검사를 완료했다. 동일 시나리오의 확장 재검증이며 합성 UI 수를 2개로 합산하지 않는다. 실제 연구에 사진이나 저자 승인을 추가하지 않았다.

앞선 외부 피드백 구현의 desktop 138개, native 피드백 15개와 기존 portfolio·분석 보정 49개도 통과했다. 아래 이전 배포본의 회귀 수를 현재 변경을 다시 검사한 수로 합산하지 않는다.

2026-10-12 정리 후 타입·빌드, desktop Node 425개, SDK 48개(운영체제 전용 1개 제외), 숨김 Chromium 29개, Electron 13개가 통과했다. Python 선택 목록의 완료 보고·분할 검사·정정 재검사를 합산한 결과는 3,113 통과·macOS 전용 2 제외이며 누락·미해결 실패는 0이다. 초기 실패와 정정 이력은 로컬 `tmp/cleanup-native-final-coverage-20261012.json`, `tmp/cleanup-native-final-node-outcomes-20261012.json`, `tmp/cleanup-native-repaired-files-pass-receipts-20261012.json`에 유지한다. 합성 자료의 검사 수를 실제 연구·심사·실험 횟수에 합산하지 않는다.

공개 배포본의 저자 출력 관련 native 41개, author/shared 집중 61개, Chromium contract 22개와 TypeScript·빌드도 통과했다. desktop Node 전체 434개는 그 이전 수정 단계에서 통과했고 당시 마지막 한정 수정은 위 집중 검사로 검증했다. 합성 Electron 두 시나리오는 최초 부하 시간 초과 후 단독 재검사에서 통과했으며 원 로그를 유지했다. 이 결과는 소프트웨어 검사이고 이번 분석 계약 수정이나 새 원고의 품질을 직접 증명하지 않는다.

두 실제 과학 원고의 생성·평가·검수·전달 묶음과 현재 S&P 새 제출 파일의 준비·저장·별도 페이지 검수는 완료했다. 다음 작업은 저자의 실제 약력·사진·지원/이해관계와 7개 승인·새 파일 QA 5개를 확인해 제출 묶음을 만들고 한 공식 포털에서 실제 제출한 뒤 접수번호·시각을 기록하는 것이다. 현재 준비는 `awaiting_file_check`이며 제출 승인이나 접수 기록은 없다. 새로운 실제 지적 없이 연구·집필·심사를 재실행하거나 횟수를 초기화하지 않는다. 추가 코드 수정은 앱 정상 종료 후 집중 검사·빌드·결속을 확인하고 같은 연구에서 검증한다.
