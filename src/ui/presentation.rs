//! Copyable application-owned colors, typography and sizing for the recipes.
//! Copy this module with the recipe sources, then customize its token values.

use gpui::{Hsla, Pixels, Rems, px, rems, rgb};

#[derive(Clone, Copy, Debug)]
pub(crate) enum Appearance {
    Compact,
    Settings,
}

// These tokens belong to this consumer, not the primitive library.
#[derive(Clone, Copy)]
pub(crate) struct Palette {
    pub(crate) canvas: Hsla,
    pub(crate) surface: Hsla,
    pub(crate) field: Hsla,
    pub(crate) foreground: Hsla,
    pub(crate) muted: Hsla,
    pub(crate) border: Hsla,
    pub(crate) accent: Hsla,
    pub(crate) accent_foreground: Hsla,
    pub(crate) highlight: Hsla,
    pub(crate) error: Hsla,
    pub(crate) padding: Rems,
    pub(crate) gap: Rems,
    pub(crate) control_height: Rems,
    pub(crate) font_size: Rems,
    pub(crate) code_font_family: &'static str,
    pub(crate) radius: Pixels,
    pub(crate) dialog_width: Rems,
}

impl Appearance {
    pub(crate) fn palette(self) -> Palette {
        // The consumer chooses the code font for its supported desktop targets.
        let code_font_family = if cfg!(target_os = "macos") {
            "Menlo"
        } else if cfg!(target_os = "windows") {
            "Consolas"
        } else {
            "DejaVu Sans Mono"
        };
        match self {
            Self::Compact => Palette {
                canvas: rgb(0x10141c).into(),
                surface: rgb(0x1a2130).into(),
                field: rgb(0x121a28).into(),
                foreground: rgb(0xf1f5f9).into(),
                muted: rgb(0xa9b6c8).into(),
                border: rgb(0x445269).into(),
                accent: rgb(0x93c5fd).into(),
                accent_foreground: rgb(0x10223d).into(),
                highlight: rgb(0x2b4160).into(),
                error: rgb(0xfca5a5).into(),
                padding: rems(1.),
                gap: rems(0.75),
                control_height: rems(1.875),
                font_size: rems(0.8125),
                code_font_family,
                radius: px(4.),
                dialog_width: rems(22.),
            },
            Self::Settings => Palette {
                canvas: rgb(0xf3f2ee).into(),
                surface: rgb(0xffffff).into(),
                field: rgb(0xfafaf8).into(),
                foreground: rgb(0x243328).into(),
                muted: rgb(0x606c63).into(),
                border: rgb(0xa6b2a7).into(),
                accent: rgb(0x286447).into(),
                accent_foreground: rgb(0xffffff).into(),
                highlight: rgb(0xe1eee3).into(),
                error: rgb(0xb42318).into(),
                padding: rems(1.75),
                gap: rems(1.25),
                control_height: rems(2.625),
                font_size: rems(0.9375),
                code_font_family,
                radius: px(10.),
                dialog_width: rems(28.),
            },
        }
    }
}
