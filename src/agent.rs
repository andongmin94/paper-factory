//! Runs the user's own Claude Code CLI in headless mode for proposals and reviews.
//!
//! The app never handles credentials: Claude Code uses whatever login the user
//! already set up. Agents only get read-only tools, so every change comes back
//! as a proposal the author accepts or rejects in the editor.

use std::{
    env,
    io::Write as _,
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::{
        Arc, Mutex,
        atomic::{AtomicBool, Ordering},
    },
};

use anyhow::{Context as _, Result, bail};
use serde::Deserialize;

#[cfg(windows)]
const CLAUDE: &str = "claude.exe";
#[cfg(not(windows))]
const CLAUDE: &str = "claude";

/// Read-only built-in tools. Edit, Write and command tools are not offered.
const READ_TOOLS: &str = "Read,Glob,Grep";

const REVISED_OPEN: &str = "<<<REVISED";
const REVISED_CLOSE: &str = "REVISED>>>";

/// Finds Claude Code on `PATH`, then in its default `~/.local/bin` install.
pub fn find_claude() -> Option<PathBuf> {
    let on_path = env::var_os("PATH")
        .into_iter()
        .flat_map(|paths| env::split_paths(&paths).collect::<Vec<_>>());
    let local = env::home_dir().map(|home| home.join(".local").join("bin"));
    on_path
        .chain(local)
        .map(|dir| dir.join(CLAUDE))
        .find(|candidate| candidate.is_file())
}

/// Whether the Think Tank skill is installed for Claude Code.
pub fn think_tank_installed() -> bool {
    env::home_dir().is_some_and(|home| home.join(".claude/skills/think-tank/SKILL.md").is_file())
}

/// A running agent process that the app can stop.
#[derive(Clone, Default)]
pub struct Cancel {
    child: Arc<Mutex<Option<Child>>>,
    cancelled: Arc<AtomicBool>,
}

impl Cancel {
    pub fn cancel(&self) {
        self.cancelled.store(true, Ordering::SeqCst);
        if let Some(child) = self.child.lock().unwrap().as_mut() {
            let _ = child.kill();
        }
    }
}

/// What to revise and how.
pub struct Revision<'a> {
    /// Manuscript file, relative to the project folder.
    pub file: &'a Path,
    pub instruction: &'a str,
    /// The text to revise: the selection, or the whole file.
    pub original: &'a str,
    pub is_selection: bool,
}

/// Asks Claude Code for a revised version of `revision.original`.
pub fn revise(
    claude: &Path,
    project: &Path,
    revision: &Revision,
    cancel: &Cancel,
) -> Result<String> {
    let scope = if revision.is_selection {
        "the selected passage below"
    } else {
        "the entire file below"
    };
    let prompt = format!(
        "You are helping an author edit the LaTeX manuscript `{file}` in the current folder.\n\
         Author's instruction: {instruction}\n\n\
         Revise only {scope}. You may read other files in this folder for context, but do not \
         modify any file. Keep LaTeX commands, labels and citations intact unless the \
         instruction asks otherwise, and keep the author's language.\n\
         Reply with the complete revised text only, between a line `{REVISED_OPEN}` and a line \
         `{REVISED_CLOSE}`, with nothing else.\n\n<<<ORIGINAL\n{original}\nORIGINAL>>>\n",
        file = revision.file.display(),
        instruction = revision.instruction,
        original = revision.original,
    );
    let reply = run(claude, project, &prompt, READ_TOOLS, cancel)?;
    extract_revision(&reply, revision.original)
}

/// Asks Claude Code to review the manuscript with the Think Tank skill.
pub fn review(claude: &Path, project: &Path, file: &Path, cancel: &Cancel) -> Result<String> {
    let prompt = format!(
        "/think-tank Review the manuscript `{file}` in the current folder, following the skill's \
         review path. Read the manuscript and the files it includes. Do not modify, create or \
         export any file. Write the review in Korean as plain text: the main findings first, \
         then concrete revision suggestions with line or section references.",
        file = file.display(),
    );
    run(claude, project, &prompt, "Read,Glob,Grep,Skill", cancel)
}

#[derive(Deserialize)]
struct Output {
    result: Option<String>,
    #[serde(default)]
    is_error: bool,
}

fn run(
    claude: &Path,
    project: &Path,
    prompt: &str,
    tools: &str,
    cancel: &Cancel,
) -> Result<String> {
    let mut command = Command::new(claude);
    command
        .args(["-p", "--output-format", "json", "--no-session-persistence"])
        .args(["--tools", tools, "--allowedTools", tools])
        .current_dir(project)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt as _;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        command.creation_flags(CREATE_NO_WINDOW);
    }
    let mut child = command
        .spawn()
        .with_context(|| format!("{}을(를) 실행하지 못했습니다", claude.display()))?;
    // The prompt goes through stdin so long passages are not limited by the command line.
    let mut stdin = child
        .stdin
        .take()
        .context("Claude Code 입력을 열지 못했습니다")?;
    let stdout = child
        .stdout
        .take()
        .context("Claude Code 출력을 열지 못했습니다")?;
    let stderr = child
        .stderr
        .take()
        .context("Claude Code 오류 출력을 열지 못했습니다")?;
    *cancel.child.lock().unwrap() = Some(child);
    stdin.write_all(prompt.as_bytes())?;
    drop(stdin);
    let reader = std::thread::spawn(move || std::io::read_to_string(stderr).unwrap_or_default());
    let stdout = std::io::read_to_string(stdout)?;
    let stderr = reader.join().unwrap_or_default();
    let status = cancel
        .child
        .lock()
        .unwrap()
        .take()
        .context("Claude Code 프로세스를 잃었습니다")?
        .wait()?;
    if cancel.cancelled.load(Ordering::SeqCst) {
        bail!("작업을 취소했습니다");
    }
    let output: Option<Output> = serde_json::from_str(stdout.trim()).ok();
    match output {
        Some(Output {
            result: Some(result),
            is_error: false,
        }) if status.success() => Ok(result),
        Some(Output {
            result: Some(result),
            ..
        }) => bail!("Claude Code가 실패했습니다: {result}"),
        _ => bail!(
            "Claude Code가 실패했습니다: {}",
            if stderr.trim().is_empty() {
                stdout.trim()
            } else {
                stderr.trim()
            }
        ),
    }
}

/// The text between the revision markers, keeping the original's trailing newline.
fn extract_revision(reply: &str, original: &str) -> Result<String> {
    let start = reply
        .find(REVISED_OPEN)
        .context("Claude Code 답에 수정본이 없습니다")?;
    let body = &reply[start + REVISED_OPEN.len()..];
    let end = body
        .rfind(REVISED_CLOSE)
        .context("Claude Code 답의 수정본이 끝나지 않았습니다")?;
    let body = &body[..end];
    let body = body
        .strip_prefix("\r\n")
        .or_else(|| body.strip_prefix('\n'))
        .unwrap_or(body);
    // Models often add blank lines before the closing marker; the original's
    // own line endings decide how the passage ends.
    let mut revised = body.trim_end_matches(['\n', '\r']).to_owned();
    revised.push_str(&original[original.trim_end_matches(['\n', '\r']).len()..]);
    Ok(revised)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn extracts_the_revision_between_markers() {
        let reply = "Sure.\n<<<REVISED\n\\section{서론}\n새 문장.\nREVISED>>>\n";
        assert_eq!(
            extract_revision(reply, "\\section{서론}\n옛 문장.\n").unwrap(),
            "\\section{서론}\n새 문장.\n"
        );
        assert_eq!(
            extract_revision("<<<REVISED\n짧게\nREVISED>>>", "길게").unwrap(),
            "짧게"
        );
        assert!(extract_revision("no markers", "x").is_err());
        // A blank line before the closing marker is not part of the passage.
        assert_eq!(
            extract_revision(
                "<<<REVISED
새 문장.

REVISED>>>",
                "옛 문장.
"
            )
            .unwrap(),
            "새 문장.
"
        );
    }
}
