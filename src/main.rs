mod compile;
mod document;
mod highlight;
mod latex;
mod pdf;
mod preview;
// The installed preset and recipes carry optional pieces this app does not use.
#[allow(dead_code, unused_imports)]
mod ui;
mod workspace;

use gpui::{
    AppContext as _, KeyBinding, Styled as _, TitlebarOptions, WindowBounds, WindowOptions, px,
    size,
};
use gpui_deck::Root;

use workspace::{Compile, Open, Save, SaveAs, Workspace, ZoomIn, ZoomOut, ZoomToFit};

#[cfg(target_os = "macos")]
const SHORTCUTS: [&str; 7] = [
    "cmd-o",
    "cmd-s",
    "cmd-shift-s",
    "cmd-b",
    "cmd-=",
    "cmd--",
    "cmd-0",
];
#[cfg(not(target_os = "macos"))]
const SHORTCUTS: [&str; 7] = [
    "ctrl-o",
    "ctrl-s",
    "ctrl-shift-s",
    "ctrl-b",
    "ctrl-=",
    "ctrl--",
    "ctrl-0",
];

fn main() {
    let path = std::env::args_os().nth(1).map(std::path::PathBuf::from);

    gpui_platform::application().run(move |cx| {
        gpui_deck::init(cx);
        ui::preset::register_fonts(cx);
        let tokens = ui::preset::selected().tokens(false);
        let [open, save, save_as, compile, zoom_in, zoom_out, zoom_fit] = SHORTCUTS;
        cx.bind_keys([
            KeyBinding::new(open, Open, None),
            KeyBinding::new(save, Save, None),
            KeyBinding::new(save_as, SaveAs, None),
            KeyBinding::new(compile, Compile, None),
            KeyBinding::new(zoom_in, ZoomIn, None),
            KeyBinding::new(zoom_out, ZoomOut, None),
            KeyBinding::new(zoom_fit, ZoomToFit, None),
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
