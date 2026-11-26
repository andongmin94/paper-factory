//! Static application-owned keycaps and shortcut combinations.

use gpui::{
    App, Div, ElementId, InteractiveElement as _, IntoElement, ParentElement as _, RenderOnce,
    Role, SharedString, Stateful, StatefulInteractiveElement as _, StyleRefinement, Styled, Window,
    div, relative, rems,
};
use gpui_deck::{ObservedElement, TestSupportExt as _};

use super::super::Palette;

/// A static key label, not an interactive key or a registered shortcut.
///
/// Text is also the default accessible name. Give symbolic keys a readable name
/// with `accessibility_label`, such as `Arrow up` for `↑`. The application owns
/// platform-specific wording and the actual key binding.
#[derive(IntoElement)]
pub(crate) struct Kbd {
    base: ObservedElement<Stateful<Div>>,
    text: SharedString,
    label: SharedString,
}

impl Kbd {
    pub(crate) fn new(
        id: impl Into<ElementId>,
        text: impl Into<SharedString>,
        palette: Palette,
    ) -> Self {
        let text = text.into();
        Self {
            base: div()
                .id(id)
                .test_support()
                .flex()
                .flex_shrink_0()
                .items_center()
                .justify_center()
                .min_w(rems(1.25))
                .px_1()
                .py_1()
                .border_1()
                .border_b_2()
                .border_color(palette.border)
                .rounded(palette.radius)
                .bg(palette.field)
                .text_color(palette.foreground)
                .text_size(palette.font_size)
                .line_height(relative(1.)),
            label: text.clone(),
            text,
        }
    }

    pub(crate) fn accessibility_label(mut self, label: impl Into<SharedString>) -> Self {
        self.label = label.into();
        self
    }
}

impl Styled for Kbd {
    fn style(&mut self) -> &mut StyleRefinement {
        self.base.style()
    }
}

impl RenderOnce for Kbd {
    fn render(self, _: &mut Window, _: &mut App) -> impl IntoElement {
        self.base
            .role(Role::Label)
            .aria_label(self.label)
            .child(self.text)
    }
}

/// A shortcut combination displayed in caller-supplied order, joined by `+`.
///
/// The group has no accessible name of its own; each key retains its readable
/// label. Use separate Kbd elements in ordinary application layout when showing
/// alternative keys instead of a simultaneous combination.
#[derive(IntoElement)]
pub(crate) struct KbdGroup {
    base: ObservedElement<Stateful<Div>>,
    keys: Vec<Kbd>,
}

impl KbdGroup {
    pub(crate) fn new(id: impl Into<ElementId>, palette: Palette) -> Self {
        Self {
            base: div()
                .id(id)
                .test_support()
                .flex()
                .flex_shrink_0()
                .items_center()
                .gap_1()
                .text_color(palette.muted)
                .text_size(palette.font_size),
            keys: Vec::new(),
        }
    }

    pub(crate) fn key(mut self, key: Kbd) -> Self {
        self.keys.push(key);
        self
    }
}

impl Styled for KbdGroup {
    fn style(&mut self) -> &mut StyleRefinement {
        self.base.style()
    }
}

impl RenderOnce for KbdGroup {
    fn render(self, _: &mut Window, _: &mut App) -> impl IntoElement {
        let mut group = self.base.role(Role::Group);
        for (index, key) in self.keys.into_iter().enumerate() {
            if index > 0 {
                group = group.child("+");
            }
            group = group.child(key);
        }
        group
    }
}
