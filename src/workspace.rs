//! The manuscript window: one `.tex` file in a GPUI Deck editor.

use std::path::{Path, PathBuf};

use futures::channel::oneshot;
use gpui::{
    AppContext as _, Context, Entity, FocusHandle, InteractiveElement as _, IntoElement,
    ParentElement as _, PathPromptOptions, PromptLevel, Render, Role, SharedString,
    StatefulInteractiveElement as _, Styled as _, Subscription, Task, Window, actions, div, px,
    rgb,
};
use gpui_deck::{
    AlertDialog, Button, DialogBackdrop, DialogClose, DialogDescription, DialogEvent, DialogPopup,
    DialogState, DialogTitle, InputAccessibility, InputEditorStyle,
    input::{EditorState, InputEvent},
};

use crate::document::Document;

actions!(paper_factory, [Open, Save, SaveAs]);

#[cfg(target_os = "windows")]
const EDITOR_FONT: &str = "Consolas";
#[cfg(target_os = "macos")]
const EDITOR_FONT: &str = "Menlo";
#[cfg(not(any(target_os = "windows", target_os = "macos")))]
const EDITOR_FONT: &str = "DejaVu Sans Mono";

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
    _subscriptions: [Subscription; 3],
}

impl Workspace {
    pub fn new(path: Option<PathBuf>, window: &mut Window, cx: &mut Context<Self>) -> Self {
        let editor = cx.new(|cx| {
            let mut editor = EditorState::new(window, cx).soft_wrap(true);
            editor.set_editor_style(InputEditorStyle {
                foreground: rgb(0x1f2328).into(),
                muted_foreground: rgb(0x8c959f).into(),
                selection: rgb(0xb6d7ff).into(),
                caret: rgb(0x0969da).into(),
                editor_active_line: Some(rgb(0xf3f6fa).into()),
                ..Default::default()
            });
            editor.set_accessibility(
                InputAccessibility::new(Some(Role::MultilineTextInput))
                    .with_label(Some("원고".into())),
            );
            editor
        });
        let editor_events = cx.subscribe_in(&editor, window, |this, _, event, window, cx| {
            if matches!(event, InputEvent::Change) && !this.dirty {
                this.dirty = true;
                this.refresh_title(window);
                cx.notify();
            }
        });

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
            _subscriptions: [editor_events, dialog_observation, dialog_events],
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
                self.editor.update(cx, |editor, cx| {
                    editor.set_value(text, window, cx);
                    // A native file dialog leaves the window without a focused element.
                    editor.focus(window, cx);
                });
                self.document = document;
                self.dirty = false;
                self.refresh_title(window);
                cx.notify();
            }
            Err(error) => show_error(window, cx, "파일을 열지 못했습니다", &error),
        }
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
        let message = format!("{}의 변경 내용을 저장할까요?", self.document.display_name());
        let detail = "저장하지 않으면 변경 내용이 사라집니다.";
        let popup = DialogPopup::new()
            .w(px(420.))
            .p_5()
            .flex()
            .flex_col()
            .gap_3()
            .bg(rgb(0xffffff))
            .border_1()
            .border_color(rgb(0xd0d7de))
            .rounded_lg()
            .shadow_lg()
            .child(DialogTitle::new().text_lg().child(message.clone()))
            .child(
                DialogDescription::new()
                    .text_color(rgb(0x59636e))
                    .child(detail),
            )
            .child(
                div()
                    .flex()
                    .justify_end()
                    .gap_2()
                    .child(DialogClose::new(&self.discard_dialog).trigger(|button| {
                        dialog_button(button.track_focus(&self.discard_cancel_focus), "취소")
                    }))
                    .child(
                        dialog_button(Button::new("discard-changes"), "저장 안 함").on_click(
                            cx.listener(|this, _, window, cx| {
                                this.choose(Choice::Discard, window, cx)
                            }),
                        ),
                    )
                    .child(
                        dialog_button(Button::new("save-changes"), "저장")
                            .bg(rgb(0x0969da))
                            .text_color(rgb(0xffffff))
                            .hover(|style| style.bg(rgb(0x0860ca)))
                            .on_click(cx.listener(|this, _, window, cx| {
                                this.choose(Choice::Save, window, cx)
                            })),
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
                    .opacity(0.3),
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

fn toolbar_button(id: &'static str, label: &'static str) -> Button {
    Button::new(id)
        .accessibility_label(label)
        .h(px(30.))
        .px_3()
        .rounded_md()
        .border_1()
        .border_color(rgb(0xd0d7de))
        .bg(rgb(0xf6f8fa))
        .hover(|style| style.bg(rgb(0xeaeef2)))
        .focus_visible(|style| style.border_color(rgb(0x0969da)))
        .child(label)
}

fn dialog_button(button: Button, label: &'static str) -> Button {
    button
        .accessibility_label(label)
        .h(px(32.))
        .px_4()
        .rounded_md()
        .border_1()
        .border_color(rgb(0xd0d7de))
        .bg(rgb(0xf6f8fa))
        .hover(|style| style.bg(rgb(0xeaeef2)))
        .focus_visible(|style| style.border_color(rgb(0x0969da)).border_2())
        .child(label)
}

impl Render for Workspace {
    fn render(&mut self, _: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        let status: SharedString = match &self.document.path {
            Some(path) => path.display().to_string().into(),
            None => "저장되지 않은 새 원고".into(),
        };
        div()
            .id("workspace")
            .key_context("Workspace")
            .on_action(cx.listener(Self::open))
            .on_action(cx.listener(Self::save_action))
            .on_action(cx.listener(Self::save_as_action))
            .size_full()
            .flex()
            .flex_col()
            .bg(rgb(0xffffff))
            .text_color(rgb(0x1f2328))
            .text_size(px(14.))
            .child(
                div()
                    .flex()
                    .items_center()
                    .gap_2()
                    .px_3()
                    .py_2()
                    .border_b_1()
                    .border_color(rgb(0xd0d7de))
                    .child(
                        toolbar_button("open", "열기").on_click(
                            cx.listener(|this, _, window, cx| this.open(&Open, window, cx)),
                        ),
                    )
                    .child(toolbar_button("save", "저장").on_click(
                        cx.listener(|this, _, window, cx| this.save_action(&Save, window, cx)),
                    ))
                    .child(toolbar_button("save-as", "다른 이름으로 저장").on_click(
                        cx.listener(|this, _, window, cx| this.save_as_action(&SaveAs, window, cx)),
                    ))
                    .child(
                        div()
                            .id("document-status")
                            .role(Role::Label)
                            .aria_label(status.clone())
                            .ml_2()
                            .text_color(rgb(0x59636e))
                            .truncate()
                            .child(status),
                    ),
            )
            .child(
                div()
                    .flex_1()
                    .min_h_0()
                    .px_2()
                    .font_family(EDITOR_FONT)
                    .text_size(px(15.))
                    .child(self.editor.clone()),
            )
            .child(self.render_discard_dialog(cx))
    }
}
