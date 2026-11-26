use gpui::{Hsla, Styled as _, Svg, px, svg};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum IconSet {
    Lucide,
    Bootstrap,
}

#[derive(Clone, Copy, Debug)]
pub enum Icon {
    Activity,
    Bookmark,
}

impl IconSet {
    /// The upstream SVG path is rendered by GPUI and tinted by the caller.
    pub fn icon(self, icon: Icon, size: f32, color: Hsla) -> Svg {
        let data: &[u8] = match (self, icon) {
            (Self::Lucide, Icon::Activity) => include_bytes!("assets/lucide-activity.svg"),
            (Self::Lucide, Icon::Bookmark) => include_bytes!("assets/lucide-bookmark.svg"),
            (Self::Bootstrap, Icon::Activity) => include_bytes!("assets/bootstrap-activity.svg"),
            (Self::Bootstrap, Icon::Bookmark) => include_bytes!("assets/bootstrap-bookmark.svg"),
        };
        svg()
            .data(data)
            .size(px(size))
            .flex_shrink_0()
            .text_color(color)
    }
}
