//! Asks the author's Claude Code for a revision or a Think Tank review, and
//! shows the result for review before anything reaches the manuscript.

use std::{
    ops::Range,
    path::{Path, PathBuf},
};

use gpui::{
    AnyElement, AppContext as _, Context, Entity, EventEmitter, FocusHandle, Focusable as _,
    FontWeight, InteractiveElement as _, IntoElement, ParentElement as _, Render, Role,
    SharedString, StatefulInteractiveElement as _, Styled as _, Window, div, px,
};
use gpui_deck::{
    Button, Dialog, DialogBackdrop, DialogClose, DialogDescription, DialogPopup, DialogState,
    DialogTitle, InputAccessibility, Textarea, TextareaState,
};
use similar::{ChangeTag, TextDiff};

use crate::{
    agent::{self, Cancel, Revision},
    ui::{Palette, preset::Tokens, recipes::ButtonVariant},
    workspace::{EDITOR_FONT, MODIFIER_KEY},
};

/// The manuscript text a request was made against.
#[derive(Clone)]
pub struct Snapshot {
    /// The manuscript file.
    pub file: PathBuf,
    /// The folder Claude Code runs in.
    pub project: PathBuf,
    /// The whole editor text when the request was made.
    pub text: String,
    /// The byte range to revise: the selection, or the whole text.
    pub range: Range<usize>,
}

/// A revision the author accepted.
pub struct Accepted {
    pub snapshot: Snapshot,
    pub revised: String,
}

pub enum AssistantEvent {
    Apply(Accepted),
}

enum Outcome {
    Proposal { snapshot: Snapshot, revised: String },
    Review(SharedString),
    Failed(SharedString),
}

pub struct Assistant {
    tokens: Tokens,
    request_dialog: Entity<DialogState>,
    result_dialog: Entity<DialogState>,
    instruction: Entity<TextareaState>,
    close_focus: FocusHandle,
    /// The request being prepared or run.
    snapshot: Option<Snapshot>,
    running: Option<(SharedString, Cancel)>,
    outcome: Option<Outcome>,
}

impl EventEmitter<AssistantEvent> for Assistant {}

impl Assistant {
    pub fn new(tokens: Tokens, window: &mut Window, cx: &mut Context<Self>) -> Self {
        let instruction = cx.new(|cx| {
            let mut state = TextareaState::new(window, cx)
                .rows(4)
                .placeholder("예: 서론을 더 간결하게 다듬고 연구 질문을 첫 문단에 밝혀 줘");
            state.set_accessibility(
                InputAccessibility::new(Some(Role::MultilineTextInput))
                    .with_label(Some("AI에게 요청할 내용".into())),
            );
            state.set_editor_style(tokens.editor_style());
            state
        });
        let instruction_focus = instruction.focus_handle(cx);
        let request_dialog =
            cx.new(|cx| DialogState::new(cx).with_initial_focus(&instruction_focus));
        let close_focus = cx.focus_handle();
        let result_dialog = cx.new(|cx| DialogState::new(cx).with_initial_focus(&close_focus));
        cx.observe(&request_dialog, |_, _, cx| cx.notify()).detach();
        cx.observe(&result_dialog, |_, _, cx| cx.notify()).detach();
        cx.observe(&instruction, |_, _, cx| cx.notify()).detach();
        Self {
            tokens,
            request_dialog,
            result_dialog,
            instruction,
            close_focus,
            snapshot: None,
            running: None,
            outcome: None,
        }
    }

    /// What the toolbar shows while an agent runs.
    pub fn running_label(&self) -> Option<SharedString> {
        self.running.as_ref().map(|(label, _)| label.clone())
    }

    pub fn cancel(&mut self, cx: &mut Context<Self>) {
        if let Some((_, cancel)) = &self.running {
            cancel.cancel();
        }
        cx.notify();
    }

    /// Opens the request dialog for `snapshot`.
    pub fn open(&mut self, snapshot: Snapshot, window: &mut Window, cx: &mut Context<Self>) {
        if self.running.is_some() {
            return;
        }
        self.snapshot = Some(snapshot);
        self.request_dialog
            .update(cx, |dialog, cx| dialog.open(window, cx));
    }

    fn request_revision(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        let instruction = self.instruction.read(cx).value().trim().to_owned();
        let Some(snapshot) = self.snapshot.clone() else {
            return;
        };
        if instruction.is_empty() {
            return;
        }
        let Some(claude) = agent::find_claude() else {
            return self.fail(claude_missing(), window, cx);
        };
        self.request_dialog
            .update(cx, |dialog, cx| dialog.close(window, cx));
        let cancel = Cancel::default();
        self.running = Some(("AI가 수정안을 만드는 중…".into(), cancel.clone()));
        cx.notify();
        cx.spawn_in(window, async move |this, cx| {
            let original = snapshot.text[snapshot.range.clone()].to_owned();
            let is_selection = snapshot.range.len() < snapshot.text.len();
            let file = relative(&snapshot.file, &snapshot.project);
            let project = snapshot.project.clone();
            let result = cx
                .background_executor()
                .spawn(async move {
                    agent::revise(
                        &claude,
                        &project,
                        &Revision {
                            file: &file,
                            instruction: &instruction,
                            original: &original,
                            is_selection,
                        },
                        &cancel,
                    )
                })
                .await;
            this.update_in(cx, |this, window, cx| {
                this.running = None;
                let outcome = match result {
                    Ok(revised) => Outcome::Proposal { snapshot, revised },
                    Err(error) => Outcome::Failed(format!("{error:#}").into()),
                };
                this.show(outcome, window, cx);
            })
            .ok();
        })
        .detach();
    }

    fn request_review(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        let Some(snapshot) = self.snapshot.clone() else {
            return;
        };
        let Some(claude) = agent::find_claude() else {
            return self.fail(claude_missing(), window, cx);
        };
        self.request_dialog
            .update(cx, |dialog, cx| dialog.close(window, cx));
        let cancel = Cancel::default();
        self.running = Some(("Think Tank가 검토하는 중…".into(), cancel.clone()));
        cx.notify();
        cx.spawn_in(window, async move |this, cx| {
            let file = relative(&snapshot.file, &snapshot.project);
            let project = snapshot.project.clone();
            let result = cx
                .background_executor()
                .spawn(async move { agent::review(&claude, &project, &file, &cancel) })
                .await;
            this.update_in(cx, |this, window, cx| {
                this.running = None;
                let outcome = match result {
                    Ok(review) => Outcome::Review(review.into()),
                    Err(error) => Outcome::Failed(format!("{error:#}").into()),
                };
                this.show(outcome, window, cx);
            })
            .ok();
        })
        .detach();
    }

    fn fail(&mut self, message: String, window: &mut Window, cx: &mut Context<Self>) {
        self.request_dialog
            .update(cx, |dialog, cx| dialog.close(window, cx));
        self.show(Outcome::Failed(message.into()), window, cx);
    }

    fn show(&mut self, outcome: Outcome, window: &mut Window, cx: &mut Context<Self>) {
        self.outcome = Some(outcome);
        self.result_dialog
            .update(cx, |dialog, cx| dialog.open(window, cx));
        cx.notify();
    }

    fn accept(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        if let Some(Outcome::Proposal { snapshot, revised }) = self.outcome.take() {
            self.instruction
                .update(cx, |state, cx| state.set_value("", window, cx));
            cx.emit(AssistantEvent::Apply(Accepted { snapshot, revised }));
        }
        self.result_dialog
            .update(cx, |dialog, cx| dialog.close(window, cx));
    }

    fn palette(&self) -> Palette {
        Palette {
            control_height: gpui::rems(2.125),
            font_size: gpui::rems(0.875),
            ..self.tokens.palette()
        }
    }

    fn popup(&self, width: f32) -> DialogPopup {
        let tokens = self.tokens;
        DialogPopup::new()
            .w(px(width))
            .max_h(px(720.))
            .p_6()
            .flex()
            .flex_col()
            .gap_3()
            .rounded(tokens.radius)
            .bg(tokens.surface)
            .border_1()
            .border_color(tokens.border)
            .text_color(tokens.ink)
            .font_family(tokens.font)
            .shadow_lg()
    }

    fn render_request(&self, cx: &Context<Self>) -> impl IntoElement {
        let tokens = self.tokens;
        let palette = self.palette();
        let scope = match &self.snapshot {
            Some(snapshot) if snapshot.range.len() < snapshot.text.len() => format!(
                "선택한 부분({}자)을 고칩니다.",
                snapshot.text[snapshot.range.clone()].chars().count()
            ),
            Some(snapshot) => format!(
                "{} 전체를 고칩니다. 일부만 고치려면 먼저 선택하세요.",
                snapshot
                    .file
                    .file_name()
                    .unwrap_or_default()
                    .to_string_lossy()
            ),
            None => String::new(),
        };
        let think_tank = agent::think_tank_installed();
        let empty = self.instruction.read(cx).value().trim().is_empty();
        let popup = self
            .popup(560.)
            .child(
                DialogTitle::new()
                    .text_lg()
                    .font_weight(FontWeight::SEMIBOLD)
                    .child("AI에게 요청"),
            )
            .child(
                DialogDescription::new()
                    .text_sm()
                    .text_color(tokens.muted)
                    .child(format!(
                        "{scope} 이 PC의 Claude Code가 읽기 전용으로 작업하고, 결과는 적용하기 전에 비교해 볼 수 있습니다."
                    )),
            )
            .child(
                div()
                    .p_2()
                    .rounded(tokens.radius)
                    .border_1()
                    .border_color(tokens.border)
                    .bg(tokens.field)
                    .child(Textarea::new(&self.instruction)),
            )
            .child(
                div()
                    .flex()
                    .items_center()
                    .gap_2()
                    .child(
                        ButtonVariant::Outline
                            .apply(Button::new("think-tank-review"), palette)
                            .accessibility_label("Think Tank로 원고 검토")
                            .disabled(!think_tank)
                            .on_click(cx.listener(|this, _, window, cx| {
                                this.request_review(window, cx)
                            }))
                            .child("Think Tank 검토"),
                    )
                    .when(!think_tank, |this| {
                        this.child(
                            div()
                                .text_xs()
                                .text_color(tokens.muted)
                                .child("Think Tank 스킬이 설치되어 있지 않습니다"),
                        )
                    })
                    .child(div().flex_1())
                    .child(DialogClose::new(&self.request_dialog).trigger(|button| {
                        ButtonVariant::Ghost
                            .apply(button, palette)
                            .accessibility_label("취소")
                            .child("취소")
                    }))
                    .child(
                        ButtonVariant::Primary
                            .apply(Button::new("request-revision"), palette)
                            .accessibility_label("수정안 받기")
                            .disabled(empty)
                            .on_click(cx.listener(|this, _, window, cx| {
                                this.request_revision(window, cx)
                            }))
                            .child("수정안 받기"),
                    ),
            );
        Dialog::new(&self.request_dialog)
            .accessibility_label("AI에게 요청")
            .backdrop(backdrop())
            .popup(popup)
    }

    fn render_result(&self, cx: &Context<Self>) -> impl IntoElement {
        let tokens = self.tokens;
        let palette = self.palette();
        let (title, body, can_apply): (&str, AnyElement, bool) = match &self.outcome {
            Some(Outcome::Proposal { snapshot, revised }) => (
                "AI 수정안",
                render_diff(&snapshot.text[snapshot.range.clone()], revised, tokens),
                true,
            ),
            Some(Outcome::Review(text)) => (
                "Think Tank 검토 결과",
                div()
                    .text_sm()
                    .whitespace_normal()
                    .child(text.clone())
                    .into_any_element(),
                false,
            ),
            Some(Outcome::Failed(message)) => (
                "AI 작업을 마치지 못했습니다",
                div()
                    .text_sm()
                    .text_color(palette.error)
                    .child(message.clone())
                    .into_any_element(),
                false,
            ),
            None => ("", div().into_any_element(), false),
        };
        let popup = self
            .popup(820.)
            .child(
                DialogTitle::new()
                    .text_lg()
                    .font_weight(FontWeight::SEMIBOLD)
                    .child(title),
            )
            .when(can_apply, |this| {
                this.child(
                    DialogDescription::new()
                        .text_sm()
                        .text_color(tokens.muted)
                        .child("빨간 줄은 지워지고 초록 줄이 들어갑니다. 적용해도 저장되지 않으며 실행 취소할 수 있습니다."),
                )
            })
            .child(
                div()
                    .id("assistant-result")
                    .flex_1()
                    .min_h(px(120.))
                    .max_h(px(520.))
                    .overflow_y_scroll()
                    .p_3()
                    .rounded(tokens.radius)
                    .border_1()
                    .border_color(tokens.border)
                    .bg(tokens.canvas)
                    .child(body),
            )
            .child(
                div()
                    .flex()
                    .justify_end()
                    .gap_2()
                    .child(DialogClose::new(&self.result_dialog).trigger(|button| {
                        let label = if can_apply { "버리기" } else { "닫기" };
                        ButtonVariant::Outline
                            .apply(button.track_focus(&self.close_focus), palette)
                            .accessibility_label(label)
                            .child(label)
                    }))
                    .when(can_apply, |this| {
                        this.child(
                            ButtonVariant::Primary
                                .apply(Button::new("apply-revision"), palette)
                                .accessibility_label("원고에 적용")
                                .on_click(cx.listener(|this, _, window, cx| this.accept(window, cx)))
                                .child("원고에 적용"),
                        )
                    }),
            );
        Dialog::new(&self.result_dialog)
            .accessibility_label(title)
            .backdrop(backdrop())
            .popup(popup)
    }
}

use gpui::prelude::FluentBuilder as _;

fn backdrop() -> DialogBackdrop {
    DialogBackdrop::new()
        .absolute()
        .inset_0()
        .bg(gpui::black())
        .opacity(0.35)
}

fn claude_missing() -> String {
    format!(
        "Claude Code를 찾지 못했습니다. Claude Code를 설치하고 로그인한 뒤 다시 시도하세요. ({MODIFIER_KEY}+K로 다시 열 수 있습니다)"
    )
}

fn relative(file: &Path, project: &Path) -> PathBuf {
    file.strip_prefix(project).unwrap_or(file).to_path_buf()
}

/// Line-by-line comparison of the original and revised text.
fn render_diff(original: &str, revised: &str, tokens: Tokens) -> AnyElement {
    let diff = TextDiff::from_lines(original, revised);
    let added = gpui::rgb(0x1a7f37);
    let removed = gpui::rgb(0xcf222e);
    let lines = diff.iter_all_changes().map(|change| {
        let (sign, color, background) = match change.tag() {
            ChangeTag::Delete => (
                "-",
                Some(removed),
                Some(gpui::Hsla::from(removed).opacity(0.08)),
            ),
            ChangeTag::Insert => (
                "+",
                Some(added),
                Some(gpui::Hsla::from(added).opacity(0.08)),
            ),
            ChangeTag::Equal => (" ", None, None),
        };
        let text = change.value().trim_end_matches(['\n', '\r']).to_owned();
        div()
            .flex()
            .gap_2()
            .px_1()
            .when_some(background, |this, bg| this.bg(bg))
            .text_color(color.map_or(tokens.muted, Into::into))
            .child(div().w(px(10.)).flex_none().child(sign))
            .child(div().min_w_0().whitespace_normal().child(text))
    });
    div()
        .font_family(EDITOR_FONT)
        .text_xs()
        .flex()
        .flex_col()
        .children(lines)
        .into_any_element()
}

impl Render for Assistant {
    fn render(&mut self, _: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        div()
            .child(self.render_request(cx))
            .child(self.render_result(cx))
    }
}
