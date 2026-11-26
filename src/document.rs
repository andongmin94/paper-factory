//! A manuscript file on disk: reading, line endings, and safe saving.

use std::{
    fs,
    io::Write as _,
    path::{Path, PathBuf},
};

use anyhow::{Context as _, Result};

/// The file a manuscript was read from, and how to write it back.
#[derive(Clone, Debug, Default, PartialEq)]
pub struct Document {
    pub path: Option<PathBuf>,
    /// Whether the file on disk uses CRLF. The editor works on LF text.
    crlf: bool,
    /// Whether the file on disk starts with a UTF-8 byte order mark.
    bom: bool,
}

impl Document {
    /// Reads a UTF-8 file and returns its text with LF line endings.
    pub fn open(path: &Path) -> Result<(Self, String)> {
        let bytes =
            fs::read(path).with_context(|| format!("{}을(를) 읽지 못했습니다", path.display()))?;
        let text = String::from_utf8(bytes)
            .with_context(|| format!("{}은(는) UTF-8 텍스트가 아닙니다", path.display()))?;
        let bom = text.starts_with('\u{feff}');
        let text = text.strip_prefix('\u{feff}').unwrap_or(&text);
        let crlf = text.contains("\r\n");
        let document = Self {
            path: Some(path.to_path_buf()),
            crlf,
            bom,
        };
        Ok((document, text.replace("\r\n", "\n")))
    }

    /// The file name shown in the window title.
    pub fn display_name(&self) -> String {
        self.path
            .as_deref()
            .and_then(Path::file_name)
            .map(|name| name.to_string_lossy().into_owned())
            .unwrap_or_else(|| "제목 없음.tex".to_owned())
    }

    /// Writes `text` to `path` in the file's original line endings.
    ///
    /// The text goes to a temporary file beside the target first, so a failed
    /// write leaves the previous manuscript intact.
    pub fn save_to(&mut self, path: &Path, text: &str) -> Result<()> {
        let mut contents = if self.bom {
            "\u{feff}".to_owned()
        } else {
            String::new()
        };
        if self.crlf {
            contents.push_str(&text.replace('\n', "\r\n"));
        } else {
            contents.push_str(text);
        }
        let file_name = path
            .file_name()
            .with_context(|| format!("{}은(는) 파일 경로가 아닙니다", path.display()))?;
        let temp = path.with_file_name(format!(
            ".{}.paper-factory-tmp",
            file_name.to_string_lossy()
        ));
        let write = || -> Result<()> {
            let mut file = fs::File::create(&temp)?;
            file.write_all(contents.as_bytes())?;
            file.sync_all()?;
            fs::rename(&temp, path)?;
            Ok(())
        };
        if let Err(error) = write() {
            let _ = fs::remove_file(&temp);
            return Err(error).with_context(|| format!("{}에 저장하지 못했습니다", path.display()));
        }
        self.path = Some(path.to_path_buf());
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn temp_dir(name: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!("paper-factory-{name}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    #[test]
    fn keeps_crlf_line_endings_on_save() {
        let dir = temp_dir("crlf");
        let path = dir.join("paper.tex");
        fs::write(&path, "\u{feff}\\section{서론}\r\n본문\r\n").unwrap();

        let (mut document, text) = Document::open(&path).unwrap();
        assert_eq!(text, "\\section{서론}\n본문\n");

        document.save_to(&path, &format!("{text}추가\n")).unwrap();
        assert_eq!(
            fs::read_to_string(&path).unwrap(),
            "\u{feff}\\section{서론}\r\n본문\r\n추가\r\n"
        );
        assert!(!dir.join(".paper.tex.paper-factory-tmp").exists());
    }

    #[test]
    fn saves_untitled_text_to_a_new_path() {
        let dir = temp_dir("new");
        let path = dir.join("new.tex");
        let mut document = Document::default();

        document.save_to(&path, "\\begin{document}\n").unwrap();
        assert_eq!(fs::read_to_string(&path).unwrap(), "\\begin{document}\n");
        assert_eq!(document.display_name(), "new.tex");
    }

    #[test]
    fn rejects_non_utf8_files() {
        let dir = temp_dir("binary");
        let path = dir.join("paper.tex");
        fs::write(&path, [0xff, 0xfe, 0x00]).unwrap();
        assert!(Document::open(&path).is_err());
    }
}
