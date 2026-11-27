mod agent;
mod assistant;
mod compile;
mod document;
mod highlight;
mod latex;
mod pdf;
mod preview;
mod project;
// The installed preset and recipes carry optional pieces this app does not use.
#[allow(dead_code, unused_imports)]
mod ui;
mod workspace;

use gpui::{
    AppContext as _, KeyBinding, Styled as _, TitlebarOptions, WindowBounds, WindowOptions, px,
    size,
};
use gpui_deck::Root;

use workspace::{
    AskAgent, Compile, Open, OpenFolder, Save, SaveAs, Workspace, ZoomIn, ZoomOut, ZoomToFit,
};

/// A shortcut on the platform's primary modifier key.
macro_rules! key {
    ($keys:literal) => {
        if cfg!(target_os = "macos") {
            concat!("cmd-", $keys)
        } else {
            concat!("ctrl-", $keys)
        }
    };
}

fn main() {
    let path = std::env::args_os().nth(1).map(std::path::PathBuf::from);

    gpui_platform::application().run(move |cx| {
        gpui_deck::init(cx);
        ui::preset::register_fonts(cx);
        let tokens = ui::preset::selected().tokens(false);
        cx.bind_keys([
            KeyBinding::new(key!("o"), Open, None),
            KeyBinding::new(key!("shift-o"), OpenFolder, None),
            KeyBinding::new(key!("s"), Save, None),
            KeyBinding::new(key!("shift-s"), SaveAs, None),
            KeyBinding::new(key!("b"), Compile, None),
            KeyBinding::new(key!("k"), AskAgent, None),
            KeyBinding::new(key!("="), ZoomIn, None),
            KeyBinding::new(key!("-"), ZoomOut, None),
            KeyBinding::new(key!("0"), ZoomToFit, None),
        ]);
        cx.on_window_closed(|cx, _| {
            if cx.windows().is_empty() {
                cx.quit();
            }
        })
        .detach();
        cx.open_window(
            WindowOptions {
                titlebar: Some(TitlebarOptions {
                    title: Some("Paper Factory".into()),
                    ..Default::default()
                }),
                window_bounds: Some(WindowBounds::centered(size(px(1440.), px(900.)), cx)),
                ..WindowOptions::default()
            },
            |window, cx| {
                let workspace = cx.new(|cx| Workspace::new(path, tokens, window, cx));
                cx.new(|cx| Root::new(workspace, window, cx).font_family(tokens.font))
            },
        )
        .expect("failed to open the Paper Factory window");
        cx.activate(true);
    });
}
