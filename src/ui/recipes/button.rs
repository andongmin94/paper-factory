//! Application-owned appearances for an existing GPUI Deck Button.

use super::super::Palette;
use gpui::{InteractiveElement as _, Styled as _, transparent_black};
use gpui_deck::Button;

#[derive(Clone, Copy)]
#[allow(dead_code)] // An application can choose just the variants it needs.
pub(crate) enum ButtonVariant {
    Primary,
    Secondary,
    Outline,
    Ghost,
    Destructive,
    Link,
}

impl ButtonVariant {
    /// Preserve the button's identity, label, activation, focus and content.
    pub(crate) fn apply(self, button: Button, palette: Palette) -> Button {
        let button = button
            .h(palette.control_height)
            .px_3()
            .flex()
            .items_center()
            .justify_center()
            .rounded(palette.radius)
            .border_1()
            .border_color(transparent_black())
            .text_color(palette.foreground)
            .text_size(palette.font_size)
            .focus_visible(|style| style.border_color(palette.foreground))
            .styles(|styles| styles.disabled(|style| style.opacity(0.5)));
        match self {
            Self::Primary => button
                .bg(palette.accent)
                .text_color(palette.accent_foreground)
                .hover(|style| style.opacity(0.85)),
            Self::Secondary => button
                .bg(palette.highlight)
                .hover(|style| style.bg(palette.field)),
            Self::Outline => button
                .border_color(palette.border)
                .bg(palette.surface)
                .hover(|style| style.bg(palette.highlight)),
            Self::Ghost => button.hover(|style| style.bg(palette.highlight)),
            Self::Destructive => button
                .text_color(palette.error)
                .border_color(palette.error)
                .hover(|style| style.bg(palette.highlight)),
            Self::Link => button
                .text_color(palette.accent)
                .underline()
                .hover(|style| style.opacity(0.85)),
        }
    }
}
