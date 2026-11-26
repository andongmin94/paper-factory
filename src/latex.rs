//! LaTeX source analysis: highlight tokens and the section outline.
//!
//! This is a lexical scan, not a TeX parser. It recognizes what a manuscript
//! author needs to see at a glance: commands, sectioning, environments, math,
//! and comments.

use std::ops::Range;

/// The kind of a highlighted span. Its name is what the style resolver sees.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum TokenKind {
    Comment,
    Command,
    /// `\section`, `\begin`, `\documentclass` and other structural commands.
    Keyword,
    /// The name inside `\begin{...}` / `\end{...}`.
    Environment,
    Math,
}

impl TokenKind {
    pub fn name(self) -> &'static str {
        match self {
            TokenKind::Comment => "comment",
            TokenKind::Command => "command",
            TokenKind::Keyword => "keyword",
            TokenKind::Environment => "environment",
            TokenKind::Math => "math",
        }
    }
}

const SECTIONS: [&str; 5] = ["part", "chapter", "section", "subsection", "subsubsection"];
const STRUCTURE: [&str; 8] = [
    "documentclass",
    "usepackage",
    "begin",
    "end",
    "title",
    "author",
    "maketitle",
    "paragraph",
];

/// Byte-offset spans of every highlighted token, in order and non-overlapping.
pub fn tokens(text: &str) -> Vec<(Range<usize>, TokenKind)> {
    let bytes = text.as_bytes();
    let mut tokens = Vec::new();
    let mut i = 0;
    while i < bytes.len() {
        match bytes[i] {
            b'%' => {
                let end = line_end(bytes, i);
                tokens.push((i..end, TokenKind::Comment));
                i = end;
            }
            b'$' => {
                let display = bytes.get(i + 1) == Some(&b'$');
                let open = if display { 2 } else { 1 };
                let end = find_math_end(bytes, i + open, display).unwrap_or(bytes.len());
                tokens.push((i..end, TokenKind::Math));
                i = end;
            }
            b'\\' => {
                let start = i;
                let name_end = command_end(bytes, i + 1);
                let name = &text[i + 1..name_end];
                i = name_end;
                match name {
                    "(" | "[" => {
                        let close = if name == "(" { "\\)" } else { "\\]" };
                        let end = text[i..].find(close).map_or(bytes.len(), |at| i + at + 2);
                        tokens.push((start..end, TokenKind::Math));
                        i = end;
                    }
                    "begin" | "end" => {
                        tokens.push((start..name_end, TokenKind::Keyword));
                        if let Some(group) = brace_group(text, i) {
                            tokens.push((group.start + 1..group.end - 1, TokenKind::Environment));
                            i = group.end;
                        }
                    }
                    _ if SECTIONS.contains(&name) || STRUCTURE.contains(&name) => {
                        tokens.push((start..name_end, TokenKind::Keyword));
                    }
                    _ => tokens.push((start..name_end, TokenKind::Command)),
                }
            }
            _ => i += 1,
        }
    }
    tokens
}

/// A sectioning command in the manuscript.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Heading {
    /// 0 for `\part` through 4 for `\subsubsection`.
    pub level: usize,
    pub title: String,
    /// 0-based line of the command.
    pub line: usize,
}

/// The manuscript's sectioning commands in document order, ignoring comments.
pub fn outline(text: &str) -> Vec<Heading> {
    let mut headings = Vec::new();
    for (line_index, line) in text.lines().enumerate() {
        let code = strip_comment(line);
        let mut rest = code;
        while let Some(at) = rest.find('\\') {
            let after = &rest[at + 1..];
            let name_len = after
                .bytes()
                .take_while(|b| b.is_ascii_alphabetic())
                .count();
            let name = &after[..name_len];
            let mut tail = after[name_len..].trim_start_matches('*');
            if let Some(level) = SECTIONS.iter().position(|section| *section == name) {
                // Skip an optional short title: \section[short]{long}.
                if tail.starts_with('[')
                    && let Some(close) = tail.find(']')
                {
                    tail = &tail[close + 1..];
                }
                let tail_offset = code.len() - tail.len();
                if let Some(group) = brace_group(code, tail_offset) {
                    let title = code[group.start + 1..group.end - 1].trim().to_owned();
                    headings.push(Heading {
                        level,
                        title,
                        line: line_index,
                    });
                }
            }
            rest = &after[name_len..];
        }
    }
    headings
}

fn strip_comment(line: &str) -> &str {
    let bytes = line.as_bytes();
    let mut i = 0;
    while i < bytes.len() {
        match bytes[i] {
            b'\\' => i += 2,
            b'%' => return &line[..i],
            _ => i += 1,
        }
    }
    line
}

fn line_end(bytes: &[u8], from: usize) -> usize {
    bytes[from..]
        .iter()
        .position(|b| *b == b'\n')
        .map_or(bytes.len(), |at| from + at)
}

/// The end of a command name starting at `from`, just after the backslash.
fn command_end(bytes: &[u8], from: usize) -> usize {
    let letters = bytes[from..]
        .iter()
        .take_while(|b| b.is_ascii_alphabetic())
        .count();
    if letters > 0 {
        let end = from + letters;
        // Starred forms such as \section* belong to the command.
        if bytes.get(end) == Some(&b'*') {
            end + 1
        } else {
            end
        }
    } else if from < bytes.len() {
        // A control symbol: one character, which may be multi-byte.
        from + utf8_len(bytes[from])
    } else {
        from
    }
}

fn utf8_len(first: u8) -> usize {
    match first {
        0xF0..=0xFF => 4,
        0xE0..=0xEF => 3,
        0xC0..=0xDF => 2,
        _ => 1,
    }
}

/// The end of inline (`$`) or display (`$$`) math, after its closing delimiter.
fn find_math_end(bytes: &[u8], from: usize, display: bool) -> Option<usize> {
    let mut i = from;
    while i < bytes.len() {
        match bytes[i] {
            b'\\' => i += 2,
            b'$' if !display => return Some(i + 1),
            b'$' if bytes.get(i + 1) == Some(&b'$') => return Some(i + 2),
            _ => i += 1,
        }
    }
    None
}

/// The `{...}` group starting at `from` after optional spaces, braces included.
fn brace_group(text: &str, from: usize) -> Option<Range<usize>> {
    let bytes = text.as_bytes();
    let start = from + bytes[from..].iter().take_while(|b| **b == b' ').count();
    if bytes.get(start) != Some(&b'{') {
        return None;
    }
    let mut depth = 0usize;
    let mut i = start;
    while i < bytes.len() {
        match bytes[i] {
            b'\\' => i += 1,
            b'{' => depth += 1,
            b'}' => {
                depth -= 1;
                if depth == 0 {
                    return Some(start..i + 1);
                }
            }
            b'\n' if i > start && bytes.get(i - 1) == Some(&b'\n') => return None,
            _ => {}
        }
        i += 1;
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    fn spans(text: &str) -> Vec<(&str, &'static str)> {
        tokens(text)
            .into_iter()
            .map(|(range, kind)| (&text[range], kind.name()))
            .collect()
    }

    #[test]
    fn highlights_commands_environments_math_and_comments() {
        let text =
            "\\section{서론} 값 $x^2$ \\emph{강조} % 메모\n\\begin{equation} \\[a\\] \\% 100";
        assert_eq!(
            spans(text),
            vec![
                ("\\section", "keyword"),
                ("$x^2$", "math"),
                ("\\emph", "command"),
                ("% 메모", "comment"),
                ("\\begin", "keyword"),
                ("equation", "environment"),
                ("\\[a\\]", "math"),
                ("\\%", "command"),
            ]
        );
    }

    #[test]
    fn display_math_and_unclosed_math_stay_in_bounds() {
        assert_eq!(spans("$$a+b$$ 끝"), vec![("$$a+b$$", "math")]);
        assert_eq!(spans("$열림"), vec![("$열림", "math")]);
        assert_eq!(spans("\\"), vec![("\\", "command")]);
    }

    #[test]
    fn outlines_sections_and_skips_comments() {
        let text = "\\section{서론}\n% \\section{숨김}\n\\subsection*[짧게]{방법 {상세}}\n본문 \\chapter {결론}";
        assert_eq!(
            outline(text),
            vec![
                Heading {
                    level: 2,
                    title: "서론".into(),
                    line: 0
                },
                Heading {
                    level: 3,
                    title: "방법 {상세}".into(),
                    line: 2
                },
                Heading {
                    level: 1,
                    title: "결론".into(),
                    line: 3
                },
            ]
        );
    }
}
