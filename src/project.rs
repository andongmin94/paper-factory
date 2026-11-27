//! A manuscript folder: its source files, the main document and the files a
//! document pulls in with `\input`, `\include` or a bibliography command.

use std::{
    fs,
    path::{Path, PathBuf},
};

/// Extensions listed in the project's file list.
const SOURCE_EXTENSIONS: [&str; 4] = ["tex", "bib", "cls", "sty"];
/// Folders that never hold manuscript sources.
const SKIPPED_DIRS: [&str; 4] = ["target", "node_modules", "build", "out"];
const MAX_DEPTH: usize = 4;
const MAX_FILES: usize = 500;

/// Source files under `root`, relative to it, sorted with folders after files.
pub fn scan(root: &Path) -> Vec<PathBuf> {
    let mut files = Vec::new();
    collect(root, root, 0, &mut files);
    files.sort_by(|a, b| {
        (a.components().count(), a.as_os_str()).cmp(&(b.components().count(), b.as_os_str()))
    });
    files
}

fn collect(root: &Path, dir: &Path, depth: usize, files: &mut Vec<PathBuf>) {
    let Ok(entries) = fs::read_dir(dir) else {
        return;
    };
    let mut entries: Vec<_> = entries.flatten().collect();
    entries.sort_by_key(|entry| entry.file_name());
    for entry in entries {
        if files.len() >= MAX_FILES {
            return;
        }
        let path = entry.path();
        let name = entry.file_name();
        let name = name.to_string_lossy();
        if name.starts_with('.') {
            continue;
        }
        if path.is_dir() {
            if depth < MAX_DEPTH && !SKIPPED_DIRS.contains(&name.as_ref()) {
                collect(root, &path, depth + 1, files);
            }
        } else if path
            .extension()
            .and_then(|ext| ext.to_str())
            .is_some_and(|ext| SOURCE_EXTENSIONS.contains(&ext))
            && let Ok(relative) = path.strip_prefix(root)
        {
            files.push(relative.to_path_buf());
        }
    }
}

/// The project folder for `current`: the nearest of its folder and up to two
/// parents where a document compiles it, or its own folder.
pub fn find_root(current: &Path, text: &str) -> PathBuf {
    let own = current.parent().unwrap_or(current).to_path_buf();
    if is_document(text) || magic_root(text).is_some() {
        return own;
    }
    current
        .ancestors()
        .skip(1)
        .take(3)
        .find(|root| main_document(root, current, text, &scan(root)) != current)
        .map_or(own, Path::to_path_buf)
}

/// The document to compile when `current` (with `text`) is being edited.
///
/// A `% !TEX root = ...` comment wins; then the current file if it has a
/// `\documentclass`; then a project file that does, preferring one that pulls
/// in the current file, then `main.tex`.
pub fn main_document(root: &Path, current: &Path, text: &str, files: &[PathBuf]) -> PathBuf {
    if let Some(target) = magic_root(text) {
        let base = current.parent().unwrap_or(root);
        return base.join(with_tex_extension(&target));
    }
    if is_document(text) {
        return current.to_path_buf();
    }
    let candidates: Vec<(PathBuf, String)> = files
        .iter()
        .filter(|file| file.extension().is_some_and(|ext| ext == "tex"))
        .map(|file| root.join(file))
        .filter_map(|path| fs::read_to_string(&path).ok().map(|text| (path, text)))
        .filter(|(_, text)| is_document(text))
        .collect();
    let includes_current = |(path, text): &(PathBuf, String)| {
        let base = path.parent().unwrap_or(root);
        includes(text)
            .iter()
            .any(|include| same_file(&base.join(&include.target), current))
    };
    candidates
        .iter()
        .find(|candidate| includes_current(candidate))
        .or_else(|| {
            candidates
                .iter()
                .find(|(path, _)| path.file_name().is_some_and(|name| name == "main.tex"))
        })
        .or(candidates.first())
        .map_or_else(|| current.to_path_buf(), |(path, _)| path.clone())
}

fn same_file(a: &Path, b: &Path) -> bool {
    match (fs::canonicalize(a), fs::canonicalize(b)) {
        (Ok(a), Ok(b)) => a == b,
        _ => a == b,
    }
}

fn is_document(text: &str) -> bool {
    text.lines()
        .map(|line| line.split('%').next().unwrap_or(""))
        .any(|line| line.contains("\\documentclass"))
}

/// `% !TEX root = main.tex` in the first lines of a file.
fn magic_root(text: &str) -> Option<String> {
    text.lines().take(10).find_map(|line| {
        let rest = line.trim_start().strip_prefix('%')?.trim_start();
        let rest = rest.strip_prefix("!TEX")?.trim_start();
        let rest = rest
            .strip_prefix("root")
            .or_else(|| rest.strip_prefix("TS-program"))
            .filter(|_| rest.starts_with("root"))?;
        Some(rest.trim_start().strip_prefix('=')?.trim().to_owned())
    })
}

/// A file a document pulls in.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Include {
    /// 0-based line of the command.
    pub line: usize,
    /// Path relative to the including document, with its extension.
    pub target: PathBuf,
}

/// `\input`, `\include`, `\subfile`, `\bibliography` and `\addbibresource`
/// targets in document order, ignoring comments.
pub fn includes(text: &str) -> Vec<Include> {
    const COMMANDS: [(&str, &str); 5] = [
        ("input", "tex"),
        ("include", "tex"),
        ("subfile", "tex"),
        ("bibliography", "bib"),
        ("addbibresource", "bib"),
    ];
    let mut found = Vec::new();
    for (line_index, line) in text.lines().enumerate() {
        let code = line.split('%').next().unwrap_or("");
        let mut rest = code;
        while let Some(at) = rest.find('\\') {
            let after = &rest[at + 1..];
            let name_len = after.bytes().take_while(u8::is_ascii_alphabetic).count();
            let name = &after[..name_len];
            let tail = after[name_len..].trim_start();
            if let Some((_, extension)) = COMMANDS.iter().find(|(command, _)| *command == name)
                && let Some(body) = tail.strip_prefix('{')
                && let Some(close) = body.find('}')
            {
                // \bibliography{a,b} names several files.
                for target in body[..close]
                    .split(',')
                    .map(str::trim)
                    .filter(|t| !t.is_empty())
                {
                    let mut path = PathBuf::from(target);
                    if path.extension().is_none() {
                        path.set_extension(extension);
                    }
                    found.push(Include {
                        line: line_index,
                        target: path,
                    });
                }
            }
            rest = &after[name_len..];
        }
    }
    found
}

fn with_tex_extension(target: &str) -> PathBuf {
    let mut path = PathBuf::from(target);
    if path.extension().is_none() {
        path.set_extension("tex");
    }
    path
}

#[cfg(test)]
mod tests {
    use super::*;

    fn temp_project(name: &str, files: &[(&str, &str)]) -> PathBuf {
        let root = std::env::temp_dir().join(format!(
            "paper-factory-project-{name}-{}",
            std::process::id()
        ));
        let _ = fs::remove_dir_all(&root);
        for (path, text) in files {
            let path = root.join(path);
            fs::create_dir_all(path.parent().unwrap()).unwrap();
            fs::write(path, text).unwrap();
        }
        root
    }

    #[test]
    fn finds_includes_and_bibliographies() {
        let text = "\\input{chapters/intro}\n% \\include{hidden}\n\\include{b.tex} \\bibliography{refs, more}";
        assert_eq!(
            includes(text),
            vec![
                Include {
                    line: 0,
                    target: "chapters/intro.tex".into()
                },
                Include {
                    line: 2,
                    target: "b.tex".into()
                },
                Include {
                    line: 2,
                    target: "refs.bib".into()
                },
                Include {
                    line: 2,
                    target: "more.bib".into()
                },
            ]
        );
    }

    #[test]
    fn scans_sources_and_skips_hidden_and_build_folders() {
        let root = temp_project(
            "scan",
            &[
                ("main.tex", ""),
                ("refs.bib", ""),
                ("notes.txt", ""),
                ("chapters/intro.tex", ""),
                (".git/x.tex", ""),
                ("build/main.tex", ""),
            ],
        );
        assert_eq!(
            scan(&root),
            vec![
                PathBuf::from("main.tex"),
                PathBuf::from("refs.bib"),
                PathBuf::from("chapters").join("intro.tex"),
            ]
        );
    }

    #[test]
    fn picks_the_document_that_includes_the_current_chapter() {
        let root = temp_project(
            "main",
            &[
                ("other.tex", "\\documentclass{article}\n"),
                (
                    "paper.tex",
                    "\\documentclass{article}\n\\input{chapters/intro}\n",
                ),
                ("chapters/intro.tex", "\\section{Intro}\n"),
            ],
        );
        let files = scan(&root);
        let intro = root.join("chapters/intro.tex");
        assert_eq!(
            main_document(&root, &intro, "\\section{Intro}\n", &files),
            root.join("paper.tex")
        );
        assert_eq!(find_root(&intro, "\\section{Intro}\n"), root);
        // A document is its own main file.
        let other = root.join("other.tex");
        assert_eq!(
            main_document(&root, &other, "\\documentclass{article}", &files),
            other
        );
        // The magic comment wins.
        assert_eq!(
            main_document(&root, &intro, "% !TEX root = ../other.tex\n", &files),
            root.join("chapters").join("../other.tex")
        );
    }
}
