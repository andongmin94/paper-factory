//! Connects the LaTeX token scan to GPUI Deck's editor highlighting seam.

use std::{ops::Range, rc::Rc, sync::Arc};

use gpui::{Context, FontStyle, HighlightStyle, SharedString, Window, rgb};
use gpui_deck::input::{
    EditorState, FoldRange, HighlightStyleResolver, InputEdit, InputHighlighter,
    InputHighlighterFactory, Rope, SharedHighlightStyleResolver,
};

use crate::latex::{self, TokenKind};

pub const LANGUAGE: &str = "latex";

/// Creates a LaTeX highlighter for the editor's language.
pub fn factory() -> InputHighlighterFactory {
    Rc::new(|language: &str| {
        (language == LANGUAGE)
            .then(|| Box::new(LatexHighlighter::default()) as Box<dyn InputHighlighter>)
    })
}

/// Colors for the token names [`TokenKind::name`] produces.
pub fn styles() -> SharedHighlightStyleResolver {
    Arc::new(LatexStyles)
}

struct LatexStyles;

impl HighlightStyleResolver for LatexStyles {
    fn style(&self, name: &str) -> Option<HighlightStyle> {
        let color = |hex: u32| HighlightStyle {
            color: Some(rgb(hex).into()),
            ..Default::default()
        };
        match name {
            "comment" => Some(HighlightStyle {
                font_style: Some(FontStyle::Italic),
                ..color(0x6e7781)
            }),
            "command" => Some(color(0x0550ae)),
            "keyword" => Some(color(0xcf222e)),
            "environment" => Some(color(0x8250df)),
            "math" => Some(color(0x116329)),
            _ => None,
        }
    }
}

#[derive(Default)]
struct LatexHighlighter {
    tokens: Vec<(Range<usize>, TokenKind)>,
}

impl InputHighlighter for LatexHighlighter {
    fn language(&self) -> SharedString {
        LANGUAGE.into()
    }

    fn update(
        &mut self,
        _: Option<InputEdit>,
        text: &Rope,
        _: bool,
        _: &mut Window,
        _: &mut Context<EditorState>,
    ) {
        // A manuscript rescans in well under a frame, so every edit rescans it whole.
        self.tokens = latex::tokens(&text.to_string());
    }

    fn styles(
        &self,
        range: &Range<usize>,
        resolver: &dyn HighlightStyleResolver,
    ) -> Vec<(Range<usize>, HighlightStyle)> {
        let mut runs = Vec::new();
        let mut cursor = range.start;
        let first = self
            .tokens
            .partition_point(|(span, _)| span.end <= range.start);
        for (span, kind) in &self.tokens[first..] {
            if span.start >= range.end {
                break;
            }
            let start = span.start.max(range.start);
            let end = span.end.min(range.end);
            if cursor < start {
                runs.push((cursor..start, HighlightStyle::default()));
            }
            runs.push((start..end, resolver.style(kind.name()).unwrap_or_default()));
            cursor = end;
        }
        if cursor < range.end {
            runs.push((cursor..range.end, HighlightStyle::default()));
        }
        runs
    }

    fn fold_ranges(&self, _: &Rope) -> Vec<FoldRange> {
        Vec::new()
    }
}
