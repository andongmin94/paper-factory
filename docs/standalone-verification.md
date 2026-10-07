# 독립 앱 검증 기록

갱신일: 2026-10-06 (Asia/Seoul). 현재 앱과 엔진 소스는 `0.13.1`이다. 아래는 `0.13.0` 전환 작업의 시작 commit `ac22fdd95778572968e3227d271a0b9846cd7f8b`부터 보존한 실제 검사 이력이다. 0.13.1의 5단계 개선·새 패키지 검사는 [UI 검증 기록](standalone-ui-provenance.md)에 구분해 기록한다.

현재 최종 검증 논문은 **3/3편**이다. 서로 다른 공개 저장소에서 실제 앱의 자체 ChatGPT 연결로 단회 실험, 새 원고와 별도 문맥 리뷰를 완료했다. PDF 총29쪽 직접 시각 검수, DOCX 본문, ZIP 전 멤버 CRC·크기·SHA 및 앱의 실제5종 저장을 통과했다. 정상 재시작 뒤 같은 연결의 새 응답과 세 완료 연구 복원을 확인했다. 최종 경로·해시·검증 범위는 마지막 체크포인트에 있으며, 이전0/1/2편 기록은 해당 시점의 이력이다. macOS는 최종 런타임 전수 정적 검사까지 통과했고 native 실행·DMG·설치·CI는 미검증이다.

## 실제로 수행한 검사

| 검사 | 결과 | 증명의 범위 |
| --- | --- | --- |
| remote `main` 대조 및 Git 상태 | 시작 HEAD와 일치, 시작 작업 트리 깨끗함 | 사용자 변경 없이 시작 |
| Python 상태·workflow·scientific controls·문서 변환 | 273 passed | OS 임시 작업공간의 기존 엔진 검사, 실제 구독 연구 아님 |
| 실제 QuickJS production 호출·TS hash·취소·owner 보호·crash cleanup | 10 passed | 기존 격리 엔진 검사, 새 독립 앱 연구 아님 |
| 새 연결 controller/실제 SDK Responses parser | 28 passed | 모의 transport; 완료 event 필수, usage failure, 취소/만료, pending 등록 복구, 계정별 증거 기록, 제한된 오류 진단 |
| 원본 공식 SDK 회귀 | 45 passed, 1 Windows skip | 모의 credentials/encryption·loopback callback·토큰 갱신; 실제 OS 암호화 또는 계정 검증 아님 |
| TypeScript main/preload/renderer/GUI 검사 소스 | pass | 타입 검사; GUI 실행 증거 아님 |
| Vite/Electron 프로덕션 빌드 | pass | 생성된 코드/자산 |
| 신규 격리 디렉터리의 기본 `npm ci`와 빌드 | pass | Node 24.21.0/npm 12.2.0, 611개 새 의존성, override 없이 설치 |
| Windows 연결 패키지 정적 검증 | pass, 7,661개 구성원 | ASAR 파일·SDK import·빌드 일치·실행 파일 해시; 앱 실행 아님 |
| 실제 Electron GUI 검사 | 2 passed, 총 34.4초 | 첫 GUI 검사 889 ms; OS 보호 저장소 fixture 및 재실행 검사 33.2초. 실제 OAuth·구독 응답 아님 |
| 크레딧 안내·연구 화면·확장된 제한 IPC GUI | 3 passed, 총 39.1초 | 실제 runtime 초기화와 종료 포함, 오류 fixture는 합성 자료 |
| 별도 포함 runtime GUI 확인 | pass, 5.5초 | 실제 ready/버전과 화면 일치, 로그인 전 시작 비활성화; 연구·OAuth 요청 없음 |
| 연구 controller 중단·리뷰·증거 복구 | 9 passed | 모의 모델·엔진, 거절·부분 응답 보존/중단실험 재실행 금지/미전송 receipt 재개/SQLite orphan 표시 |
| 제한된 Python IPC·workflow·변환·수집·인증 경계 | 221 passed, 1 skipped | OS 소유 임시 공간; 실제 QuickJS guest→분석→native exports→ZIP, 실제 구독 논문 아님 |
| Windows 포함 runtime | pass | 공식 CPython 3.14.8·고정 wheels·Node 24.21.0·QuickJS·Pandoc·Typst·폰트, 빈 시스템 PATH 및 한글·공백 경로 이동 |

서로 다른 범주의 검사 수를 새 연구 성공 수로 합산하지 않는다. 원본 SDK source/test는 commit `f723814abdccec135b519c451fb6e1992ee5e933`에서 처음에 변경 없이 도입했다. 이후 SSE client deadline의 좁은 변경과 새 회귀는 아래 12:45 UTC 체크포인트에 기록하며 현재 source 전체가 원본과 동일하다고 주장하지 않는다. 원본 neobrutal-ui 컴포넌트의 commit·SHA256은 UI 출처 문서에 있다.

## 실패와 보류

- 초기 Playwright Electron launch 2건 실패 (`Process failed to launch`, exit 1). 당시 성공 화면·실제 safeStorage 검사·로그인·구독 응답을 얻지 못했다. 이후 재시도 실패까지 `.paper-factory/standalone-verification/electron-launch-before-resume/`, `electron-launch-after-resume/`, `electron-launch-path-normalized/`에 보존했다.
- 중단 요청 후 해당 실행 PID 6512·31856이 더 이상 존재하지 않는 것을 담당 에이전트가 확인했다.
- 사용자는 다른 세션의 computer use를 방해하지 않도록 한동안 Electron 실행·UI 자동화를 제한했으며, 이후 그 제한을 해제했다. 앱 자체 OAuth 계정 연결과 ChatGPT 구독 사용 권한 승인을 사전 승인했고 **Chrome 사용을 지정**했다. 실제 OAuth와 후속 설치본의 연결 검증은 아래에 따로 기록했다.
- 실행 실패 원인은 Windows에서 desktop 경로의 끝 슬래시가 명령 인자 인용을 깨뜨린 문제와 ESM 최상위 `await app.whenReady()`의 시작·ready 순환대기였다. 경로를 `resolve`로 정규화하고 앱 초기화를 readiness `.then(...)`으로 바꾼 뒤 실제 GUI 검사 2건이 통과했다.
- OS 보호 저장소 fixture는 합성 인증 자료의 암호화와 별도 앱 실행 간 복원을 확인했다. 이를 실제 사용자 OAuth 로그인·토큰 검증·구독 사용 성공으로 계산하지 않는다. pending 등록 재개·계정 구분 등의 모든 실제 인증 분기가 통과한 것으로도 해석하지 않는다.
- Windows 실제 OAuth·동의·계정별 모델 목록·완료된 구독 응답·재시작 연결 복원을 아래 기록대로 확인했다. 다른 앱 인증 파일은 읽거나 복사하지 않았다.
- macOS 실제 CI 실행·빌드 결과·설치·로그인·실험·원본 파일 저장은 **미검증**이다. 새 CI 정의는 실행 증거가 아니다.
- Python/Node·QuickJS·문서 변환 환경을 포함한 최종 Windows 설치본의 전수 해시·실행·자체 연결 복원·새 응답 확인을 통과했다. 3개 저장소의 새 논문과 사용자 저장본 검수 완료는 마지막 체크포인트에 기록했다.

## 이전 연결 전용 빌드 및 배포 기록 (역사적 체크포인트)

`desktop/release/connection-package-verification.json`은 정적 패키지 검사가 통과할 때만 생성한다. 앱 버전·시각·플랫폼·구성원 수·ASAR/실행 파일 크기·SHA256을 기록하며 실제 인증·응답·재시작 상태를 `unverified`로 명시한다. `package:connection`은 최종 연구 설치본으로 계산하지 않는다.

2026-10-05 09:15:58 KST, Windows x64 정적 검사 통과:

| 파일 | bytes | SHA256 |
| --- | ---: | --- |
| `desktop/release/win-unpacked/resources/app.asar` | 42,523,674 | `bbe21f33c1a27477f296f67d94da4d28c627d1f044d1d0910d946400fa638857` |
| `desktop/release/win-unpacked/Paper Factory.exe` | 245,726,208 | `187a1cc6d58e4617d60465938bfc01930693800db7f514370625fac7296b9d3c` |

위 크기·해시는 해당 시점의 정적 패키지 검증 이력으로 유지한다. 이후 launch/readiness 수정 소스의 GUI 검사와 구분하며, 최종 설치본은 다시 빌드해 그 설치본의 해시와 실제 사용 증거를 기록해야 한다.

최초 정적 검사에는 Windows ASAR 내부 경로 구분자 처리 오류가 있었다. 검사 도구를 플랫폼 구분자로 수정한 뒤 기존 패키지를 재검사해 통과했다. 앱·실험을 실행하거나 결과물을 주입하지 않았다.

npm 12.2.0이 esbuild 설치 스크립트를 자동 차단하는 것을 확인하여 검토한 `esbuild@0.27.7`만 허용하고 현재 NSIS 경로에 필요 없는 `electron-winstaller` 스크립트는 명시적으로 거부했다. 시스템 npm/OS 설정은 변경하지 않았다. lock 갱신 시 registry의 optional tarball에 `EALLOWREMOTE`가 발생하여 lock URL host가 `registry.npmjs.org`뿐임을 확인한 뒤 해당 명령에만 `--allow-remote=all`을 적용했다. **새 디렉터리의 기본 `npm ci`와 빌드는 우회 없이 통과했다.**

격리 설치 증거는 `.paper-factory/standalone-clean-install-7ec372c98e574b0e9e3be0869bfbccbd/`에 있다. desktop-only 복사본의 첫 빌드는 repository LICENSE가 빠져 실패했다. 루트 LICENSE를 포함한 실제 repository 구조로 수정한 뒤 성공했다. 초기 실패·최종 로그·종료 코드·source hash receipt를 모두 보존했다. Receipt SHA256: `8c79c776a1573aaab553865fd4946aec3377fb0a2bad5443f37fea0d52c51388`.

## 실제 연결 게이트 통과

2026-10-05 지정된 Chrome에서 이 앱의 신규 OAuth 등록과 구독 사용 동의를 진행했다. 패키지의 자체 보호 저장소에 연결을 저장했고, 실제 모델 목록 5개를 조회했다. `gpt-6-astra`의 `response.completed`를 확인한 뒤 앱을 정상 종료했다. 해당 앱 프로세스와 창이 없는 것을 확인하고 새 프로세스로 실행했다. 새 로그인 없이 같은 profile의 연결이 복원되었으며 새로운 요청이 완료됐다.

| 실제 사건 | UTC | 결과 |
| --- | --- | --- |
| 자체 OAuth 완료 | 07:41:36.963 | connected/sharing true |
| 첫 실제 완료 응답 | 07:44:36.279 | `Paper Factory connection works.` |
| 완전 종료 후 새 launch | 07:48:11.168 | 같은 profile, connected/sharing true |
| 재실행 후 새 실제 완료 응답 | 07:56:44.656 | `Paper Factory connection works.` |

두 응답의 텍스트 SHA256은 `a0ae5d7b5f387303253b02b254d91296c7d35747c075fd08cdfff9d1955ecbce`다. 같은 텍스트라는 이유로 요청을 재사용한 것으로 계산하지 않는다. 각 새 요청의 started/completed 사건과 사이의 launch 사건이 자체 `connection-checks.jsonl`에 있다. 이전 실제 사용량 오류 3건도 삭제하지 않았다.

사용자가 제공한 이미지대로 ChatGPT 사용량 설정의 **“사용량 한도에 도달한 후 다른 앱에서 크레딧 사용 허용”** 옵션을 켰다. Chrome에서 다시 로드하여 켜짐이 유지되는 것을 확인했고 그 후 응답이 완료됐다. 이는 사용자가 승인한 기존 크레딧 사용이며 신규 구매·자동 충전 설정을 변경하지 않았다. 앱의 확인 체크박스는 사용자가 공식 설정을 켰다는 확인이며 원격 설정 상태로 위장하지 않는다. 공개 SDK에 해당 계정 설정을 읽거나 변경하는 API가 없어 공식 사용량 페이지로 연결한다.

라이브 증거는 `.paper-factory/standalone-verification/live-connection-20261005/`에 보존했다. 이 실행의 ASAR SHA256은 `de9c5cebe64a2e4fbd0c8f5d74104ef57f8e8b99e90c18462673f5d023d140ed`, EXE SHA256은 `f19b274207a0b7b8bb51f2d6dc0b4fec6a7b90b54040cc796f0f22cbdc376f97`이다. 이는 연결 체크포인트의 실제 검증이며 최종 연구 설치본·논문 검증은 아니다.

이 게이트 통과 후 제한된 Python IPC·포함 런타임·연구 구현 및 legacy 정리를 완료했다. 실제 논문 검증은 별도 사건으로 기록한다.

## 포함 런타임과 최초 설치 검사

Windows의 실제 포함 CPython·Node·QuickJS·Pandoc·Typst·폰트 환경을 시스템 PATH 없이 실행했고, 전체 해시·한글/공백 경로 재배치·native 문서 재열기 검사를 통과했다. macOS Intel/ARM64 자료의 조립·해시·실행파일 아키텍처도 검증했으나 Mac에서 실행한 결과는 아니다.

2026-10-05 정리 전 Mac 외부 플랫폼 조립에서는 ARM64 5,161개·Intel 5,158개 파일의 전체 해시, 각 42개 고정 wheel, 원문 라이선스와 Mach-O 아키텍처를 확인했다. 원본 Python 아카이브 실행 모드는 `0775`, Node·Pandoc은 `0755`다. 당시 증거는 `.paper-factory/standalone-mac-runtime-build-156d0677-7315-4773-9343-982d4abbc13e/verification-receipt.json`에 그대로 보존했다. 이후 최종 소스로 다시 조립한 결과는 아래 기록한다.

최초 Windows NSIS 설치 파일 `9ac0ac6364f96547698d123e741449ec84a982830c784e66b48ade7f4286aa7f`는 새 `Paper Factory Standalone` 경로에 종료 코드 0으로 설치됐다. 설치된 EXE와 ASAR는 정적 패키지 해시와 일치하고 자체 계정 연결도 복원됐다. 그러나 설치 후 전체 runtime 검증에서 pip의 `t64-arm.exe`, `w64-arm.exe` 두 파일이 없는 것을 발견했다. 다른 파일은 존재하며 unpacked에는 두 파일이 있다. 제외된 원인은 확정하지 않았고 보안 설정을 변경하지 않았다.

검증을 우회하지 않고 앱 runtime에 필요 없는 빌드 도구 pip를 payload에서 제거하여 다시 묶었다. 최초 설치 파일·정적 receipt·실패 화면·미포함 목록은 `.paper-factory/standalone-verification/installed-app-20261005/`에 보존했다. 최초 설치에서는 과학실험·실제 모델 요청을 시작하지 않았다.

## 정리 후 설치본 검증 체크포인트

최종 엔진은 Python 모듈 21개와 QuickJS worker 하나다. obsolete plugin·CLI·Cloud·수동 제출·Docker/네이티브 호스트 runner를 제거했으며 필요한 runtime 입력과 원문 고지는 desktop으로 이동했다. 기존 논문·실패 기록·출력은 보존했다. 정리 목록과 겹치는 테스트 그룹은 `standalone-cleanup-inventory.md`에 있다. 최종 앱/SDK 테스트는 84 passed, Windows SDK 1 skip이며, 합성 Electron UI 검사는 4 passed다. 이를 실제 OAuth나 논문 성공 수로 합산하지 않는다.

Windows final runtime은 4,463개 파일, 30개 고정 wheel이고 전체 해시와 실제 native probe를 통과했다. Inventory SHA256: `217776ea8de7cefa09e35f9a4ff0f9793640578843d0b945dac250b8137d9221`. Mac ARM64 4,349개/Intel 4,346개, 각 29개 wheel도 동일한 최종 소스 바이트·전수 해시·라이선스·원본 Mach-O 아키텍처 대조를 통과했다. Mac inventory SHA256은 각각 `037c83b14410bab2f72ad207b9a36589823e7513deb228bb86989a7985f7f088`, `136aaafb2c0512f94123ec5c146630df9ae46c2b9935c2dd8c06d114a8e5115c`다. Source manifest SHA256은 세 플랫폼 모두 `c7f5da4ca213b77bcf0acde3c71cc9a96e82896000303a41988344b2a1e86a12`다.

Mac 조립은 Windows NTFS 위의 외부 플랫폼 검사다. 빌더가 실행파일을 `0755`로 설정하지만 실제 Mac 파일시스템의 권한 유지·native 실행·DMG·설치·CI는 미검증이다. 최종 Mac 증거는 `.paper-factory/standalone-mac-runtime-final-1e32964b-0662-40f4-8e42-e4c6a852f599/`에 있다.

Windows 최종 NSIS를 09:39:17 UTC에 정적 검증하고 기존 자체 앱 경로 `C:/Users/Andongmin/AppData/Local/Programs/Paper Factory Standalone`에 종료 코드 0으로 설치했다. 설치 후 4,463개 파일의 전수 해시, EXE·ASAR 대조, GUI runtime ready를 확인했다. 09:41:13.400 UTC에 같은 자체 연결이 복원됐고, 09:42:06.718 UTC에 `gpt-6-astra`의 새 실제 응답이 완료됐다. 설치 파일은 Authenticode `NotSigned`다. 깨끗한 별도 VM 설치와 Mac 설치를 수행한 것으로 주장하지 않는다.

| 당시 설치 파일 | bytes | SHA256 |
| --- | ---: | --- |
| `Paper Factory Setup 0.13.0.exe` | 234,873,533 | `d25f1da75bd000fd88885940dc2410228b681581a2f6c8c5e05969b3560711fb` |
| 설치된 `Paper Factory.exe` | 245,726,208 | `f901100d85aeba395fb6f5ffa51e22945137f6717ad55399cec54666517e2ddb` |
| 설치된 `resources/app.asar` | 42,599,131 | `c2f3c12344fe81a4f921580f00a4842537e6f3e8f2380d8cada2c4c01ecc0f9c` |

최종 설치 receipt·정적 receipt·실제 화면은 `.paper-factory/standalone-verification/installed-app-20261005/`에 보존했다. 두 번째 설치의 5,295개 파일 전수 검사와 09:00:10.892 UTC 실제 응답도 별도 이력으로 보존했다.

## 사이드 탭과 실제 원고 단계의 보완

위 설치본은 실제 첫 연구를 수행한 체크포인트이며 이후 사이드 탭과 원고 근거 전달·재개 보완 소스의 설치본은 따로 검증한다. 연결·새 연구·결과를 고정 사이드 탭으로 분리하고 입력과 작성/리뷰 모델 선택을 유지했다. 최신 앱/SDK 회귀는 87 passed와 Windows skip 1개, 실제 Electron fixture는 4 passed(14.3초)다. fixture의 모델과 인증 자료는 합성이며 실제 연구 수로 계산하지 않는다.

실제 `neobrutal-ui` 연구 `research-9a477cc5d054`의 실행 attempt 1은 성공했다. Production 함수 호출은 17회이고 scalar 관측 32개와 156개 fixture를 보존했다. 양성 제어와 의도적 오류 음성 제어 모두 통과했고 cleanup은 확인됐다. 동결 observations SHA256은 `778284664bc50532301f62e292ad7b72171413c8d64b1c7d4ed942b63cd12b14`다. 첫 두 코드 리뷰 거절·수정과 세 번째 코드 리뷰 승인은 실제 별도 모델 호출 원문으로 보존했다.

첫 원고 리뷰는 원시 관측과 원본 컴파일/실험 코드가 실제로 보존돼 있어도 모델 문맥에 빠져 있다는 점과 계획된 두 번째 문헌 검색 누락을 지적하며 거절했다. 거절은 그대로 보존한다. 후속 원고 작성 중 사용자의 중단 요청이 처리되어 실제 부분 응답을 interrupted receipt로 남겼다. 과학실험은 이보다 먼저 성공 종료했고 반복 실행하지 않았다.

보완한 main은 작성자와 별도 리뷰어에게 해시 검증한 완전한 production 소스, 실험 파일, 원시 관측과 fixture, runtime manifest, 마지막 승인 코드 리뷰를 전달한다. 문맥 상한을 넘거나 필요한 근거가 없으면 중단하며 생략한 근거로 승인하지 않는다. 문헌 수집은 기존 원문을 변경하지 않고 누락된 검색만 추가 버전으로 보존한다.

`workflow.resumeWriting`은 cancelled 상태의 analyzed/manuscript 단계에서만 허용한다. 전수 frozen SHA, retained succeeded execution, cleanup/handle, 실제 production-call gate, 실제 passed=True 양성/음성 제어와 분석의 raw/protocol/control 연결을 확인한 뒤 원고 작업만 복원한다. 이전 workflow 전체 상태·시간대가 포함된 실제 시각·실행/관측/분석 SHA·attempt를 새 `authoring-resume-<uid>.json`으로 보존한다. 집중 재개 회귀 14 passed(2.26초), 전체 workflow 84 passed(13.13초), 문헌/비실험 IPC subset 66 passed/3 Windows symlink skips/8 deselected(3.20초)다. 이 그룹들을 고유 성공 수로 합산하지 않으며 실제 userData를 수정한 검사도 아니다.

최종 검수된 성공 논문은 현재 0/3편이다. 실행·제어의 기술적 성공과 고정 프로토콜의 과학적 완료, 원고 승인과 파일 검수를 각각 구분한다. 아래 후속 독립 원고 리뷰에서 첫 연구의 프로토콜 무효를 확인했으므로 이 연구는 성공 수에서 제외한다.

## 사이드 탭 설치본의 실제 검증

2026-10-05 10:30:56.235 UTC에 최신 Windows 패키지를 정적으로 검증했다. ASAR 7,663개 구성원과 runtime 4,463개 파일 전수 해시, SDK import, renderer와 포함 엔진 21개 Python 모듈/worker의 현재 소스 바이트 일치를 확인했다. Windows inventory SHA256은 `e7e62a60ca3bacd2632cc2b4f956bf49a1ab736d3b46103611c56d187f3bb00c`다. 동일 엔진 소스의 Mac ARM/Intel 정적 조립 inventory SHA256은 `5c0754c620a3fdf7b47b149a4fd347bac886827c0388044055aca59957b8f1e4`, `7eb30df5796d6aff236108f9b7c34dfa94a5fe6baced57ff781bee66a895b3f9`다. Reviewed runtime manifest의 SHA는 계속 `c7f5da4ca213b77bcf0acde3c71cc9a96e82896000303a41988344b2a1e86a12`이며 이는 엔진 소스 전체의 해시가 아니다. 개별 파일 inventory와 현재 소스 바이트 대조로 엔진 변경을 검증했다. Mac native/DMG/CI 검증은 수행하지 않았다.

자체 앱 프로세스가 없는 것을 확인하고 기존 자체 설치 경로를 갱신했다. NSIS는 10:32:35.733 UTC에 종료 코드 0을 반환했다. 설치된 EXE·ASAR·inventory는 패키지와 일치하며 10:32:48.360 UTC에 설치된 runtime 파일 4,463개 전수 해시를 다시 검증했다. 설치본을 실제 GUI로 실행해 고정 사이드 탭과 같은 자체 계정 연결 복원을 확인했다. 10:33:19.292 UTC 모델 5개 조회, 10:33:39.228 UTC 새 `gpt-6-astra` 응답의 `response.completed`를 확인했다. Authenticode 상태는 `NotSigned`다.

| 최신 Windows 파일 | bytes | SHA256 |
| --- | ---: | --- |
| `Paper Factory Setup 0.13.0.exe` | 234,877,401 | `2e21ba2cb3de7361b9264235650b9d57793552b2662b0672c1f7593128dff8fe` |
| 설치된 `Paper Factory.exe` | 245,726,208 | `b70320b8c35eaf485031e7647c34ad8d41853ed43bd58bd948861ca5b8d8cb8f` |
| 설치된 `resources/app.asar` | 42,611,554 | `7316b0b4731ca0b977870f4ca2e6de0d51221043db0be218e4ca9a392e125b64` |

원본 installer·정적/설치/전수 검사 receipt와 실제 화면은 `.paper-factory/standalone-verification/installed-app-20261005/sidebar-install-ab3e1e10-c1cf-4246-80d0-2343765ac032/`에 보존했다. 이전 설치본과 실패 기록은 덮어쓰지 않았다.

이 설치본의 결과 탭에서 작성 `gpt-6-astra`, 별도 리뷰 `gpt-5.6-sol`을 선택해 같은 `research-9a477cc5d054`를 명시 재개했다. 10:35:31.773 UTC의 `authoring-resume-97b12e351f8d.json`은 이전 cancelled/analyzed 전체 상태와 execution attempt 1, 원시 관측 SHA를 보존했다. 기존 문헌 원문을 유지한 채 누락 검색을 추가했고 10:35:34 UTC에 완전한 근거를 포함한 새 원고 요청을 시작했다. 처음 실험은 위 이전 설치 체크포인트에서 완료됐으며 새 설치본에서 재실행하지 않았다.

## 첫 연구의 프로토콜 무효와 내보내기 중단

10:37:39 UTC에 완전한 근거를 받은 작성자 응답이 완료됐다. 별도 reviewer는 10:40:23 UTC에 원고를 거절했다. 첫 고정 프로토콜이 요구한 emitted JavaScript 원문과 별도 사전 syntax/builtin 검증 receipt가 제공되지 않았고, exact-object metric의 omission/undefined 구분을 JSON 관측 경계가 보존하지 못했기 때문이다. 이는 관측 뒤 수정할 수 있는 문구 문제가 아니라 프로토콜 완료를 무효화하는 차이다. 원시 관측·불리한 comparator 결과·실행·제어·거절 원본을 그대로 보존했다.

후속 작성자는 프로토콜이 무효인 실행을 보고하는 원고로 수정했고 10:45:19 UTC에 별도 reviewer가 이를 승인했다. 제목은 **Bounded preview-path identity extraction: observed agreement and protocol-invalidating measurement discrepancies**다. Abstract와 Conclusion은 프로토콜이 유효하게 완료되지 않았고 수치를 frozen exact-object metric의 유효한 추정값으로 해석할 수 없다고 명시한다. 이 승인과 파일 생성은 성공 논문 3편의 하나로 계산하지 않는다. 같은 과학실험은 다시 실행하지 않았다.

PDF/DOCX/Markdown/TeX와 재현 ZIP은 10:45:21 UTC까지 생성됐으나 마지막 검증 요청이 120초 제한을 넘어 `ENGINE_TIMEOUT`으로 중단됐다. 당시 앱 기록은 export 단계 실패였고 생성 파일을 완료 파일로 표시하지 않았다. 원본 경로는 첫 연구의 `research/exports/`이며 그대로 보존했다. PDF는 9쪽, DOCX는 3,015단어/62단락/2개 표, ZIP은 512개 구성원과 510개 inventory entry다. 당시에는 PDF 전쪽 시각 검수와 앱 저장/열기를 완료한 결과가 아니었다. 후속 다섯 번째 설치본의 export 완료와 PDF reader 열기는 아래 별도 체크포인트로 기록한다.

문서 읽기만 별도 진단한 installed bundled Python 3.14.8 결과는 PDF 전쪽 text 0.779초, DOCX 0.388초, ZIP CRC와 전 inventory hash 0.204초다. Trusted 통계 재계산은 0.0015초, 기존 분석의 그림 포함 재계산은 1.668초, 원고 rendering은 0.0086초로 완료됐고 기존 분석과 차이가 없었다. 관측/실험 코드는 실행하지 않았고 이 외부 진단을 앱 성공 검증으로 계산하지 않았다. 재현 ZIP의 진단 전후 SHA256은 `a583a15553683013387a1614d447052f985ed41a05e4d49b3545512b765c74aa`로 같다. 그 진단으로 timeout 원인을 확정하지 못했다. 후속 설치본의 실제 앱 검증은 아래에 따로 기록한다.

진단 증거는 `.paper-factory/standalone-verification/export-timeout-diagnostic-20261005-66865c43-7744-4fc6-95c9-b71ea25791c0/`, `trusted-verification-diagnostic-20261005-11ed0cfb-ffb2-4463-b213-d636e23c066c/`에 있다. 내보내기 재시도가 원래 partial files를 덮어쓰지 않도록 고유 attempt 디렉터리와 시작 receipt를 먼저 저장하는 보완을 구현했고 synthetic workflow 85개가 통과했다. 이후 소스는 아래 다섯 번째 설치본에 반영했다. TypeScript planning/code 안내도 실제 compiler manifest의 hash/version/options 범위로 명확히 했다. 직전 문구 보완의 scientific regressions는 163 passed(12.38초)이며 최종 소스 검사와 구분한다. 기존 고정 프로토콜을 수정하거나 과거 미제공 증거를 소급 생성하지 않는다.

## 내보내기·비재실행·컴파일 증거 소스 회귀

2026-10-05 후속 소스 보완의 전체 Python 회귀는 **669 passed, 7 skipped (125.21초)**이며 기존 `.venv`와 Node 24.21.0을 사용했다. 로그는 `.paper-factory/standalone-verification/verification-journal-tests-20261005-7d60cc2e-1c3b-4d4d-99b3-7931115f2f63/full.txt`, SHA256 `eacbcb424547d6eae8d18111e8f44a682e3bc3a0750cbb044a63453fd80a6bc9`다. 집중 workflow 24 passed/81 deselected(12.23초), 별도 QuickJS 148 passed(72.76초)와 scientific 163 passed(12.00초)는 전체와 겹치므로 합산하지 않는다.

마지막 검증은 고유 attempt 안에 실제 시각의 phase journal을 exclusive 생성하고 각 행을 flush/fsync한다. 통계는 frozen 관측의 `_compute`와 기존 동일 7개 결과 그룹을 비교하며 그림이나 실험을 다시 생성하지 않는다. PDF/DOCX import부터 ZIP까지 phase를 구분하고 journal은 성공 후에만 동결한다. 이미 exported인 문서 재검증도 새 journal만 추가하고 기존 validation/ZIP은 변경하지 않는다. 마지막 journal/validation은 ZIP 생성 뒤의 별도 동결 근거이며 ZIP에 포함됐다고 주장하지 않는다.

실행 이력이 있는 `submit_code`/`start_experiment`는 상태 검사·런타임 접근·파일 쓰기 전에 `EXPERIMENT_ALREADY_DISPATCHED`로 거절한다. blocked/cancelled/running/analyzed 네 상태의 자료·진단 불변, attempt 0의 실행 전 코드 수정 허용을 회귀로 확인했다. 실제 worker가 받은 TypeScript 파일별 `mode`, `sourceMap`, `sourceUrl` 전체 옵션을 `compiled_files[path].transformation_options`로 기록하고 readiness가 검증한다. Top-level transformer options는 shared settings임을 표시한다. 과거 실제 실험의 manifest나 계획은 수정하지 않았다.

보완 소스의 runtime 재조립·Windows 설치와 실제 실패 보고서 export 완료는 아래 체크포인트에서 확인했다. 기존 native fixture의 긴 basetemp(working directory 290자) 실패는 보존한 뒤 새 짧은 자체 fixture 경로에서 통과했으며, 실제 앱의 export-attempt physical 경로는 196자로 그 실패와 다르다. 이를 실제 120초 timeout의 원인으로 계산하지 않는다. 최종 합격 논문은 계속 **0/3**이다.

## 다섯 번째 설치본과 실패 보고서 export 완료

2026-10-05 11:40:00.675 UTC에 보완 소스의 Windows 패키지를 정적으로 검증했다. ASAR 7,663개 구성원, runtime 4,463개 파일의 전수 해시, SDK import·renderer 자산과 포함 엔진 소스 바이트 일치를 확인했다. Windows runtime inventory SHA256은 `b68b03f9c2800c74fef73777aa8ee9c146a24be7cdcf8237e6bbe38b2a52b4ea`다. 이 정적 receipt의 실제 로그인·응답·재시작 항목은 `unverified`로 유지하며 후속 실제 사건으로 대신하지 않는다.

NSIS는 11:41:44.319 UTC에 시작해 11:42:29.338 UTC에 종료 코드 0으로 기존 자체 앱 경로에 설치를 완료했다. 설치된 EXE·ASAR는 아래 정적 해시와 일치했고 11:43:10.894 UTC에 설치 runtime 4,463개 파일의 전수 해시를 다시 확인했다. 보존한 `installer.exe` 자체도 SHA256을 다시 계산해 설치 receipt와 일치함을 확인했다. Authenticode는 `NotSigned`이며 개발 도구 없는 별도 VM 설치를 수행한 증거가 아니다.

| 파일 | bytes | SHA256 |
| --- | ---: | --- |
| `Paper Factory Setup 0.13.0.exe` | 234,878,368 | `a951c8f1d87eb3afefc15a142d9add60d8582fb0cd3a705581e8aad7474e0692` |
| 설치된 `Paper Factory.exe` | 245,726,208 | `82db72a408cb6912cb67c7f6546c0d0e645460c201ce74dd75059125ac2dd963` |
| 설치된 `resources/app.asar` | 42,611,552 | `0b34f041f4a857228ae2949da4283b1c62c777c43030c2cf02773e1582845987` |

11:43:51.644 UTC에 자체 연결 복원을 기록했고 11:44:22.050 UTC에 실제 모델 목록을 새로 조회했다. 새 `gpt-6-astra` 완료 응답의 화면 시각은 11:44:25 UTC이며, `connection-checks.jsonl`의 완료 확인 기록 시각은 11:45:10.629 UTC다. 두 시각을 동일한 사건 timestamp로 합치지 않는다.

같은 첫 연구 `research-9a477cc5d054`의 실패 보고서 export를 명시 재개한 결과 실제 앱이 `exported·completed`와 결과 파일을 표시했다. `failed-report-export-completed.jpg`와 `failed-report-opened-in-reader.jpg`는 완료 상태와 9쪽 PDF의 외부 reader 열기를 보여 준다. 기존 과학실험 attempt 1은 재실행하지 않았고 기존 프로토콜·관측·거절·부분 산출물은 보존했다. 이 보고서는 프로토콜 무효를 명시하므로 과학적으로 성공한 논문 수는 여전히 **0/3**이다. PDF 전쪽 시각 검수·DOCX 시각 검수·모든 저장 버튼의 실제 사용자 동작 검증은 이 화면 증거만으로 완료하지 않는다. 이전 timeout의 원인도 이번 완료만으로 확정하지 않는다.

Installer·정적/설치/전수 검사 receipt·token-free 연결 기록과 실제 화면은 `.paper-factory/standalone-verification/installed-app-20261005/goal-install-f4f99acd-fa8d-40ec-b4e9-52bc7d18b18b/`에 보존했다. 설치 receipt SHA256은 `a7e28e1480b8e2b2c82287213a7ba562461667acfb8f8d397fb081eb497432e8`다. 이 문서 갱신은 해당 보존 파일을 읽었으며 앱·인증 자료·모델·과학실험은 실행하거나 수정하지 않았다.

같은 SOURCE FINAL의 Mac ARM/Intel 정적 조립·전수 해시·소스 22개 파일·Mach-O 및 원문 고지 대조도 갱신했다. ARM은 4,349개 파일/593,560,373 bytes, inventory SHA256 `767bef8355dff1e63c1fc1b77779233834f213b76a6a1e4b9a565ef3a472fc78`; Intel은 4,346개/526,526,228 bytes, `08e2631b74f6d022d04d39ae8a696d470e57902e0051cf8fd272cd56caebf46c`다. 각 profile의 29개 wheel·58개 upstream 원문 고지·20개 PBS 고지와 실행파일 원본 바이트를 확인했고 pip는 포함하지 않았다. 증거는 `.paper-factory/standalone-mac-runtime-journal-final-db5e3272-463f-4059-a770-68417f3c3b60/verification-receipt.json`이며 SHA256은 `55a9cb798bcf18368645a1ac8119b31b08aa68100f30b770805835d11150baa8`다. Windows NTFS 조립과 원본 archive의 실행 mode 확인은 실제 Mac POSIX 권한·native 실행·DMG 생성/설치·CI 실행의 증거가 아니다.
# Goal 후속 실제 연구와 문서 QA: 2026-10-05 12:23 UTC

설치본 build5에서 Frontron `research-b071d98fbed0`을 새로 생성했다. 작성 `gpt-6-astra`, 별도 코드·원고 리뷰 `gpt-5.6-sol`이며, 실제 계획·코드 completion과 code-review accepted 기록을 보존했다. 실험 attempt 1은 실제 production 호출 17회, 관측 32개, retained fixture 39개, 유효한 알려진 결과의 양성 제어와 의도적 2→3 오류의 음성 제어, exit 0과 cleanup confirmed를 기록했다. raw SHA256은 `5df31089d6aaae47376db7424086246edb318e98e3339de18e61638481919657`, frozen protocol은 `38d072f5aaee6514156d09fe0a9252936c32045082ab610ae1485476cd433484`다.

원시 실험 뒤 첫 분석의 그림 생성 구간에서 engine request 120초 timeout이 발생했다. `analysis/attempt-1`의 부분 파일과 timeout 화면을 보존했다. 실제 앱의 실행 환경 다시 확인 버튼으로 엔진을 다시 시작했고, 기존 `_recover`가 성공 receipt·원시 관측·cleanup을 검증한 뒤 분석만 복구했다. `analysis/attempt-1-recovery-d49bc89269de`에 그림 42,253 bytes와 분석 파일이 생성되고 12:18:09 UTC에 analyzed/ready로 확인됐다. 원래 raw/protocol 해시와 execution attempt 1은 유지했으며 과학실험을 재실행하지 않았다. 이어 실제 재개 버튼으로 작성 completion `939e8efb…`(12:22:14 UTC), 별도 원고 리뷰 요청 `30607f66…`(12:22:15 UTC)이 생성됐다. 아직 원고 리뷰·최종 내보내기·성공 집계는 미완료다.

공식 npm/node-semver README의 range/primitive/X/tilde/caret 명세도 실험 시작 전 읽었다. 별도 QA `.paper-factory/standalone-semver-inspection-3be1166f-72f7-4cb2-91fd-80a2b0556dc7/`에 고정 커밋 `6e05b7637396ac66522cff8731f07cfe0ef49a29`, 원문 25,669 bytes와 SHA `f1a789dcec285150be24db2ea04dd3175031554fa9834ec92fab83fb5e025a57`, 12:11:51 UTC fetch receipt를 보존했다. 이 외부 판독을 앱 collector가 수집한 자료나 앱 ZIP 내부 citation으로 가장하지 않았고 frozen 앱 자료를 수정하지 않았다.

기존 protocol-invalid preview 보고서도 실제 저장 PDF 9쪽을 모두 150 dpi로 렌더링하고 원본 이미지로 시각 확인했다. 잘림·겹침·빈 페이지는 없으나 4쪽 양끝 맞춤의 단어 간격이 과도하다. DOCX 실제 62문단·2표·1이미지, ZIP 513 members/511 inventory의 모든 CRC·크기·SHA와 native 파일 대응은 확인됐다. DOCX 시각 배치는 미검증이다. 또한 원고 8쪽의 새 원고 리뷰 미제출 문구는 실제 accepted review와 충돌하며 legacy compiler receipt에는 최신 파일별 옵션이 없다. 파일 무결성과 읽기 가능성을 확인한 것이며 과학 성공으로 계산하지 않는다. 이 보고서의 성공 기여는 계속 0이다. QA는 `.paper-factory/standalone-output-qa-4da9fed8-3005-4406-85ac-9f34cdf71367/runs/legacy-pdf-cc005c7b-132c-4d6b-9c4b-d2302a194665/` 및 `runs/legacy-docx-zip-ade1335e-890d-445d-b45a-7b0389119409/continued/`에 보존했다.

## SSE deadline·분석 초기화 보완: 2026-10-05 12:45 UTC

Frontron의 실제 원고 리뷰 `30607f66…`는 12:25:15.746 UTC에 `stream_interrupted`로 실패했다. 원인은 응답 본문까지 적용되던 SDK의 180초 client deadline이며, 보존된 부분 응답 4,091자는 승인이나 완료 응답이 아니다. 성공한 execution attempt 1·17회 production 호출·32개 관측은 그대로 두고 같은 과학실험을 재실행하지 않았다. 원고 리뷰·최종 내보내기·검수된 성공 논문은 이 체크포인트에서 미완료이며 과학 성공 수는 **0/3**이다.

SDK `responses.ts`의 제한을 `10 * 60_000`으로 맞추고 새 regression 3개에서 이전 3분 cutoff 이후의 `response.completed`, SSE headers 이후 caller abort, 10분 deadline에서 미완료 부분 응답 실패를 확인했다. caller abort와 terminal completion 요구는 유지된다. 전체 npm 검사는 **101 passed, 1 Windows skip**(desktop 53 + SDK 48, fail 0)이다. 로그는 `.paper-factory/standalone-verification/stream-deadline-20261005-487dcc5597df4b3d9e1725d97cfbe132/npm-test.txt`, SHA256 `ead3b8e9765771da664153e3cc715afcb0804de6ae947aee136e45f4e24a2350`다. 모의 fetch·timer 검사이며 실제 구독 요청의 추가 성공으로 계산하지 않는다.

분석 timeout의 별도 synthetic 진단은 설치된 CPython 3.14.8·NumPy 2.5.3과 EngineClient의 같은 environment allowlist를 사용하되 HOME/TEMP/cache를 고유 폴더로 격리했다. 숫자 `[1,2]`만 사용했다. experiment worker가 RLock을 가진 상태에서 Matplotlib을 처음 import하고 IPC status thread는 같은 lock, main thread는 pipe stdin을 기다리면 old-cache 복사본과 fresh cache 모두 NumPy `_multiarray_umath` native extension의 `create_module`에서 멈췄다. 35초 간격 faulthandler stack을 보존했고 140초 뒤 실행 파일·PID·고유 script/case 경로를 검증한 해당 probe 둘만 종료했다. native C stack을 얻지 않았으므로 내부 loader/NumPy 구현의 더 깊은 원인은 확정하지 않는다.

main thread에서 그림을 만들거나, cold worker 동안 main이 `Future.result`를 기다리거나, main에서 NumPy 또는 Agg/pyplot를 먼저 import한 경우는 모두 약 2초에 완료됐다. `StandaloneRuntime`은 owner/home/env/fonts 검증 뒤 runner·WorkflowService 생성 전에 기존 Matplotlib의 Agg/pyplot를 세 문장으로 초기화한다. 과학 측정과 `_figures` 공식은 변경하지 않았다. source SHA256은 `b61f09770a1aaf1c0cdb8b0426d14b99baa3ebf4155ad5c20f273219a49b3c4b`다. 소스의 정확한 세 AST 문장만 추출한 installed-Python postfix probe도 old/fresh 모두 통과했고 시작/ownership/request 집중 회귀는 14 passed/11 deselected였다. 진단 receipt는 `.paper-factory/standalone-matplotlib-thread-diagnostic-1791203036132-a9cc1cf5/diagnosis-receipt.json`, SHA256 `358d651c2ba6d7c279e8b43932725bc578adaf1c5a56ae66b55637a25e243453`이다. 실제 앱·연구 자료·인증 자료·기존 cache를 이 진단에서 수정하지 않았다.

최신 포함 runtime은 다음과 같다. 세 플랫폼의 reviewed dependency manifest SHA256은 기존 `c7f5da4ca213b77bcf0acde3c71cc9a96e82896000303a41988344b2a1e86a12`이며 engine source 전체의 해시와 구분한다.

| runtime | files | bytes | inventory SHA256 | 검증 범위 |
| --- | ---: | ---: | --- | --- |
| Windows x64 | 4,463 | 564,841,353 | `303c08c185c3f5054609c96d116bb71e28696937cc0e2c63c93b167a5d81b4ea` | actualHostTested true, 포함 native probe |
| Mac ARM64 | 4,349 | 593,560,619 | `4b2fbfe8ae3d9c2dbab990c1358821a235359e4d0a5a7f51732656ca80cf1966` | Windows에서 외부 플랫폼 조립·정적 검사 |
| Mac Intel | 4,346 | 526,526,474 | `151d7ed3ef7f0979b6c93fb0949c0b28d3e0df4d7d48825ddc1ea3879ee2156e` | Windows에서 외부 플랫폼 조립·정적 검사 |

Windows build receipt는 `.paper-factory/standalone-runtime-builder/build-win32-x64-f72cd04d-baa8-48a5-8a75-3ba243fe3b72/build-receipt.json`이다. Mac 양쪽은 22개 engine 파일에 같은 early Agg source를 포함하며 전파일 SHA/size, 각 29개 고정 wheel·58개 upstream 원문 고지·20개 PBS 고지와 각 85개 Mach-O의 target CPU를 대조했다. 기존 runtime과 실패/receipt는 보존했다. Mac 증거는 `.paper-factory/standalone-mac-runtime-early-agg-1791203909251-afa39480/verification-receipt.json`, SHA256 `7e8222621128987f61e413d3913c5d0775b7edd27425fa8b0bd57aada7305638`이다. 원본 Python archive mode `0775`, Node/Pandoc `0755` 확인과 빌더의 chmod는 Mac 파일시스템의 실제 권한 보존 증거가 아니다. **Mac native 실행·DMG·설치·로그인·CI는 미검증**이다.

explicit resume는 engine start·runtime ready·retained workflow status를 확인한 뒤 모델을 검증한다. timeout 등 engine transport 오류는 cached ready를 무효화한다. live controller 작업과 startup lease가 동시 resume를 막고, 내구성 있는 started/completed/failed/interrupted receipt를 후속 작업 전에 reconcile한다. 미완료 started journal이나 부분 응답을 승인으로 바꾸지 않는다. 이미 dispatch한 과학실험은 재실행하지 않고 검증된 보존 분석과 원고 단계만 이어간다.

작성자 prompt는 모든 frozen resource bound와 실제 sampling/call count를 명시하도록 요구하고 mutable review status·작성 UI의 기능 상태를 과학 원고에서 제외한다. fresh reviewer도 해당 주장을 보존 근거와 대조한다. 모델의 draft assessment는 journal peer review나 과학적 타당성의 자동 승인이 아니다. 12:45 UTC 현재 정확한 explicit Node 경로로 수행하는 **새 전체 Python 회귀·최종 NSIS 검증·실제 설치 6차는 pending**이다. 기존 다섯 번째 설치의 연결/export 성공을 이 새 소스의 설치 검증으로 소급 계산하지 않는다.

## 여섯 번째 실제 설치·전체 회귀·원고 재개: 2026-10-05 12:58 UTC

Mac profile proposal 두 개를 합치고 Windows inventory `303c08…`가 유지되는지 확인한 최종 NSIS의 정적 검증은 12:46:52.724 UTC에 통과했다. Installer 234,879,323 bytes/SHA256 `4f34429325ae7a6599f40de83943d4c611acd0bffed1610155ac588abd35f5a1`, EXE 245,726,208 bytes/`91af5e3d0552f6c7efe77b29da1210cc3dae98b6d0eb92a533adda9d4c841db3`, ASAR 42,615,476 bytes/`da6c525fb906dc9f5d61ee9f0f12379d0361282041d16040785fffc5617c0183`다. 이 정적 검사 전에 만든 pre-Mac-binding installer와 receipt도 별도로 보존했다.

실제 설치는 기존 소유 앱의 종료를 확인한 뒤 12:48:05.855–12:49:03.253 UTC, exit 0으로 수행했다. 설치된 EXE·ASAR 해시와 모든 runtime 4,463개 파일 및 engine 원문 22개를 대조했고 12:49:22.491 UTC에 일치했다. 서명 상태는 `NotSigned`다. 실제 설치본을 GUI에서 실행해 자체 연결 복원·5개 모델 목록·12:51:58.913 UTC의 새 `gpt-6-astra` `response.completed`를 확인했다. Windows 창 제어의 일시적인 foreground PID 오류는 제어 세션 재초기화 후 복구했으며 앱·연구 상태를 조작해 성공을 만들지 않았다. 증거는 `.paper-factory/standalone-verification/installed-app-20261005/goal-install-early-agg-be871a5a-2f63-49b5-9fe1-7707dcbf0304/`에 있다.

최신 Python 전체 검사는 명시적 설치 Node v24.21.0으로 **671 passed, 7 skipped (126.10초)**, exit 0이다. 초기 잘못된 Node 지정으로 일부 검사가 skipped된 로그와 이어 나온 3개 fixture 실패도 보존했다. 실패한 합성 handle 두 곳이 ambient Node를 가리켜 지정한 Node와 달랐으므로 test-only 두 줄을 실제 선택식에 맞췄고 production 소유권 guard는 변경하지 않았다. 해당 집중 검사는 4 passed/144 deselected였다. 전체 검사의 Node SHA 전후는 `ba4e6d110e8c1592a1ecd390f6b05f3da124b13871a5be62b341a07a853c6c32`로 일치했다. 로그 `.paper-factory/standalone-verification/node-identity-fixture-20261005-37266708786b4352a82f3f21d60608b1/full.txt`의 SHA256은 `c6cae16ee66a0f2f7ac7e06883e7cc7a6aa08ca1727fdb3d635880b674efcc91`이다. 집중 검사와 전체 검사는 중복 합산하지 않는다.

같은 Frontron 연구 `research-b071d98fbed0`을 실제 앱의 재개 버튼으로 이어갔다. 새 작성 completion `574c1c8d…`는 12:56:15.725 UTC에 보존됐고 별도 문맥 리뷰 `aae39f48…`는 12:56:16.738 UTC에 시작했다. 기존 protocol/raw/execution/analysis 해시와 experiment attempt 1은 그대로다. 원고 검토·내보내기·최종 파일 QA가 끝나기 전 성공 수는 **0/3**으로 유지한다.

## 실제 리뷰 거절과 외부 문서 근거 전달 보완: 2026-10-05 13:12 UTC

별도 원고 리뷰 `aae39f48…`는 12:58:37.341 UTC에 완료됐고 `accepted:false`, issue 1을 기록했다. 측정·seed/unit/condition grid·controls·컴파일·자원 제한·문헌·provenance는 검토했지만, 고정 procedure의 공식 npm/node-semver 사전 명세 판독 증거가 전달 자료에 없었다. 실제 외부 판독·고정 원문 fetch receipt는 실험 전에 보존했으나 reviewer 요청이 이 자료를 포함하지 않았다. 완료된 거절을 승인으로 바꾸거나 해당 결손을 문구 수정만으로 해소하지 않는다.

자동 수정의 새 writer completion `8202…`와 이후 review interruption `0f63…`도 보존했다. 13:00:55.444 UTC에 실제 앱의 취소 버튼으로 원고 요청을 중단했다. workflow는 analyzed/ready, app pipeline paused이며 기존 protocol/raw/execution/analysis 해시와 단회 실험은 유지했다. 이후 앱을 정상 종료했다. 읽기 감사는 `.paper-factory/standalone-verification/frontron-final-audit-7a4426d6-cf8e-4984-891e-e6f3a3ea09de/readonly-final-audit.json`, SHA256 `1c701c197479433cae6b2b61047b8554d306268014a87177e965bdf0cc233c55`이며 성공 기여는 0이다.

다음 설치본을 위해 native 문서 선택→원본 bytes·SHA256·현재 import 시각 보존→작성자와 별도 리뷰의 전체 자료→재현 ZIP 경로를 구현 중이다. 외부 문서 내부 날짜·내용은 공급된 주장으로 구분하며, 현재 가져온 시각을 과거 사전 판독 시각으로 가장하지 않는다. 이 입력으로 프로토콜·실험 코드·관측·제어·리뷰 승인 기록을 대체하지 않는다. 공개 원문과 판독 receipt 세 개, 별도로 13:08:19 UTC에 받은 고정 commit의 ISC LICENSE와 license-fetch receipt 두 개를 원본 SHA 그대로 준비했다. 라이선스 수집은 사후 고지 보완이며 사전 판독 근거로 주장하지 않는다. Native 선택용 다섯 문서는 29,186 bytes이며 준비 기록은 `.paper-factory/standalone-supporting-packet-bfbb349c-990e-44d4-8722-c33f78ba25a5/packet-receipt.json`에 있다. 기능·검사·새 설치·실제 근거 전달·새 리뷰·export는 완료 전이며 과학 성공 수는 계속 **0/3**이다.

## 추가 근거 기능 SOURCE FINAL: 2026-10-05 13:33 UTC

추가 근거는 main 소유 native 다중 파일 선택에서 받는다. Renderer는 연구 ID만 전달하며 호스트 경로나 임의 바이트를 지정하지 않는다. controller는 picker 이전부터 작업 lease를 보유하고 runtime·현재 workflow·fatal control 상태를 확인한다. UTF-8 원문 1–8개, 파일별 128 KiB·연구 전체 256 KiB의 누적 한도를 모두 검증한 뒤 현재 import receipt와 새 문서 artifact를 추가한다. 원본 protocol·code·execution·observations·analysis·리뷰는 덮어쓰지 않으며 모델 호출·자동 재개·실험 dispatch도 없다. 작성과 새 리뷰에서 원문·import receipt 전체를 해시와 상호 목록으로 확인하고 재현 ZIP에 포함한다. 전체 문맥 한도 초과 시 일부를 생략해 승인하지 않는다.

백엔드 신규 합성 검사는 85 passed, 기존 작성 재개·material·IPC 집중 검사는 43 passed/87 deselected다. 초기 ASCII 이름 검사의 Unicode case-fold 4개 실패도 보존했고 re.ASCII 적용 후 통과했다. 최신 앱 77개와 SDK 48개는 총 125 passed/1 skipped다. 저장된 이전 job row의 supportingDocuments 필드가 없어도 첫 publish 전에 초기화하고 검증된 엔진 목록에서 갱신하는 회귀를 포함한다. 소스 완료 receipt는 supporting-evidence-backend-20261005-d37210209b064b679dc4d8d601606a7a/source-final-receipt.json (SHA256 f15ce9811144365ed438028d34bed2b1abbd76e10ebaf57685b9d530b4aa5450), supporting-evidence-ui-20261005-cba19f1ee7544b11babf253cfa4e5d70/source-final-receipt.json (9cdff14db691b7e5dc1a30d99c2e17cdcc08ed4d8dfcb2d14e523c878f4d5829)이며 모두 .paper-factory/standalone-verification/ 아래에 있다.

Windows runtime 조립은 exit 0, 4,463 files/564,850,370 bytes, inventory SHA256 a05e54466fd5a77f8f592154f441fd37e15d09266b59e4f8ac8d7c100d72a6e8이다. build receipt는 .paper-factory/standalone-runtime-builder/build-win32-x64-dd43d4b3-8769-4a2c-bfc3-5028dd82d0f4/build-receipt.json이다. 최신 앱 build도 exit 0이다. 최신 전체 Python·Electron fixture·Mac proposal·NSIS·실제 설치·실제 native import·새 리뷰·논문 export는 이 체크포인트에서 pending이다. Frontron 실제 job의 analyzed/ready/paused와 frozen artifacts 57개를 가져오기 전 읽기 전용 snapshot으로 보존했다. 성공 논문은 계속 0/3이다.
## 일곱 번째 실제 설치·native import와 반환 상태 오류: 2026-10-05 13:46 UTC

최신 전체 Python 회귀는 756 passed/7 skipped, 134.25초다. skipped는 Windows symlink 권한 5개와 실제 macOS guardian/EOF cleanup 2개다. 로그 SHA256은 166b26197676f753c3687a4bd00a3c51533f93ded1e60d067725577676e8c000이다. 같은 소스의 기존 Electron fixture 4개는 18.0초에 통과했고 모든 소유 임시 앱은 종료됐다. npm wrapper의 옵션 전달 오류는 앱 시작 이전 실패로 보존했으며 local Playwright CLI 직접 호출로 실행했다. 전체 proof는 .paper-factory/standalone-verification/supporting-import-full-20261005-2b032b42f8d34d338d0bb855888d2f38/이다.

Windows inventory a05e54466fd5a77f8f592154f441fd37e15d09266b59e4f8ac8d7c100d72a6e8을 보존하며 Mac 두 proposal만 병합했다. ARM inventory는 7e26225433da9e03651c435b5bd7bfed6296567301f8981475e68cd3bbb606d0, Intel은 f8da772d0e96cc43fc4775819990fbd51bb28cb44b9617602719e2c8186bb009이다. 각 전체 파일·원문 소스22·29 wheel·58 upstream 고지·20 PBS 고지·85개 Mach-O target CPU 검증을 보존했다. Mac proof는 .paper-factory/standalone-mac-runtime-supporting-evidence-80b7ac9b9e1247049dcc8e843ac49fc9/이며 실제 Mac 실행·DMG·설치·CI는 여전히 미검증이다.

일곱 번째 NSIS는 234,883,151 bytes/SHA256 02925390c3e1b5a389b15028523ee9316b3956c8ae5d7224cff220b66e5e7455, EXE245,726,208 bytes/eb12773870e2e2b5af0286010bd2f22ac5241ddc11aa37834de0dceee78751cd, ASAR42,628,439 bytes/c2ba4f4cd4735a7d2b3552557edd3de99179b9b2a55119bbd96d9b6dca30d030이다. 실제 설치는 13:36:56.623–13:37:47.423 UTC exit0이며 설치 파일 전수·source22 검증도 13:37:49.513 UTC에 통과했다. 자체 계정 복원 뒤 13:39:27 UTC에 새 Astra 응답 완료를 확인했다. 인증 토큰은 proof로 복사하지 않았다. 설치·native import proof는 .paper-factory/standalone-verification/supporting-install-dd64132f-39af-42e5-8605-4f342856b9dd/에 있다.

실제 앱의 추가 근거 선택→native OpenDialog에서 준비된 공개 문서5개를 가져왔고 보존 완료·첨부5개 표시를 확인했다. 긴 다중 절대 경로가 common dialog 입력란에서 잘려 제출하지 않고, 폴더로 이동한 뒤 정확한 다섯 basename을 입력해 선택했다. 그러나 addEvidence의 성공 반환 snapshot이 finally 이전 starting=true일 때 만들어져, idle event 뒤 IPC 반환값을 적용한 Renderer가 busy=true로 남았다. 단위·fixture 및 초기 source audit에서 놓친 실제 동작 결함이며 성공 UI 검증으로 숨기지 않는다. 모델 재개 전에 정상 종료했고 새 측정이나 원고 요청은 아직 없다. 최소 수정은 성공 snapshot 반환을 finally lease 해제 뒤로 이동하는 것이다. 수정 전 true!==false 재현·수정 후 반환값/마지막 publish 동일 회귀를 확인했고 새 app-only 설치본과 실제 성공 import 검증은 pending이다. Python·과학 엔진·runtime 바이트는 이 반환 상태 보완에서 변경하지 않는다. 성공 논문은 계속0/3이다.

## 여덟 번째 실제 설치·추가 근거 성공 반환·원고 재개: 2026-10-05 14:05 UTC

성공 반환을 finally 뒤로 옮긴 최신 앱 전체 검사는 125 passed/1 skipped이며 Electron fixture 4개도 16.7초에 통과했다. 수정 전 실패와 수정 후 성공 로그는 `.paper-factory/standalone-verification/evidence-return-lease-20261005-c86ec677b92747c5b3814be040434628/`에 보존했다. Python 소스와 포함 runtime은 이 UI 수정에서 변경되지 않았고 앞선 756 passed/7 skipped 전체 회귀가 같은 Python 소스에 적용된다.

여덟 번째 NSIS는 234,883,177 bytes/SHA256 `3da7d6e151dd51eec915a690fe28b8cd8a279c96e8b6494f106649373efcbff9`, EXE 245,726,208 bytes/`f764ac81998c73fdb55f63ce91f00c4e68a86cea909cb0709a78ff3b4a65c5b5`, ASAR 42,628,437 bytes/`66b2b1f00b57abe42e716d6cef1c49001efefa628e6923768688ba20d398dde8`이다. 실제 설치는 13:50:24.002–13:51:12.871 UTC exit 0이며, 13:51:15.081 UTC에 설치된 전체 runtime 4,463개/564,850,370 bytes와 source 22개·EXE·ASAR의 일치를 확인했다. Windows inventory와 Mac 두 정적 proposal은 앞선 체크포인트와 같다. 서명 상태는 NotSigned이며 깨끗한 외부 Windows VM, Mac native/DMG/설치/CI를 검증한 것으로 주장하지 않는다.

실제 GUI에서 자체 OAuth 연결이 복원됐고 13:52:54 UTC의 새 Astra connection response.completed를 확인했다. native 파일 선택으로 기존에 보존된 공개 pinned commit-api.json 원문 8,481 bytes/SHA256 `c2675220701d1d461d1d123d64eb8aa4a02c17a8e4bfeb2a2fe4905a8c096ebb`을 추가했다. 14:03 UTC 후속 실제 화면에서 보존 완료·첨부 6개·연구 시작 가능·활성 재개 버튼을 확인했다. 총 문서는 37,667 bytes이며 공급 문서 내부 날짜를 이번 앱 가져오기 시각과 구분한다. 기존 문서를 덮어쓰거나 사전 판독 주장을 앱이 인증한 것으로 바꾸지 않았다. 설치·연결·선택·성공 반환 화면은 `.paper-factory/standalone-verification/evidence-return-install-a2101e4c-cd61-4b57-9583-09a50971e26e/`에 있다.

이후 실제 앱에서 GPT-6-Astra 작성/GPT-5.6-Sol 독립 리뷰 모델 선택을 확인하고 같은 Frontron 연구의 재개 버튼을 눌렀다. 새 원고·리뷰·export·최종 파일 QA는 이 체크포인트에서 진행 중이며 성공 논문은 0/3이다. 기존 protocol·실험 코드·원시 관측·분석·단회 과학실험은 추가 문서 가져오기의 대체 대상이 아니다.

추가 읽기 감사는 import `supporting-document-import-0b87698a01f7`의 실제 시각 13:55:14.128662 UTC와 후속 화면 확인 시각을 구분했다. 이전 artifact 79개의 원본 bytes·경로·SHA·size가 모두 동일했고, raw `5df310…`·protocol `38d072…`·analysis `e67953…` 및 execution attempt 1의 실제 17회 호출·cleanup true가 유지됐다. 새 writer `fa229adf-5d4e-4136-812a-e0ec33421a74`는 14:04:53.800 UTC에 시작했으며 실제 요청에 문서 6개와 가져오기 receipt 2개 원문 전체 및 external-untrusted/no-preinspection 구분이 포함된 것을 대조했다. 감사 receipt `.paper-factory/standalone-verification/supporting-import6-audit-c45163ad-8177-4a71-a395-0633eb0c66ec/readonly-import6-audit.json`의 SHA256은 `34c83a1bc0236299b9f041abd3ad71e8d5f135280aa3a7ba417e8e7ad6a29397`이다. 이 감사는 원고 승인이나 완료된 논문 수로 합산하지 않는다.

writer `fa229adf…`는 14:07:20.033 UTC에 완료됐고, 별도 reviewer `e689844d-5ed4-4a0b-9587-57b177252157`가 전체 원문을 받아 14:10:10.031 UTC에 `accepted:false`/issue 2로 완료됐다. 리뷰는 원고의 mutable acceptance 문구 제거와 외부 SemVer 사전 판독의 controller-verification 결손을 명확히 설명하도록 요구했다. 관측·제어·짝지은 통계·컴파일·문헌·제한에 관한 나머지 18개 검토 항목도 원문 그대로 보존한다. 단독 source 감사가 구체적 문제를 못 찾았다는 사실로 모델의 실제 거절을 대체하지 않는다. 자동 수정 writer `7b393c76-7aa8-4196-8011-abba372e2fda`는 14:10:11.196 UTC에 시작했다. 고정 procedure 원문은 permitted research facilities outside the guest의 실제 판독을 요구한다. 외부 수동 판독 기록과 앱 자체 검증의 경계를 실제 기록으로 대조하며 현재 가져오기 시각을 과거 판독의 인증으로 계산하지 않는다. 실험은 재실행하지 않고 이 시점의 성공 편수는 계속 0/3이다.

수정 writer `7b393c76…`는 14:12:28.983 UTC에 완료됐고 별도 review `4d55b5bc…`는 14:14:49.066 UTC에 `accepted:false`/issue 1로 완료됐다. 원고가 provenance 결손을 명시한 사실과 실제 앱 검증의 결손을 리뷰가 여전히 승인하지 않은 사실을 모두 보존했다. 원래 protocol은 outside-guest 시설의 판독을 허용하며 외부 fetch 12:11:50–12:11:51 UTC는 실험보다 앞선다. 외부 사전 판독과 온전한 JSON 관측이 있다는 host QA 판단을 새 앱 리뷰 승인으로 치환하지 않는다. 세 번째 수정 writer `2aadbb83…`가 시작한 뒤 실제 앱의 취소 버튼을 눌렀고, 14:17 UTC 화면에서 유휴·paused·analyzed/ready 상태를 확인했다. 이 연구는 승인된 원고/export가 없으므로 최종 성공 수에 포함하지 않으며 동일 과학실험을 재실행하지 않는다.

## Premiere 새 연구 시작: 2026-10-05 14:19 UTC

여덟 번째 설치본의 자체 연결에서 공개 URL과 수정 사전 요청 3,993자를 실제 입력하고 연구 시작을 한 번 눌렀다. 새 연구 ID는 `research-a90ccd5fee76`, writer GPT-6-Astra/reviewer GPT-5.6-Sol이며 실제 화면은 created/ready·plan 진행을 표시했다. 요청은 complete original `plugin/lib/planner.js:approveCandidates`만을 사용해 정수 셀 삭제 합집합의 독립 계약과 overlap-blind additive budget을 비교한다. seed 17/29·각 8개 유효 계획·두 조건·단일 binary metric·실제 반환 양성 제어와 의도적 오류 검출을 요구하며, 해당 native 입력 화면은 앞선 설치 증거 폴더의 `premiere-new-study-start-ready.jpg`와 screen.txt에 보존했다. 새 계획·코드·독립 리뷰·실험·원고·export는 이 체크포인트에서 완료되지 않았고 성공 논문은 계속 0/3이다.

## 실험 전 계획 자료 전달 결손과 보완: 2026-10-05 14:30 UTC

실제 계획 completion `c37a1fbd…`는 14:19:59.335 UTC에 `feasible:false`를 기록했다. 원래 planner.js는 17,205 bytes/SHA256 `d5ae61bf96669917e1485382cc99c39157cf057d39504bf8afbd7fae1aa2cdef`로 완전하게 보존됐지만 초기 모델 요청은 16,000자 발췌에서 tokenize 중간과 helper/UMD export 앞부분을 잘랐다. 코드·원고의 전체 페이지 조회 경로가 계획에는 연결되지 않은 실제 전달 결함이다. 온전한 원본을 임의 코드로 대체하거나 모델의 거절을 승인으로 바꾸지 않는다. created/ready·execution attempt 0·code 0·frozen protocol 없음 상태와 실패 원문을 보존했다.

읽기 감사 `.paper-factory/standalone-verification/premiere-planning-delivery-audit-4a7f75e7-3c49-4596-997a-bb1e95b92e4a/readonly-planning-delivery-audit.json`의 SHA256은 `1f834e250a83f7d45174b70a8cc3825f74cff8a158ce1ea2e7e16b90877f8196`이다. 계획 요청에도 선언된 원본 목록·해시·완전한 UTF-8 페이지와 실제 LICENSE/NOTICE 원문을 전달하고 기존 전체 문맥 한도를 적용하도록 수정 중이다. 취소의 authoritative workflow 반환을 목록에 반영하지 않아 ready가 남는 별도 UI 상태 결함도 보완한다. 앱을 정상 종료하고 해당 설치 EXE 프로세스가 없음을 확인했다. Python·과학 엔진·runtime·실제 자료는 이 main controller 수정에서 변경하지 않는다. 후속 앱 회귀·설치 9차·같은 미실행 연구의 명시 계획 재개는 완료 전이다.

## 아홉 번째 설치와 실제 전체 계획 전달: 2026-10-05 15:00 UTC

main controller와 직접 대응하는 테스트 두 파일만 수정했다. 계획에도 선택한 원본 전체와 루트 README/LICENSE/NOTICE를 읽어 전달하고, 각 페이지 SHA·Unicode codepoint offset·재조립 UTF-8 SHA·byte size·누적 문맥 상한을 검증한다. 원문 SHA/size 전량 목록은 내부 검증에 사용하며 모델에는 전체 선택 원문 map을 전달한다. 500,000자는 material 누적 상한이고 전체 직렬화 prompt 길이라는 주장은 하지 않는다. 취소는 current task 정리와 실제 workflow 상태 갱신까지 lease를 유지하며 finally 이후 유휴 snapshot을 반환한다. 이전 reviewMaterials 경로는 교체했다. 앱·SDK 160 passed/1 skipped 및 격리 Electron 4 passed/16.9초를 통과했다. 완료 receipt `desktop/.paper-factory/standalone-verification/controller-source9-fix-6bb85d72-e958-4fac-a5a1-91f126de2d43/source-final.json`의 SHA256은 `97f70e4a92881eb1728b91a6952e6bee231da5826a5ff861becf4063430fc5d2`다. 독립 읽기 감사에서도 구체적 차단 결함이 없었으며 두 소스와 완료 receipt·로그 해시 대조를 별도 보존했다.

NSIS 조립·정적 패키지 검증과 실제 설치는 exit 0이다. 설치 시각은 14:53:20.143–14:54:11.817 UTC, installer 234,883,742 bytes/SHA256 `7f47576e79d30957c71f7c14cc26ca8dbe9cc17a91919b79ee07ece05797705c`, EXE245,726,208 bytes/`295d0a3b5f25f171f44d7fa6fe5cd7a312dc0866d8e7ab4307b1f18c773ed0c0`, ASAR42,632,122 bytes/`3d16c8956f29c94be4c40a2de811a02772447a0dfd04399591a42ba0ceb073e0`이다. 설치된 EXE/ASAR·main/preload·모든 참조 renderer JS/CSS가 현재 빌드와 일치한다. runtime 4,463 files·inventory `a05e54466fd5a77f8f592154f441fd37e15d09266b59e4f8ac8d7c100d72a6e8`·엔진 source22 전수 검증을 14:54:22.648 UTC에 통과했다. 설치 앱 helper의 첫 실행은 Windows ASAR 경로 separator 사용 오류로 실패했으며 원문을 보존하고 기존 static verifier와 같은 native separator로 고쳐 재검증했다. 앱 파일 누락이나 실제 엔진 오류로 계산하지 않는다. 서명은 NotSigned이며 Mac native/DMG/install/CI의 미검증 경계는 그대로다.

실제 설치 앱이 자체 계정을 복원했고 14:55:56.029 UTC에 `gpt-6-astra`의 새 `response-completed`를 받았다. 인증 파일은 읽거나 proof로 복사하지 않았다. 보존된 Frontron의 원고만 명시적으로 재개한 뒤 실제 취소 버튼을 눌러 유휴·analyzed/cancelled·CANCELLED를 확인했다. 취소 요청 중간 화면과 완료 상태를 구분하며 이 검증을 새 과학실험이나 승인 원고로 계산하지 않는다. 같은 자료의 실험 재실행은 없다. 설치·실제 응답·취소 완료와 후속 계획 재개 화면은 `.paper-factory/standalone-verification/planning-material-install-e96560c6-5b66-460c-abde-e917ff0589de/`에 보존했다.

Premiere `research-a90ccd5fee76`는 14:58:36.469 UTC에 실제 새 계획 요청 `fa54c17e-8163-4b15-a467-6f0f7e6f9ab8`을 시작했다. 전체 planner17,205 B·소비자 editor-flow6,354 B·LICENSE11,339 B·NOTICE190 B·README9,055 B가 manifest SHA/size와 일치함을 요청 원문으로 대조했다. 최초 feasible=false 요청·원본·목표는 불변이다. 새 계획은 14:59:59.389 UTC에 feasible=true로 완료됐고 protocol `331dbcf2ab981a4da09dabe54ca03daead95cf8c577ce99b18aee1447b1356e7`/11,503 B로 동결됐다. 정수 셀의 8행×seed2·production-first·독립 점유 oracle·additive budget comparator·32 scalar grid·실제 정상/의도적 오류 검출/별도 safety 제어 및 18회 호출 계획을 검토했다. code `ecedd5c3…` 요청은 15:00:05.737 UTC에 시작됐다. 실제 두 Crossref query의 보존된 abstract 6개만 문헌 근거로 사용할 수 있으며, 원래 query에 쓴 Survey 제목을 그 자체로 읽었다고 주장하지 않는다. 이 체크포인트에서는 코드·새 독립 리뷰·실험·원고·export 완료 증거가 아직 없었고 성공 수는 0/3이었다.

## Premiere 단회 실험·원고 승인과 출력 수정: 2026-10-05 15:29 UTC

실제 code completion `ecedd5c3…`는 15:01:45.225 UTC, 별도 code reviewer `b8faaa90…`는 15:04:24.870 UTC에 accepted=true/issues=[]로 완료됐다. 단회 execution attempt 1의 실제 원본 호출은 18회, 입력 단위는 16개, 짝지은 관측은 32개다. 두 정상 제어 호출과 같은 실제 반환의 의도적 오류 검출, 별도 safety 제어를 확인했으며 cleanup=true/active_handle 없음/exit 0이다. 성공 반환 12회와 의도된 알고리즘 거절 6회를 인프라 오류와 구분했다. production 평균 1.0, additive comparator 평균 0.8125, comparator-minus-production 평균 -0.1875/표본 SD 0.4031128874/단위 16은 원시 관측·분석·원고 표와 일치한다. 실제 전체 원본 66개와 고정 artifact 76개의 SHA·크기를 전수 대조했다. 과학 감사 기록은 `.paper-factory/standalone-verification/premiere-live-readonly-audit-1c62d923-4bae-47d2-a5cb-3a159e808bcd/final-scientific-audit-108db872.json`(SHA256 `2c1ee07d3312fca692eeda7d2f33ed9feb9e676b1c1242aa2359916c8298a004`)이다.

새 Astra 원고 `2807d14d…`는 15:07:13.660 UTC, 실제 별도 Sol 원고 리뷰 `10297a63…`는 15:09:34.494 UTC에 accepted=true/issues=[]로 완료됐다. 앱은 15:09:35.980 UTC에 exported/completed/idle 및 Markdown·PDF·Word·TeX·재현 ZIP을 표시했다. 고유 export attempt는 `export-attempt-271ec693c299`이며 PDF SHA256 `878655e31642ace38f91d2842eb686548b3da90e619a6f48953c9ff271240148`, Markdown `34a791b6cd776656e2046409bd05fc586f076eeeba89082311bffcd8ae43bf22`, ZIP `815c39ce1eb82dcf8491da67e3d62ec4a1b29b16f0673c4a1acf27746d696896`다. 실제 native Markdown 저장은 최종 output 폴더에서 25,104 bytes·동일 SHA로 확인했고, 아직 나머지 네 형식의 최종 native 저장은 완료하지 않았다.

읽기 전용 출력 QA `qa-92f8fd99-817c-4096-9af7-de7529815862`는 PDF 10쪽 전체를 150 dpi로 렌더링해 직접 확인했고 잘림·겹침·빈쪽·그림/표 절단은 없었다. 그러나 9쪽 References[2]에서 Crossref 제목의 span/br HTML 표시가 발견돼 pdfVisualQualityPassed=false로 보존했다. DOCX 67문단·2표·1그림·OOXML 19개 및 ZIP 129개 전 멤버의 CRC·크기·SHA 검사는 통과했으며 DOCX native 시각 검수로 주장하지 않는다. 출력 입력 8개의 전후 해시는 동일하다. 이 체크포인트에서 제목 렌더링 보완과 완료 연구의 명시 원고 수정 기능을 Source10에서 구현 중이었다. 이전 원고·리뷰·export·관측을 보존하고, 새 실제 writer/reviewer와 새 export를 거치되 같은 과학실험은 다시 실행하지 않는다. 최종 성공 논문은 출력 수정·검수·앱 저장/열기 완료 전 **0/3**으로 유지한다.

## 열 번째 설치본과 Playwright 전환: 2026-10-06 02:37 KST

Source10의 서지 제목 렌더링은 기존 HTML→plain helper를 제목 필드에만 적용한다. 원문 문헌·canonical citation metadata·저자·연도·DOI·원고 본문은 변경하지 않는다. 완료 연구의 명시 `workflow.reviseWriting`은 전량 frozen/source 해시·성공 execution·cleanup·실제 양성/의도적 오류 검출·분석 연결·완료 validation/journal·이전 원고 승인 해시를 검증한다. 고유 revision receipt에 이전 전체 workflow를 보존하고 이전 원고·승인·출력을 history alias로 유지한 뒤 analyzed/ready에서 새 실제 작성·리뷰만 허용한다. 기존 draft/관측과 과학실험 attempt는 유지된다.

Python 전체 검사는 **786 passed/7 skipped, 144.37초**다. Source10 22개 소스와 `PF_NODE_BIN`의 Node 24.21.0 바이트는 검사 전후 동일했고 Node SHA256은 `ba4e6d110e8c1592a1ecd390f6b05f3da124b13871a5be62b341a07a853c6c32`다. skip 7개는 Windows symlink 권한 5개와 실제 macOS guardian/EOF 검사 2개다. 전체 log SHA256 `64fe135722cabbd1d5fa7bad8fac51b29ec2d00e0e2b5299f1f54511ff1b198e`, full receipt `9c92042bf3845a58b8b15e349038aa3026b4717981991876d59adb6e9b6cdbd3`를 보존했다. 새 기능의 focused45/주변64 검사를 통과했고, 최초 긴 pytest cwd의 WinError267 실패는 보존한 뒤 소스 변경 없이 짧은 owned basetemp에서 재확인했다. 앱·SDK 전체는 **179 passed/1 skipped**(desktop131/SDK48, POSIX 조건1 skip), Electron fixture는 **4 passed/21.3초**다. Frontend final receipt SHA256 `49995bf174d6a474cb86d3af35b6577c4c806583d6e3c03d6d476cb9964f3bed`, backend `6c102e41639d6b0bfa7509c7991f7202ebe5236852a9e8a2612508824a401f67`이다.

세 runtime을 순서대로 재조립했다. Windows **4,463파일/564,855,928 B**, inventory `949d693f56816232223e075adcbcd304d7c055bc25df7a0a35781985748bd62c`; Mac ARM **4,349파일/593,575,194 B**, `439263126d9f6da97899fea234b37716cf345b8afa1fefc1f38644793e4cfc94`; Mac Intel **4,346파일/526,541,049 B**, `8259f9b2b9118a153f36faab27a7183253a32dc441299b5b12493ba4cff500de`다. Binding SHA256 `a50db0b453b9ee8b1309afcf06ebdc3642545ce662fd0786251c6b84789a91d2`이며 세 프로필이 현재 source22/manifest와 연결된다. 독립 Mac 정적 QA는 각 모든 파일·85 Mach-O CPU·source22·58 original notices·42 font copies·29 wheels·20 PBS notices, 고유 pinned archive64개를 확인했다. Receipt `222dd24bf98c4af75bd49762ac9a2fe8e09b8de9460414baee6ff6ba61f723a0`와 source 전후 `519d16b2e2d1e1d6b484a7ba10979c2ce5a1d1a155ca6e2fd04360f19a5ad285`가 보존됐다. Mac native 실행·권한·DMG·설치·CI는 모두 미검증이다.

NSIS 실제 설치는 **02:23:57.491–02:24:53.649 KST, exit0**이다. Installer **234,884,972 B/SHA256 `8e75784de277159e373ac0dbef971c94374b1d699269d3c79969eb977e779418`**, 설치 EXE **245,726,208 B/`1c691239b4c97c05bad2cd33f7076c4a89c96b58078d65cba023b7e15d7d4d1d`**, ASAR **42,635,956 B/`881554ec433714ac33c20b0248557b7ebc7d824470fdbfb9b24fce35fe4e30ad`**다. 02:25:14.144 KST에 설치 runtime4463/source22 전량 대조, 02:25:26.487에 EXE/ASAR 및 main/preload/renderer와 참조 JS/CSS 일치를 확인했다. EXE는 NotSigned이며 clean Windows VM 검사는 수행하지 않았다. 실제 자체 연결의 새 Astra response는 **02:26:33.187 KST**에 완료됐고 safe event/text SHA는 `a0ae5d7b5f387303253b02b254d91296c7d35747c075fd08cdfff9d1955ecbce`다. 설치·전체 검사 증거는 `.paper-factory/standalone-verification/authoring-revision-install-ddcd2967-fdae-4778-bef6-7c2f21b47271/`에 있다.

사용자가 모니터를 끄고 계속 진행하도록 요청해 실제 설치 앱의 조작을 기존 Playwright Electron API로 전환했다. 유휴 앱을 정상 종료한 뒤 같은 installed EXE를 `executablePath`로 실행했고 실제 `app.isPackaged=true`, installed ASAR, 동일 own userData를 확인했다. OS 화면 캡처·좌표 입력·dialog mock·모델/엔진 직접 CLI 호출 없이 DOM의 실제 모델 조회와 선택을 수행했다. DOM/Chromium 화면 캡처가 성공했지만 OS의 실제 모니터 전원 상태를 별도로 측정한 증거로 주장하지 않는다. Playwright는 native OS SaveDialog를 조작하지 않으므로 Source11에서 앱 내부의 저장 경로 입력창을 구현한다. 새로운 저장 동작의 실제 검증은 아직 pending이다.

Premiere의 실제 원고 수정 버튼을 한 번 클릭해 **02:33:41.333597 KST**에 `authoring-revision-a67b2c58ad8a`를 생성했다. 이전 workflow의 17필드/76개 metadata가 원본과 정확히 같고 12 history alias·64 untouched의 path/SHA/size/full bytes가 유지됐다. Current79 frozen 전파일 해시는 통과했고 execution attempt1/calls18/raw32/대조군3/cleanuptrue 및 protocol/raw/analysis/literature는 불변이다. 새 실제 Astra writer `d6944206-5e15-4ff5-a367-f6b5eb944a1e`는 **02:33:42.872 KST**에 시작됐고 prompt189,319 chars/SHA256 `b4c75fffb9ed7145c2a13edb6650b742524d4c2bbdd91fa2211b3db6857bbe1e`의 main↔engine 원문 일치를 확인했다. Revision audit SHA256 `e0ad96e13eb13e4080958db4d915c8989f9ead487e40deb94e09e0049190627e`를 `.paper-factory/standalone-verification/source10-actual-revision-audit-20261006-c81a6b8ac6184aab963d2917a5fdafa9/`에 보존했다. 새 원고·별도 리뷰·export·출력 QA·5종 실제 앱 저장 완료 전 최종 성공 수는 **0/3**이다.

## 두 번째 원고의 시각 검사 실패와 Source11: 2026-10-06 02:55 KST

Astra writer는 02:36:10.749 KST, 새 Sol reviewer `b78326be…`는 02:37:42.406 KST에 accepted=true/issues=[]로 완료됐다. 02:37:43.940 KST의 새 export `export-attempt-8d19cd85d9de`는 PDF135,360 B/SHA256 `83c7cb96031168bfe26afa2c4ca01c2b5a1a12f2bd43950616d080fb7bc14932`, MD25,182 B/`a68e4e6484fd67734f19b8a1a15529edce308817aa7a280b5d9ddd7a5e7522c5`, ZIP1,529,180 B/`cb27165e629322425eb8f4a43c4b234870b19ffedd042c0ce17d51d2792c4d8d`를 생성했다. 현재 100개 frozen metadata와 이전 76개 전량 바이트, 7개 과학 artifact·18회 호출·32관측·단회 execution의 불변을 확인했다. Export read-only audit SHA256 `9c78728cbfe3d4f6616e279e43309110ddec6204ccbd0c4ea2959393115da00b`를 보존했다.

새 PDF 10쪽 전체를 150dpi로 직접 검수했다. 잘림·겹침은 없으나 9쪽 References[2]에 span/br 표시가 계속 남았다. 실제 raw title은 `&lt;span&gt;…&lt;/span&gt;`와 `&lt;br&gt;`를 포함한다. 첫 수정은 파서가 entity를 literal tag로 해석한 뒤 제거할 기회가 없어 실제 인코딩 형태를 처리하지 못했다. DOCX63문단·표2·그림1/OOXML19 및 ZIP153 전 멤버 CRC·size·SHA는 일치하며 입력8개 전후 바이트가 같다. 시각 검사 결과는 false로 보존한다. QA proof `visual-resource-reference-proof.json` SHA256 `af9a2b0eec98c55d35f9c30d18abd6f9065aa0186f4105ff562a83e9121c2846`와 `supplemental-byte-content-proof.json` SHA256 `b0f3b5246d74ac0d4042772ac441f9b6e05f1d2c6e6e76edbe8d01fe8cf731fc`는 `.paper-factory/standalone-output-qa-4da9fed8-3005-4406-85ac-9f34cdf71367/runs/qa-037cb458-3e1b-40e2-9a3a-e8e3ebb5a66c/`에 있다.

Source11은 문자열 제목에만 표준 `html.unescape` 한 번 후 기존 HTML→plain helper를 적용한다. 실제 encoded title의 실패 회귀를 먼저 보존했고 focused13 통과와 합성 MD/PDF/DOCX/TeX/canonical10개 원본 해시를 확인했다. 원문 제목·저자·DOI·본문·raw 문헌을 변경하지 않았다. Backend final receipt SHA256 `a06bfc20c5d01314779b1fd1aeca8c4608ed2418806090351c5cdd8b8073f818`에 기록했다. 앱은 기존 Base UI로 절대 저장 경로 입력·저장·취소·오류 수정을 제공하며 기존 native SaveDialog 경로를 제거했다. 제한 IPC·원본 SHA 검증·app-data 보호·실제 write/fsync/저장 후 해시 확인을 유지했다. Frontend184 passed/1 skipped 및 Electron4/4(18.6초)를 통과했고 final receipt SHA256 `f165d3a5c7212497233a76b0c9636f9ed46f940838b68835463fce93eeba6d66`이다. 이 합성 검사를 실제 저장 완료로 계산하지 않는다. 새 전체 검사·세 런타임 조립·설치·실제 세 번째 원고와 리뷰·5종 저장은 진행 중이며 성공 수는 **0/3**이다.

## 열한 번째 설치와 세 번째 원고 시작: 2026-10-06 03:07 KST

Source11 전체 Python **794 passed/7 skipped, 138.08초**를 02:54:36.162–02:56:54.827 KST에 통과했다. Source22 및 지정 내장 Node24.21.0은 전후 동일하며 full log SHA256 `bb2f50af8d1b2d54786c79692415f3556a78b95d2909d1816cb81387a118a5f1`, receipt `fc1feb08836f5e22612d9b55f05873a6efa03d8ac7320e004604be7c288a536b`다. 세 runtime을 순서대로 재조립했다. Win4463/564,856,045 B/inventory `476a0042d48f5c120b6e06e54cc388dbc8773dfa70229c645c2fb51099e894ce`, Mac ARM4349/593,575,311 B/`9ed9b00611c1e40e1c1377a67ac85059d5a6678f54706ff0c86c7de445eabee7`, Intel4346/526,541,166 B/`2b51e6b6d35d048061ad7fe8fe3722ef086db2635c4154fb056946db519904ed`다. Current binding SHA256 `d4603bc14f2650ae6a469ddae60d18b725836e0754a97f2663c34b475ad23a3c`와 source22 전후 baseline을 전수 대조했다. 독립 Mac QA receipt `afbe1ef6a78345eff6530cf9ff153840ee762171b06f0fdb90782812b0ded7ec`, source 전후 `a60dd116020c387aebdf2b3ea2aee89b3c90fce0ecad0f1b74f899aed8bff565`는 새 `qa-b9d86eed-a2e3-4370-9c77-b868ba212ef2`에 보존했다. Mac native/POSIX 권한/DMG/설치/CI는 미검증이다.

NSIS 정적 검증 후 실제 설치는 **03:01:26.056–03:02:16.394 KST, exit0**이다. Installer234,888,910 B/SHA256 `07cb0979d7b823d2a02e8b9c5eee5fab200c2e6f80c19712b7ac7cd2543d7f19`, EXE245,726,208 B/`ba7f8e41e4f084fac44cc593df469abc1ac83638e7e81a6feb6ac26e74856d92`, ASAR42,652,545 B/`8f991abc99d2a7435d94cb58fd80f026670990e61261d0da0275e5994fd530de`다. 설치된 앱 파일·main/preload/index 및 참조 JS/CSS와 runtime4463/source22를 전량 대조했다. Installed runtime receipt SHA256 `079f753f6f479ec4f9e61beee44160175e732cc0f4a9531157d0018959b39664`, installed app receipt `3dfe06705ba90654e0a3bb73c6784c9ccf20dd6f401d583c524766234a4f74c7`다. 실제 설치 앱은 isPackaged=true/installed ASAR/같은 own userData이며 자체 연결을 복원해 **03:03:07 KST** 새 Astra 완료 응답을 받았다. Proof는 `.paper-factory/standalone-verification/combined-source11-install-128e14e7-e3fb-4129-8c06-f8b103b2709b/`, Chromium 화면은 `output/playwright/standalone-live-source11-20261006-128e14e7/`에 있다. 서명·clean VM 검증의 제한은 유지된다.

모델 선택 영역의 이름이 바뀐 후 기존 group name으로 snapshot을 기다리던 도구 세션이 시간 초과로 초기화됐다. 실제 원고 수정 전이었고 앱 mainPID47972는 그대로 유휴 상태였다. 공식 Playwright `connectOverCDP`로 이 앱의 loopback DevTools endpoint에 다시 연결했으며 앱을 다시 실행하거나 계정 파일·연구 상태를 수정하지 않았다. 이후 실제 DOM 목록의 Astra writer/Sol reviewer를 선택하고 Premiere 원고 수정 버튼을 한 번 클릭했다. 새 revision `authoring-revision-d39966374d7b`는 **03:05:13.457640 KST**이며 previous_workflow17fields/100metadata가 직전 snapshot과 정확히 같다. 이전100개 full bytes/SHA/path/size·과학7개·단회 execution/18calls/32rows/control3/cleanup가 불변이다. 새 Astra request `378f2c8e-bb21-4c91-a81e-7f74eaf410c4`는 03:05:15.458 KST에 시작했고 동일한 고정 과학 입력을 읽는다. Revision audit SHA256 `1a6c062eae46478803f7ba86068129ef33a9440cfe2929e4c216a40dc5fbd82a`는 `.paper-factory/standalone-verification/source11-actual-draft3-revision-audit-20261006-32935bd51b8547d3bfc534c22c31c74d/`에 있다. 새 리뷰·출력 QA·앱 실제 저장/열기/폴더 확인은 진행 중이며 최종 성공은 **0/3**이다.

## Premiere 사용자 산출 완료와 두 번째 연구: 2026-10-06 03:18 KST

새 Astra writer는03:07:57.405 KST, 새 별도 Sol reviewer `df481a6c-d5f1-470f-8bca-c11f14b90bcc`는03:08:50.363 KST에 accepted=true/issues=[]로 완료됐다. Native submission의 review는 현재 Markdown SHA256 `ec9816ccf42324e2817e4c6fec30983eef00efbff43c5a13deb7429437ef1495`와 protocol/analysis/literature 해시를 정확히 승인한다. 03:08:52.021 KST에 `export-attempt-9a4f5f1c4740`/exported·completed·idle이 됐다. 현재124개 전량 해시·이전100개 full bytes·과학7개·execution1/18calls/32rows/controls3는 불변이며 원래6개 abstract의 encoded title도 유지한다. 최종 읽기 감사 SHA256 `bdfbd28eb4945bf468a727f03bffdaf8ff1986f4f589689df0803a1733dfb860`, fresh inference binding `bb3f74691de5ab7011b993de4c162d4da7b01a9534f238f97e14edb4661ad81f`를 보존했다. 이전 두 원고·승인·세 export attempt·revision receipt가 재현 ZIP에 포함되고 중첩 ZIP은 없다.

새 QA run `qa-1b4992b6-1ff6-4149-b85e-d6adffdf2638`에서 PDF10쪽을150dpi original로 직접 모두 확인했다. 참고문헌[2]의 span/br 표시·잘림·겹침·깨진 글리프가 없다. DOCX65문단/3200단어/표2/그림1 전본문과 OOXML19 및 ZIP176 모든 멤버의 CRC/size/SHA를 확인했다. 입력8개 전후 bytes는 동일하다. 시각/내용 proof SHA256 `3bc1359cc0f4e4954b5843e66abdd2947407aebfb64c4aff7e7f4a0784be690b`, supplemental `4eb15c9b62f851d7d9cc7382c55a102a68d005665eb69c2ce5394af6afe30f5d`다. 4쪽 문자열 문장의 중복 마침표3개는 비차단 편집 주석으로 남겼으며 새 수정·review를 꾸미지 않았다. DOCX 페이지 시각 검수나 과학 재측정을 한 증거로 표현하지 않는다. 첫 실험의 scientific audit·unchanged science7·현재 새 실제 reviewer와 결론/한계의 제한을 함께 확인했다.

실제 설치 앱에서 다섯 저장 버튼과 새 경로 dialog의 저장 버튼으로 `output/standalone-20261005-46bf68c6/premiere-ai-harness/`에 저장했다. 저장본5개 size/SHA가 frozen 원본과 정확히 같다. 이전 native Markdown은 하위 `superseded-reference-formatting/`에 그대로 보존했다. Save UI proof SHA256 `7aec120d4e9145518982bc3c8745580c84d5d983c70d3423ca5a48c2cb0c979c`, verified copies `de7b180ebf3ac36611ddfb7670f96671d4e96f06791fea7c6b50fb2d99bf3e45`다.

실제 앱의 PDF 열기 버튼은 mock 없이 성공한 shell 호출을 완료했고 Acrobat Reader의 paper.pdf 창을 관측했다. 접근성 tree에는 그 Reader의 전체 경로나 문서 본문이 없어 해당 Reader의 정확한 파일/렌더 완료를 주장하지 않는다. 같은 SHA의 사용자 저장본을 별도로 기존 Chrome154.0.8037.97에서 Playwright로 열어 exact file URL, PDF viewer10쪽, 실제 첫쪽 표시를 확인했다. Chrome connector 미제공 및 channel의 ProgramFiles 조회 오류를 설치·환경 변경 없이 기존 Chrome EXE 경로 지정으로 해결했다. 결과 폴더 버튼도 mock 없이 실행했고 Explorer 접근성의 전체 C:→Packages→LocalCache→Paper Factory Standalone→research-a90ccd5fee76→export-attempt-9a4f5f1c4740 경로와20개 파일 표시를 확인했다. Native 화면 캡처·활성화·입력은 사용하지 않았으며 접근성만 읽었다. Open/folder 구분 proof SHA256 `e0abf0a1381f3639aabce556e4aab81b70e0bbb7780b9310264ee84793fedc19`와 Chrome 화면을 보존했다. 이 한계를 유지하면서 실제 출력의 사용 가능성과 앱 기능을 확인해 Premiere를 첫 최종 연구로 계산한다. **최종 성공 수1/3**이다.

| 저장소·연구 ID | 사용자 파일 | 크기·SHA256 |
| --- | --- | --- |
| premiere-ai-harness / research-a90ccd5fee76 | [PDF](../output/standalone-20261005-46bf68c6/premiere-ai-harness/paper.pdf) | 137,681 B / `c42ff37295d4e0770022047f4365596800fbb0b7f1211dcd128b8978979c8e03` |
| 동일 연구 | [DOCX](../output/standalone-20261005-46bf68c6/premiere-ai-harness/paper.docx) | 54,648 B / `d33f2a08eb3a22332560770bc5db12d56d6d40ff20b893326261d159467e0b5d` |
| 동일 연구 | [Markdown](../output/standalone-20261005-46bf68c6/premiere-ai-harness/paper.md) | 25,415 B / `ec9816ccf42324e2817e4c6fec30983eef00efbff43c5a13deb7429437ef1495` |
| 동일 연구 | [TeX](../output/standalone-20261005-46bf68c6/premiere-ai-harness/paper.tex) | 29,836 B / `8c20e0bd544b7e04e8f5799ea2905f1444c5bd6dbceda649d6ffcfacedc0fa24` |
| 동일 연구 | [재현 ZIP](../output/standalone-20261005-46bf68c6/premiere-ai-harness/reproducibility.zip) | 1,970,175 B / `a094e013ad4af9ac8de957f0f62209d15da20021a1ae8c55001ae2aaa12cfe7e` |

03:16:32 KST에 실제 앱 새 연구 버튼으로 `research-6561ac63db99`를 생성했다. 대상은 같은 neobrutal-ui 저장소의 별도 navigation callable/연구 질문이며 이전 무효 preview 실험을 수정·재실행하지 않는다. 새 요청3309chars/목표 SHA256 `bac65ba8098ccbefebad1a25941c12e07a09e854ef5832eefc908d7210d22e4c`, writerAstra/reviewerSol을 실제 화면에 입력했다. 실제 시작 후 자동 결과 탭으로 전환된 상태에서 이미 사라진 ‘진행 중인 연구 보기’ 버튼을 읽던5초 timeout은 입력 도구 문제이며 실제 연구를 다시 시작하지 않았다. 이 시작 체크포인트의 나머지 두 저장소 검수는 pending이었으며 이후 완료 근거는 아래에 추가한다.

## Navigation 완료와 마지막 CLI 연구: 2026-10-06 03:40 KST

`research-6561ac63db99`의 생산 함수는 고정 commit `b4da2463fe710a77bf464c65125a1a7f40424722`의 전체 `docs/src/site/lib/navigation.ts:isNavigationPathActive`다. 원본908 B/SHA256 `8e860a4c40dc679d248ba5d1eb7e05f0369bb17d073eaee2c34682609805c219`와 MIT 저작권 원문을 검증했다. 실제 새 계획과 별도 코드 리뷰 뒤 단 한 번 실행했고, seed17/29·각8개·두 조건의32개 binary 관측과 실제 생산 호출18회(본 실험16+유효 입력 제어2)를 확인했다. 양성은 알려진 비루트 동일 경로의 실제 true 반환, 음성은 같은 유효 입력의 실제 boolean을 반전해 독립 oracle가 불일치를 검출한 경우다. 예외·timeout·호스트 오류를 제어 성공으로 쓰지 않았으며 cleanup=true/경계 실패0이다.

독립 oracle는 관측 전 고정한 의미 token 배열의 동치·엄격한 선행 segment 관계이고 comparator는 raw equality/prefix다. Production 평균1, raw-prefix 평균0.375, 짝지은 comparator-minus-production 평균−0.625·표본표준편차0.5·n16을 원시32행에서 확인했다. 두 seed의 공유 root 사례는 독립 무작위 모집단으로 취급하지 않는다. 일반 URL·전체 사이트·배포·성능·통계적 유의성 또는 새로움의 결론으로 확장하지 않았다.121개 retained fixture의 실제 bytes/SHA, 사전16입력과 실제 boolean, 분석의 연결을 대조했다. Compiler는 실제 Node24.21.0 `stripTypeScriptTypes`와 원본/compiled SHA 및 파일별 strip/sourceMap/sourceUrl 옵션이다. 보존되지 않는 emitted JS·별도 pre-call receipt·호출별 trace를 보존했다고 주장하지 않는다. 실제 두 문헌 query와 읽힌6개 abstract만 사용했다. 두 번째 query의 inspected0은 이미 첫 query에서 수집 cap6에 도달한 결과다.

실제 새 Astra writer `84895fea…`는03:22:32.874 KST, 새 별도 Sol reviewer `e8d3348a…`는03:23:35.291에 accepted=true/issues=[]로 완료됐다. 현재 Markdown·protocol·analysis·literature 해시를 승인하는 native review와 main↔engine10개 모델 receipt 원문을 확인했다. Author metadata는 빈 객체다.03:23:37.021 KST의 새 `export-attempt-87abe0bb8817`은 exported/completed이며 current72개 전량 frozen SHA, 초기24개와 과학51개 원본의 불변을 확인했다. 과학 감사 SHA256 `0430046ee8422162f659e867bbd6751bc2eb04e5b7bdaf71569f266aab6d1dea`, 최종 export `e645735d62201dc9448801c6cedf504fd5595a49ed78934e5ed76ef331067914`, 출력 연결 `d8ddd71755fb5ae691844fb5916aa0476ca1506f55576b3f150cb232c9e5ffd1`은 `.paper-factory/standalone-verification/navigation-actual-readonly-audit-20261006-c7f6f84db0a34132882f931a1e30d7b7/`에 있다. 원래 읽기 감사의 initial26 표기는 실제24개 사전 dictionary의 완전 일치 검사를 다시 세어 바로잡았다. 기존 receipt는 변경하지 않고 `frozen-count-correction-receipt.json` SHA256 `5a5b864baa8c2e4cd74b86b4e3909c9b32faf8a7cf0cf03d1408f5301311e03f`에 정정 근거를 보존했다.

새 출력 QA `qa-5a38624d-c2ca-4d6f-9c54-912348e50883`에서 PDF10쪽 전체를150dpi original로 직접 확인했다. 참고문헌은 plain text이고 태그·잘림·겹침·깨진 글리프·빈 페이지·표/그림 잘림이 없다. DOCX66문단/3261단어/표2/그림1 전체 본문, OOXML19 및 ZIP476개 전 멤버의 CRC·size·SHA를 대조했다. ZIP inventory474개·original source416개·generated4개·model evidence20개와 원문 source/license/README가 일치하며 입력8개 전후 bytes도 같다. 현재 resource ceiling11개+network/host-fs 부재13개 실제 policy와 cleanup을 확인했다.5쪽 중복 마침표2개는 비차단 편집 주석으로 보존한다. QA report SHA256 `70883346e3efb9bb6f924232e1c2d60b98f051e2c579f770ce061316f5b9ad90`, 시각 proof `ec12c1426b0bf946ca049e702a749c7c0d7b32c4ed157d3a90c9076c0d712676`, 추가 byte/content proof `a9a7cab693f85cf641c8630d356c26657e99745f4bf58ad734240dfdb7fa6267`를 보존했다. DOCX 페이지 시각 검사는 하지 않았다.

03:24:56.090–03:24:57.033 KST에 설치 앱의5개 실제 저장 버튼·내부 경로 창으로 아래 파일을 저장했다. 모든 저장본은 frozen 원본 size/SHA와 같다. Save UI proof SHA256 `5cfaa414cdddeb8ee4b68171cdabdfb1f97c500ced01c54cf45de640ab3a42a6`, 저장본 검증 `91edda2779ce792c141f40a873267810774d178b9e7e1d54911b591dd9ff1b50`다. 앱 PDF 열기 요청은 실제 shell 성공으로 확인했다. Native Reader의 정확한 파일 경로나 본문 렌더는 UIA에 노출되지 않으므로 단정하지 않는다. 별도 Chrome154에서 정확한 사용자 저장본 file URL·SHA·PDF viewer1/10·실제 첫쪽을 확인했다. 실제 결과 폴더 버튼 후 Explorer 접근성의 전체 새 연구 ID·export-attempt 경로와20개 파일을 확인했다. Native 입력·활성화·화면 캡처는0회다. Open/folder proof SHA256 `e21b12e2377d2c9f34b67204f3eb7a3f574fced5588638623799c9d23a432057`와 `navigation-saved-pdf-chrome-loaded.png`를 보존했다. 별도 과학 감사·실제 리뷰·출력 검수와 사용자 저장/열기/폴더 확인을 함께 판정해 **최종 성공 수2/3**이다.

| 저장소·연구 ID | 사용자 파일 | 크기·SHA256 |
| --- | --- | --- |
| neobrutal-ui / research-6561ac63db99 | [PDF](../output/standalone-20261005-46bf68c6/neobrutal-ui/paper.pdf) | 137,191 B / `0a3444cf6c3aff1b74a72b6f1a2d7fd037790ef1ee360380b1da30d2f10556fc` |
| 동일 연구 | [DOCX](../output/standalone-20261005-46bf68c6/neobrutal-ui/paper.docx) | 55,395 B / `c578ea104334592eb5976e1f9aeee4d8702a8fc8a581996347a2a256fcabbc97` |
| 동일 연구 | [Markdown](../output/standalone-20261005-46bf68c6/neobrutal-ui/paper.md) | 25,388 B / `91bb3007aed00d3ff4c55a2fc27639a4b4a94431e45591af4f327dc0da2ea612` |
| 동일 연구 | [TeX](../output/standalone-20261005-46bf68c6/neobrutal-ui/paper.tex) | 29,993 B / `a4ac6ec8d2cbd08efd8e991cd70ce84f465bbf859715db9314f2be3100f69317` |
| 동일 연구 | [재현 ZIP](../output/standalone-20261005-46bf68c6/neobrutal-ui/reproducibility.zip) | 2,125,684 B / `ffd16df274da73671bbc3a8826b09eda8d0f1b8a5417fa89eee35156bf1a0789` |

03:26:55 KST에 실제 새 연구 버튼으로 `research-f68ee0139f78`를 만들었다. 별도 Frontron callable `frontron/src/cli/options.ts:parseCliOptions`의 source 전체5212 B/SHA256 `08a4e578395eabc7db1b8c3fdf85287b896ba20b4a213e6d5765dfee340a5bc3`와 commit `3a7da2822721801db88ea059d204c8c6c622fab4`를 확인했다. 실제 main 목표3993자(SHA256 `719b4af273953e1ddeca473a58e548f185880b063e8b72cc10dfb85750cb5e79`)는 끝 LF를 포함한 사전3994자 파일의 trim 결과다. 새 계획은16개 정확한 argv/JSON 기대값과 first-value-wins 비교를 관측 전에 고정했다. 기존 SemVer 실험은 제외·보존하며 재실행하지 않는다.

새 CLI의3개 실제 코드 작성·각 별도 리뷰가 모두 거절됐다. 마지막 리뷰03:36:16.919 KST는 알고리즘20항목은 확인했으나 라이선스/저작권 원문을 guest fixture에 넣지 않았다는1개 문제를 남겼다. 실제 원문 source·root LICENSE.md·nested frontron/LICENSE는 이미 controller가 전량 frozen 검증·보존하며 ZIP의 source/와 source-provenance.json에 포함한다. 그러나 code/reviewer 자료 선택은 plan.source_files만 읽어 notices와 이 controller 계약을 전달하지 않았다. 이 실행 전 자료 전달 결함을 다음 Source12 체크포인트에서 수정했다. 계획·관측·리뷰를 바꾸거나 수용을 자동 처리하지 않으며 이 중단 시점은 execution0/code submission0/draft0이고 기존3회 거절 원문은 전량 보존한다. 새 실제 코드/별도 리뷰·단회 실행·원고·출력 검수 전에는 성공 수를 늘리지 않는다.

## Source12 설치와 CLI 코드 작성 재개: 2026-10-06 03:53 KST

Source12는 main의 materials 선택과 그 회귀 검사2파일만 바꿨다. 모든 단계의 작성·새 reviewer에 manifest에서 검증한 root README·root/nested LICENSE/LICENCE/COPYING/NOTICE 전체 원문을 전달한다. Controller의 전체 원본 검증/보존·성공 ZIP source/<path>·source-provenance.json 계약을 untrusted JSON 밖에서 설명하며 guest fixture의 소스/고지 복제를 요구하지 않는다. 미래 export가 완료됐다거나 라이선스 권한·review가 승인됐다는 주장은 없다. 기존 SHA/size/페이지/500k/경로 검증과 리뷰 거절 조건을 유지했다.

변경 전 created/planned/analyzed 자료 전달3개 검사 실패를 보존하고 신규19개 통과, 전체203 passed/1 Windows POSIX skip, Electron4 passed/20.2초를 확인했다. Source12 final receipt SHA256 `f72b3de43e70d2edeb43f4a6a04e41bff4e53b6d56d04d8d904ffbc2e207d2fa`, 독립 읽기 검토 `c7b0d31cf70dc33f222234499755c7d50e5153914b6affa966702a35c73c956c`다. 엔진 소스22개(Python21개+worker1개) 및 Source11 frontend9개는 full bytes/SHA가 이전과 같아794/7skip 전체 Python·세 runtime·Mac 정적 QA 근거를 그대로 보존했다. 새 Python 검사·runtime 재빌드·과학실험을 수행한 것처럼 합산하지 않는다.

NSIS 실제 설치는 **03:47:10.578–03:47:57.230 KST, exit0**이다. Installer234,889,236 B/SHA256 `126c5c2bc31c7944d4950de06b11efffebd233cc67af2c9677391d00e0715fac`, EXE245,726,208 B/`d2063b8b4e0bf834f16edd0b918a1a3ee9a8b3b74c93d8bef0115c02b98bcd7c`, ASAR42,653,282 B/`fc0685589d439039d63375293f5193890be83986c2dc575964a35f912b485428`를 확인했다.03:48:13.263에 설치 앱/main/preload/renderer와 모든 참조 자산을 현재 빌드와 대조했고03:48:14.372에 runtime4463/source22 전량이 일치했다. Static package receipt SHA256 `619e469ec9ae7a021de0207d1ab1eb362546a7c2dc89d33bf7c1cdf165adedb8`, installed app `39ab8aa33b0210cdc02ccb07f01354dd7888c5326f64ab05c4e43ae68d9781d3`, installed runtime `e97268ad0bd0c5f2a7963d96cbfd1f7d0c72856c1b61d91975ddcce4537976cc`다. 기존 사용자 저장본10개의 크기/SHA도 전량 같으며 이전 실제 앱은 유휴에서 정상 window close로 종료했다. Proof는 `.paper-factory/standalone-verification/controller-provenance-install-source12-44bdf328-94c9-4a87-be54-97dd62fa1014/`에 있다.

같은 installed EXE를 Playwright Electron API로 실행해 isPackaged=true/installed ASAR/동일 own userData를 확인했다. 자체 연결 복원·실제5개 모델 목록 조회 후 **03:49:12 KST**에 새 Astra 완료 응답 `Paper Factory connection works.`를 받았다. 실제 DOM에서 writerAstra/reviewerSol을 확인하고 **03:51:09.603 KST**에 기존 CLI 연구의 재개 버튼을 한 번 클릭했다. 접힌 `<details>`의 모델 선택기를 직접 읽던5초 timeout은 UI locator 문제이며 연구를 다시 시작하거나 모델 요청을 반복하지 않았다. 새 작성 요청 `2265c93d…`는03:51:13.045에 시작했고 prompt134,463chars/SHA256 `35e7fafe012312b7b5d3f2191d2005487e76838eb0581842533e38f9937d1422`다.

읽기 감사는 생산 opts5212 B/08a4…·root LICENSE.md1065 B/2f492…·frontron/LICENSE1066 B/cd95…·create-frontron/LICENSE1067 B/0bdd…·root README4083 B/a3b7…의 실제 Project asset 원문을 모두 새 prompt의 UTF-8 bytes/SHA와 대조했다. JSON 밖 controller 계약도 정확히 전달됐다. Main↔engine started receipt 및 이전46개 frozen metadata/path/SHA/size/full bytes, goal/plan은 그대로이며 current48개 전수 해시가 일치한다. Execution/code/draft0 및 supporting0이며 진단용 문서를 앱에 가져오지 않았다. 실제 코드·리뷰·실험·원고·출력 결과는 이 시점에 pending이다. 실제 context 감사 `source12-start-context-audit.json` SHA256 `d6d8ee9f3e04afffa29260a1a3d5359b73aea2f1e3494b1efdf6567a9420b590`와 업데이트 전3회 거절 감사 `f2299cc7381e864ca124cac325f77b339bd97b70cf03ab64300e2f8964d06bcd`를 보존했다. Mac native/DMG/설치/CI·clean VM·서명 제한은 변함없다.

## 최종 세 연구·저장본·정상 재시작: 2026-10-06 04:20 KST

최종 성공 수는 **3/3**이다. 실제 설치본에서 선택한 writer는 `gpt-6-astra`, 각 새 문맥 reviewer는 `gpt-5.6-sol`이다. 각 연구의 성공 실행은1회이며 관측을 주입하거나 같은 과학실험을 재실행하지 않았다. 이전 preview의 무효 보고서와 SemVer의 중단 연구는 보존하고 성공 수에서 제외한다. 완료 원고는 근거와 재현 자료가 연결된 연구 초안이며 학술적 새로움·학술지 승인·출판 성공을 주장하지 않는다.

| 연구 | 실제 연구 ID / 마지막 export | 단회 과학실험 | 최종 출력 QA |
| --- | --- | --- | --- |
| Premiere 후보 승인 | `research-a90ccd5fee76` / `export-attempt-9a4f5f1c4740` | 호출18·원시 scalar32·cleanup=true; 이전 과학 자료와 실패 원고 불변 | PDF10쪽·DOCX65문단/3,200단어·표2/그림1·OOXML19·ZIP176멤버 |
| Navigation 활성화 | `research-6561ac63db99` / `export-attempt-87abe0bb8817` | 호출18·원시 scalar32·cleanup=true; 이전24개/과학51개 불변 | PDF10쪽·DOCX66문단/3,261단어·표2/그림1·OOXML19·ZIP476멤버 |
| Frontron CLI 값 바인딩 | `research-f68ee0139f78` / `export-attempt-c673234c00a2` | 호출17·원시 scalar32·cleanup=true; 이전46개/과학95개 불변 | PDF9쪽·DOCX62문단/3,046단어·표2/그림1·OOXML19·ZIP261멤버 |

세 PDF의29쪽 모두150dpi 원본 크기로 직접 확인했다. 잘림·겹침·빈쪽·글리프·표/그림 절단·HTML 제목 노출은 없었다. 일부 본문의 중복 마침표는 사소한 편집 사항으로 기록했으며 실제 원고를 사후 수정하지 않았다. DOCX는 전체 본문·표·그림과 OOXML 전 멤버를 검사했고 페이지 배치 시각 검수로 표현하지 않는다. ZIP은 모든 멤버의 CRC·실제 bytes·size/SHA 및 inventory/source/model evidence를 대조했다. 각 QA의8개 입력과 전후 원본 해시도 그대로다.

### 마지막 CLI의 실제 코드·실험·원고 근거

고정 commit은 `3a7da2822721801db88ea059d204c8c6c622fab4`이며 전체 생산 파일 `frontron/src/cli/options.ts:parseCliOptions`는5,212 B/SHA256 `08a4e578395eabc7db1b8c3fdf85287b896ba20b4a213e6d5765dfee340a5bc3`다. 타입 제거 외에 import나 생산 코드를 바꾸지 않았다. Root LICENSE.md와 두 패키지 LICENSE, root README 전체 원문·원본 inventory·controller 보존 계약을 실제 작성 및 새 리뷰 요청과 대조했다. 기존3회 코드 거절과 Source12의2회 문헌 설명 거절을 모두 보존했다. 두 실제 문헌 query는 모두 성공했으며 abstract 상한 때문에 첫 query에서6개, 둘째에서0개를 보존했다. 실패 query나 읽은 full text로 표현하지 않는다.

Source12의 세 번째 새 코드 writer `b9f…`는 **03:59:29.528 KST**, 새 Sol reviewer `62729bc3…`는 **04:00:22.850 KST**, accepted=true/issues=[]로 완료했다. 승인된 bundle 제출1회 뒤 성공 execution1회만 수행했다. 고정한16개 literal argv/기대 JSON/거절, seeds17/29×8의32 scalar를107개 보존 fixture와 실제 생산 반환·동기 Error에 연결했다.17회 실제 gate 중9회 반환(표본8+양성1),8회 알고리즘 거절이며 fatal infrastructure error는 없다. 양성 제어의 실제 정상 반환을 의도적으로 틀린 기대값과 비교한 음성 제어는 불일치를 검출했다. Timeout·누락 호출·예외를 음성 성공으로 계산하지 않았다.

Production 평균1.0과 `first_value_wins` comparator 평균0.8125(13/16), comparator-minus-production 평균-0.1875/표본 SD0.4031128874/n16은 원시 관측·분석·원고 표와 일치한다. 반복 init 문자열3개 사례의 마지막 값 바인딩에 한정한 비교이며, 외부 CLI 관습·shell·파일시스템·성능·보안·SemVer·모집단·p-value로 일반화하지 않는다. Node24.21.0의 실제 파일별 strip compiler manifest와 원본/변환 해시를 보존하며 호출별 trace를 측정했다고 주장하지 않는다. Author metadata는 빈 객체다.

새 Astra 원고 `57e99b9c…`는 **04:02:23.874 KST**, 새 Sol reviewer `16316635…`는 **04:03:32.547 KST**, accepted=true/issues=[]로 완료했다. Writer 원문과 실제 draft, 별도 native 승인과 현재 Markdown/protocol/analysis/literature 해시, main↔engine 모델 receipt 전체를 대조했다. 새 export는 **04:03:34.443938 KST**이며 최종 frozen112개와 이전 실패46개/과학95개의 full bytes가 유지됐다.

과학·최종 원고 감사는 `.paper-factory/standalone-verification/frontron-cli-actual-readonly-audit-20261006-5f10c678b0774ccda6fed510466ea8c2/`에 있다. `scientific-data-consistency-receipt.json` SHA256 `e77b54d02f5d9aa20bdbbc82a7120402a3dfa14a92da5858a8cc986fa72d86e0`, `export-paths-and-binding-receipt.json` `4334dd41aa4db0cb4e1e930e8471a0dba97f5dd73c5d7828293f63f048fafef6`, `final-export-audit-receipt.json` `bde1b96c3c4695a691e2509d29daa5f64fd2ba5e4517550de4aaea6ccc00efed`를 보존했다. 원래 navigation/CLI 초기 artifact 수의26→실제24 정정 receipt도 이 디렉터리에 있으며 원래 기록은 변경하지 않았다.

출력 QA는 `.paper-factory/standalone-output-qa-4da9fed8-3005-4406-85ac-9f34cdf71367/runs/qa-ec1980d5-f975-4b24-80d0-20ef69743a03/`다. `qa-report.json` SHA256 `1f0d2fbb1117d029723afb3ddac27ba75d0d91bc1a6af590494200f865238b09`, 시각 검수 `05b4e5051a4a3e982a993c51f5d40c2e03cee61e657e182c917c19c6653fad79`, 추가 자원/문헌 검사 `b970a94347483de890dbfc35acadf2377196383a06aa2692014dc84b1e402625`, 읽기 전용 검사 `a7630b02d119d0a7a4730881f9c88e1f6f361e97ee27bf09309e7a4e51704507`다. ZIP261멤버 중 inventory259/source161/generated4/model evidence60을 확인했고 원본 MIT 고지3개와 현재 원고·관측의 연결을 대조했다. 과거 거절 후보의 문헌 문장은 과거 model evidence이며 최종 과학 주장으로 취급하지 않는다.

### 실제 앱의 최종 저장 경로와 해시

공통 사용자 폴더는 `C:/Users/Andongmin/Desktop/repository/paper-factory/output/standalone-20261005-46bf68c6/`다. 아래15개 논문/재현 파일은 각 연구의 실제 앱 저장 버튼과 앱 내부 경로 창으로 저장했다. 원래 frozen bytes와 정확히 일치하며 최종 원본을 수동 복사하거나 편집하지 않았다.

| 저장소 | 파일 | bytes | SHA256 |
| --- | --- | ---: | --- |
| premiere-ai-harness | `paper.pdf` | 137681 | `c42ff37295d4e0770022047f4365596800fbb0b7f1211dcd128b8978979c8e03` |
| premiere-ai-harness | `paper.docx` | 54648 | `d33f2a08eb3a22332560770bc5db12d56d6d40ff20b893326261d159467e0b5d` |
| premiere-ai-harness | `paper.md` | 25415 | `ec9816ccf42324e2817e4c6fec30983eef00efbff43c5a13deb7429437ef1495` |
| premiere-ai-harness | `paper.tex` | 29836 | `8c20e0bd544b7e04e8f5799ea2905f1444c5bd6dbceda649d6ffcfacedc0fa24` |
| premiere-ai-harness | `reproducibility.zip` | 1970175 | `a094e013ad4af9ac8de957f0f62209d15da20021a1ae8c55001ae2aaa12cfe7e` |
| neobrutal-ui | `paper.pdf` | 137191 | `0a3444cf6c3aff1b74a72b6f1a2d7fd037790ef1ee360380b1da30d2f10556fc` |
| neobrutal-ui | `paper.docx` | 55395 | `c578ea104334592eb5976e1f9aeee4d8702a8fc8a581996347a2a256fcabbc97` |
| neobrutal-ui | `paper.md` | 25388 | `91bb3007aed00d3ff4c55a2fc27639a4b4a94431e45591af4f327dc0da2ea612` |
| neobrutal-ui | `paper.tex` | 29993 | `a4ac6ec8d2cbd08efd8e991cd70ce84f465bbf859715db9314f2be3100f69317` |
| neobrutal-ui | `reproducibility.zip` | 2125684 | `ffd16df274da73671bbc3a8826b09eda8d0f1b8a5417fa89eee35156bf1a0789` |
| frontron | `paper.pdf` | 133770 | `8582b3f882854c20f80f6f41906b9e17fce82dc984ae644d3542f7bdf7294411` |
| frontron | `paper.docx` | 55026 | `5447e530b30ffc900889ad28ca9467fccdc7fe372848130f16dd5e1220bfacce` |
| frontron | `paper.md` | 23728 | `4b8e60d0fa06703b9f17d37229baef0cb3a62767b103625d62e652e13b8f8535` |
| frontron | `paper.tex` | 28080 | `31690a85d1266e4ea79205e60be2caf6576a9134a502c3f4bb2b22d8fcb94d67` |
| frontron | `reproducibility.zip` | 2340812 | `9b8a27213192e6819a0fdb986ef3a3bcaa58a6b4471752698f93fd40ab6b1de3` |

CLI의 실제5종 저장은 **04:06:24 KST**에 완료했다. Source12 설치 proof 디렉터리의 `cli-real-app-save5.json` SHA256 `1bef764fc729b3ea77361619d04126668ed04b8be43ad4bfc24b0c0baae7da50`와 `cli-save5-verified.json` `6882f090063722ede5a04f6cdf5761f611475bfcf3b13d8446e1a43db0700d58`로 실제 UI와 원본 byte 대조를 분리했다. 각 연구의 PDF 열기 버튼은 unmocked shell 요청 뒤 pending이 해제되고 오류가 없었다. Native Reader 접근성에서 정확한 파일 경로나 렌더를 확인할 수 없으므로 단정하지 않는다. 기존 Chrome154로 정확한 사용자 저장본 file URL·SHA·각1/10,1/10,1/9 viewer·실제 첫 페이지를 별도로 확인했다. 실제 폴더 버튼 뒤 Explorer 접근성에서 각 새 연구/export 전체 경로와20개 파일을 읽었다. Native 화면 캡처·입력·활성화는0회다.

CLI open/folder receipt SHA256 `e7222c8394893ee817f960ba8cd2d9144f206033e331d2d6730f4f0d40378dbe`, 실제 Chrome 첫 페이지의 후속 검수 `b37a7a68b14ce49b4d8a282a848ab73b664905dcd52312c99b512ad4919a2ad5`, full folder 접근성 `0f2b29c976001a0adb873cebf9bf35633f02f8de75f7338e6e1f0755ccb64e50`를 보존했다. 최초 receipt의 시각 검수 false는 그 시점에 아직 직접 보지 않았다는 뜻이며 후속 proof로 보완했고 원래 proof는 덮어쓰지 않았다.

Saved Markdown/TeX의 상대 그림 참조를 위해 **04:11:24.408784 KST**에 각 실제 저장 ZIP의 기존 `figure-1.png`를 CRC·inventory·frozen SHA로 대조해 해당 사용자 폴더에 추가 전달했다. 앱에서 저장한 primary15개와 실제 workflow/원고는 전후 변경0이다. 그림3개는 새 측정·생성이 아니며 앱의 그림 Save UI를 실행했다고 표현하지 않는다. `saved-figure-delivery-receipt.json` SHA256 `f8e6d57d5c800d16927633bcd35fe9fabbbe3ec9fbf562dd03fe3aed8986bd64`다.

| 사용자 폴더의 기존 ZIP 그림 | bytes | SHA256 |
| --- | ---: | --- |
| `premiere-ai-harness/figure-1.png` | 36536 | `07c9e17de83a24b3f5060c740d95f736f67bfd5094e6940fcedf509d267c49e3` |
| `neobrutal-ui/figure-1.png` | 37187 | `7858ca8d9e017501c4a8a7150c8764138175d9afb58c7955c26ddcf2fe2bccda` |
| `frontron/figure-1.png` | 37635 | `1e3e3e5f6fe8fa4f0e0eb3789a425b53cac2152f16ed2a7ab7f23b04f1cd340a` |

### 정상 종료·복원과 환경 제한

실제 Source12 앱을 **04:11:59.495 KST**에 정상 종료하고 해당 EXE 프로세스0을 확인한 뒤 **04:12:24 KST**에 새 프로세스로 실행했다. `isPackaged=true`, 설치 ASAR와 같은 자체 userData를 확인했고 모든5개 job과 세 최종 `exported/completed/idle` 연구가 복원됐다. 같은 연결의 실제 서버 모델 목록을 새로 조회한 뒤 **04:13:33 KST**에 새 Astra 완료 응답 `Paper Factory connection works.`를 받았다. 연구를 재개하거나 과학실험을 dispatch하지 않았다. 결과 화면에서 앱을 유휴 상태로 열어 두었다.

`final-normal-close.json` SHA256 `384a88a0429d1c22e94aab700e02d3de717c957b7f59256e15caca84c838f942`, `final-normal-restart-proof.json` `1693b39a8ab64a33d82330800e5b726ba084c5e995e38292e3fee41653a509af`, `final-restart-runtime-meta.json` `39fcd4f50482c8f316e720cac29f6379d79204580efeb8fe39b2cc19f307e5b1`이다. 실제 renderer의 응답/결과 ARIA와 Chromium PNG는 `output/playwright/standalone-live-source12-23cb02e9-6db9-455a-af30-4396b0acebee/`에 있다. OS의 실제 모니터 전원 상태를 측정했다고 주장하지 않는다.

최신 Source12 앱/SDK203 passed/1 existing Windows skip, Electron4 passed/20.2초 및 바이트가 동일한 Source11 Python794 passed/7 skipped, 세 런타임과 Mac 전량 정적 검사 근거를 보존했다. Windows 설치 EXE는 NotSigned이고 clean Windows VM은 미검증이다. Mac ARM/Intel의 전체 파일·고정 소스·원문 notices·아카이브·Mach-O 아키텍처 정적 검사는 통과했지만 native 실행·실제 POSIX 권한·DMG 생성/설치·OAuth·연구·CI 실행은 미검증이다. DOCX 페이지 배치의 시각 검수도 미수행이며 전체 내용/OOXML 검수와 구분한다.

현재 의존성 electron-builder26.15.3의 `app-builder-lib/out/packager.js:368`은 Windows 호스트에서 Mac target을 명시적으로 거부한다. 이 조건을 읽기 전용으로 확인했다. macOS 네이티브 앱/DMG 빌드와 실제 설치 검증에는 Mac 실행 환경이 필요하며, Windows의 Mac 런타임 정적 조립을 해당 성공으로 표현하지 않는다.

재시작 뒤 **04:23:34.058727 KST**의 독립 읽기 전용 감사는 live WAL-aware SQLite `mode=ro`로 세 연구의17개 필드·124/72/112개 frozen metadata/path/size/SHA 및 전체 파일 bytes가 Root의 재시작 전 snapshot과 정확히 같음을 확인했다. 기존 SemVer의102개 historical frozen 원본과 과학 raw/analysis·execution1도 불변이다. 기존 preview의 현재110개 full hash·execution1·32관측·cleanup을 확인했으며, 이 감사에는 이전 전체 snapshot이 없어 preview 전체의 전후 바이트 동일성을 새로 주장하지 않는다. 모든5개 job, 기존 중단 상태와 세 최종 유휴 상태가 유지됐다.

같은 감사에서 현재 Source12 두 소스, 설치 EXE/ASAR, 포함 런타임4,463개 파일과 엔진22개를 전수 대조했다. **04:24:54.513 KST**의 별도 순수 파일 검사는 패키지 설정의 정확한6개 dist 파일(main/preload/LICENSE/renderer HTML/JS/CSS)과 설치 ASAR, runtime binding이 일치함을 확인했다. 실제 workflow·모델·IPC·엔진 실행·UI 입력·원본 writes 없이 자체 proof만 기록했다. 증거는 `.paper-factory/standalone-verification/final-restart-integrity-audit-b8af9974-a782-40af-93e0-2d2feaf1a4e0/`의 `readonly-restart-integrity-receipt.json` SHA256 `f065ede8172ef92474c18ad707446a7e2cf462269c1ac0262926f4986aa00935`, `asar-dist-binding-receipt.json` `2482fa45c32ff6c06ad3dddab0de454f2fc4c7de5401be173da77d03102fe477`이다. 실제 저장본15개와 기존 ZIP 그림3개의 전수 해시·CRC·inventory도 독립 재확인했다. 로컬 Windows cache 디렉터리는 내용·원본을 변경하지 않고 `.gitignore`에서 제외했다.

**04:27:32.663325 KST**에 끝낸 통합 읽기 전용 검사 `final-readonly-integrity-summary.json` SHA256은 `6e32eb49c807e449c3521008cb5bca3894a3a0608690dd1f262885e30507720b`다. 세 저장 ZIP의 총913멤버/907개 inventory row, 현재 Markdown/TeX6개 상대 그림 참조, DOCX3개 embedded PNG가 실제 ZIP/frozen 그림과 같음을 확인했다. 별도 saved child receipt SHA256은 `91ad2fd216f2e2cc5e58c7fdf8bb397395cf813436d1adb7e5ab2066eae2fe32`다. 예전 실패 원고를 보존한 `superseded-reference-formatting/paper.md`의 하위 폴더에는 그림을 추가하지 않았으며 이를 현재 전달본으로 계산하지 않는다. 현재 전달 파일의 blocker는 없다.

## 0.14.0 연구 품질 설계와 최종 검증: 2026-10-07

0.14.0은 실험 전에 연구 질문·기여·문헌·비교 대상·표본·실행 가능성을 검토하고, 원고 작성 후 기여·문헌 사용·해석·내용과 분량을 별도로 검토한다. 기준 미충족은 **연구 보류** 또는 **원고 보류**로 표시하며 반려된 원고를 완료 파일로 내보내지 않는다. 앞부분의 구버전 3/3 기록은 당시 파일 생성과 재현 자료의 기술적 검증 이력이며 현재 학술 품질 기준의 통과를 뜻하지 않는다. 기존 원본은 변경하지 않았다.

실제 리뷰 모델로 기존 ARTEX·Premiere·Frontron 설계의 첫 StudyReview를 각각 수행했다. 세 건 모두 반려되어 executionAttempt=0을 유지했다. 음성 평가 harness는 첫 검토가 네이티브 엔진에 보존된 직후 의도적으로 중단했으며 계획 보완·코드·실험·원고 요청은 수행하지 않았다. 따라서 해당 세 설계의 반려를 확인하며 controller의 전체 재시도 흐름이나 일반적인 분류 정확도를 입증하지 않는다. 원래 설계·근거의 해시와 완료 모델 receipt를 대조했다.

별도의 실제 Premiere 알고리즘 후보 research-fea847f32ddc는 confidence 우선 선택과 독립 한계 커버리지 탐욕·작은 문제의 정확 부분집합 비교를 제안했다. 함수 수준 실험은 기술적으로 가능했으나 확보된 문헌으로 추가 연구 기여를 정당화하지 못해 proposed/blocked, STUDY_INFEASIBLE로 종료했다. executionAttempt=0이며 새 원고나 결과 파일은 생성하지 않았다. 현재 버전에서 학술 품질을 통과한 새 논문은 검증하지 못했다.

최종 소스와 포함된 Windows 런타임으로 아래 회귀 검사를 완료했다. Electron은 fresh 임시 앱 데이터와 hidden/offscreen 창에서 실제 main/preload/IPC를 사용했으며 사용자 인증 자료를 읽지 않았다. 마지막 전체 11건은 재시도 없이 통과했고 소유 테스트 프로세스는 종료했다.

| 검사 | 결과 | 최종 로그 SHA256 |
| --- | --- | --- |
| Python | 967 통과·7 건너뜀, 316.37초 | 40117c0d0e51da89f1cfefe0b0d6e69757cda2058aba96f73ed71661f80b8328 |
| 데스크톱 | 223 통과 | 26afa027d51b2d382d28f76c2433286f2666ed61577677f43c71697b497c6309 |
| 공식 SDK | 48 통과·1 Windows 건너뜀 | 위 데스크톱 통합 로그 |
| Electron | 11 통과, 약 1.1분 | 292eb0d510bdb362a3e6ae2d03d4496d747e3df00c250647e51922cbfcfe2252 |

Python 건너뜀은 Windows symlink 권한 5건과 macOS 네이티브 guardian/EOF 2건이다. PDF 변환·표 레이아웃 부분 검사는 위 Python 범위에 포함된 26건이다. 긴 metric/unit/condition의 2·8조건과 N=36·10000, 완전한 수치·문자열 보존, PDF 셀 경계 및 DOCX 원문 값을 검증했다. 시각 검수는 합성 PDF 8개·9페이지를 전량 확인했고 표 겹침·잘림이나 Pretendard 한국어 regular/bold 글리프 손실이 없었다. 간결한 네이티브 원고는 2페이지다. 이 검수는 문서 변환의 가독성과 내용 보존 근거이며 학술 기여나 실제 모델의 원고 승인 근거가 아니다.

별도의 fresh 네이티브 실행 환경 smoke는 전체 런타임 2,218개 파일의 SHA256, 19개 배포 의존성과 제거한 플로팅 모듈 11개의 부재를 확인했다. QuickJS IPC 준비·정리, 빈 초기 workflow 목록, shutdown closed/exit0 및 포함된 인터프리터의 한국어 PDF·DOCX·TeX 변환을 확인했다. PDF에는 Pretendard Regular/Bold가 포함됐다. 해당 smoke의 모델 호출·과학실험 dispatch·설치 실행은 모두 0회다.

Windows NSIS 0.14.0 패키지 검증은 **2026-10-07 09:36:18.981 KST**에 exit0으로 완료했다. 앱 소스·SDK import·renderer·Pretendard·포함 엔진 소스 및 런타임 2,218개 파일의 전체 해시가 일치했다. 이 결과는 정적 패키지 검증이며 최종 배포본을 새로 설치해 GUI·OAuth·인증 복원까지 확인한 결과는 아니다. macOS 네이티브 실행·설치도 새로 주장하지 않는다. 이 작업에서 GitHub Releases에 설치 파일을 게시하지 않았다.

| 로컬 패키지 | bytes | SHA256 |
| --- | ---: | --- |
| desktop/release/Paper Factory Setup 0.14.0.exe | 213,000,730 | 9bce300bb549f04cb6c8d10be0304033daf550f042aea82791c7c06275049b7f |
| desktop/release/win-unpacked/resources/app.asar | 44,715,779 | 54c52da7652725268c0797f47eb89e3be4c64b8540a02e8a16daf1acf070d178 |

원시 평가·로그·QA 자료는 ignored .paper-factory/ 아래 보존하며 인증 자료와 모델 원문은 커밋하지 않는다. 검증 기록의 SHA256은 다음과 같다.

| 기록 | SHA256 |
| --- | --- |
| quality-evaluation-20261007/negative/results.json | 426b7f91ec0a76bf804565e1fef4b6788146379ca84470e9ec67b36d590ed4e3 |
| quality-evaluation-20261007/positive/result.json | 9b9583e081f90d386bf3c0daae9abae88373d89c730154cffacb1f4f46a02b86 |
| quality-evaluation-20261007/trimmed-native-smoke-73c02c53711e/receipt.json | 9b358f72d11b89d952f27c7f4a2ee82abe6292ac5686ebc87c412c2729048555 |
| 런타임 inventory | 40e38987753987aa1353651a81655b218ff281acfd4edc7df11aa4b1a8bf284b |
| pdf-quality-20261007/qa-summary.json | 21781476b60953ffd5d983e8fd3e239eb404d2edc53b30f6c781b5489e1bda04 |
| quality-verification-20261007/package-final-verification.log | 06a3262091db3b7b5c2d4dda34fb94c2cd6b0a13650a75736a5260290bf0b2b4 |

## 0.14.1 실제 연구 흐름 점검: 2026-10-07

Madi 저장소의 실제 선택적 수정 diff를 대상으로 앱의 `ResearchController`, 공식 계정 연결 SDK와 포함된 Windows 엔진을 실행했다. 별도 평가 디렉터리에서 창을 띄우지 않았으며 기존 사용자의 연구나 계정 연결·로그아웃 설정은 변경하지 않았다. 추가 근거는 앱의 취소·문서 가져오기·명시적 준비 재개 경로로 전달했다. 실험 결과나 심사 응답을 대신 작성하지 않았다.

이 과정에서 발견한 제품 결함을 수정했다.

- 저장소 전체의 압축 해제 상한은 충족하지만 단일 WASM 파일이 8 MiB를 넘으면 수집을 거절했다. 중복 단일 파일 상한을 제거하고 다운로드 24 MiB·전체 압축 해제 64 MiB·10,000개 항목과 경로·링크 검사를 유지했다. 실제 Madi 원본 464개·19,997,584 B와 라이선스를 누락 없이 보존하고 스냅샷 무결성을 확인했다.
- 최초 설계 프롬프트가 문헌 수집 전에도 검토한 문헌을 요구해 검색 단계로 진행하지 못했다. 초기에는 잠정 제안과 검색어를 작성하고, 수집 후 독립 StudyReview가 승인해야 계획을 고정하도록 단계 책임을 명확히 했다. 실제 문헌·기여 심사 기준과 실행 승인 게이트는 유지했다.
- 코드 작성 모델에 이미 완료된 연구 승인 기록이 빠졌고, 모델이 후속 심사 호출도 맡아야 한다고 해석했다. 실제 StudyReview와 선정 문헌을 전달하고, 모델은 구현을 반환하며 앱이 후속 코드 심사·제출·실행을 맡는다고 명시했다. 초기 제안의 미승인 상태 문구와 동결 계획은 수정하지 않았다.
- 실험 코드가 가져온 긴 원문을 직접 읽을 수 없어 원문·발췌 출처 검사를 구현하지 못했다. 고정 계획의 선언된 소스와 가져오기 영수증으로 검증한 UTF-8 문서만 `readScientificInput(key)`로 제공한다. 줄바꿈·BOM·Unicode의 원본 바이트 해시를 엔진과 worker가 대조하며, 임의 경로·네트워크·생산 guest에 노출하지 않는다. 입력 28개·512회 읽기·반환 JSON 16 MiB의 상한을 적용한다. 바이트 일치는 문서 내용의 진실성이나 발췌 provenance 검증을 대신하지 않는다.
- 코드 보완 중 직전 응답이 짧은 미완성 구현이면 앞선 구현과 심사 이유가 사라졌다. 제한된 코드 재시도에서 이전 후보와 각 반려 이유를 함께 전달하며, 최종 승인 후보만 한 번 제출한다. 원고 재시도와 동결 계획·관측 결과는 변경하지 않는다.
- 실제 실험은 성공했지만 원고 단계에서 재현 fixture의 Base64 원문이 검토 자료 상한을 넘었다. 원시 관측 전체와 각 fixture의 바이트·해시를 검증한 뒤 모든 측정값·제어 결과를 그대로 전달하고 fixture 원문만 이름·해시·크기로 바꾼다. 원고 작성자와 심사자 모두 생략한 원문을 읽었다고 주장하거나 제공되지 않은 측정을 추론해서는 안 된다고 명시한다. 원시 자료와 내보내기는 변경하지 않고, 투영된 자료를 포함한 자료 본문 합계 상한 500,000자를 유지한다. 이는 지시문·스키마·후보 원고·JSON 직렬화를 더한 최종 모델 요청 전체의 글자 수 상한이 아니다.

평가 도구 자체의 긴 임시 경로도 짧은 별도 루트로 바꿨다. Windows 장경로 설정이나 앱의 기본 데이터 경로는 변경하지 않았다. 수집·초기 제안에서 멈춘 이전 평가 기록은 그대로 보존했다.

| 검사 | 결과 |
| --- | --- |
| Python 전체 회귀 | 1,027 통과·7 건너뜀, 319.22초 |
| 새 입력 API·불변 게이트 추가 확인 | 최종 관련 53 통과. 메모리 부족 뒤 실패·정리 확인 포함 |
| Windows 종료·복구 모듈 | 17 통과·2 macOS 건너뜀 |
| 재현 안내 변경 후 네이티브 내보내기 | 2 통과, 8.09초 |
| 최종 데스크톱·공식 SDK | 231 통과 / 48 통과·1 Windows 건너뜀 |
| 최종 hidden/offscreen Electron | Playwright 11 통과, 49.3초, 재시도 없음 |
| 최종 포함 실행 환경 | 19개 고정 의존성, 2,218개 파일·473,541,283 B, 네이티브 QuickJS와 한국어 PDF·DOCX·TeX 변환 확인 |
| 최종 Windows NSIS 패키지 | 앱·SDK·renderer·Pretendard·엔진 소스와 런타임 전체 파일 검증 통과 |

전체 검사 중 기존 강제 종료 테스트의 직접 worker 요청에 새 필수 입력 필드가 빠져 한 건 실패했다. Windows와 macOS 테스트용 요청을 현재 계약으로 갱신한 뒤 해당 모듈과 최종 전체 검사를 통과했다. 생산 실행기에 구형 요청 호환 경로를 추가하지 않았다. 특정 문자열 할당 OOM을 catch하여 성공하는 우회는 재현하지 못했으며 반환 문자열 타입 확인은 예방 검사로 구분한다.

이번 패키지 확인은 정적 파일 검사이며 새 설치·OAuth 전체 흐름의 재검증을 뜻하지 않는다. 최종 소스로 Electron 11건을 별도 임시 앱 데이터와 hidden/offscreen 창에서 실행해 실제 main·preload·IPC·중단·복원·품질 보류 표시를 확인했다. 실제 사용자 인증 자료를 사용하지 않았으며, 모의 인증 fixture의 복원 검사를 실제 로그인 확인으로 표현하지 않는다.

| 최종 파일 | bytes | SHA256 |
| --- | ---: | --- |
| desktop/release/Paper Factory Setup 0.14.1.exe | 213,088,474 | 56082c7515b800f2acdde37d0dd54cad56a7eebf72776e53e423fedcb6c78194 |
| desktop/release/win-unpacked/resources/app.asar | 44,722,085 | 9c20e4a06114617e059d5724a6ff90ab747a29e9c760214c594db221aa895517 |
| 런타임 inventory | — | 816280d00ff7b734d31f006e8fb2f9222a290eb4d0f068da68b369a767257d89 |

새 연구 `research-c9268a619211`은 Madi commit `246b58dda40f83787a8971fd72ecb8cb3f7ddffd`의 실제 생산 함수·호출 화면·테스트와 사전에 고정한 12개 문서 발췌를 읽었다. 정확 DOI 두 건의 실제 초록을 수집했고 최초 StudyReview의 여섯 기준을 통과했다. 관련 없는 서지 검색 결과는 근거로 선정하지 않았다.

승인된 실험은 한 번 실행해 24개 입력 쌍·3조건·2지표의 144개 관측과 3개 제어를 남겼다. 생산 함수 호출 25회가 완료됐고 네이티브 실행·정리 모두 성공했다. 750개 fixture의 바이트·해시와 원문 정규화·12개 발췌의 출처, 961개 작은 토큰 쌍의 정렬, 24개 치환·384개 부분 반영 목표, 반환값과 분석 수치를 별도의 읽기 전용 검사로 대조했다. 생산 호출별 fixture는 생성 코드가 남긴 자료이며, 네이티브 게이트의 25회 집계와 구분한다.

생산 조건의 평균 부분 반영 가능 비율은 0.5, 두 정확 비교 조건은 각각 1.0이었다. 변경되지 않은 문맥을 변경 조각에 포함하는 비율은 각각 0.5·0·0이었다. 두 정확 비교 알고리즘은 모든 24개 입력에서 정렬·반환값·지표가 같았다. 관찰된 차이는 상한 초과 시 단일 변경 조각을 반환하는 정책과 일치하며, 새로운 정렬 효과나 일반적인 사용자 경험·성능 우월성을 입증하지 않는다.

실제 원시 관측 3,144,764 B의 SHA256은 `a30e289bba0b105565088dd6ae07607573d48478d1f6bed55256ecccf376a72c`다. 모델 전달 자료는 132,084 B이며 모든 144개 관측과 3개 제어가 원본과 같다. 원문 2,258,284 B를 생략한 750개 fixture는 검증된 해시·크기로 표시했다. 이 파일 검사 자체에는 모델 호출·과학실험 실행이 없다. 문맥 문제 이후에는 성공한 실험을 재실행하지 않고 원고 작성만 재개한다.

실제 원고 작성 재개는 `resume-runs/55445a0c75da`에서 수행했다. 같은 작성·심사 모델로 초안 3개와 독립 심사 요청 3개를 완료했으며 세 심사 모두 기여 기준을 반려했다. 첫 초안의 정렬 동일성 해석은 보완됐지만, 최종적으로 알려진 상한 정책 확인을 넘어서는 실증 기여를 입증하지 못했다. 수치가 맞고 소프트웨어 계약 검사로 유용하다는 점과 논문으로 충분하다는 판정은 구분한다. 별도의 읽기 전용 원고 감사도 같은 기여 결함을 확인했다. 이는 모델 초안 심사이며 학술지 동료심사가 아니다.

최종 상태는 `analyzed/blocked/MANUSCRIPT_REJECTED`, 과학 실행 1회·초안 3회·정리 대기 없음이다. 평가 결과는 `held-without-paper`, `paperGenerated=false`, `shutdownConfirmed=true`였다. 완료 PDF·DOCX·TeX·재현 ZIP은 생성하지 않았다. 따라서 실제 모델을 통한 원고 작성과 품질 보류는 확인했지만, 써먹을 만한 논문이 승인·내보내기까지 이어지는 성공 사례는 아직 확인하지 못했다. 기존 실행·분석·입력·소스는 보존했다.

최종 심사가 지적한 모델 입력 문맥 설명의 본문 유입도 반영했다. 검증된 artifact 내용·해시 비교를 설명하되 작성 모델의 prompt나 가시성을 원고에 쓰지 않도록 전달 지침을 명시했다. 생략한 원문을 읽었다고 주장하지 말라는 제한은 유지한다. 이 마지막 표현 지침은 후속 회귀 검사에서 전달을 확인했으며, 보류된 연구를 다시 작성하거나 실제 모델의 개선 효과를 재검증하지 않았다.

종료 후 독립 읽기 전용 검사에서 기존 110개 artifact와 464개 소스가 불변이고 최종 142개 artifact의 실제 바이트·SHA·크기가 엔진과 종료 기록에 일치함을 확인했다. 실행 폴더는 `attempt-1`뿐이며 소유 Electron·엔진 프로세스도 종료됐다. 이 연구의 PDF 시각 검수와 재현 ZIP 내용 검수는 생성물이 없어 수행하지 않았다.

최종 패키지는 **2026-10-07 12:00:57.992 KST**에 정적 검증을 통과했다. Windows의 임시 ZIP 추출 폴더 rename에서 `EPERM`이 반복돼, 설치된 동일 버전 Electron 배포 디렉터리를 electron-builder의 `electronDist` 옵션으로 사용했다. 제품 코드에 재시도·호환 경로를 추가하지 않았다. 이 마지막 표현 지침 이후 데스크톱 231건·SDK 48건은 다시 통과했으며, Electron 11건은 직전 자료 투영 구현으로 수행한 검사다.

| 최종 기록 | SHA256 |
| --- | --- |
| resume-runs/55445a0c75da/result.json | 548a1eba812b34b0b8334abaf26e421935b67be164582731d931b9f92f16ec0e |
| resume-runs/55445a0c75da/snapshot.json | 58163e3da5d40d31db1b628572d5362c6cd99e63620a6f44d687b3925cc228c2 |
| verification/desktop-model-context-final.log | 46961420f429aff8b761740edae285cf3d223bb65af67b66060cc649d3428e15 |
| verification/electron-observation-projection-final.log | 04147b87296732f396f31d1383ccbc530483a94c5431168736102527de090c99 |
| verification/package-verify-model-context-final.log | 6fea1ad4488e427e3a2a01a740a82515e88b77f6576295c72384cc6e67a102b8 |

원시 실행·테스트·패키지 기록은 ignored `.paper-factory/quality-positive-20261007/`와 `.paper-factory/qpos/560974298f49/` 아래에 보존한다. 모델 원문과 계정 자료는 커밋하지 않는다.
