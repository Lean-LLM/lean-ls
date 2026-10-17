use super::OrganizationStrategy;
use crate::config::DateStrategyConfig;
use chrono::{DateTime, Local, TimeZone};
use std::{
    fs,
    path::{Path, PathBuf},
};

pub struct DateStrategy {
    config: DateStrategyConfig,
}

impl DateStrategy {
    pub fn new(config: DateStrategyConfig) -> Self {
        Self { config }
    }

    fn get_date_from_metadata(&self, path: &Path) -> Option<DateTime<Local>> {
        path.metadata()
            .ok()?
            .modified()
            .ok()?
            .duration_since(std::time::UNIX_EPOCH)
            .ok()
            .map(|d| Local.timestamp_opt(d.as_secs() as i64, 0).single())?
    }

    fn format_date_path(&self, date: DateTime<Local>) -> PathBuf {
        let path_str = match self.config.group_by.as_str() {
            "year" => date.format("%Y").to_string(),
            "day" => date.format("%Y/%m/%d").to_string(),
            _ => date.format("%Y/%m").to_string(),
        };
        PathBuf::from(path_str)
    }
}

impl OrganizationStrategy for DateStrategy {
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

            if let Some(date) = self.get_date_from_metadata(&path) {
                let relative_date_path = self.format_date_path(date);
                let target_dir = dir.join(&relative_date_path);
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
