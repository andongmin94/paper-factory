//! Runs the Tectonic TeX engine on a saved manuscript.

use std::{
    env,
    path::{Path, PathBuf},
    process::Command,
};

use anyhow::{Context as _, Result};

#[cfg(windows)]
const ENGINE: &str = "tectonic.exe";
#[cfg(not(windows))]
const ENGINE: &str = "tectonic";

/// Finds Tectonic on `PATH`, then in `~/.local/tectonic`.
pub fn find_engine() -> Option<PathBuf> {
    let on_path = env::var_os("PATH")
        .into_iter()
        .flat_map(|paths| env::split_paths(&paths).collect::<Vec<_>>());
    let local = env::home_dir().map(|home| home.join(".local").join("tectonic"));
    on_path
        .chain(local)
        .map(|dir| dir.join(ENGINE))
        .find(|candidate| candidate.is_file())
}

/// The result of one engine run.
pub struct Outcome {
    /// The PDF beside the manuscript, when the engine produced one.
    pub pdf: Option<PathBuf>,
    /// The engine's combined output.
    pub log: String,
}

/// Compiles `tex` with `engine`, writing the PDF beside it. Blocks until done.
pub fn compile(engine: &Path, tex: &Path) -> Result<Outcome> {
    let directory = tex.parent().context("원고 파일의 폴더를 찾지 못했습니다")?;
    let mut command = Command::new(engine);
    command
        .args(["-X", "compile", "--keep-logs"])
        .arg(tex)
        .current_dir(directory);
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt as _;
        // Keep the engine's console window from flashing over the app.
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        command.creation_flags(CREATE_NO_WINDOW);
    }
    let output = command
        .output()
        .with_context(|| format!("{}을(를) 실행하지 못했습니다", engine.display()))?;
    let mut log = String::from_utf8_lossy(&output.stdout).into_owned();
    log.push_str(&String::from_utf8_lossy(&output.stderr));
    let pdf = tex.with_extension("pdf");
    Ok(Outcome {
        pdf: (output.status.success() && pdf.is_file()).then_some(pdf),
        log,
    })
}

/// One line of compiler output worth showing, with its manuscript line when known.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Problem {
    pub text: String,
    /// The source file and 0-based line, relative to the compiled document's folder.
    pub location: Option<(PathBuf, usize)>,
}

/// The engine's error lines, or the end of the log when it reported none.
pub fn problems(log: &str) -> Vec<Problem> {
    let errors: Vec<&str> = log
        .lines()
        .filter(|line| line.starts_with("error:") || line.starts_with('!'))
        .collect();
    let lines = if errors.is_empty() {
        let all: Vec<&str> = log.lines().collect();
        all[all.len().saturating_sub(20)..].to_vec()
    } else {
        errors
    };
    lines
        .into_iter()
        .map(|text| Problem {
            text: text.to_owned(),
            location: source_location(text),
        })
        .collect()
}

/// Reads `chapters/intro.tex:22:` from an engine message as that file's 0-based line 21.
/// Tectonic may omit the extension, as in `chapters/intro:22:`.
fn source_location(text: &str) -> Option<(PathBuf, usize)> {
    let message = text.strip_prefix("error:").unwrap_or(text).trim_start();
    let (path, rest) = message.split_once(':')?;
    if path.is_empty() || path.contains(char::is_whitespace) {
        return None;
    }
    let digits = rest.split(':').next()?;
    let line = digits.trim().parse::<usize>().ok()?.checked_sub(1)?;
    let mut path = PathBuf::from(path);
    if path.extension().is_none() {
        path.set_extension("tex");
    }
    Some((path, line))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn picks_error_lines_and_their_source_lines() {
        let log = "note: Running TeX ...\nerror: paper.tex:5: Undefined control sequence\nnote: done\nerror: halted";
        assert_eq!(
            problems(log),
            vec![
                Problem {
                    text: "error: paper.tex:5: Undefined control sequence".into(),
                    location: Some(("paper.tex".into(), 4)),
                },
                Problem {
                    text: "error: halted".into(),
                    location: None,
                },
            ]
        );
        assert_eq!(problems("a\nb").len(), 2);
        assert_eq!(
            problems("error: chapters/intro.tex:12: Missing $ inserted")[0].location,
            Some(("chapters/intro.tex".into(), 11))
        );
        assert_eq!(
            problems("error: chapters/method:3: Undefined control sequence")[0].location,
            Some(("chapters/method.tex".into(), 2))
        );
        assert_eq!(
            problems("error: something bad happened inside XeTeX")[0].location,
            None
        );
    }
}
