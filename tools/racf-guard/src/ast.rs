use std::fmt;

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub enum ResourceClass {
    Facility,
    Dir,
    Command,
    Ps,
    Custom(String),
}

impl ResourceClass {
    pub fn from_str(s: &str) -> Self {
        match s.trim().to_uppercase().as_str() {
            "FACILITY" => ResourceClass::Facility,
            "DIR" | "DIRECTORY" => ResourceClass::Dir,
            "COMMAND" | "CMD" => ResourceClass::Command,
            "PS" | "PROCESS" => ResourceClass::Ps,
            other => ResourceClass::Custom(other.to_string()),
        }
    }

    pub fn as_str(&self) -> &str {
        match self {
            ResourceClass::Facility => "FACILITY",
            ResourceClass::Dir => "DIR",
            ResourceClass::Command => "COMMAND",
            ResourceClass::Ps => "PS",
            ResourceClass::Custom(s) => s.as_str(),
        }
    }
}

impl fmt::Display for ResourceClass {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.as_str())
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AccessLevel {
    None,
    Deny,
    Ask,
    Allow,
}

impl AccessLevel {
    pub fn from_str(s: &str) -> Option<Self> {
        match s.trim().to_uppercase().as_str() {
            "NONE" | "DENY" => Some(AccessLevel::Deny),
            "ASK" | "AUDIT" => Some(AccessLevel::Ask),
            "ALLOW" | "READ" | "UPDATE" | "CONTROL" | "ALTER" => Some(AccessLevel::Allow),
            _ => None,
        }
    }

    pub fn as_str(&self) -> &'static str {
        match self {
            AccessLevel::None | AccessLevel::Deny => "DENY",
            AccessLevel::Ask => "ASK",
            AccessLevel::Allow => "ALLOW",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Statement {
    AddGroup {
        group: String,
        data: Option<String>,
    },
    Connect {
        user: String,
        group: String,
    },
    RDefine {
        class: ResourceClass,
        profile: String,
        uacc: AccessLevel,
    },
    Permit {
        profile: String,
        class: ResourceClass,
        id: String,
        access: AccessLevel,
    },
    SetrOpts {
        raw: String,
    },
}
