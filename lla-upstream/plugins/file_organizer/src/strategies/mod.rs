pub mod date;
pub mod extension;
pub mod size;
pub mod r#type;

use std::path::{Path, PathBuf};

pub trait OrganizationStrategy {
    fn organize(&self, dir: &Path, dry_run: bool) -> Result<Vec<(PathBuf, PathBuf)>, String>;
    fn execute_moves(&self, moves: Vec<(PathBuf, PathBuf)>) -> Result<(), String>;
}

pub use date::DateStrategy;
pub use extension::ExtensionStrategy;
pub use r#type::TypeStrategy;
pub use size::SizeStrategy;
