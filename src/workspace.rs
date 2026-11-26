//! The manuscript window: one `.tex` file in a GPUI Deck editor.

use std::{
    path::{Path, PathBuf},
    sync::Arc,
    time::Instant,
};

use futures::channel::oneshot;
use gpui::{
    AnyElement, AppContext as _, Axis, Context, Entity, FocusHandle, FontWeight,
    InteractiveElement as _, IntoElement, ParentElement as _, PathPromptOptions, PromptLevel,
    Render, Role, SharedString, StatefulInteractiveElement as _, Styled as _, Subscription, Task,
    Window, actions, div, prelude::FluentBuilder as _, px,
};
use gpui_deck::{
    AlertDialog, Button, DialogBackdrop, DialogClose, DialogDescription, DialogEvent, DialogPopup,
    DialogState, DialogTitle, InputAccessibility, InputEditorStyle, Resizable, ResizablePanel,
    ResizableState,
    input::{EditorState, InputEvent, Position},
};

use crate::{
    compile::{self, Problem},
    document::Document,
    highlight,
    latex::{self, Heading},
    pdf::PdfDocument,
    preview::{PdfPreview, PreviewEvent},
    ui::{
        Palette,
        preset::Tokens,
        recipes::{ButtonVariant, Kbd, KbdGroup},
    },
};

actions!(
    paper_factory,
    [Open, Save, SaveAs, Compile, ZoomIn, ZoomOut, ZoomToFit]
);

const NO_PDF_HINT: &str = "컴파일(Ctrl+B)하면 PDF가 여기에 표시됩니다.";

/// The platform's primary shortcut modifier, as printed on its keys.
#[cfg(target_os = "macos")]
pub const MODIFIER_KEY: &str = "⌘";
#[cfg(not(target_os = "macos"))]
pub const MODIFIER_KEY: &str = "Ctrl";

#[cfg(target_os = "windows")]
pub const EDITOR_FONT: &str = "Consolas";
#[cfg(target_os = "macos")]
pub const EDITOR_FONT: &str = "Menlo";
#[cfg(not(any(target_os = "windows", target_os = "macos")))]
pub const EDITOR_FONT: &str = "DejaVu Sans Mono";

/// The answer to the unsaved-changes dialog.
enum Choice {
    Save,
    Discard,
    Cancel,
}

pub struct Workspace {
    editor: Entity<EditorState>,
    document: Document,
    dirty: bool,
    /// Set once the user has resolved unsaved changes for a pending close.
    close_confirmed: bool,
    /// Modal unsaved-changes dialog; it blocks editing while open.
    discard_dialog: Entity<DialogState>,
    discard_cancel_focus: FocusHandle,
    /// Receives the dialog's answer while it is open.
    pending_choice: Option<oneshot::Sender<Choice>>,
    outline: Vec<Heading>,
    preview: Entity<PdfPreview>,
    compiling: bool,
    tokens: Tokens,
    /// Outline, editor and preview widths, resizable by dragging their dividers.
    panes: Entity<ResizableState>,
    _subscriptions: [Subscription; 5],
}

impl Workspace {
    pub fn new(
        path: Option<PathBuf>,
        tokens: Tokens,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) -> Self {
        let editor = cx.new(|cx| {
            let mut editor = EditorState::new(window, cx)
                .soft_wrap(true)
                .language(highlight::LANGUAGE);
            editor.set_highlighter_factory(highlight::factory(), cx);
            editor.set_editor_style(InputEditorStyle {
                editor_active_line: Some(tokens.accent.opacity(0.06)),
                editor_gutter_background: Some(tokens.surface),
                highlight_styles: highlight::styles(),
                ..tokens.editor_style()
            });
            editor.set_accessibility(
                InputAccessibility::new(Some(Role::MultilineTextInput))
                    .with_label(Some("원고".into())),
            );
            editor
        });
        let editor_events = cx.subscribe_in(&editor, window, |this, editor, event, window, cx| {
            if !matches!(event, InputEvent::Change) {
                return;
            }
            this.outline = latex::outline(&editor.read(cx).value());
            if !this.dirty {
                this.dirty = true;
                this.refresh_title(window);
            }
            cx.notify();
        });

        // Cursor moves change the outline's current section.
        let editor_observation = cx.observe(&editor, |_, _, cx| cx.notify());

        let discard_cancel_focus = cx.focus_handle();
        let discard_dialog =
            cx.new(|cx| DialogState::new(cx).with_initial_focus(&discard_cancel_focus));
        let dialog_observation = cx.observe(&discard_dialog, |_, _, cx| cx.notify());
        // Escape or the cancel button closes the dialog without an explicit answer.
        let dialog_events = cx.subscribe(&discard_dialog, |this, _, event, _| {
            if let DialogEvent::Closed(_) = event
                && let Some(sender) = this.pending_choice.take()
            {
                let _ = sender.send(Choice::Cancel);
            }
        });

        let preview = cx.new(|_| PdfPreview::new(tokens));
        let panes = cx.new(|cx| {
            ResizableState::new(
                Axis::Horizontal,
                [
                    ResizablePanel::new(0.16)
                        .limits(0.08..=0.3)
                        .pixel_limits(px(160.)..=px(360.))
                        .collapsible(0.),
                    ResizablePanel::new(0.42).pixel_limits(px(320.)..=px(10_000.)),
                    ResizablePanel::new(0.42).pixel_limits(px(280.)..=px(10_000.)),
                ],
                cx,
            )
        });
        let preview_events = cx.subscribe_in(&preview, window, |this, _, event, window, cx| {
            let PreviewEvent::JumpToLine(line) = event;
            this.jump_to(*line, window, cx);
        });

        let weak = cx.weak_entity();
        window.on_window_should_close(cx, move |window, cx| {
            weak.update(cx, |this, cx| this.should_close(window, cx))
                .unwrap_or(true)
        });

        let mut this = Self {
            editor,
            document: Document::default(),
            dirty: false,
            close_confirmed: false,
            discard_dialog,
            discard_cancel_focus,
            pending_choice: None,
            outline: Vec::new(),
            preview,
            compiling: false,
            tokens,
            panes,
            _subscriptions: [
                editor_events,
                editor_observation,
                dialog_observation,
                dialog_events,
                preview_events,
            ],
        };
        if let Some(path) = path {
            this.load(&path, window, cx);
        }
        this.editor
            .update(cx, |editor, cx| editor.focus(window, cx));
        this.refresh_title(window);
        this
    }

    fn load(&mut self, path: &Path, window: &mut Window, cx: &mut Context<Self>) {
        match Document::open(path) {
            Ok((document, text)) => {
                self.outline = latex::outline(&text);
                self.editor.update(cx, |editor, cx| {
                    editor.set_value(text, window, cx);
                    // A native file dialog leaves the window without a focused element.
                    editor.focus(window, cx);
                });
                self.document = document;
                self.dirty = false;
                self.refresh_title(window);
                // Show the PDF from an earlier compile until the next one.
                let existing = path.with_extension("pdf");
                if existing.is_file() {
                    self.show_pdf(existing, cx);
                } else {
                    self.preview
                        .update(cx, |preview, cx| preview.set_message(NO_PDF_HINT, cx));
                }
                cx.notify();
            }
            Err(error) => show_error(window, cx, "파일을 열지 못했습니다", &error),
        }
    }

    /// Loads `pdf` in the background and shows it.
    fn show_pdf(&mut self, pdf: PathBuf, cx: &mut Context<Self>) {
        let preview = self.preview.clone();
        cx.spawn(async move |_, cx| {
            let document = cx
                .background_executor()
                .spawn(async move { PdfDocument::open(&pdf) })
                .await;
            preview.update(cx, |preview, cx| match document {
                Ok(document) => {
                    let status = format!("{}쪽", document.page_sizes.len());
                    preview.set_document(Arc::new(document), Some(status.into()), cx)
                }
                Err(error) => preview.set_message(format!("{error:#}"), cx),
            });
        })
        .detach();
    }

    fn compile(&mut self, _: &Compile, window: &mut Window, cx: &mut Context<Self>) {
        if self.compiling {
            return;
        }
        let Some(engine) = compile::find_engine() else {
            self.preview.update(cx, |preview, cx| {
                preview.set_problems(
                    vec![Problem {
                        text: "Tectonic을 찾지 못했습니다. PATH 또는 ~/.local/tectonic에 tectonic을 설치하세요."
                            .into(),
                        line: None,
                    }],
                    cx,
                )
            });
            return;
        };
        // The engine reads the file on disk, so unsaved edits are saved first.
        let saved = if self.dirty || self.document.path.is_none() {
            self.save(false, window, cx)
        } else {
            Task::ready(true)
        };
        self.compiling = true;
        cx.notify();
        cx.spawn_in(window, async move |this, cx| {
            let tex = match saved.await {
                true => this
                    .update(cx, |this, _| this.document.path.clone())
                    .ok()
                    .flatten(),
                false => None,
            };
            let Some(tex) = tex else {
                this.update(cx, |this, cx| {
                    this.compiling = false;
                    cx.notify();
                })
                .ok();
                return;
            };
            let started = Instant::now();
            let result = cx
                .background_executor()
                .spawn(async move {
                    let outcome = compile::compile(&engine, &tex)?;
                    let document = outcome.pdf.as_deref().map(PdfDocument::open).transpose()?;
                    anyhow::Ok((outcome.log, document))
                })
                .await;
            let seconds = started.elapsed().as_secs_f32();
            this.update(cx, |this, cx| {
                this.compiling = false;
                this.preview.update(cx, |preview, cx| match result {
                    Ok((_, Some(document))) => {
                        let status =
                            format!("{}쪽 · 컴파일 {seconds:.1}초", document.page_sizes.len());
                        preview.set_document(Arc::new(document), Some(status.into()), cx)
                    }
                    Ok((log, None)) => preview.set_problems(compile::problems(&log), cx),
                    Err(error) => preview.set_problems(
                        vec![Problem {
                            text: format!("{error:#}"),
                            line: None,
                        }],
                        cx,
                    ),
                });
                cx.notify();
            })
            .ok();
        })
        .detach();
    }

    fn jump_to(&mut self, line: usize, window: &mut Window, cx: &mut Context<Self>) {
        self.editor.update(cx, |editor, cx| {
            editor.set_cursor_position(Position::new(line as u32, 0), window, cx);
        });
    }

    fn write(&mut self, path: &Path, window: &mut Window, cx: &mut Context<Self>) -> bool {
        let text = self.editor.read(cx).value();
        match self.document.save_to(path, &text) {
            Ok(()) => {
                self.dirty = false;
                self.refresh_title(window);
                cx.notify();
                true
            }
            Err(error) => {
                show_error(window, cx, "저장하지 못했습니다", &error);
                false
            }
        }
    }

    /// Saves the manuscript, asking for a path when it has none or `choose_path` is set.
    /// Resolves to whether the text is now on disk.
    fn save(
        &mut self,
        choose_path: bool,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) -> Task<bool> {
        if let (Some(path), false) = (self.document.path.clone(), choose_path) {
            return Task::ready(self.write(&path, window, cx));
        }
        let directory = self
            .document
            .path
            .as_deref()
            .and_then(Path::parent)
            .map(Path::to_path_buf)
            .or_else(std::env::home_dir)
            .unwrap_or_default();
        let name = self.document.display_name();
        let chosen = cx.prompt_for_new_path(&directory, Some(&name));
        cx.spawn_in(window, async move |this, cx| {
            let Ok(Ok(Some(path))) = chosen.await else {
                return false;
            };
            this.update_in(cx, |this, window, cx| this.write(&path, window, cx))
                .unwrap_or(false)
        })
    }

    /// Resolves to true when the current text may be replaced or discarded.
    fn confirm_discard(&mut self, window: &mut Window, cx: &mut Context<Self>) -> Task<bool> {
        if !self.dirty {
            return Task::ready(true);
        }
        // One question at a time: a second request while the dialog is open is declined.
        if self.pending_choice.is_some() {
            return Task::ready(false);
        }
        let (sender, answer) = oneshot::channel();
        self.pending_choice = Some(sender);
        self.discard_dialog
            .update(cx, |dialog, cx| dialog.open(window, cx));
        cx.spawn_in(window, async move |this, cx| match answer.await {
            Ok(Choice::Save) => {
                match this.update_in(cx, |this, window, cx| this.save(false, window, cx)) {
                    Ok(saved) => saved.await,
                    Err(_) => false,
                }
            }
            Ok(Choice::Discard) => true,
            Ok(Choice::Cancel) | Err(_) => false,
        })
    }

    fn choose(&mut self, choice: Choice, window: &mut Window, cx: &mut Context<Self>) {
        if let Some(sender) = self.pending_choice.take() {
            let _ = sender.send(choice);
        }
        self.discard_dialog
            .update(cx, |dialog, cx| dialog.close(window, cx));
    }

    fn render_discard_dialog(&self, cx: &Context<Self>) -> AlertDialog {
        let tokens = self.tokens;
        let palette = self.palette();
        let message = format!("{}의 변경 내용을 저장할까요?", self.document.display_name());
        let detail = "저장하지 않으면 변경 내용이 사라집니다.";
        let popup = DialogPopup::new()
            .w(px(440.))
            .p_6()
            .flex()
            .flex_col()
            .gap_2()
            .rounded(tokens.radius)
            .bg(tokens.surface)
            .border_1()
            .border_color(tokens.border)
            .text_color(tokens.ink)
            .shadow_lg()
            .child(
                DialogTitle::new()
                    .text_lg()
                    .font_weight(FontWeight::SEMIBOLD)
                    .child(message.clone()),
            )
            .child(
                DialogDescription::new()
                    .text_sm()
                    .text_color(tokens.muted)
                    .child(detail),
            )
            .child(
                div()
                    .mt_4()
                    .flex()
                    .justify_end()
                    .gap_2()
                    .child(DialogClose::new(&self.discard_dialog).trigger(|button| {
                        ButtonVariant::Outline
                            .apply(button.track_focus(&self.discard_cancel_focus), palette)
                            .accessibility_label("취소")
                            .child("취소")
                    }))
                    .child(
                        ButtonVariant::Ghost
                            .apply(Button::new("discard-changes"), palette)
                            .accessibility_label("저장 안 함")
                            .on_click(cx.listener(|this, _, window, cx| {
                                this.choose(Choice::Discard, window, cx)
                            }))
                            .child("저장 안 함"),
                    )
                    .child(
                        ButtonVariant::Primary
                            .apply(Button::new("save-changes"), palette)
                            .accessibility_label("저장")
                            .on_click(cx.listener(|this, _, window, cx| {
                                this.choose(Choice::Save, window, cx)
                            }))
                            .child("저장"),
                    ),
            );
        AlertDialog::new(&self.discard_dialog)
            .accessibility_label(message)
            .accessibility_description(detail)
            .backdrop(
                DialogBackdrop::new()
                    .absolute()
                    .inset_0()
                    .bg(gpui::black())
                    .opacity(0.35),
            )
            .popup(popup)
    }

    fn open(&mut self, _: &Open, window: &mut Window, cx: &mut Context<Self>) {
        let confirmed = self.confirm_discard(window, cx);
        cx.spawn_in(window, async move |this, cx| {
            if !confirmed.await {
                return;
            }
            let Ok(chosen) = cx.update(|_, cx| {
                cx.prompt_for_paths(PathPromptOptions {
                    files: true,
                    directories: false,
                    multiple: false,
                    prompt: Some("열기".into()),
                })
            }) else {
                return;
            };
            let Ok(Ok(Some(paths))) = chosen.await else {
                return;
            };
            if let Some(path) = paths.into_iter().next() {
                this.update_in(cx, |this, window, cx| this.load(&path, window, cx))
                    .ok();
            }
        })
        .detach();
    }

    fn save_action(&mut self, _: &Save, window: &mut Window, cx: &mut Context<Self>) {
        self.save(false, window, cx).detach();
    }

    fn save_as_action(&mut self, _: &SaveAs, window: &mut Window, cx: &mut Context<Self>) {
        self.save(true, window, cx).detach();
    }

    fn should_close(&mut self, window: &mut Window, cx: &mut Context<Self>) -> bool {
        if self.close_confirmed || !self.dirty {
            return true;
        }
        let confirmed = self.confirm_discard(window, cx);
        cx.spawn_in(window, async move |this, cx| {
            if confirmed.await {
                this.update_in(cx, |this, window, _| {
                    this.close_confirmed = true;
                    window.remove_window();
                })
                .ok();
            }
        })
        .detach();
        false
    }

    fn refresh_title(&self, window: &mut Window) {
        let marker = if self.dirty { "● " } else { "" };
        window.set_window_title(&format!(
            "{marker}{} — Paper Factory",
            self.document.display_name()
        ));
    }
}

fn show_error(window: &mut Window, cx: &mut gpui::App, message: &str, error: &anyhow::Error) {
    let detail = format!("{error:#}");
    // The only answer dismisses the prompt, so its result carries nothing.
    drop(window.prompt(PromptLevel::Critical, message, Some(&detail), &["확인"], cx));
}

/// A titled card holding one of the three panes.
fn pane(
    tokens: Tokens,
    title: &'static str,
    extra: Option<AnyElement>,
    body: AnyElement,
) -> AnyElement {
    tokens
        .panel()
        .size_full()
        .flex()
        .flex_col()
        .overflow_hidden()
        .child(
            div()
                .h(px(38.))
                .flex_none()
                .flex()
                .items_center()
                .gap_2()
                .px_3()
                .border_b_1()
                .border_color(tokens.border)
                .child(
                    div()
                        .text_xs()
                        .font_weight(FontWeight::SEMIBOLD)
                        .text_color(tokens.muted)
                        .child(title),
                )
                .children(extra),
        )
        .child(div().flex_1().min_h_0().child(body))
        .into_any_element()
}

/// The keycaps for a modifier shortcut such as Ctrl+B.
fn shortcut(id: &'static str, key: &'static str, palette: Palette) -> KbdGroup {
    KbdGroup::new(id, palette)
        .key(Kbd::new((id, 0usize), MODIFIER_KEY, palette))
        .key(Kbd::new((id, 1usize), key, palette))
}

impl Workspace {
    fn palette(&self) -> Palette {
        Palette {
            control_height: gpui::rems(2.125),
            font_size: gpui::rems(0.875),
            ..self.tokens.palette()
        }
    }

    fn render_toolbar(&self, cx: &Context<Self>) -> impl IntoElement {
        let tokens = self.tokens;
        let palette = self.palette();
        let name = self.document.display_name();
        let folder: SharedString = match &self.document.path {
            Some(path) => path
                .parent()
                .map(|dir| dir.display().to_string())
                .unwrap_or_default()
                .into(),
            None => "저장되지 않은 새 원고".into(),
        };
        let action = |id: &'static str, label: &'static str| {
            ButtonVariant::Ghost
                .apply(Button::new(id), palette)
                .accessibility_label(label)
                .child(label)
        };
        let keys = palette;
        div()
            .h(px(52.))
            .flex_none()
            .flex()
            .items_center()
            .gap_1()
            .px_4()
            .bg(tokens.surface)
            .border_b_1()
            .border_color(tokens.border)
            .child(
                div()
                    .mr_3()
                    .flex()
                    .items_center()
                    .gap_2()
                    .child(
                        div()
                            .size(px(22.))
                            .rounded(px(6.))
                            .bg(tokens.accent)
                            .text_color(tokens.on_accent)
                            .text_xs()
                            .font_weight(FontWeight::BOLD)
                            .flex()
                            .items_center()
                            .justify_center()
                            .child("P"),
                    )
                    .child(
                        div()
                            .font_family(tokens.heading)
                            .font_weight(FontWeight::SEMIBOLD)
                            .child("Paper Factory"),
                    ),
            )
            .child(
                action("open", "열기")
                    .on_click(cx.listener(|this, _, window, cx| this.open(&Open, window, cx))),
            )
            .child(
                action("save", "저장").on_click(
                    cx.listener(|this, _, window, cx| this.save_action(&Save, window, cx)),
                ),
            )
            .child(action("save-as", "다른 이름으로 저장").on_click(
                cx.listener(|this, _, window, cx| this.save_as_action(&SaveAs, window, cx)),
            ))
            .child(
                div()
                    .id("document-status")
                    .role(Role::Label)
                    .aria_label(format!("{name} {folder}"))
                    .flex_1()
                    .min_w_0()
                    .mx_4()
                    .flex()
                    .items_center()
                    .justify_center()
                    .gap_2()
                    .child(div().font_weight(FontWeight::MEDIUM).child(name))
                    .when(self.dirty, |this| {
                        this.child(
                            div()
                                .size(px(7.))
                                .flex_none()
                                .rounded_full()
                                .bg(tokens.accent),
                        )
                    })
                    .child(
                        div()
                            .min_w_0()
                            .truncate()
                            .text_xs()
                            .text_color(tokens.muted)
                            .child(folder),
                    ),
            )
            .child(shortcut("compile-keys", "B", keys).mr_2())
            .child(
                ButtonVariant::Primary
                    .apply(Button::new("compile"), palette)
                    .accessibility_label("컴파일")
                    .disabled(self.compiling)
                    .px_4()
                    .font_weight(FontWeight::MEDIUM)
                    .on_click(cx.listener(|this, _, window, cx| this.compile(&Compile, window, cx)))
                    .child(if self.compiling {
                        "컴파일 중…"
                    } else {
                        "컴파일"
                    }),
            )
    }

    fn render_outline(&self, cx: &Context<Self>) -> AnyElement {
        let tokens = self.tokens;
        let palette = self.palette();
        let cursor_line = self.editor.read(cx).cursor_position().line as usize;
        // The section containing the cursor is the last heading at or above it.
        let current = self
            .outline
            .iter()
            .rposition(|heading| heading.line <= cursor_line);
        // Indent relative to the document's top heading level.
        let top = self
            .outline
            .iter()
            .map(|heading| heading.level)
            .min()
            .unwrap_or(0);
        let headings = self.outline.iter().enumerate().map(|(index, heading)| {
            let line = heading.line;
            let depth = heading.level - top;
            let selected = current == Some(index);
            ButtonVariant::Ghost
                .apply(Button::new(("heading", index)), palette)
                .accessibility_label(heading.title.clone())
                .current(selected)
                .w_full()
                .h(px(30.))
                .flex_none()
                .pr_2()
                .pl(px(10. + 14. * depth as f32))
                .justify_start()
                .text_color(if selected {
                    tokens.accent
                } else if depth == 0 {
                    tokens.ink
                } else {
                    tokens.muted
                })
                .when(selected, |this| {
                    this.bg(palette.highlight).font_weight(FontWeight::MEDIUM)
                })
                .on_click(cx.listener(move |this, _, window, cx| this.jump_to(line, window, cx)))
                .child(div().truncate().child(heading.title.clone()))
        });
        let body = if self.outline.is_empty() {
            div()
                .p_3()
                .text_sm()
                .text_color(tokens.muted)
                .child("\\section을 쓰면 여기에 목차가 생깁니다.")
                .into_any_element()
        } else {
            div()
                .id("outline")
                .role(Role::Navigation)
                .aria_label("목차")
                .size_full()
                .p_1()
                .flex()
                .flex_col()
                .overflow_y_scroll()
                .children(headings)
                .into_any_element()
        };
        pane(tokens, "목차", None, body)
    }

    fn render_editor(&self, cx: &Context<Self>) -> AnyElement {
        let tokens = self.tokens;
        let position = self.editor.read(cx).cursor_position();
        let extra = div()
            .ml_auto()
            .text_xs()
            .text_color(tokens.muted)
            .child(format!(
                "{}줄 {}칸",
                position.line + 1,
                position.character + 1
            ))
            .into_any_element();
        let body = div()
            .size_full()
            .pr_2()
            .bg(tokens.surface)
            .font_family(EDITOR_FONT)
            .text_size(px(14.5))
            .child(self.editor.clone())
            .into_any_element();
        pane(tokens, "원고", Some(extra), body)
    }
}

impl Render for Workspace {
    fn render(&mut self, _: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        let tokens = self.tokens;
        let palette = self.palette();
        div()
            .id("workspace")
            .key_context("Workspace")
            .on_action(cx.listener(Self::open))
            .on_action(cx.listener(Self::save_action))
            .on_action(cx.listener(Self::save_as_action))
            .on_action(cx.listener(Self::compile))
            .on_action(cx.listener(|this, _: &ZoomIn, _, cx| {
                this.preview.update(cx, |preview, cx| preview.zoom_in(cx))
            }))
            .on_action(cx.listener(|this, _: &ZoomOut, _, cx| {
                this.preview.update(cx, |preview, cx| preview.zoom_out(cx))
            }))
            .on_action(cx.listener(|this, _: &ZoomToFit, _, cx| {
                this.preview
                    .update(cx, |preview, cx| preview.zoom_to_fit(cx))
            }))
            .size_full()
            .flex()
            .flex_col()
            .bg(tokens.canvas)
            .text_color(tokens.ink)
            .text_size(px(14.))
            .font_family(tokens.font)
            .child(self.render_toolbar(cx))
            .child(
                Resizable::new("panes", &self.panes)
                    .flex_1()
                    .min_h_0()
                    .p_2()
                    .panel(self.render_outline(cx))
                    .handle(move |index, handle| {
                        handle
                            .accessibility_label(if index == 0 {
                                "목차 너비"
                            } else {
                                "편집기와 미리보기 너비"
                            })
                            .w(px(8.))
                            .rounded_sm()
                            .hover(|style| style.bg(palette.highlight))
                            .focus_visible(|style| style.bg(palette.highlight))
                    })
                    .panel(self.render_editor(cx))
                    .panel(
                        tokens
                            .panel()
                            .size_full()
                            .overflow_hidden()
                            .child(self.preview.clone()),
                    ),
            )
            .child(self.render_discard_dialog(cx))
    }
}
