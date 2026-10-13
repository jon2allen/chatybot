use clap::{Parser, Subcommand};
use racf_guard::engine::RacfEngine;
use racf_guard::models::{PolicyDecision, PolicyRequest};
use racf_guard::parser::parse_racf_script;
use std::fs;
use std::io::{self, Read};
use std::path::{Path, PathBuf};

const DEFAULT_EMBEDDED_POLICY: &str = r#"
# -----------------------------------------------------------------------------
# Default Embedded RACF Reference Policy for Chatybot
# -----------------------------------------------------------------------------
# Base User & Group Definitions
ADDGROUP DEVELOPER DATA('Core Software Developers')
ADDGROUP SYSADM DATA('System Administrators')

# Facility Classes for Tools
RDEFINE FACILITY git.* UACC(ASK)
PERMIT git.status CLASS(FACILITY) ID(DEVELOPER) ACCESS(ALLOW)
PERMIT git.diff CLASS(FACILITY) ID(DEVELOPER) ACCESS(ALLOW)
PERMIT git.log CLASS(FACILITY) ID(DEVELOPER) ACCESS(ALLOW)

RDEFINE FACILITY read_file UACC(ASK)
PERMIT read_file CLASS(FACILITY) ID(DEVELOPER) ACCESS(ALLOW)
RDEFINE FACILITY list_directory UACC(ASK)
PERMIT list_directory CLASS(FACILITY) ID(DEVELOPER) ACCESS(ALLOW)
RDEFINE FACILITY view_file UACC(ALLOW)
RDEFINE FACILITY list_dir UACC(ALLOW)
RDEFINE FACILITY grep_search UACC(ALLOW)
RDEFINE FACILITY write_file UACC(ASK)
PERMIT write_file CLASS(FACILITY) ID(DEVELOPER) ACCESS(ALLOW)
RDEFINE FACILITY replace_file_content UACC(ASK)
PERMIT replace_file_content CLASS(FACILITY) ID(DEVELOPER) ACCESS(ALLOW)
RDEFINE FACILITY run_command UACC(ASK)

# Directory Protections
RDEFINE DIR . UACC(ASK)
RDEFINE DIR ./** UACC(ASK)
PERMIT . CLASS(DIR) ID(DEVELOPER) ACCESS(ALLOW)
PERMIT ./** CLASS(DIR) ID(DEVELOPER) ACCESS(ALLOW)
RDEFINE DIR /etc/** UACC(DENY)
RDEFINE DIR /sys/** UACC(DENY)
RDEFINE DIR /proc/** UACC(DENY)
RDEFINE DIR /Users/** UACC(ALLOW)
RDEFINE DIR /home/** UACC(ALLOW)
RDEFINE DIR /tmp/** UACC(ALLOW)

# Command Patterns
RDEFINE COMMAND rm* UACC(DENY)
RDEFINE COMMAND sudo* UACC(DENY)
RDEFINE COMMAND git* UACC(ALLOW)
RDEFINE COMMAND cargo* UACC(ALLOW)
RDEFINE COMMAND pytest* UACC(ALLOW)
"#;

#[derive(Parser, Debug)]
#[command(
    name = "racf-guard",
    about = "RACF-style reference security policy engine for Chatybot",
    version = "0.1.0"
)]
struct Args {
    /// Path to the .racf policy definitions file
    #[arg(short, long)]
    policy: Option<PathBuf>,

    /// Display all loaded RACF groups, users, resource profiles, and ACL permissions, then exit
    #[arg(short = 'l', long = "list-rules", alias = "list")]
    list_rules: bool,

    /// Print a concise one-line engine identification banner and exit
    #[arg(short = 'b', long = "banner")]
    banner: bool,

    /// Enable verbose security evaluation trace logs to stderr
    #[arg(short = 'd', long)]
    debug: bool,

    /// Dry-run evaluate a tool from CLI arguments without stdin
    #[arg(long)]
    check: bool,

    /// Tool name to check (used with --check)
    #[arg(long, default_value = "git.status")]
    tool: String,

    /// User ID to simulate (used with --check)
    #[arg(long)]
    user: Option<String>,

    /// Administrative update command to mutate the policy database on disk
    #[command(subcommand)]
    command: Option<Commands>,
}

#[derive(Subcommand, Debug)]
enum Commands {
    /// Execute and persist a raw RACF statement (e.g. 'PERMIT git.push CLASS(FACILITY) ID(DEVELOPER) ACCESS(ALLOW)')
    Exec {
        /// Raw RACF statement string
        statement: String,
    },
    /// Define a new logical group role
    Addgroup {
        /// Group name
        group: String,
        /// Optional group description
        #[arg(short, long)]
        data: Option<String>,
    },
    /// Connect a system user ID to a RACF group
    Connect {
        /// System user ID
        user: String,
        /// Target RACF group
        #[arg(short, long)]
        group: String,
    },
    /// Define a resource profile with Universal Access (UACC)
    Rdefine {
        /// Resource class (FACILITY, DIR, COMMAND, PS)
        class: String,
        /// Profile pattern (e.g. git.*, /etc/**)
        profile: String,
        /// Universal Access fallback (ALLOW, ASK, DENY)
        #[arg(short, long, default_value = "DENY")]
        uacc: String,
    },
    /// Grant or restrict access to a profile for a user or group
    Permit {
        /// Profile pattern
        profile: String,
        /// Resource class (FACILITY, DIR, COMMAND, PS)
        #[arg(short, long)]
        class: String,
        /// User ID or Group ID
        #[arg(short, long)]
        id: String,
        /// Access level (ALLOW, ASK, DENY)
        #[arg(short, long, default_value = "ALLOW")]
        access: String,
    },
}

fn find_policy_path(explicit: Option<&PathBuf>) -> Result<Option<PathBuf>, String> {
    if let Some(p) = explicit {
        if p.exists() {
            return Ok(Some(p.clone()));
        } else {
            return Err(format!("Explicit policy file not found: '{}'", p.display()));
        }
    }
    if let Ok(env_path) = std::env::var("RACF_POLICY_PATH") {
        let p = PathBuf::from(env_path);
        if p.exists() {
            return Ok(Some(p));
        }
    }
    let candidates = [
        Path::new("security.racf"),
        Path::new("tools/racf-guard/examples/security.racf"),
        Path::new("examples/security.racf"),
    ];
    for c in candidates {
        if c.exists() {
            return Ok(Some(c.to_path_buf()));
        }
    }
    Ok(None)
}

fn resolve_target_policy_path(explicit: Option<&PathBuf>) -> PathBuf {
    if let Some(p) = explicit {
        return p.clone();
    }
    if let Ok(Some(discovered)) = find_policy_path(None) {
        return discovered;
    }
    PathBuf::from("security.racf")
}

fn load_engine(policy_path: Option<&PathBuf>) -> Result<RacfEngine, String> {
    let mut engine = RacfEngine::new();
    let script = if let Some(path) = policy_path {
        fs::read_to_string(path).map_err(|e| format!("Failed to read policy file {:?}: {}", path, e))?
    } else {
        DEFAULT_EMBEDDED_POLICY.to_string()
    };

    let stmts = parse_racf_script(&script)?;
    engine.load_statements(stmts);
    Ok(engine)
}

/// Persists a validated RACF statement to disk, creating both a standard and timestamped backup first.
fn persist_statement(policy_path: &Path, stmt_str: &str) -> Result<(), String> {
    // 1. Validate statement syntax first before doing anything
    let test_script = format!("{}\n", stmt_str);
    parse_racf_script(&test_script)
        .map_err(|e| format!("Invalid RACF statement syntax: {}", e))?;

    // 2. Create backup if policy file already exists
    if policy_path.exists() {
        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_secs())
            .unwrap_or(0);
        let timestamped_backup = PathBuf::from(format!("{}.bak.{}", policy_path.display(), timestamp));
        let backup_path = PathBuf::from(format!("{}.bak", policy_path.display()));
        let _ = fs::copy(policy_path, &timestamped_backup);
        fs::copy(policy_path, &backup_path)
            .map_err(|e| format!("Failed to create backup at {:?}: {}", backup_path, e))?;
        println!(
            "[RACF Admin] Created backup copies: '{}' and '{}'",
            backup_path.display(),
            timestamped_backup.display()
        );
    } else {
        if let Some(parent) = policy_path.parent() {
            if !parent.as_os_str().is_empty() {
                fs::create_dir_all(parent)
                    .map_err(|e| format!("Failed to create directory {:?}: {}", parent, e))?;
            }
        }
        fs::write(policy_path, "# RACF Security Database Policy\n")
            .map_err(|e| format!("Failed to initialize {:?}: {}", policy_path, e))?;
    }

    // 3. Read existing content and append new statement
    let existing_content = fs::read_to_string(policy_path)
        .map_err(|e| format!("Failed to read {:?}: {}", policy_path, e))?;

    let mut new_content = existing_content;
    if !new_content.ends_with('\n') {
        new_content.push('\n');
    }
    new_content.push_str(stmt_str);
    new_content.push('\n');

    // 4. Write new content
    fs::write(policy_path, &new_content)
        .map_err(|e| format!("Failed to write to {:?}: {}", policy_path, e))?;

    // 5. Re-parse entire file to ensure total database integrity
    match parse_racf_script(&new_content) {
        Ok(stmts) => {
            let mut engine = RacfEngine::new();
            engine.load_statements(stmts);
            let total_profiles: usize = engine.profiles.values().map(|v| v.len()).sum();
            println!(
                "[RACF Admin] Persisted statement to '{}':\n  {}",
                policy_path.display(),
                stmt_str
            );
            println!(
                "[RACF Admin] Database reloaded successfully ({} groups, {} profiles).",
                engine.groups.len(),
                total_profiles
            );
            Ok(())
        }
        Err(err) => {
            // Restore from backup on failure
            let backup_path = PathBuf::from(format!("{}.bak", policy_path.display()));
            if backup_path.exists() {
                let _ = fs::copy(&backup_path, policy_path);
                println!(
                    "[RACF Admin Warning] Restored '{}' from backup due to parsing error.",
                    policy_path.display()
                );
            }
            Err(format!("Database integrity check failed after write: {}", err))
        }
    }
}

fn main() {
    let args = Args::parse();

    // Check if an administrative persistence command was given
    if let Some(cmd) = args.command {
        let target_path = resolve_target_policy_path(args.policy.as_ref());
        let stmt_str = match cmd {
            Commands::Exec { statement } => statement,
            Commands::Addgroup { group, data } => {
                if let Some(d) = data {
                    format!("ADDGROUP {} DATA('{}')", group, d)
                } else {
                    format!("ADDGROUP {}", group)
                }
            }
            Commands::Connect { user, group } => {
                format!("CONNECT {} GROUP({})", user, group)
            }
            Commands::Rdefine {
                class,
                profile,
                uacc,
            } => {
                format!(
                    "RDEFINE {} {} UACC({})",
                    class.to_uppercase(),
                    profile,
                    uacc.to_uppercase()
                )
            }
            Commands::Permit {
                profile,
                class,
                id,
                access,
            } => {
                format!(
                    "PERMIT {} CLASS({}) ID({}) ACCESS({})",
                    profile,
                    class.to_uppercase(),
                    id,
                    access.to_uppercase()
                )
            }
        };

        if let Err(e) = persist_statement(&target_path, &stmt_str) {
            eprintln!("[RACF Admin Error] {}", e);
            std::process::exit(1);
        }
        return;
    }

    let policy_path = match find_policy_path(args.policy.as_ref()) {
        Ok(p) => p,
        Err(err) => {
            eprintln!("[RACF Error] {}", err);
            let decision = PolicyDecision::deny(err);
            println!("{}", serde_json::to_string(&decision).unwrap());
            std::process::exit(1);
        }
    };

    let engine = match load_engine(policy_path.as_ref()) {
        Ok(e) => e,
        Err(err) => {
            let decision = PolicyDecision::deny(format!("RACF engine initialization error: {}", err));
            println!("{}", serde_json::to_string(&decision).unwrap());
            std::process::exit(0);
        }
    };

    // If --banner mode is requested: print concise engine banner and exit
    if args.banner {
        let total_profiles: usize = engine.profiles.values().map(|v| v.len()).sum();
        let source_desc = policy_path
            .as_ref()
            .and_then(|p| p.file_name())
            .map(|f| f.to_string_lossy().to_string())
            .unwrap_or_else(|| "embedded policy".to_string());
        println!(
            "RACF-Guard v{} ({} groups, {} profiles loaded from {})",
            env!("CARGO_PKG_VERSION"),
            engine.groups.len(),
            total_profiles,
            source_desc
        );
        return;
    }

    // If --list-rules mode is requested: print full audit report and exit
    if args.list_rules {
        let source_desc = policy_path
            .as_ref()
            .map(|p| p.display().to_string())
            .unwrap_or_else(|| "Embedded Default Policy".to_string());
        print!("{}", engine.format_audit_report(Some(&source_desc)));
        return;
    }

    // If --check mode is requested
    if args.check {
        let mut req = PolicyRequest {
            tool: args.tool,
            parameters: Default::default(),
            context: Default::default(),
            version: Some("1.0".to_string()),
            request_id: None,
            timestamp: None,
        };
        if let Some(u) = args.user {
            req.context.insert("user".to_string(), serde_json::Value::String(u));
        }
        let (decision, trace) = engine.evaluate_request_debug(&req, args.debug);
        if args.debug {
            for line in trace {
                eprintln!("{}", line);
            }
        }
        println!("{}", serde_json::to_string_pretty(&decision).unwrap());
        return;
    }

    // Default mode: Read JSON from stdin
    let mut input = String::new();
    if let Err(e) = io::stdin().read_to_string(&mut input) {
        let decision = PolicyDecision::deny(format!("Failed to read from stdin: {}", e));
        println!("{}", serde_json::to_string(&decision).unwrap());
        return;
    }

    let input_trimmed = input.trim();
    if input_trimmed.is_empty() {
        let decision = PolicyDecision::deny("Received empty request on stdin");
        println!("{}", serde_json::to_string(&decision).unwrap());
        return;
    }

    let request: PolicyRequest = match serde_json::from_str(input_trimmed) {
        Ok(req) => req,
        Err(e) => {
            let decision = PolicyDecision::deny(format!("Invalid JSON request payload: {}", e));
            println!("{}", serde_json::to_string(&decision).unwrap());
            return;
        }
    };

    // Debug is active if CLI flag --debug was set OR context contains "debug": true
    let is_debug = args.debug
        || request
            .context
            .get("debug")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);

    let (decision, trace) = engine.evaluate_request_debug(&request, is_debug);

    if is_debug {
        for line in trace {
            eprintln!("{}", line);
        }
    }

    let output_json = match serde_json::to_string(&decision) {
        Ok(json) => json,
        Err(e) => {
            let fallback = PolicyDecision::deny(format!("Serialization error: {}", e));
            serde_json::to_string(&fallback).unwrap()
        }
    };

    println!("{}", output_json);
}
