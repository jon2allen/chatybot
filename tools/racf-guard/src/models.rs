use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Verdict {
    Allow,
    Ask,
    Deny,
}

impl Verdict {
    pub fn as_str(&self) -> &'static str {
        match self {
            Verdict::Allow => "allow",
            Verdict::Ask => "ask",
            Verdict::Deny => "deny",
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PolicyPromptDetails {
    pub title: String,
    pub message: String,
    pub risk_level: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct PolicyRequest {
    pub tool: String,
    #[serde(default)]
    pub parameters: HashMap<String, serde_json::Value>,
    #[serde(default)]
    pub context: HashMap<String, serde_json::Value>,
    #[serde(default)]
    pub version: Option<String>,
    #[serde(default)]
    pub request_id: Option<String>,
    #[serde(default)]
    pub timestamp: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct PolicyDecision {
    pub status: String,
    pub reason: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub prompt_details: Option<PolicyPromptDetails>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub modified_parameters: Option<HashMap<String, serde_json::Value>>,
}

impl PolicyDecision {
    pub fn allow(reason: impl Into<String>) -> Self {
        Self {
            status: "allow".to_string(),
            reason: reason.into(),
            prompt_details: None,
            modified_parameters: None,
        }
    }

    pub fn deny(reason: impl Into<String>) -> Self {
        Self {
            status: "deny".to_string(),
            reason: reason.into(),
            prompt_details: None,
            modified_parameters: None,
        }
    }

    pub fn ask(reason: impl Into<String>, title: &str, message: &str, risk_level: &str) -> Self {
        Self {
            status: "ask".to_string(),
            reason: reason.into(),
            prompt_details: Some(PolicyPromptDetails {
                title: title.to_string(),
                message: message.to_string(),
                risk_level: risk_level.to_string(),
            }),
            modified_parameters: None,
        }
    }
}
