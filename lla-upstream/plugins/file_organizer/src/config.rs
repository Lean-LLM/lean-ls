use lla_plugin_utils::config::PluginConfig;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExtensionStrategyConfig {
    #[serde(default = "default_extension_enabled")]
    pub enabled: bool,
    #[serde(default = "default_extension_create_nested")]
    pub create_nested: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DateStrategyConfig {
    #[serde(default = "default_date_enabled")]
    pub enabled: bool,
    #[serde(default = "default_date_format")]
    pub format: String,
    #[serde(default = "default_date_group_by")]
    pub group_by: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TypeStrategyConfig {
    #[serde(default = "default_type_enabled")]
    pub enabled: bool,
    #[serde(default = "default_type_categories")]
    pub categories: HashMap<String, Vec<String>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SizeRange {
    pub name: String,
    pub max_bytes: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SizeStrategyConfig {
    #[serde(default = "default_size_enabled")]
    pub enabled: bool,
    #[serde(default = "default_size_ranges")]
    pub ranges: Vec<SizeRange>,
}

fn default_extension_enabled() -> bool {
    true
}

fn default_extension_create_nested() -> bool {
    true
}

fn default_date_enabled() -> bool {
    true
}

fn default_date_format() -> String {
    "%Y/%m/%d".to_string()
}

fn default_date_group_by() -> String {
    "month".to_string()
}

fn default_type_enabled() -> bool {
    true
}

fn default_type_categories() -> HashMap<String, Vec<String>> {
    let mut categories = HashMap::new();
    categories.insert(
        "documents".to_string(),
        vec![
            "pdf".to_string(),
            "doc".to_string(),
            "docx".to_string(),
            "txt".to_string(),
            "md".to_string(),
        ],
    );
    categories.insert(
        "images".to_string(),
        vec![
            "jpg".to_string(),
            "jpeg".to_string(),
            "png".to_string(),
            "gif".to_string(),
            "svg".to_string(),
        ],
    );
    categories.insert(
        "videos".to_string(),
        vec![
            "mp4".to_string(),
            "mov".to_string(),
            "avi".to_string(),
            "mkv".to_string(),
        ],
    );
    categories.insert(
        "audio".to_string(),
        vec![
            "mp3".to_string(),
            "wav".to_string(),
            "flac".to_string(),
            "m4a".to_string(),
        ],
    );
    categories.insert(
        "archives".to_string(),
        vec![
            "zip".to_string(),
            "rar".to_string(),
            "7z".to_string(),
            "tar".to_string(),
            "gz".to_string(),
        ],
    );
    categories
}

fn default_size_enabled() -> bool {
    true
}

fn default_size_ranges() -> Vec<SizeRange> {
    vec![
        SizeRange {
            name: "tiny".to_string(),
            max_bytes: Some(102400),
        }, // 0-100KB
        SizeRange {
            name: "small".to_string(),
            max_bytes: Some(1048576),
        }, // 100KB-1MB
        SizeRange {
            name: "medium".to_string(),
            max_bytes: Some(104857600),
        }, // 1MB-100MB
        SizeRange {
            name: "large".to_string(),
            max_bytes: Some(1073741824),
        }, // 100MB-1GB
        SizeRange {
            name: "huge".to_string(),
            max_bytes: None,
        }, // >1GB
    ]
}

impl Default for ExtensionStrategyConfig {
    fn default() -> Self {
        Self {
            enabled: default_extension_enabled(),
            create_nested: default_extension_create_nested(),
        }
    }
}

impl Default for DateStrategyConfig {
    fn default() -> Self {
        Self {
            enabled: default_date_enabled(),
            format: default_date_format(),
            group_by: default_date_group_by(),
        }
    }
}

impl Default for TypeStrategyConfig {
    fn default() -> Self {
        Self {
            enabled: default_type_enabled(),
            categories: default_type_categories(),
        }
    }
}

impl Default for SizeStrategyConfig {
    fn default() -> Self {
        Self {
            enabled: default_size_enabled(),
            ranges: default_size_ranges(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IgnoreConfig {
    #[serde(default = "default_ignore_patterns")]
    pub patterns: Vec<String>,
    #[serde(default = "default_ignore_extensions")]
    pub extensions: Vec<String>,
}

fn default_ignore_patterns() -> Vec<String> {
    vec![
        ".git".to_string(),
        "node_modules".to_string(),
        "target".to_string(),
    ]
}

fn default_ignore_extensions() -> Vec<String> {
    vec![".tmp".to_string(), ".bak".to_string()]
}

impl Default for IgnoreConfig {
    fn default() -> Self {
        Self {
            patterns: default_ignore_patterns(),
            extensions: default_ignore_extensions(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OrganizerConfig {
    #[serde(default = "default_colors")]
    pub colors: HashMap<String, String>,
    #[serde(default)]
    pub extension: ExtensionStrategyConfig,
    #[serde(default)]
    pub date: DateStrategyConfig,
    #[serde(default)]
    pub type_strategy: TypeStrategyConfig,
    #[serde(default)]
    pub size: SizeStrategyConfig,
    #[serde(default)]
    pub ignore: IgnoreConfig,
}

fn default_colors() -> HashMap<String, String> {
    let mut colors = HashMap::new();
    colors.insert("success".to_string(), "bright_green".to_string());
    colors.insert("info".to_string(), "bright_blue".to_string());
    colors.insert("error".to_string(), "bright_red".to_string());
    colors.insert("path".to_string(), "bright_yellow".to_string());
    colors
}

impl Default for OrganizerConfig {
    fn default() -> Self {
        Self {
            colors: default_colors(),
            extension: ExtensionStrategyConfig::default(),
            date: DateStrategyConfig::default(),
            type_strategy: TypeStrategyConfig::default(),
            size: SizeStrategyConfig::default(),
            ignore: IgnoreConfig::default(),
        }
    }
}

impl PluginConfig for OrganizerConfig {}
