mod document;
mod workspace;

use gpui::{AppContext as _, KeyBinding, TitlebarOptions, WindowBounds, WindowOptions, px, size};
use gpui_deck::Root;

use workspace::{Open, Save, SaveAs, Workspace};

#[cfg(target_os = "macos")]
const SHORTCUTS: [&str; 3] = ["cmd-o", "cmd-s", "cmd-shift-s"];
#[cfg(not(target_os = "macos"))]
const SHORTCUTS: [&str; 3] = ["ctrl-o", "ctrl-s", "ctrl-shift-s"];

fn main() {
    let path = std::env::args_os().nth(1).map(std::path::PathBuf::from);

    gpui_platform::application().run(move |cx| {
        gpui_deck::init(cx);
        let [open, save, save_as] = SHORTCUTS;
        cx.bind_keys([
            KeyBinding::new(open, Open, None),
            KeyBinding::new(save, Save, None),
            KeyBinding::new(save_as, SaveAs, None),
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
                window_bounds: Some(WindowBounds::centered(size(px(960.), px(720.)), cx)),
                ..WindowOptions::default()
            },
            |window, cx| {
                let workspace = cx.new(|cx| Workspace::new(path, window, cx));
                cx.new(|cx| Root::new(workspace, window, cx))
            },
        )
        .expect("failed to open the Paper Factory window");
        cx.activate(true);
    });
}
