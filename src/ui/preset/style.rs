use super::IconSet;
use gpui::{prelude::*, *};
use gpui_deck::{Button, Field, Input, InputEditorStyle, InputState, box_shadow, input::InputMode};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Style {
    Base,
    Neobrutal,
    Neumorphism,
}

#[derive(Clone, Copy)]
pub struct Preset {
    style: Style,
    // Each row is [canvas, input well, foreground, muted foreground, border].
    base: [[u32; 5]; 2],
    accent: [u32; 2],
    chart: [[u32; 2]; 2],
    heading: &'static str,
    font: &'static str,
    icons: IconSet,
    radius: Option<f32>,
}

fn family(value: &str) -> Option<&'static str> {
    Some(match value {
        "pretendard" => "Pretendard",
        "spectral" => "Spectral",
        "space-mono" => "Space Mono",
        _ => return None,
    })
}

impl Preset {
    pub fn parse(code: &str) -> Option<Self> {
        let mut parts = code.split('.');
        if parts.next()? != "v1" {
            return None;
        }
        let style = match parts.next()? {
            "base" => Style::Base,
            "neobrutal" => Style::Neobrutal,
            "neumorphism" => Style::Neumorphism,
            _ => return None,
        };
        let base = match parts.next()? {
            "neutral" => [
                [0xf5f5f5, 0xe9e9e9, 0x171717, 0x5e5e5e, 0xd4d4d4],
                [0x171717, 0x121212, 0xf5f5f5, 0xb3b3b3, 0x404040],
            ],
            "zinc" => [
                [0xf4f4f5, 0xe4e4e7, 0x18181b, 0x585862, 0xd4d4d8],
                [0x18181b, 0x101013, 0xf4f4f5, 0xb4b4bf, 0x414148],
            ],
            "stone" => [
                [0xf5f3ef, 0xe8e4df, 0x292524, 0x665d57, 0xd6d0c9],
                [0x24211f, 0x191614, 0xf5f2ef, 0xb9aea5, 0x4c4541],
            ],
            "sage" => [
                [0xe7eee9, 0xd8e3db, 0x1a2b24, 0x50665b, 0xc3d1c9],
                [0x121b17, 0x101713, 0xe9f5ee, 0x9aafa4, 0x394e43],
            ],
            "lavender" => [
                [0xebe9f4, 0xddd9e9, 0x252036, 0x625970, 0xcac4d7],
                [0x171520, 0x131119, 0xf1edff, 0xaaa0bd, 0x493e59],
            ],
            "clay" => [
                [0xefe8df, 0xe2d7cb, 0x35271f, 0x6a584d, 0xd0c1b3],
                [0x211814, 0x18120f, 0xf8eee6, 0xb8a093, 0x514039],
            ],
            "graphite" => [
                [0xe6e8eb, 0xd5d9de, 0x1d232b, 0x55606b, 0xc2c9d2],
                [0x111419, 0x0d1014, 0xedf1f6, 0x9fa9b6, 0x3b4653],
            ],
            _ => return None,
        };
        let accent = match parts.next()? {
            "neutral" => [0x262626, 0xe5e5e5],
            "blue" => [0x1d4ed8, 0x93c5fd],
            "green" => [0x166534, 0x86efac],
            "violet" => [0x6d28d9, 0xc4b5fd],
            "rose" => [0xbe123c, 0xfda4af],
            "sage" => [0x266651, 0x83cfad],
            _ => return None,
        };
        let chart = match parts.next()? {
            "neutral" => [[0x424242, 0x9b9b9b], [0xe5e5e5, 0x737373]],
            "ocean" => [[0x026c96, 0x66abc7], [0x6ac5eb, 0x357f9e]],
            "forest" => [[0x2f6646, 0x91ad61], [0x8bd6a6, 0x718c4c]],
            "sunset" => [[0xb34628, 0xeaa350], [0xff9c71, 0xa77847]],
            "violet" => [[0x7551ad, 0xba98d6], [0xc4a4ed, 0x9872b4]],
            _ => return None,
        };
        let heading = family(parts.next()?)?;
        let font = family(parts.next()?)?;
        let icons = match parts.next()? {
            "outline" => IconSet::Lucide,
            "solid" => IconSet::Bootstrap,
            _ => return None,
        };
        let radius = match parts.next()? {
            "default" => None,
            "none" => Some(0.),
            "small" => Some(4.),
            "large" => Some(22.),
            _ => return None,
        };
        parts.next().is_none().then_some(Self {
            style,
            base,
            accent,
            chart,
            heading,
            font,
            icons,
            radius,
        })
    }

    pub fn tokens(self, dark: bool) -> Tokens {
        let mode = usize::from(dark);
        let [canvas, field, ink, muted, border] = self.base[mode].map(|v| Hsla::from(rgb(v)));
        let overlay = if dark {
            white().opacity(0.055)
        } else {
            white().opacity(0.9)
        };
        let surface = if self.style == Style::Neumorphism {
            canvas
        } else {
            canvas.to_rgb().blend(overlay.to_rgb()).into()
        };
        Tokens {
            style: self.style,
            dark,
            canvas,
            surface,
            field,
            ink,
            muted,
            border,
            accent: rgb(self.accent[mode]).into(),
            on_accent: if dark { rgb(0x101010).into() } else { white() },
            chart: self.chart[mode].map(|v| rgb(v).into()),
            heading: self.heading,
            font: self.font,
            icons: self.icons,
            radius: px(self.radius.unwrap_or(match self.style {
                Style::Base => 10.,
                Style::Neobrutal => 2.,
                Style::Neumorphism => 16.,
            })),
        }
    }
}

/// Resolved app-owned colors, geometry and typography for this appearance.
#[derive(Clone, Copy)]
pub struct Tokens {
    pub style: Style,
    pub dark: bool,
    pub canvas: Hsla,
    pub surface: Hsla,
    pub field: Hsla,
    pub ink: Hsla,
    pub muted: Hsla,
    pub border: Hsla,
    pub accent: Hsla,
    pub on_accent: Hsla,
    pub chart: [Hsla; 2],
    pub heading: &'static str,
    pub font: &'static str,
    pub icons: IconSet,
    pub radius: Pixels,
}

impl Tokens {
    /// Feed the same surface, focus, accent and geometry into installed Deck recipes.
    pub(crate) fn palette(self) -> super::super::Palette {
        super::super::Palette {
            canvas: self.canvas,
            surface: self.surface,
            field: self.field,
            foreground: self.ink,
            muted: self.muted,
            border: self.border,
            accent: self.accent,
            accent_foreground: self.on_accent,
            highlight: self.accent.opacity(0.16),
            radius: self.radius,
            error: rgb(if self.dark { 0xfda4af } else { 0xb91c1c }).into(),
            ..super::super::Appearance::Settings.palette()
        }
    }

    fn shadow(self, inset: bool) -> Vec<BoxShadow> {
        match self.style {
            Style::Base => Vec::new(),
            Style::Neobrutal if inset => Vec::new(),
            Style::Neobrutal => vec![box_shadow(4., 4., 0., 0., self.ink)],
            Style::Neumorphism => {
                let light = white().opacity(if self.dark { 0.08 } else { 0.92 });
                let shade = if self.dark {
                    black().opacity(0.6)
                } else {
                    self.ink.opacity(0.18)
                };
                let distance = if inset { 2. } else { 5. };
                let blur = if inset { 5. } else { 12. };
                vec![
                    BoxShadow {
                        inset,
                        ..box_shadow(distance, distance, blur, 0., shade)
                    },
                    BoxShadow {
                        inset,
                        ..box_shadow(-distance, -distance, blur, 0., light)
                    },
                ]
            }
        }
    }

    pub fn panel(self) -> Div {
        div()
            .rounded(self.radius)
            .bg(self.surface)
            .text_color(self.ink)
            .font_family(self.font)
            .when(self.style == Style::Base, |v| {
                v.border_1().border_color(self.border)
            })
            .when(self.style == Style::Neobrutal, |v| {
                v.border_2().border_color(self.ink)
            })
            .shadow(self.shadow(false))
    }

    /// Accent action with Deck keyboard, focus, disabled and pointer behavior.
    pub fn button(self, id: impl Into<ElementId>, label: impl Into<SharedString>) -> Button {
        let label = label.into();
        Button::new(id)
            .accessibility_label(label.clone())
            .flex()
            .items_center()
            .justify_center()
            .gap_2()
            .min_h(px(38.))
            .px_4()
            .rounded(self.radius)
            .bg(self.accent)
            .text_color(self.on_accent)
            .font_family(self.font)
            .font_weight(FontWeight::SEMIBOLD)
            .when(self.style == Style::Neobrutal, |v| {
                v.border_2().border_color(self.ink)
            })
            .shadow(self.shadow(false))
            .cursor_pointer()
            .hover(|s| s.opacity(0.9))
            .active(|s| s.shadow_none().opacity(0.84))
            .focus_visible(|s| s.underline().border_2().border_color(self.on_accent))
            .styles(|s| s.disabled(|s| s.opacity(0.5).shadow_none()))
            .child(label)
    }

    pub fn editor_style(self) -> InputEditorStyle {
        InputEditorStyle {
            foreground: self.ink,
            muted_foreground: self.muted,
            caret: self.accent,
            selection: self.accent.opacity(0.25),
            ..Default::default()
        }
    }

    pub fn field(
        self,
        id: &'static str,
        label: &'static str,
        input: &Entity<InputState>,
        window: &Window,
        cx: &App,
    ) -> Field<InputMode> {
        let focus = input.focus_handle(cx);
        let border = if focus.is_focused(window) {
            self.accent
        } else if self.style == Style::Neobrutal {
            self.ink
        } else {
            self.border
        };
        Field::new(id, input, label)
            .flex()
            .flex_col()
            .gap_2()
            .w_full()
            .min_w_0()
            .text_color(self.ink)
            .font_family(self.font)
            .styles(|s| s.label(|s| s.font_weight(FontWeight::MEDIUM).text_size(px(13.))))
            .child(
                div()
                    .w_full()
                    .min_w_0()
                    .h(px(40.))
                    .px_3()
                    .flex()
                    .items_center()
                    .rounded(self.radius)
                    .bg(self.field)
                    .border_1()
                    .when(self.style == Style::Neobrutal, |v| v.border_2())
                    .border_color(border)
                    .shadow(self.shadow(true))
                    .on_mouse_down(MouseButton::Left, move |_, window, cx| {
                        focus.focus(window, cx)
                    })
                    .child(div().min_w_0().flex_1().child(Input::new(input))),
            )
    }
}
