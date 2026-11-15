# Paper Factory

Rust + GPUI 기반의 로컬 중심 논문 작성 데스크톱 앱.

**현재 상태: 저장소 초기화만 완료. 실행 가능한 앱과 AI 연동은 아직 구현하지 않았습니다.**

## 역할

- **Paper Factory**: 로컬 논문 프로젝트를 열고 편집·저장하고, 컴파일 결과와 AI 변경 내용을 검토하는 앱.
- **[GPUI Design](https://github.com/andongmin94/gpui-design)**: 앱에서 사용하는 공통 네이티브 UI 기반. 별도 저장소로 유지합니다.
- **[Think Tank](https://github.com/andongmin94/think-tank)**: 연구·집필 스킬. 기존 스킬 구현을 앱 저장소로 복제하지 않습니다.

Overleaf를 웹뷰로 감싸거나 포팅하지 않습니다. Rust와 GPUI로 독립적인 데스크톱 앱을 개발합니다.

## 첫 구현 범위

먼저 로컬 `.tex` 파일 하나를 열고, 편집하고, 저장할 수 있는 네이티브 앱을 완성합니다. 이후 로컬 LaTeX 컴파일과 PDF 미리보기를 연결합니다.

AI 기능은 사용자의 공식 Claude Code 또는 Codex 실행 환경과 연동하는 방향으로 설계합니다. 실제 지원 인터페이스와 인증 조건을 확인한 후 구현하며, 이 저장소가 개인 구독을 임의의 API 이용권으로 전환하는 것은 아닙니다.

Think Tank 연결은 위 작업 흐름이 동작한 뒤 추가합니다. 현재 스킬의 지원 범위를 넘는 전 학문 분야 지원을 선언하지 않습니다. 실시간 공동 편집·교내 인증·클라우드 서비스는 첫 구현에 포함하지 않습니다.

## 현재 파일

- `README.md`: 제품 역할, 첫 구현 범위, 현재 상태.
- `AGENTS.md`: 개발 지침.
- `.gitignore`, `.gitattributes`: 저장소 기본 설정.

현재 소스 코드와 Cargo manifest는 없습니다. 컴파일·실행·UI 검증을 완료한 앱으로 취급하지 않습니다. 라이선스는 아직 지정하지 않았습니다.

## 저장소

공개 저장소: https://github.com/andongmin94/paper-factory

기본 브랜치는 `main`입니다. 이 저장소는 Paper Factory 데스크톱 앱을 위한 별도 Git 이력으로 시작했으며, 기존 연구·집필 스킬과 이력은 [Think Tank](https://github.com/andongmin94/think-tank)에서 유지합니다.
