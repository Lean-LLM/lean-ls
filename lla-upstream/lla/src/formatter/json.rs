use crate::error::Result;
use crate::plugin::PluginManager;
use lla_plugin_interface::proto::DecoratedEntry;
use std::io::{self, Write};

use super::serializable::{find_git_root, get_git_status_map, to_serializable};

pub fn write_json_array_stream<I>(
    entries: I,
    _plugin_manager: &mut PluginManager,
    pretty: bool,
    include_git_status: bool,
) -> Result<()>
where
    I: IntoIterator<Item = DecoratedEntry>,
{
    let mut stdout = io::BufWriter::new(io::stdout());

    let mut git_status_map = None;
    let mut git_root = None;

    // Prepare git status map if any plugin/git format would have been requested
    // We don't compute git by default; only when git format is active in current run.
    // Here we infer it from plugin_manager or rely on existing fields. To keep it simple,
    // we attempt to find git root from first entry lazily.

    stdout.write_all(b"[")?;
    let mut first = true;
    for entry in entries {
        if first {
            first = false;
        } else {
            stdout.write_all(b",")?;
        }

        // Determine git status lazily
        let git_status = if include_git_status {
            if git_root.is_none() {
                if let Some(parent) = std::path::Path::new(&entry.path).parent() {
                    if let Some(root) = find_git_root(parent) {
                        git_root = Some(root.clone());
                        git_status_map = Some(get_git_status_map(&root));
                    }
                }
            }
            if let Some(root) = &git_root {
                let full = std::path::Path::new(&entry.path);
                let rel = full.strip_prefix(root).unwrap_or(full);
                let rel_str = rel.to_string_lossy().to_string();
                git_status_map
                    .as_ref()
                    .and_then(|m| m.get(&rel_str))
                    .cloned()
            } else {
                None
            }
        } else {
            None
        };

        let serial = to_serializable(&entry, git_status);
        if pretty {
            let json = serde_json::to_string_pretty(&serial)?;
            stdout.write_all(json.as_bytes())?;
        } else {
            let json = serde_json::to_string(&serial)?;
            stdout.write_all(json.as_bytes())?;
        }
    }
    stdout.write_all(b"]")?;
    stdout.flush()?;
    Ok(())
}

pub fn write_ndjson_stream<I>(
    entries: I,
    _plugin_manager: &mut PluginManager,
    include_git_status: bool,
) -> Result<()>
where
    I: IntoIterator<Item = DecoratedEntry>,
{
    let mut stdout = io::BufWriter::new(io::stdout());

    let mut git_status_map = None;
    let mut git_root = None;

    for entry in entries {
        let git_status = if include_git_status {
            if git_root.is_none() {
                if let Some(parent) = std::path::Path::new(&entry.path).parent() {
                    if let Some(root) = find_git_root(parent) {
                        git_root = Some(root.clone());
                        git_status_map = Some(get_git_status_map(&root));
                    }
                }
            }
            if let Some(root) = &git_root {
                let full = std::path::Path::new(&entry.path);
                let rel = full.strip_prefix(root).unwrap_or(full);
                let rel_str = rel.to_string_lossy().to_string();
                git_status_map
                    .as_ref()
                    .and_then(|m| m.get(&rel_str))
                    .cloned()
            } else {
                None
            }
        } else {
            None
        };

        let serial = to_serializable(&entry, git_status);
        let json = serde_json::to_string(&serial)?;
        stdout.write_all(json.as_bytes())?;
        stdout.write_all(b"\n")?;
    }
    stdout.flush()?;
    Ok(())
}
