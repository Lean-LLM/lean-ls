use super::OrganizationStrategy;
use crate::config::TypeStrategyConfig;
use std::{
    collections::HashMap,
    fs,
    path::{Path, PathBuf},
};

pub struct TypeStrategy {
    config: TypeStrategyConfig,
    extension_to_category: HashMap<String, String>,
}

impl TypeStrategy {
    pub fn new(config: TypeStrategyConfig) -> Self {
        let mut extension_to_category = HashMap::new();
        for (category, extensions) in &config.categories {
            for ext in extensions {
                extension_to_category.insert(ext.clone(), category.clone());
            }
        }
        Self {
            config,
            extension_to_category,
        }
    }

    fn get_category(&self, path: &Path) -> Option<String> {
        path.extension()
            .and_then(|ext| ext.to_str())
            .map(|ext| ext.to_lowercase())
            .and_then(|ext| self.extension_to_category.get(&ext))
            .cloned()
    }
}

impl OrganizationStrategy for TypeStrategy {
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

            if let Some(category) = self.get_category(&path) {
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
