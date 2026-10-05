# 독립 공개 저장소 선정

2026-10-05 공개 원본을 확인한 정적 선정 기록과 후속 실제 연구의 수용 상태다. 최초 선정 조사 자체에서는 연구나 생산 코드를 실행하지 않았고 사전 명세를 관측값으로 취급하지 않는다. 현재 최종 수용은 아래 표와 마지막 체크포인트에 기록하며, 최초 후보·실패·제외 근거는 이력으로 보존한다.

## 현재 실제 연구: 2026-10-06 04:20 KST

| 서로 다른 저장소 | 최종 질문의 생산 함수 | 실제 연구 ID | 수용 상태 |
| --- | --- | --- | --- |
| premiere-ai-harness | `plugin/lib/planner.js:approveCandidates` | `research-a90ccd5fee76` | 단회실험·실제 새 원고/별도리뷰·5종출력·전쪽 PDF/내용/ZIP 검수·실제 저장/열기요청/폴더 확인 완료 |
| neobrutal-ui | `docs/src/site/lib/navigation.ts:isNavigationPathActive` | `research-6561ac63db99` | 별도 질문의 단회실험·실제 새 원고/별도리뷰·5종출력·전쪽 PDF/내용/ZIP 검수·실제 저장/열기요청/폴더 확인 완료 |
| frontron | `frontron/src/cli/options.ts:parseCliOptions` | `research-f68ee0139f78` | Source12 실제 앱에서 코드 attempt1·단회 과학실험1·새 원고/별도리뷰 승인·5종출력·전쪽 PDF/내용/ZIP 검수·실제 저장/열기요청/폴더 확인 완료 |

최종 검증 논문은 **3/3**이다. 세 연구는 각각 성공 실행1회이며 현재 동결 artifact124/72/112개를 전량 해시 대조했다. Preview identity와 SemVer의 이전 실패 연구는 제외하고 같은 실험을 재실행하지 않는다. 최초 후보와 현재 질문을 혼동하지 않도록 아래 표는 당시의 선정 이력으로 유지한다. 현재 생산 소스 전체와 원본 라이선스는 실제 앱 수집본/commit/SHA와 대조했고 상세 과학·출력 근거는 [최종 검증 기록](standalone-verification.md)에 있다.

## 최초 선정 조사 이력

| 저장소 | 고정 커밋 | 원문 라이선스 | 선정 생산 함수 |
| --- | --- | --- | --- |
| [neobrutal-ui](https://github.com/andongmin94/neobrutal-ui) | `b4da2463fe710a77bf464c65125a1a7f40424722` | MIT, Copyright (c) 2023 Samuel Breznjak | `docs/src/data/preview-registry.ts:getPreviewIdentity` |
| [frontron](https://github.com/andongmin94/frontron) | `3a7da2822721801db88ea059d204c8c6c622fab4` | MIT, Copyright (c) 2024 andongmin | `frontron/src/init/dependency-compatibility.ts:parseDeclaredMajor` |
| [premiere-ai-harness](https://github.com/andongmin94/premiere-ai-harness) | `4c014fd019d219c531753f2461b7cdb20b389f01` | Apache-2.0, Copyright 2026 Andongmin | `plugin/lib/planner.js:approveCandidates` |

GitHub API의 `owner.login`, `private:false`, 커밋 응답과 라이선스 실제 파일을 각각 확인했다. 계정 소유와 원본 저작자 표기를 동일하다고 추정하지 않았다. 이번 세 후보의 API 라이선스 값은 각각 MIT/MIT/Apache-2.0이었고, null·NOASSERTION에 의존한 선정은 없다. 특히 neobrutal-ui의 원문 저작자는 위에 표시한 Samuel Breznjak이다.

## 실행 가능 범위와 원본 증거

세 후보 모두 후속 계획의 `dependencies`는 `[]`이다. 아래 파일 전체의 고정 원본을 `source_paths`로 사용하며, 함수 부분 추출이나 import 수정, 호스트 객체 주입, 외부 패키지 설치를 전제로 하지 않는다. 호출 인자·반환 관측은 제한된 JSON 자료로 구성한다.

| 저장소 | `source_paths` | 원본 바이트 | 원본 SHA-256 |
| --- | --- | ---: | --- |
| neobrutal-ui | `["docs/src/data/preview-registry.ts"]` | 1,089 | `3593b5e09f2e303e32cfddb492a4a7015ca5d673fbe8d83225faa4bf75ba4665` |
| frontron | `["frontron/src/init/dependency-compatibility.ts"]` | 2,185 | `8ff35331f4a12d300a95bdb6d65ec7a8fde9763ffd70cf9a8e462c6f0a2c1e86` |
| premiere-ai-harness | `["plugin/lib/planner.js"]` | 17,205 | `d5ae61bf96669917e1485382cc99c39157cf057d39504bf8afbd7fae1aa2cdef` |

neobrutal-ui와 frontron은 앱의 검증된 변환 방식과 같은 Node v24.21.0 `node:module.stripTypeScriptTypes`, `mode:'strip'`으로 문법 변환만 확인했다. 변환 뒤 runtime import 선언은 두 파일 모두 없다. 프로젝트 코드는 실행하지 않았고 원본을 덮어쓰지 않았다. 변환 결과 해시와 변환기 버전은 각 `selection-manifest.json`에 보존했다.

premiere-ai-harness는 동일 파일 안의 UMD 내보내기를 사용한다. 현재 QuickJS worker의 기존 UMD 어댑터가 `module.exports`의 own export를 선택하는 경로를 소스로 확인했다. `typeof module/window` 분기는 존재하지만 Node·DOM API 호출은 없다. 브라우저 이름은 `PAI.approveCandidates`, 컨트롤러 선택자는 위 표의 `파일:함수`이다. 실제 QuickJS 성공 여부는 후속 실제 호출과 원본·변환 해시·production call trace로 확인해야 한다.

원본과 공개 API 응답은 ignored 경로 `.paper-factory/standalone-verification/repository-selection-20261005/`에 보존했다.

- `neobrutal-ui/`: `repository-api.json`, `commit-api.json`, `public-receipts.json`, `selection-manifest.json`, `selected-source/`, `hand-specified-fixtures.json`. 기존 공개 reference의 고정 Git blob에서 원본 바이트를 복사했다.
- `frontron/`: 같은 API·선정 영수증, 고정 커밋의 codeload `source.zip`과 펼친 `source/`, 원본 `selected-source/`, 미실행 명세 fixture. ZIP 응답 해시·바이트 수·조회 시각도 기록했다.
- `premiere-ai-harness/`: `receipts/`의 repository·commit·license 원문 응답, 고정 커밋 `source/`, Git blob 대조·SHA가 있는 `metadata.json`, 독립 검토 `selection-proposal.md`, 미실행 fixture 4개.

MIT 원문 고지와 Apache LICENSE·NOTICE는 각각 유지했다. frontron은 루트 `LICENSE.md`와 선정 패키지의 `frontron/LICENSE`를 모두 읽고 보존했다. 공개 계정 소유 정보만으로 제3자 저작권·Adobe 호스트 소프트웨어·상표에 대한 권리를 확장하지 않는다.

## 1. neobrutal-ui: 미리보기 경로 식별

선정 [원본 함수](https://github.com/andongmin94/neobrutal-ui/blob/b4da2463fe710a77bf464c65125a1a7f40424722/docs/src/data/preview-registry.ts#L11)는 `getPreviewIdentity(sourcePath:string)`이며 `{component, example?}`를 반환한다. 파일의 타입·기본 미리보기 이름 표·문자열 처리만 필요하다. runtime import, React, DOM, fs, 네트워크, async, 프로세스 API가 없다.

실제 생산 사용은 [docs/src/data/components.ts](https://github.com/andongmin94/neobrutal-ui/blob/b4da2463fe710a77bf464c65125a1a7f40424722/docs/src/data/components.ts#L29)의 `getPreviewIdentity(modulePath)` 호출이다. 문서 사이트의 예제 모듈을 컴포넌트와 미리보기 이름으로 분류한다. 테스트에만 존재하는 함수를 선정한 것이 아니다.

연구 질문: 동일한 컴포넌트·예제 의미를 가진 POSIX/Windows 경로와 기본 미리보기·중첩 예제 표현에서 생산 함수가 의도한 식별자를 보존하고, 빈 컴포넌트를 거절하는가?

독립 oracle는 생산 문자열 파서를 다시 구현하지 않는다. 사전에 정한 의미 튜플 `(component, example)`로 경로 fixture를 생성하고, 그 튜플 자체를 기대 JSON으로 보존한다. `/examples/ui/` 앞의 위치 경로, `./` 유무, `/`와 `\\` 구분자, `index`, chart의 `chart-area-stacked`, sidebar의 `page`, 깊이 1~3 예제를 조건으로 교차한다. 기본 예제는 `example` 키가 없는 것이 명세다. 빈 문자열과 `./`는 별도 거절 제어군이다.

범위는 8개 명시 제어 fixture와 최대 96개 경로, 문자열당 256자, 예제 깊이 최대 3으로 제한한다. 정확한 JSON 일치·기본/이름 있는 예제 구분·거절 일치율을 기록한다. 실제 파일 시스템 경로 접근, URL 보안, 전체 사이트 라우팅 품질로 일반화하지 않는다. 잘못된 기대 컴포넌트 또는 예제 키를 주입한 음성 대조가 실패하는지 별도로 확인한다.

선정 제외 근거:

- `registry/src/lib/utils.ts`: 단순 이름 변환 함수도 같은 파일에서 `clsx`·`tailwind-merge` runtime import를 포함한다. 함수만 추출하거나 의존성을 제거하면 원본 전체 사용 조건을 어긴다.
- `registry/src/data/theme-styles.ts`의 CSS serializer와 `theme.ts`: 계산은 순수하지만 `./theme` 확장자 생략 import 및 `@/data/colors` alias가 있다. 현재 frozen loader는 정확한 상대 파일 경로만 처리하며 alias/확장자 보정을 하지 않으므로, 원본 무수정 계획으로는 제외한다. 출력 CSS의 `@import` 문자열은 JS 실행 의존성 문제와 별개다.
- `registry/src/lib/blog-posts.ts:getBlogPost`: import 없이 호출 가능하나 고정 예시 콘텐츠의 단순 조회여서 이번 경로 식별 연구보다 조건·독립 검증 범위가 좁다.
- React 컴포넌트·훅·Next 페이지·문서 빌드 스크립트는 DOM/호스트/외부 의존 관계 때문에 제외한다.

별도 적합한 예비 함수는 [docs/src/site/lib/navigation.ts:isNavigationPathActive](https://github.com/andongmin94/neobrutal-ui/blob/b4da2463fe710a77bf464c65125a1a7f40424722/docs/src/site/lib/navigation.ts#L22)이다. 동일 파일만 필요하고 실제 site-header/sidebar에서 호출된다. 경로 토큰 접두 관계와 `/docs` 대 `/docsmith` 경계를 독립 oracle로 삼을 수 있으나, 이번 선정은 미리보기 식별 함수 하나로 고정한다.

## 2. frontron: 버전 선언의 단일 major 추정

선정 [원본 함수](https://github.com/andongmin94/frontron/blob/3a7da2822721801db88ea059d204c8c6c622fab4/frontron/src/init/dependency-compatibility.ts#L26)는 `parseDeclaredMajor(value:string)`이며 정수 또는 `null`을 반환한다. 같은 파일의 `isDependencyProtocol`과 정규식만 사용한다. `./shared`는 `import type`이므로 검증된 타입 제거 후 runtime import가 남지 않는다. 타입 정의 파일의 Node import를 guest에 포함하지 않는다.

생산 호출은 같은 파일 `inspectToolDependencyDeclarations`의 선언·템플릿 major 계산이고, [init/package-json.ts](https://github.com/andongmin94/frontron/blob/3a7da2822721801db88ea059d204c8c6c622fab4/frontron/src/init/package-json.ts#L61)와 [doctor/inspections.ts](https://github.com/andongmin94/frontron/blob/3a7da2822721801db88ea059d204c8c6c622fab4/frontron/src/doctor/inspections.ts#L102)가 이를 사용한다. 전체 CLI/설정 파일 수정 경로를 guest에 넣을 필요는 없다.

연구 질문: 단일 major로 확정 가능한 선언을 추정하는 함수가 정확한 버전·caret·tilde·와일드카드·상하한 비교 선언에서, 의미상 여러 major를 허용하는 범위를 단일 major로 오인하는가?

독립 oracle는 생산 정규식을 복사하지 않는다. [npm/node-semver의 공식 범위 명세](https://github.com/npm/node-semver#ranges)를 읽어 사전 fixture별 허용 버전 집합 조건과 기대 단일 major를 고정한다. numeric release tuple을 사전 명세의 비교 연산자로 판정한다. 여러 major를 허용하는 경우에는 서로 다른 major의 두 만족 버전을 증인으로 함께 보존한다. 예를 들어 `>=2.0.0`의 `2.0.0/3.0.0`, `>2.0.0`의 `2.0.1/3.0.0`, `<2.0.0`의 `0.9.0/1.9.0`은 단일 major 명세를 만족하지 않는다. `<=0.9.9`는 major 0의 상한 제어군이다.

`2.3.4`, `^2.3.4`, `~2.3.4`, `2.x`, `workspace:^2.3.4`, `latest`, 논리합도 사전 구분한다. frozen fixture는 선언당 128자, release major 0~6, minor/patch 0~9, 최대 128건으로 제한한다. prerelease·build metadata·복잡한 범위 조합은 이번 추론 범위에서 제외한다. 여러 major 허용의 증인은 단일 major 가정을 반박하는 데 사용하며 유한 표본으로 모든 범위를 증명한다고 주장하지 않는다.

정확한/오인/판정 보류 수와 선언 군별 일치율을 기록한다. 숫자 앞부분만 읽는 단순 comparator를 별도로 둘 수 있지만 정답 oracle로 사용하지 않는다. 명세 표에서 의도적으로 한 major 기대값을 바꾸는 음성 대조를 실패로 탐지해야 한다. 현재 원본의 비교 연산자 처리로 불일치가 생길 가능성은 소스에서 얻은 가설이며, 측정 결과로 보고하지 않는다.

fs/path/child-process를 쓰는 init·update·doctor·실행 서버 전체, YAML·JSONC 패키지 의존 파서, Electron 템플릿은 제외한다. 이 파일의 순수 함수가 선정 가능하다는 사실은 Frontron 전체를 QuickJS에서 실행할 수 있다는 뜻이 아니다.

## 3. premiere-ai-harness: 편집 승인 구간 안전성

선정 [원본 함수](https://github.com/andongmin94/premiere-ai-harness/blob/4c014fd019d219c531753f2461b7cdb20b389f01/plugin/lib/planner.js)는 `approveCandidates(plan, selectedIds)`이다. 반환은 JSON으로 보존 가능한 `keepRanges`, `stats`이고 잘못된 입력·안전성 위반은 동기 오류로 나온다. validatePlan/validateRules, mergeRanges/invertRanges, clamp/round3, approvalSafetyError와 상수는 모두 같은 파일에 있다.

실제 생산 호출은 [editor-flow.js](https://github.com/andongmin94/premiere-ai-harness/blob/4c014fd019d219c531753f2461b7cdb20b389f01/plugin/lib/editor-flow.js#L154)의 `currentApproval()`이며, `applyRoughCut()`이 승인된 `keepRanges`를 실제 편집 적용 함수에 전달한다. plugin/index.html의 script 연결과 index.js의 apply 버튼 연결도 원문으로 확인했다. 실제 Premiere 세션을 실행했다는 증거는 아니다.

연구 질문: 겹침·접촉·포함 관계·짧은 잔여 틈이 있는 후보 삭제 구간에서 생산 승인이 시간 합집합 보존과 삭제 비율·최소 유지 길이 제약을 충족하는가?

독립 oracle는 100ms 정수 셀 점유 표다. 선택 구간의 각 반개구간 셀을 삭제 표시하고, 삭제 셀 수와 나머지 연속 셀 run을 직접 센다. 생산의 정렬/merge/invert 코드를 복사하거나 호출하지 않는다. 삭제 비율 한도와 최소 유지 run 길이를 셀 명세로 판정한 뒤 마지막에 초 단위로 변환한다. comparator는 개별 구간 길이를 겹침 제거 없이 더하는 단순 방식이며 정답에 사용하지 않는다.

범위는 길이 10~60초, 후보/선택 ID 각 최대 12개, 고정 rule 5개, 사전 seed 3개와 seed당 기본 단위 최대 80개다. 삭제 비율 0.4·최소 유지 0.25초를 명시하고 겹침 없는 대응 조건·겹침/포함 조건·짧은 틈 조건을 비교한다. 삭제 union 오차, keep endpoint 오차(0.001초 허용), 승인 일치, 단순 comparator의 거짓 거절을 측정한다. sub-ms 수치나 사람의 영상 품질 평가는 다루지 않는다.

10초 원본의 `[1,4)`, `[2,5)` 삭제는 합집합 4초·유지 `[0,1),[5,10)`인 경계 명세다. 개별 길이 합은 6초로 comparator가 다른 판정을 낼 수 있다. `[1,2)`, `[2.2,3)`는 0.2초 유지 틈이 최소 유지 제약보다 짧은 거절 제어군이다. 원문 입력·사전 정답·음성 대조 설명은 미실행 fixture로 보존했다.

Adobe 어댑터, 편집 UI/DOM/storage, 인증·호스트 qualification, async Premiere 호출, 패키지/evidence 스크립트는 제외한다. 같은 파일의 textSimilarity/createEditPlan 및 별도 transcript 파서는 후보이지만 사람 언어/형식의 추가 명세보다 승인 구간의 독립 수학 oracle가 명확하여 후자를 우선했다.

## 후속 실제 연구의 수용 조건

각 연구를 실행할 때 이 선정 커밋·원본 SHA와 실제 수집 원본이 일치해야 한다. original source를 frozen map에 넣고 기존 검증된 compiler/UMD adapter만 사용한다. alias 치환·함수 발췌·의존 패키지 설치로 선정 조건을 느슨하게 만들지 않는다. 세 소스 모두 JSON 함수 호출만 허용하며 호스트/fs/network/Node/DOM/async 경로는 포함하지 않는다.

컨트롤러의 실제 생산 호출 수·성공 반환과 경계 실패 기록, 독립 oracle와 사전 fixture, 오류를 포함한 실제 JSON 반환 관측, 음성 대조, 수치 분석, 모델 작성·리뷰 원문과 고정 프로토콜의 실제 준수가 있어야 과학적 완료로 판단할 수 있다. 실행기가 제공하지 않는 호출별 trace·변환 JavaScript 전체·별도 사전 probe receipt를 추가 완료 조건으로 만들거나 보존됐다고 주장하지 않는다. 정적 선정 자료만으로 연구 완료나 재현 실험 성공을 주장하지 않는다.

## 첫 연구의 수용 실패와 별도 탐색 경로 질문

`research-9a477cc5d054`의 `getPreviewIdentity` 실험은 1회 실행·17회 production call·32개 관측·제어 통과를 기록했지만, frozen exact-object metric과 JSON 관측 경계의 불일치 및 실제 제공되지 않는 사전 compiler 증거 요구로 프로토콜 완료가 무효다. 후속 원고는 그 무효를 명시하는 실패 보고로 독립 리뷰를 통과했다. 같은 실험을 재실행하거나 원래 protocol/관측을 바꾸지 않으며 성공 3편으로 계산하지 않는다. 내보내기 마지막 검증의 timeout은 별도 기술적 실패다.

위 최초 선정 조사에서 이미 예비로 확인한 `isNavigationPathActive`를 별도의 질문 후보로 확인했다. 이는 미리보기 식별 관측을 고치는 실험이 아니라 다른 production callable의 navigation highlight 경계를 조사하는 신규 연구다. 고정 커밋과 MIT 원문은 동일하지만 함수와 입력 도메인·질문·protocol·코드·리뷰·관측은 모두 별도로 생성해야 한다. 실제 source 전체는 `docs/src/site/lib/navigation.ts`, 908 bytes, SHA256 `8e860a4c40dc679d248ba5d1eb7e05f0369bb17d073eaee2c34682609805c219`다. 원문에 runtime import가 없고 입력은 문자열·문자열·boolean, 반환은 JSON으로 관측 가능한 boolean이다. 실제 site-header의 import와 호출을 확인했다.

독립 oracle는 경로를 토큰 배열로 분리해 후행 빈 토큰과 segment 관계를 판정하고, comparator는 의도적으로 단순한 문자열 prefix 조건을 사용한다. 사전 범위는 seed 2개와 seed당 서로 다른 route-pair fixture 8개다. 정확한 경로·후행 slash·진짜 하위 segment·문자열 prefix만 같은 다른 경로·root target·후손 옵션을 분리하며 URL/query/fragment/percent decoding/DOM routing은 다루지 않는다. 정상 반환 양성 제어와 그 실제 boolean에 대해 잘못된 기대값을 주입하는 의도적 오류 음성 제어를 계획 전에 명시해야 한다. 아직 해당 함수의 실제 실험·리뷰·관측은 없다.

추가로 `mini-cast:parseCssColor`와 JIZURA를 조사했다. 전자는 독립 callable로 기술적 적합성이 있으나 source code 사용·복제·수정·배포를 허용하지 않는 restrictive license여서 실제 실행·재현 패키지 후보에서 제외했다. 후자는 MIT지만 원본 파일이 `window.J`를 즉시 요구해 무수정·무호스트주입 guest 범위에 부적합하다. 이를 강제로 실행하거나 라이선스 권한을 추정하지 않았다.

## 실제 후속 연구 시작: 2026-10-05

최신 Windows 설치본의 새 연구 화면에 Frontron URL과 사전에 작성한 3,821자 목표를 입력하고 연구 시작을 한 번 눌렀다. 실제 앱은 `research-b071d98fbed0`을 만들었으며, 작성 모델 `gpt-6-astra`와 리뷰 모델 `gpt-5.6-sol`로 계획 생성을 시작했다. 이 시점에는 새 실험 관측이나 성공 원고가 없으므로 성공 편수는 여전히 0/3이다.

후속 앱 입력은 위 초기 후보 조사보다 작은 범위로 정했다. Frontron은 seed 17/29 각각 선언 8개, production/exact-version-only 두 조건과 단일 major/unknown 일치 0/1만 비교한다. Premiere 후보는 seed 17/29 각각 계획 8개, 100 ms 정수 셀의 독립 삭제 합집합·유지 run 명세와 승인 일치만 비교한다. 탐색 경로 후보는 seed 17/29 각각 route pair 8개와 boolean 활성 일치만 비교한다. 이 목표들은 관측 전에 작성한 요청이며 실제 모델의 frozen 계획·코드·리뷰나 측정 결과를 대신하지 않는다. 실제 계획이 생성되면 그 계획과 실행 기록으로 준수를 판정해야 한다.

세 요청 모두 JSON으로 실제 관측 가능한 값만 판정하고, 유효한 알려진 production 결과의 양성 제어 및 의도적 오류를 검출하는 음성 제어를 요구한다. TypeScript 증거 범위는 원본/변환 SHA256, 변환기 이름·버전, 실제 파일별 `mode/sourceMap/sourceUrl` 옵션이다. 현재 실행기가 보존하지 않는 변환 JS 전체 바이트나 별도 사전 문법 probe 영수증을 완료 조건으로 만들지 않는다. 짝지은 차이는 comparator minus production으로 고정한다.

최종 사전 요청과 HEAD 재확인 영수증은 `.paper-factory/standalone-verification/prospective-goals-20261005-41b6c42c/`, 탐색 경로의 별도 요청은 `.paper-factory/standalone-navigation-candidate-44749067-63a3-4857-ad07-d2be04adf465/goal-final.txt`에 보존했다. 앱 시작 화면 증거는 `goal-install-f4f99acd-fa8d-40ec-b4e9-52bc7d18b18b/frontron-start-ready.jpg`이다.

## 두 신규 요청의 공개 원본 재확인과 수정 입력

2026-10-05 13:39–13:40 UTC에 인증 없이 공개 GitHub API를 다시 읽었다. Premiere HEAD는 `4c014fd019d219c531753f2461b7cdb20b389f01`, neobrutal-ui HEAD는 `b4da2463fe710a77bf464c65125a1a7f40424722`로 기존 고정 커밋과 같았다. 전체 `planner.js` 17,205 bytes/SHA256 `d5ae61bf96669917e1485382cc99c39157cf057d39504bf8afbd7fae1aa2cdef`, 전체 `navigation.ts` 908 bytes/SHA256 `8e860a4c40dc679d248ba5d1eb7e05f0369bb17d073eaee2c34682609805c219`도 일치했다. 원문 Apache-2.0 LICENSE·NOTICE와 MIT 저작권 고지, 생산 호출 위치, README와 Premiere 작성자 테스트를 보존하고 읽기만 했다. HEAD 일치는 이 조회 시점의 사실이며 실제 앱 수집 후에도 고정 source와 대조해야 한다.

공개 API body·HTTP 상태·조회 시각·응답 SHA256·Git blob 대조와 점검표는 `.paper-factory/standalone-verification/next-studies-preflight-20261005-1694b54feb75466e8733a0634adafb37/`에 있다. `public-preflight-receipt.json` SHA256은 `3f6d25e19c90e58d3155dd0fcce81eb7adbed0112ce94ba9d18cabf23ac9c5ed`다. 저장소 JavaScript·앱·엔진·모델을 실행하거나 사용자 연구 자료를 읽지 않은 공개 원본 사전 점검이다.

두 요청의 oracle는 연구자가 사전에 명시하는 정수 셀 점유·segment token 계약이다. 검토한 제한 범위에는 SemVer처럼 별도 외부 규격을 정답의 근거로 요구하는 내용이 없다. 생산 소비자와 작성자 테스트가 있다는 사실을 전체 저자 의도·Adobe 편집 적합성·보편적 URL/라우팅 정확성의 근거로 확장하지 않는다. 문헌은 실제 읽은 방법론 excerpt만 사용하며 이 계약의 보편적 규범성을 증명한다고 주장하지 않는다.

최신 입력 문구는 아래 새 파일이며 위 원래 목표는 바이트 그대로 보존했다. 두 신규 요청에 해당하는 실제 모델 계획·실험·논문은 이 입력 준비 시점에 각각 0건이다. 이 문구와 정적 점검은 frozen protocol·complete code·독립 리뷰·관측을 대신하지 않는다.

| 새 요청 파일 | 글자 수·UTF-16 code units | SHA256 |
| --- | ---: | --- |
| `premiere-goal-revised.txt` | 3,993 | `80fed8d401250e89914e4c5a42b6df20749a05b79348a1bc85cb0449c586a337` |
| `navigation-goal-revised.txt` | 3,309 | `bac65ba8098ccbefebad1a25941c12e07a09e854ef5832eefc908d7210d22e4c` |

두 파일은 `.paper-factory/standalone-verification/prospective-goal-revisions-20261005-a8f792d4d9f242ecb8ab25e4cb0ad936/`에 있다. `goal-input-ready-receipt.json`에는 원래 3,990/2,933자 요청의 전후 해시·글자 수와 원본 불변을 기록했고 SHA256은 `bde46ed1aa6dea76cdee5557e3aea27503023591128d11cc8fda0a50fa903e4e`다. 새 입력은 각각 기존의 seed 17/29·seed당 8개 단위·짝지은 두 조건·단일 binary metric·유효한 실제 반환 대조군·comparator minus production 기술통계·증거 제한을 유지한다.

Premiere에는 numeric candidate endpoints `0 <= start < end <= duration`와 기존 candidate ID만 포함하는 명시적·중복 없는 `selectedIds` 부분집합을 추가했다. 원본 `validatePlan`은 끝점을 검증하지 않고 `mergeRanges`가 범위 밖 값을 clamp하거나 빈 구간을 버리므로 이 유효 입력 범위를 관측 전에 동결해야 한다. 선택 없음은 유효하며 최소 유지 run 검사는 실제 삭제가 있을 때만 적용한다. Navigation에는 연구자 정의 segment 계약의 기술적 비교라는 범위와 실제 literature query `The Oracle Problem in Software Testing A Survey`, `metamorphic testing oracle problem survey`를 추가했다. 실제 계획·코드에서 정확한 16개 입력·독립 기대값, root/후행 slash 생성 규칙, 실제 읽은 문헌과 JSON/변환 증거 경계를 동결하고 단회 실험 전에 독립 검토해야 한다.

## Frontron의 별도 CLI 입력 계약 후보: 2026-10-05 14:31 UTC

SemVer 연구의 실제 원고 거절과 단회 실험을 보존하고, 같은 저장소의 다른 callable `frontron/src/cli/options.ts:parseCliOptions(argv)`를 신규 질문으로 조사했다. 14:25:50.638 UTC 공개 GitHub 조회에서 HEAD는 `3a7da2822721801db88ea059d204c8c6c622fab4`였고, 원본 5,212 bytes/SHA256 `08a4e578395eabc7db1b8c3fdf85287b896ba20b4a213e6d5765dfee340a5bc3`는 보존된 archive와 같았다. 파일의 import는 type-only이며 실제 `runCli` 소비자를 확인했다. README가 internal implementation/nonpublic API로 설명한다는 경계와 MIT 원문도 보존했다. 공개 조회와 정적 판독은 실제 QuickJS 실행 적합성 검증이 아니다.

새 요청은 seed 17/29·각 8개 argv·생산 조건 먼저·독립 사전 표의 바인딩/거절 일치 0/1을 요구한다. 반복 init 문자열 옵션의 last-value-wins 계약과 first-value-wins comparator를 비교하며, 나머지 명령·옵션 문법은 동일하게 판정한다. 선택적 키의 부재는 JSON에서 명시적으로 표현하고 raw undefined/own-key 관측을 요구하지 않는다. 유효 반환 양성 제어와 같은 실제 출력에 잘못된 기대값을 주입하는 음성 제어, 원본·변환 SHA와 실제 파일별 변환 옵션, 단회 실험과 별도 코드/원고 리뷰를 요구한다. 호스트 CLI·파일시스템·shell·보안 또는 성능 효과는 연구 범위에 포함하지 않는다. 독립 계약을 외부 표준으로 가장하지 않으며 방법론 문헌은 실제 읽은 excerpt만 사용한다.

Plain 요청 `goal-user-request-final.txt`는 3,994자(끝 개행 제외 3,993자)/SHA256 `8874885d02fcd33ac8e8894a10c68078a30afffb2e0762f64dba7ae8362621e5`다. 공개 원본 receipt `6926ecc0ba9193897b278aed4a3c6aa5708a499763c88b4c16f1ff11d365fb9c`와 입력 준비 receipt `b47d42e401554dd5ba21cedd75486bf58218df219fdfc0c7c4968e705329048a`는 `.paper-factory/standalone-verification/frontron-cli-candidate-20261005-3acba2d13616453aac1e53d1df9c2e60/`에 있다. 이 시점에는 새 CLI 연구의 모델 계획·코드·실험·승인·논문이 없으며, 기존 SemVer 관측을 고치거나 재실행한 것으로 계산하지 않는다.

## 최종 실제 연구 완료: 2026-10-06 04:20 KST

Frontron CLI의 실제 연구는 원본 전체 `frontron/src/cli/options.ts` 5,212 bytes/SHA256 `08a4e578395eabc7db1b8c3fdf85287b896ba20b4a213e6d5765dfee340a5bc3`와 고정 commit `3a7da2822721801db88ea059d204c8c6c622fab4`를 사용했다. type-only import를 제거한 JSON callable만 guest에 포함했고 `runCli`·호스트 파일시스템·shell을 실행하지 않았다. root README와 원본 MIT 고지 `LICENSE.md`, `create-frontron/LICENSE`, `frontron/LICENSE`를 작성·새 리뷰에 전달하고 재현 ZIP의 전체 source 및 inventory에 보존했다. 이 원문 보존을 별도의 라이선스 법률 판단이나 승인으로 표현하지 않는다.

기존 설치본의 코드 후보3개와 Source12 이후 후보3개의 실제 작성/새 리뷰 쌍 및 거절 원문을 모두 보존했다. 최종 승인 코드는 attempt1, 성공 과학실험1회, 원고 draft1이다. 실제 production gate17회는16개 sampling 호출과 양성 제어1회이며 정상 반환9회·거절8회다. 고정 fixture107개, raw32행, 실제 양성/의도적 오류 음성 제어2개와 cleanup=true를 확인했다. 유한16개 짝의 정확도는 production1.0, `first_value_wins`0.8125이고 comparator minus production 평균은−0.1875, 표본 SD0.4031128874다. 이는 반복 init 문자열 옵션에 대한 연구자 정의 last-value-wins 계약의 기술적 비교이며, 외부 규범·CLI 전체 정확성·성능·p값·일반화 주장은 없다.

두 Crossref 질의는 모두 성공했고 첫 질의에서6개 abstract를 읽었으며 두 번째는 정한 조회 상한 안에서 새 문헌0개를 resolve했다. 실제 읽은 방법론 자료의 제한을 원고에 반영했다. 새 Astra 원고와 별도 문맥 Sol 리뷰가 승인한 마지막 export는 `export-attempt-c673234c00a2`다. 원래 후보·실패 관측과 실제 거절을 최종 승인 주장으로 바꾸지 않았다.

세 최종 연구의 PDF10/10/9쪽(총29쪽)을 원본 크기 이미지로 직접 전쪽 검수했다. DOCX65/66/62문단·3200/3261/3046단어·각 표2/그림1 및 각 OOXML19멤버 내용과 ZIP176/476/261멤버의 CRC·크기·SHA·inventory를 전량 대조했다. 앱의 실제 기본5종 저장을 연구마다 완료해15개 원본 bytes와 일치했고, 앱 PDF 열기 요청·정확한 export 폴더 표시 및 별도 Chrome의 정확한 사용자 저장 PDF 표시를 확인했다. Markdown·TeX의 `figure-1.png`는 검증한 실제 저장 ZIP에서 기존 원본 bytes만 별도 전달했으며 앱 Save 동작으로 계산하지 않는다. native Reader의 정확한 파일/렌더링과 DOCX 페이지 시각 검증은 미확인이다. 최종 파일·실제 모델/실험 연결·출력 및 정상 재시작 근거는 [검증 기록](standalone-verification.md)과 [설치·UI 기록](standalone-ui-provenance.md)에 있다. 이3편 완료는 학술적 새로움·학술지 승인·출판을 보장하지 않는다.
