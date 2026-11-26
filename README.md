# Paper Factory

Rust + GPUI 기반의 로컬 중심 논문 작성 데스크톱 앱.

**현재 상태: `.tex` 파일 하나를 목차·문법 강조 편집기로 쓰고, Tectonic으로 컴파일해 PDF를 옆에서 미리 봅니다. 여러 파일 프로젝트와 AI 연동은 아직 없습니다.**

## 역할

- **Paper Factory**: 로컬 논문 프로젝트를 열고 편집·저장하고, 컴파일 결과와 AI 변경 내용을 검토하는 앱.
- **[GPUI Deck](https://github.com/andongmin94/gpui-deck)**: 앱에서 사용하는 헤드리스 GPUI UI 기반. 동작·상태·포커스·접근성은 GPUI Deck이, 화면 구성과 스타일은 앱이 맡습니다. 별도 저장소로 유지합니다.
- **[Think Tank](https://github.com/andongmin94/think-tank)**: 연구·집필 스킬. 기존 스킬 구현을 앱 저장소로 복제하지 않습니다.

Overleaf를 웹뷰로 감싸거나 포팅하지 않습니다. Rust와 GPUI로 독립적인 데스크톱 앱을 개발합니다.

## 첫 구현 범위

로컬 `.tex` 파일 하나를 열고, 편집하고, 저장하고, 로컬에서 컴파일해 PDF를 미리 보는 네이티브 앱입니다.

편집기는 GPUI Deck의 `EditorState`(줄 번호·진단·LSP 연결 지점)를 기반으로 합니다. GPUI Deck에는 파서와 PDF 표시 기능이 없으므로 LaTeX 문법 강조는 이 앱의 하이라이터로, PDF 미리보기는 [hayro](https://github.com/LaurenzV/hayro)(순수 Rust PDF 렌더러)로 구현합니다.

AI 기능은 사용자의 공식 Claude Code 또는 Codex 실행 환경과 연동하는 방향으로 설계합니다. 실제 지원 인터페이스와 인증 조건을 확인한 후 구현하며, 이 저장소가 개인 구독을 임의의 API 이용권으로 전환하는 것은 아닙니다.

Think Tank 연결은 위 작업 흐름이 동작한 뒤 추가합니다. 현재 스킬의 지원 범위를 넘는 전 학문 분야 지원을 선언하지 않습니다. 실시간 공동 편집·교내 인증·클라우드 서비스는 첫 구현에 포함하지 않습니다.

## 현재 기능

- 파일 하나 편집: GPUI Deck `EditorState`(줄 번호, 자동 줄바꿈)로 UTF-8 `.tex` 파일을 엽니다. 실행 인자로 경로를 주거나 **열기**(Ctrl/Cmd+O)를 씁니다.
- 저장: **저장**(Ctrl/Cmd+S), **다른 이름으로 저장**(Ctrl/Cmd+Shift+S). 원래 파일의 줄바꿈(CRLF/LF)과 UTF-8 BOM을 유지하고, 임시 파일에 먼저 쓴 뒤 교체해 저장 실패 시 기존 원고가 남습니다.
- 변경 보호: 창 제목에 `●`로 저장되지 않은 변경을 표시합니다. 변경이 있을 때 다른 파일을 열거나 창을 닫으면 GPUI Deck `AlertDialog`로 저장 / 저장 안 함 / 취소를 묻고, 답할 때까지 편집 입력을 막습니다.
- 화면: GPUI Deck Create의 Base 프리셋(`v1.base.zinc.blue.neutral.pretendard.pretendard.outline.default`)을 씁니다. 상단 도구 막대와 목차 | 원고 | PDF 세 카드로 구성되며, 카드 사이 경계를 끌거나 포커스한 뒤 방향키로 너비를 조절합니다. 목차는 접을 수 있습니다.
- 문법 강조: 명령어, 구조 명령(`\section`, `\begin` 등), 환경 이름, 수식(`$…$`, `\[…\]`), 주석을 색으로 구분합니다.
- 목차: 왼쪽에 `\part`~`\subsubsection` 목록을 수준별로 보여 주고, 누르면 해당 줄로 이동합니다. 입력할 때마다 갱신되고, 커서가 있는 섹션을 강조합니다. 원고 카드 머리에는 커서의 줄·칸을 표시합니다.
- 컴파일: **컴파일**(Ctrl/Cmd+B)은 저장되지 않은 변경을 먼저 저장한 뒤 [Tectonic](https://tectonic-typesetting.github.io/)으로 원고 옆에 PDF를 만듭니다. Tectonic은 `PATH` 또는 `~/.local/tectonic`에서 찾으며, 처음 컴파일할 때 필요한 TeX 패키지를 내려받습니다.
- PDF 미리보기: 화면에 보이는 쪽만 백그라운드에서 렌더링하고 최근 10쪽만 메모리에 둡니다. 쪽 수와 컴파일 시간을 표시하고, 파일을 열 때 옆에 PDF가 있으면 바로 보여 줍니다.
- 배율: 기본은 폭 맞춤이며 **−**/**+**(Ctrl/Cmd+-, Ctrl/Cmd+=)로 25~300% 사이를 조절하고 **폭 맞춤**(Ctrl/Cmd+0)으로 돌아갑니다. 페이지가 창보다 넓으면 가로로 스크롤합니다.
- 컴파일 오류: 마지막으로 성공한 PDF를 그대로 둔 채 위에 오류를 보여 줍니다. 줄 번호가 있는 오류를 누르면 편집기의 해당 줄로 이동합니다.

```sh
cargo run -- path/to/paper.tex
```

## 소스 구성

- `src/main.rs`: 앱 시작, 단축키, 창.
- `src/workspace.rs`: 화면(목차 | 편집기 | 미리보기), 열기·저장·컴파일 흐름, 변경 보호.
- `src/document.rs`: 파일 읽기, 줄바꿈 처리, 안전한 저장.
- `src/latex.rs`: LaTeX 토큰 분석과 목차 추출.
- `src/highlight.rs`: 토큰을 GPUI Deck 하이라이터와 색상에 연결.
- `src/compile.rs`: Tectonic 찾기와 실행, 오류 줄과 원고 줄 번호 추출.
- `src/pdf.rs`: PDF 읽기와 쪽 단위 렌더링.
- `src/ui/`: `gpui-deck-cli` 0.0.3으로 설치한 앱 소유 디자인 소스. `preset/`은 Base 프리셋 토큰·글꼴, `recipes/`는 Button·Kbd 레시피입니다. `gpui-deck diff --to src/ui`로 설치 원본과 비교합니다.
- `src/preview.rs`: 미리보기 화면(가상 스크롤, 배율, 오류 목록).
- `rust-toolchain.toml`, `Cargo.toml`: GPUI Deck과 같은 Rust 1.99.1, `gpui-pre`/`gpui-pre-platform` =0.3.12, `gpui-deck` =0.0.1.

## 검증 현황

- `cargo fmt`, `cargo clippy --all-targets -D warnings`, `cargo test`(파일 처리·LaTeX 분석·오류 추출 7건) 통과.
- Windows에서 실행해 확인: 한글이 포함된 CRLF 파일 열기, 편집, 저장(Ctrl+S), 열기·다른 이름으로 저장 파일 대화상자, 확인 창의 저장 / 저장 안 함 / 취소, 확인 창이 떠 있는 동안 편집 입력 차단.
- Windows에서 실행해 확인(Tectonic 0.17.0): 문법 강조, 목차 표시와 줄 이동, `kotex` 한글 원고 컴파일과 PDF 미리보기, 컴파일 실패 시 이전 PDF 유지와 오류 줄 이동, 배율 조절과 가로 스크롤, Base 프리셋 화면, 현재 섹션 강조, 카드 너비 조절(마우스 끌기·방향키), 한글 입력기(Microsoft 한국어 IME)로 "한글" 조합 입력.
- 긴 원고 측정(Windows, 52쪽·160KB `kotex` 원고): 컴파일 2.6초. 전체 쪽 렌더링은 0.2초(릴리스 빌드)지만 이미지가 403MB라 화면에 보이는 쪽만 렌더링하도록 바꿨고, 처음부터 끝까지 스크롤해도 앱 메모리가 약 115~185MB에 머뭅니다. 문법 강조·목차 분석은 1.6MB 원고에서 2ms(릴리스 빌드)입니다.
- CI(`.github/workflows/verify.yml`): Linux·Windows·macOS에서 테스트와 빌드, Linux에서 포맷·Clippy. 아직 GitHub에서 실행 결과를 확인하지 않았습니다.
- 확인하지 않음: macOS·Linux에서 창 실행, 다른 한글 입력기, 화면 낭독기.
- 알려진 제약: 렌더링 해상도는 PDF 1pt당 2픽셀로 고정이라 고해상도 화면에서 200%를 넘게 확대하면 흐려질 수 있습니다.

라이선스는 아직 지정하지 않았습니다.

## 저장소

공개 저장소: https://github.com/andongmin94/paper-factory

기본 브랜치는 `main`입니다. 이 저장소는 Paper Factory 데스크톱 앱을 위한 별도 Git 이력으로 시작했으며, 기존 연구·집필 스킬과 이력은 [Think Tank](https://github.com/andongmin94/think-tank)에서 유지합니다.
