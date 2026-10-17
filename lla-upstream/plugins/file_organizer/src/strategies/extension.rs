use super::OrganizationStrategy;
use crate::config::ExtensionStrategyConfig;
use std::{
    collections::HashMap,
    fs,
    path::{Path, PathBuf},
};

pub struct ExtensionStrategy {
    config: ExtensionStrategyConfig,
}

impl ExtensionStrategy {
    pub fn new(config: ExtensionStrategyConfig) -> Self {
        Self { config }
    }
}

impl OrganizationStrategy for ExtensionStrategy {
    fn organize(&self, dir: &Path, dry_run: bool) -> Result<Vec<(PathBuf, PathBuf)>, String> {
        if !self.config.enabled {
            return Ok(Vec::new());
        }

        let mut moves = Vec::new();
        let mut extension_dirs: HashMap<String, PathBuf> = HashMap::new();

        let entries = fs::read_dir(dir).map_err(|e| format!("Failed to read directory: {}", e))?;
        for entry in entries.filter_map(Result::ok) {
            let path = entry.path();
            if path.is_dir() {
                continue;
            }
            if let Some(ext) = path.extension().and_then(|e| e.to_str()) {
                let ext = ext.to_lowercase();
                let target_dir = extension_dirs.entry(ext.clone()).or_insert_with(|| {
                    let mut target = PathBuf::from(dir);
                    if self.config.create_nested {
                        match ext.as_str() {
                            "jpg" | "jpeg" | "png" | "gif" | "bmp" | "svg" => {
                                target.push("images");
                                target.push(ext);
                            }
                            "mp4" | "avi" | "mov" | "mkv" | "wmv" => {
                                target.push("videos");
                                target.push(ext);
                            }
                            "mp3" | "wav" | "flac" | "m4a" | "ogg" => {
                                target.push("audio");
                                target.push(ext);
                            }
                            "doc" | "docx" | "pdf" | "txt" | "rtf" | "md" => {
                                target.push("documents");
                                target.push(ext);
                            }
                            "zip" | "rar" | "7z" | "tar" | "gz" => {
                                target.push("archives");
                                target.push(ext);
                            }
                            _ => target.push(ext),
                        }
                    } else {
                        target.push(ext);
                    }
                    target
                });
                if !target_dir.exists() && !dry_run {
                    fs::create_dir_all(target_dir.clone())
                        .map_err(|e| format!("Failed to create directory: {}", e))?;
                }
                let target_path = target_dir.join(path.file_name().unwrap());
                moves.push((path, target_path));
            }
        }

        Ok(moves)
    }

    fn execute_moves(&self, moves: Vec<(PathBuf, PathBuf)>) -> Result<(), String> {
        for (source, target) in moves {
            if let Some(parent) = target.parent() {
                if !parent.exists() {
                    fs::create_dir_all(parent)
                        .map_err(|e| format!("Failed to create directory: {}", e))?;
                }
            }

            fs::rename(&source, &target).map_err(|e| {
                format!(
                    "Failed to move '{}' to '{}': {}",
                    source.display(),
                    target.display(),
                    e
                )
            })?;
        }
        Ok(())
    }
}
