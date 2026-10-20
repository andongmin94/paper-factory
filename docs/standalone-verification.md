# 현재 검증 범위

2026-10-20 연구 설계 개선 기준이다. 제품 흐름과 보존할 실제 연구는 [현재 상태와 다음 세션](next-session.md), 구현 동작은 [연구 설계와 근거 보완](research-development.md)을 따른다.

## 이번 코드 검증

| 검증 | 결과와 범위 |
| --- | --- |
| Native | **31개 통과**. 질문 선정·설계·수집·한도, 보완 회차의 기본 5회/강화 6회 전체 경로, 첫 저장소 연구 경로 |
| Desktop | **134개 통과**. 최초 연구 입력·자료 전달과 보완 UI·예약/단계 표시 |
| 내용 전달 | 합성 근거가 잠정 질문을 바꾸고, 완료한 비교·발견이 두 원고 본문·실제 인용/참고문헌 입력까지 전달됨 |
| 기존 연구 호환성 | 전체 workflow의 독립 일반 파일 복제본에서 새 서비스 2개와 IPC 조회; 종료된 contract 2와 전체 품질 객체 불변 |
| 원본 보존 | workflow 1,176개·원자료 161개·SDK raw 70개/dispatch 35개·기존 원고/심사/ZIP/템플릿 및 이전 15개 증거/납품 디렉터리 바이트 불변 |
| 빌드 | TypeScript·데스크톱/SDK 빌드와 새 모듈 소스·패키지 문법 검사 통과 |

전체 흐름 검사는 모델 응답·HTTP 자료를 주입했고 해당 경로의 Word/PDF 변환도 대체했다. 원문 수집기의 증명과 실패 처리·실제 원고 입력 연결을 확인했지만 실제 계정 모델의 연구 성과나 새 출력 레이아웃을 측정한 것은 아니다. UI 30개 검사는 production React 합성 상태 검사이며 위 Desktop 검사와 중복 합산하지 않는다.

기존 Frontron은 **SDK 35회·영구 예약 24/24회·품질 심사 10회**, contract 2의 종료된 round 2를 유지한다. 새 서비스의 조회 중 네트워크·collector·runner·runtime 요청 시도는 0회다. 원본 서비스를 열어 연구를 재개하지 않았다. 이번 작업의 실제 추가 SDK·예약·집필·심사는 모두 **0회**다.

## 최신 로컬 패키지

- 실행 파일: `desktop/release/research-design-20261020/win-unpacked/Paper Factory.exe`
- 실행 파일 SHA256: `1889ab05b39f9726ef466acbb5cdf8cabb6b2b8d06095f52f53d6b7b6a42b693`
- source 123개·native 자산 54개·runtime 2,443개와 공식 템플릿의 bytes/SHA 결속 확인.
- source binding: `108681ae30845021c6e1da0a8ed97308befe0827bbdac34c9b607d7a2d38c953`

미배포 로컬 산출물이다. **이 패키지의 실제 앱 기동·계정 접근·연구 재개·추가 SDK 실행은 하지 않았다.** 공개 [0.14.20 릴리스](https://github.com/andongmin94/paper-factory/releases/tag/v0.14.20)와 최신 소스·로컬 패키지의 기능 범위를 구분한다.

## 로컬 증거와 핵심 해시

증거 루트는 `output/playwright/research-design-20261020/`다. 증거·런타임·원고와 계정은 Git에 포함하지 않는다. 아래 파일은 그 실행 PC의 로컬 자료이며 새 clone에 있다고 가정하지 않는다.

| 파일 | SHA256 | 의미 |
| --- | --- | --- |
| `checks.json` | `bde8eec8832b220d5e47e3e446d40b7c972ad9ec2dee6892a006912c747abdcc` | 최종 31/134 검사 로그·생산 소스 15개·조회/보존 증거 결속 |
| `preservation-final.json` | `71fa99ffef76915e91aceaf69287640f31725cf47fe8d6967da09cd861d5dd69` | 원본 바이트와 누적 횟수 불변 |
| `closed-study-current-source.json` | `b6f9c9dc85d4a341636ea85c6bb9ad9adc60d96474baef19969b52090c5f1b4d` | 새 소스로 복제본 조회, 실제 전체 품질 객체와 종료 상태 일치 |
| `build-proof.json` | `a6155df1a11da84bbf858b8915730f27727b43bc3bc8517e49e3f6ada41ccdb7` | 패키지·소스·런타임·템플릿과 검사 증거 결속 |

기준 목록은 `preservation-baseline.json`, 복제 방법은 `readonly-clone-preparation.json`, 합성 UI 검사는 `question-design-ui-proof.json`에 보존한다. 운영 원자료와 실패 기록은 정리 과정에서 삭제하지 않았다.

## 실제 원고 평가와의 구분

마지막 실제 숨김 Electron·Playwright 연구와 공식 템플릿 원고 생성·독립 평가는 **2026-10-18** 실행이다. 그 새 후보의 9개 항목 점수는 Software **6/8/7/6/7/8/8/7/9**, S&P **6/8/7/7/7/8/6/5/9**이며 둘 다 `revise_before_submission`이다. 새 후보와 기존 최선 원고를 모두 보존했다. 모든 항목 9점·현재 투고 권고 수준은 미달성이다.

이번 코드 변경으로 실제 원고 품질이 얼마나 올랐는지는 아직 측정하지 않았다. 공식 템플릿 출력·형식 통과·독립 내용 평가·저자 승인·포털 접수는 각기 별도 결과다. 현재 제출 준비는 `awaiting_file_check`이고 저자 승인·실제 접수 기록은 없다.

마지막 실제 납품은 로컬 `output/pdf/frontron-renewed-20261018/` 및 `output/pdf/frontron-renewed-20261018.zip`이다. ZIP SHA256은 `ee39abcfb20e3d69494a1d4c3159bbccb02482697696a35ce3cf32d2691a67a0`, 폴더 manifest SHA256은 `78cf3e3e53e4d35c8da475fdf5c7bef671fc78fd52e45b8bbe2899162fef419e`다. 실제 원고·실행·검수·이전 배포의 전체 누적 기록은 [2026-10-20 정리 전 검증 이력](history/standalone-verification-20261020.md)에 보존했다. 과거의 진행 중 상태·긍정 판정·초기화 지시를 현재 상태로 사용하지 않는다.
