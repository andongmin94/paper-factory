//! Application-owned Create preset. Copy or edit these sources with your app.
mod icons;
mod selected;
mod showcase;
mod style;

pub use icons::{Icon, IconSet};
pub use showcase::Showcase;
pub use style::{Preset, Style, Tokens};

/// The configuration selected when this module was installed.
pub fn selected() -> Preset {
    Preset::parse(selected::CODE).expect("valid installed GPUI Deck preset")
}

/// Register the faces used by Create. Keep existing registrations such as the
/// documentation preview's four Pretendard weights.
pub fn register_fonts(cx: &gpui::App) {
    use std::borrow::Cow;
    let text = cx.text_system();
    let available = text.all_font_names();
    let faces: [(&str, &'static [u8]); 3] = [
        (
            "Pretendard",
            include_bytes!("assets/Pretendard-Regular.otf"),
        ),
        ("Spectral", include_bytes!("assets/Spectral-Regular.ttf")),
        ("Space Mono", include_bytes!("assets/SpaceMono-Regular.ttf")),
    ];
    let missing: Vec<_> = faces
        .into_iter()
        .filter(|(family, _)| !available.iter().any(|name| name == family))
        .map(|(_, data)| Cow::Borrowed(data))
        .collect();
    if !missing.is_empty() {
        text.add_fonts(missing).expect("register Create fonts");
    }
}

/// Open the installed preset's interactive sample in a GPUI Deck root.
pub fn showcase(dark: bool, window: &mut gpui::Window, cx: &mut gpui::App) -> gpui::AnyView {
    use gpui::AppContext as _;
    register_fonts(cx);
    cx.new(|cx| Showcase::new(selected(), dark, window, cx))
        .into()
}
