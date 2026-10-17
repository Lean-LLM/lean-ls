use super::OrganizationStrategy;
use crate::config::SizeStrategyConfig;
use std::{
    fs,
    path::{Path, PathBuf},
};

pub struct SizeStrategy {
    config: SizeStrategyConfig,
}

impl SizeStrategy {
    pub fn new(config: SizeStrategyConfig) -> Self {
        Self { config }
    }

    fn get_size_category(&self, size: u64) -> Option<String> {
        self.config
            .ranges
            .iter()
            .find(|range| match range.max_bytes {
                Some(max) => size <= max,
                None => true,
            })
            .map(|range| range.name.clone())
    }
}

impl OrganizationStrategy for SizeStrategy {
    fn organize(&self, dir: &Path, dry_run: bool) -> Result<Vec<(PathBuf, PathBuf)>, String> {
        if !self.config.enabled {
            return Ok(Vec::new());
        }

        let mut moves = Vec::new();
        let entries = fs::read_dir(dir).map_err(|e| format!("Failed to read directory: {}", e))?;

        for entry in entries.filter_map(Result::ok) {
            let path = entry.path();
            if path.is_dir() {
                continue;
            }

            let metadata = fs::metadata(&path)
                .map_err(|e| format!("Failed to get metadata for '{}': {}", path.display(), e))?;

            if let Some(category) = self.get_size_category(metadata.len()) {
                let target_dir = dir.join(&category);
                let target_path = target_dir.join(path.file_name().unwrap());

                if !target_dir.exists() && !dry_run {
                    fs::create_dir_all(&target_dir)
                        .map_err(|e| format!("Failed to create directory: {}", e))?;
                }

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
