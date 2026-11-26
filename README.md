# Paper Factory

Rust + GPUI 기반의 로컬 중심 논문 작성 데스크톱 앱.

**현재 상태: 로컬 `.tex` 파일 하나를 열고·편집하고·저장하는 기본 앱. LaTeX 문법 강조, 컴파일, PDF 미리보기, AI 연동은 아직 없습니다.**

## 역할

- **Paper Factory**: 로컬 논문 프로젝트를 열고 편집·저장하고, 컴파일 결과와 AI 변경 내용을 검토하는 앱.
- **[GPUI Deck](https://github.com/andongmin94/gpui-deck)**: 앱에서 사용하는 헤드리스 GPUI UI 기반. 동작·상태·포커스·접근성은 GPUI Deck이, 화면 구성과 스타일은 앱이 맡습니다. 별도 저장소로 유지합니다.
- **[Think Tank](https://github.com/andongmin94/think-tank)**: 연구·집필 스킬. 기존 스킬 구현을 앱 저장소로 복제하지 않습니다.

Overleaf를 웹뷰로 감싸거나 포팅하지 않습니다. Rust와 GPUI로 독립적인 데스크톱 앱을 개발합니다.

## 첫 구현 범위

먼저 로컬 `.tex` 파일 하나를 열고, 편집하고, 저장할 수 있는 네이티브 앱을 완성합니다. 이후 로컬 LaTeX 컴파일과 PDF 미리보기를 연결합니다.

편집기는 GPUI Deck의 `EditorState`(줄 번호·접기·진단·LSP 연결 지점)를 기반으로 합니다. GPUI Deck에는 파서와 PDF 표시 기능이 없으므로 LaTeX 문법 강조와 PDF 미리보기는 이 앱에서 구현합니다.

AI 기능은 사용자의 공식 Claude Code 또는 Codex 실행 환경과 연동하는 방향으로 설계합니다. 실제 지원 인터페이스와 인증 조건을 확인한 후 구현하며, 이 저장소가 개인 구독을 임의의 API 이용권으로 전환하는 것은 아닙니다.

Think Tank 연결은 위 작업 흐름이 동작한 뒤 추가합니다. 현재 스킬의 지원 범위를 넘는 전 학문 분야 지원을 선언하지 않습니다. 실시간 공동 편집·교내 인증·클라우드 서비스는 첫 구현에 포함하지 않습니다.

## 현재 기능

- 파일 하나 편집: GPUI Deck `EditorState`(줄 번호, 자동 줄바꿈)로 UTF-8 `.tex` 파일을 엽니다. 실행 인자로 경로를 주거나 **열기**(Ctrl/Cmd+O)를 씁니다.
- 저장: **저장**(Ctrl/Cmd+S), **다른 이름으로 저장**(Ctrl/Cmd+Shift+S). 원래 파일의 줄바꿈(CRLF/LF)과 UTF-8 BOM을 유지하고, 임시 파일에 먼저 쓴 뒤 교체해 저장 실패 시 기존 원고가 남습니다.
- 변경 보호: 창 제목에 `●`로 저장되지 않은 변경을 표시합니다. 변경이 있을 때 다른 파일을 열거나 창을 닫으면 GPUI Deck `AlertDialog`로 저장 / 저장 안 함 / 취소를 묻고, 답할 때까지 편집 입력을 막습니다.

```sh
cargo run -- path/to/paper.tex
```

## 소스 구성

- `src/main.rs`: 앱 시작, 단축키, 창.
- `src/workspace.rs`: 편집기 화면, 열기·저장 흐름, 변경 보호.
- `src/document.rs`: 파일 읽기, 줄바꿈 처리, 안전한 저장.
- `rust-toolchain.toml`, `Cargo.toml`: GPUI Deck과 같은 Rust 1.99.1, `gpui-pre`/`gpui-pre-platform` =0.3.12, `gpui-deck` =0.0.1.

## 검증 현황

- `cargo fmt`, `cargo clippy --all-targets -D warnings`, `cargo test`(파일 처리 3건) 통과.
- Windows에서 실행해 확인: 한글이 포함된 CRLF 파일 열기, 편집, 저장(Ctrl+S), 열기·다른 이름으로 저장 파일 대화상자, 확인 창의 저장 / 저장 안 함 / 취소, 확인 창이 떠 있는 동안 편집 입력 차단.
- CI(`.github/workflows/verify.yml`): Linux·Windows·macOS에서 테스트와 빌드, Linux에서 포맷·Clippy. 아직 GitHub에서 실행 결과를 확인하지 않았습니다.
- 확인하지 않음: 한글 입력기(IME) 조합 입력, macOS·Linux에서 창 실행.

라이선스는 아직 지정하지 않았습니다.

## 저장소

공개 저장소: https://github.com/andongmin94/paper-factory

기본 브랜치는 `main`입니다. 이 저장소는 Paper Factory 데스크톱 앱을 위한 별도 Git 이력으로 시작했으며, 기존 연구·집필 스킬과 이력은 [Think Tank](https://github.com/andongmin94/think-tank)에서 유지합니다.
