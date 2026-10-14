use crate::ast::{AccessLevel, ResourceClass, Statement};
use crate::models::{PolicyDecision, PolicyRequest};
use glob_match::glob_match;
use std::collections::{HashMap, HashSet};

use std::path::Path;

fn dirs_home() -> Option<String> {
    std::env::var("HOME")
        .or_else(|_| std::env::var("USERPROFILE"))
        .ok()
}

pub fn expand_tilde(path: &str) -> String {
    if path == "~" {
        dirs_home().unwrap_or_else(|| "~".to_string())
    } else if let Some(stripped) = path.strip_prefix("~/") {
        if let Some(home) = dirs_home() {
            format!("{}/{}", home.trim_end_matches('/'), stripped)
        } else {
            path.to_string()
        }
    } else {
        path.to_string()
    }
}

pub fn normalize_path(path: &str) -> String {
    if path.starts_with('*') {
        return path.to_string();
    }
    let expanded = expand_tilde(path);
    let p = Path::new(&expanded);
    let abs_path = if !p.is_absolute() {
        if let Ok(cwd) = std::env::current_dir() {
            cwd.join(p)
        } else {
            p.to_path_buf()
        }
    } else {
        p.to_path_buf()
    };

    let mut components = Vec::new();
    let is_absolute = abs_path.is_absolute();
    for component in abs_path.components() {
        match component {
            std::path::Component::Prefix(prefix) => {
                components.push(prefix.as_os_str().to_string_lossy().to_string());
            }
            std::path::Component::RootDir => {}
            std::path::Component::CurDir => {}
            std::path::Component::ParentDir => {
                components.pop();
            }
            std::path::Component::Normal(c) => {
                components.push(c.to_string_lossy().to_string());
            }
        }
    }
    let mut res = String::new();
    if is_absolute {
        res.push('/');
    }
    res.push_str(&components.join("/"));
    if res.is_empty() {
        ".".to_string()
    } else {
        res
    }
}

pub fn canonicalize_path_if_exists(path: &str) -> Vec<String> {
    let mut results = Vec::new();
    if path.contains('*') || path.contains('?') {
        return results;
    }
    let expanded = expand_tilde(path);
    let p = Path::new(&expanded);
    let abs_path = if !p.is_absolute() {
        if let Ok(cwd) = std::env::current_dir() {
            cwd.join(p)
        } else {
            p.to_path_buf()
        }
    } else {
        p.to_path_buf()
    };

    let resolved = if let Ok(canon) = std::fs::canonicalize(&abs_path) {
        Some(canon.to_string_lossy().to_string())
    } else if let Some(parent) = abs_path.parent() {
        if let Ok(canon_parent) = std::fs::canonicalize(parent) {
            if let Some(file_name) = abs_path.file_name() {
                Some(canon_parent.join(file_name).to_string_lossy().to_string())
            } else {
                None
            }
        } else {
            None
        }
    } else {
        None
    };

    if let Some(r) = resolved {
        if r.starts_with("/private/") {
            results.push(r["/private".len()..].to_string());
        }
        if r.starts_with("/System/Volumes/Data/") {
            results.push(r["/System/Volumes/Data".len()..].to_string());
        } else {
            results.push(r);
        }
    }
    results
}

#[derive(Debug, Clone)]
pub struct Profile {
    pub class: ResourceClass,
    pub pattern: String,
    pub uacc: AccessLevel,
    pub acl: HashMap<String, AccessLevel>,
    pub is_generic: bool,
}

impl Profile {
    pub fn new(class: ResourceClass, pattern: String, uacc: AccessLevel) -> Self {
        let is_generic = pattern.contains('*') || pattern.contains('?');
        Self {
            class,
            pattern,
            uacc,
            acl: HashMap::new(),
            is_generic,
        }
    }

    /// Higher score indicates higher specificity.
    /// Discrete (exact) matches always beat generic wildcard matches.
    pub fn specificity_score(&self) -> usize {
        let char_count = self.pattern.chars().count();
        if !self.is_generic {
            100_000 + char_count
        } else {
            // Count non-wildcard characters as higher specificity
            let literal_chars = self.pattern.chars().filter(|c| *c != '*' && *c != '?').count();
            let mut score = literal_chars * 10 + char_count;
            // Patterns with specific filename/leaf constraints (not ending with directory wildcards)
            // have higher specificity than general directory container patterns.
            if !self.pattern.ends_with("/**") && !self.pattern.ends_with("/*") {
                score += 1_000;
            }
            score
        }
    }

    pub fn matches(&self, resource: &str) -> bool {
        if self.class == ResourceClass::Dir {
            let norm_pattern = normalize_path(&self.pattern);
            let norm_resource = normalize_path(resource);
            if !self.is_generic {
                norm_pattern == norm_resource
            } else if glob_match(&norm_pattern, &norm_resource) {
                true
            } else if norm_pattern.starts_with("**") {
                // If pattern is '**/*' and norm_resource is '/Users/...', match with leading '/'
                let rooted_pattern = format!("/{}", norm_pattern);
                if glob_match(&rooted_pattern, &norm_resource) {
                    true
                } else {
                    // Also test against filename or raw resource
                    if let Some(filename) = Path::new(&norm_resource).file_name().and_then(|f| f.to_str()) {
                        glob_match(&norm_pattern, filename)
                    } else {
                        false
                    }
                }
            } else {
                false
            }
        } else if self.class == ResourceClass::Content {
            let pat_lower = self.pattern.to_lowercase();
            let res_lower = resource.to_lowercase();
            if !self.is_generic {
                res_lower == pat_lower || res_lower.contains(&pat_lower)
            } else {
                let normalized_pattern = if pat_lower.contains('*') && !pat_lower.contains("**") {
                    pat_lower.replace('*', "**")
                } else {
                    pat_lower.clone()
                };
                if glob_match(&normalized_pattern, &res_lower) {
                    return true;
                }
                for line in res_lower.lines() {
                    if glob_match(&pat_lower, line) {
                        return true;
                    }
                }
                false
            }
        } else if !self.is_generic {
            self.pattern == resource
        } else {
            // For commands and facility names, * should match all characters including slashes
            let normalized_pattern = if self.pattern.contains('*') && !self.pattern.contains("**") {
                self.pattern.replace('*', "**")
            } else {
                self.pattern.clone()
            };
            glob_match(&normalized_pattern, resource)
        }
    }
}

#[derive(Debug, Default)]
pub struct RacfEngine {
    pub groups: HashSet<String>,
    pub group_data: HashMap<String, Option<String>>,
    pub user_groups: HashMap<String, HashSet<String>>,
    pub profiles: HashMap<ResourceClass, Vec<Profile>>,
    pub class_default_uacc: HashMap<ResourceClass, AccessLevel>,
}

impl RacfEngine {
    pub fn new() -> Self {
        let mut class_default = HashMap::new();
        // By default, unmatched resources in any class are DENIED
        class_default.insert(ResourceClass::Facility, AccessLevel::Deny);
        class_default.insert(ResourceClass::Dir, AccessLevel::Deny);
        class_default.insert(ResourceClass::Command, AccessLevel::Deny);
        class_default.insert(ResourceClass::Ps, AccessLevel::Deny);
        class_default.insert(ResourceClass::Content, AccessLevel::Allow);

        Self {
            groups: HashSet::new(),
            group_data: HashMap::new(),
            user_groups: HashMap::new(),
            profiles: HashMap::new(),
            class_default_uacc: class_default,
        }
    }

    /// Load and apply parsed RACF statements into the database.
    pub fn load_statements(&mut self, statements: Vec<Statement>) {
        for stmt in statements {
            match stmt {
                Statement::AddGroup { group, data } => {
                    self.groups.insert(group.clone());
                    self.group_data.insert(group, data);
                }
                Statement::Connect { user, group } => {
                    self.groups.insert(group.clone());
                    self.user_groups.entry(user).or_default().insert(group);
                }
                Statement::RDefine {
                    class,
                    profile,
                    uacc,
                } => {
                    let list = self.profiles.entry(class.clone()).or_default();
                    if let Some(existing) = list.iter_mut().find(|p| p.pattern == profile) {
                        existing.uacc = uacc;
                    } else {
                        list.push(Profile::new(class, profile, uacc));
                    }
                }
                Statement::Permit {
                    profile,
                    class,
                    id,
                    access,
                } => {
                    let list = self.profiles.entry(class.clone()).or_default();
                    if let Some(existing) = list.iter_mut().find(|p| p.pattern == profile) {
                        existing.acl.insert(id, access);
                    } else {
                        let mut prof = Profile::new(class, profile, AccessLevel::Deny);
                        prof.acl.insert(id, access);
                        list.push(prof);
                    }
                }
                Statement::SetrOpts { .. } => {
                    // Handled / informational
                }
            }
        }
    }

    /// Generates a formatted ASCII audit report of all groups, users, and resource profiles.
    pub fn format_audit_report(&self, source: Option<&str>) -> String {
        let mut out = String::new();
        out.push_str("================================================================================\n");
        out.push_str("                    RACF SECURITY DATABASE AUDIT REPORT\n");
        out.push_str("================================================================================\n");
        if let Some(s) = source {
            out.push_str(&format!("Policy Source: {}\n\n", s));
        } else {
            out.push_str("Policy Source: Embedded Fallback\n\n");
        }

        // 1. Groups & User Connections
        out.push_str("--- [ GROUPS & CONNECTS ] ------------------------------------------------------\n");
        let mut sorted_groups: Vec<&String> = self.groups.iter().collect();
        sorted_groups.sort();

        if sorted_groups.is_empty() {
            out.push_str("  (No groups defined)\n");
        } else {
            for grp in sorted_groups {
                let desc = match self.group_data.get(grp).and_then(|d| d.as_deref()) {
                    Some(d) => format!(" (DATA: {})", d),
                    None => String::new(),
                };
                out.push_str(&format!("  GROUP: {}{}\n", grp, desc));

                // Connected users
                let mut connected_users: Vec<&String> = self
                    .user_groups
                    .iter()
                    .filter(|(_, grps)| grps.contains(grp))
                    .map(|(u, _)| u)
                    .collect();
                connected_users.sort();
                if !connected_users.is_empty() {
                    let users_str = connected_users
                        .into_iter()
                        .map(|s| s.as_str())
                        .collect::<Vec<_>>()
                        .join(", ");
                    out.push_str(&format!("    \u{21b3} CONNECTED USERS: {}\n", users_str));
                }
            }
        }
        out.push('\n');

        // 2. Resource Classes and Profiles
        let classes = [
            ResourceClass::Facility,
            ResourceClass::Dir,
            ResourceClass::Command,
            ResourceClass::Content,
            ResourceClass::Ps,
        ];

        for class in &classes {
            out.push_str(&format!(
                "--- [ RESOURCE CLASS: {} ] ----------------------------------------------\n",
                class
            ));
            if let Some(profs) = self.profiles.get(class) {
                let mut sorted_profs: Vec<&Profile> = profs.iter().collect();
                sorted_profs.sort_by(|a, b| a.pattern.cmp(&b.pattern));

                if sorted_profs.is_empty() {
                    out.push_str("  (No profiles defined)\n");
                } else {
                    for p in sorted_profs {
                        let prof_type = if p.is_generic { "Generic" } else { "Discrete" };
                        out.push_str(&format!(
                            "  PROFILE: {:<32} [{:<8}] UACC: {}\n",
                            p.pattern,
                            prof_type,
                            p.uacc.as_str()
                        ));

                        // ACL permits
                        let mut sorted_acl: Vec<(&String, &AccessLevel)> = p.acl.iter().collect();
                        sorted_acl.sort_by(|a, b| a.0.cmp(b.0));
                        for (id, acc) in sorted_acl {
                            out.push_str(&format!(
                                "    \u{21b3} PERMIT ID: {:<22} ACCESS: {}\n",
                                id,
                                acc.as_str()
                            ));
                        }
                    }
                }
            } else {
                out.push_str("  (No profiles defined)\n");
            }
            out.push('\n');
        }

        out.push_str("================================================================================\n");
        out
    }

    /// Resolve effective user ID from request or system environment.
    pub fn resolve_user<'a>(&self, request: &'a PolicyRequest) -> String {
        if let Some(u) = request.context.get("user").and_then(|v| v.as_str()) {
            if !u.is_empty() {
                return u.to_string();
            }
        }
        if let Ok(u) = std::env::var("USER") {
            if !u.is_empty() {
                return u;
            }
        }
        if let Ok(u) = std::env::var("LOGNAME") {
            if !u.is_empty() {
                return u;
            }
        }
        if let Ok(u) = std::env::var("USERNAME") {
            if !u.is_empty() {
                return u;
            }
        }
        "DEFAULT".to_string()
    }

    /// RACF profile evaluation logic for a single (class, resource) pair with optional debug trace.
    pub fn evaluate_resource(
        &self,
        user: &str,
        class: &ResourceClass,
        resource: &str,
    ) -> (AccessLevel, String) {
        self.evaluate_resource_trace(user, class, resource, &mut None)
    }

    pub fn evaluate_resource_trace(
        &self,
        user: &str,
        class: &ResourceClass,
        resource: &str,
        trace: &mut Option<&mut Vec<String>>,
    ) -> (AccessLevel, String) {
        if let Some(t) = trace.as_deref_mut() {
            t.push(format!(
                "[RACF Debug] Evaluating Class '{}', Resource '{}' for User '{}'",
                class, resource, user
            ));
        }

        let profiles = match self.profiles.get(class) {
            Some(p) => p,
            None => {
                let default_acc = self
                    .class_default_uacc
                    .get(class)
                    .copied()
                    .unwrap_or(AccessLevel::Deny);
                if let Some(t) = trace.as_deref_mut() {
                    t.push(format!(
                        "[RACF Debug] \u{2514}\u{2500} No profiles registered for class '{}' -> Class default DENY",
                        class
                    ));
                }
                return (
                    default_acc,
                    format!("No profiles defined for class {}", class),
                );
            }
        };

        // Find all matching profiles
        let mut matches: Vec<&Profile> = profiles.iter().filter(|p| p.matches(resource)).collect();

        if matches.is_empty() {
            let default_acc = self
                .class_default_uacc
                .get(class)
                .copied()
                .unwrap_or(AccessLevel::Deny);
            if let Some(t) = trace.as_deref_mut() {
                t.push(format!(
                    "[RACF Debug] \u{2514}\u{2500} No profile matched '{}:{}' -> Class default DENY",
                    class, resource
                ));
            }
            return (
                default_acc,
                format!("No matching profile found for {}:{}", class, resource),
            );
        }

        // Sort by specificity score descending (highest score first)
        matches.sort_by(|a, b| b.specificity_score().cmp(&a.specificity_score()));
        let winning_profile = matches[0];

        if let Some(t) = trace.as_deref_mut() {
            t.push(format!(
                "[RACF Debug] \u{251c}\u{2500} Matched {} profile(s). Best match: '{}' ({}, score: {})",
                matches.len(),
                winning_profile.pattern,
                if winning_profile.is_generic { "Generic" } else { "Discrete" },
                winning_profile.specificity_score()
            ));
        }

        // 1. Direct User Permit
        if let Some(&user_access) = winning_profile.acl.get(user) {
            let reason = format!(
                "User '{}' directly permitted {} on {}:{}",
                user,
                user_access.as_str(),
                class,
                winning_profile.pattern
            );
            if let Some(t) = trace.as_deref_mut() {
                t.push(format!(
                    "[RACF Debug] \u{2514}\u{2500} Direct user permit found: ID('{}') -> ACCESS({})",
                    user,
                    user_access.as_str()
                ));
            }
            return (user_access, reason);
        } else if let Some(t) = trace.as_deref_mut() {
            t.push(format!(
                "[RACF Debug] \u{251c}\u{2500} No direct permit for user '{}' on profile '{}'",
                user, winning_profile.pattern
            ));
        }

        // 2. Group Permit
        if let Some(groups) = self.user_groups.get(user) {
            let mut sorted_groups: Vec<&String> = groups.iter().collect();
            sorted_groups.sort();
            if let Some(t) = trace.as_deref_mut() {
                let grp_list = sorted_groups
                    .iter()
                    .map(|s| s.as_str())
                    .collect::<Vec<_>>()
                    .join(", ");
                t.push(format!(
                    "[RACF Debug] \u{251c}\u{2500} Checking group permits for user's groups: [{}]",
                    grp_list
                ));
            }
            let mut best_group_access: Option<(AccessLevel, &str)> = None;
            for group in sorted_groups {
                if let Some(&group_access) = winning_profile.acl.get(group) {
                    if let Some(t) = trace.as_deref_mut() {
                        t.push(format!(
                            "[RACF Debug] \u{251c}\u{2500} Found group permit: GROUP('{}') -> ACCESS({})",
                            group,
                            group_access.as_str()
                        ));
                    }
                    // Precedence: ALLOW > ASK > DENY
                    match (best_group_access, group_access) {
                        (None, _) => best_group_access = Some((group_access, group)),
                        (Some((AccessLevel::Deny, _)), other) => {
                            best_group_access = Some((other, group));
                        }
                        (Some((AccessLevel::Ask, _)), AccessLevel::Allow) => {
                            best_group_access = Some((AccessLevel::Allow, group));
                        }
                        _ => {}
                    }
                }
            }

            if let Some((grp_access, grp_name)) = best_group_access {
                let reason = format!(
                    "User '{}' granted {} via group '{}' on {}:{}",
                    user,
                    grp_access.as_str(),
                    grp_name,
                    class,
                    winning_profile.pattern
                );
                if let Some(t) = trace.as_deref_mut() {
                    t.push(format!(
                        "[RACF Debug] \u{2514}\u{2500} Effective group access: GROUP('{}') -> ACCESS({})",
                        grp_name,
                        grp_access.as_str()
                    ));
                }
                return (grp_access, reason);
            }
        } else if let Some(t) = trace.as_deref_mut() {
            t.push(format!(
                "[RACF Debug] \u{251c}\u{2500} User '{}' is not connected to any RACF groups",
                user
            ));
        }

        // 3. Fallback to Profile Universal Access (UACC)
        if let Some(t) = trace.as_deref_mut() {
            t.push(format!(
                "[RACF Debug] \u{2514}\u{2500} Falling back to Profile UACC({}) for '{}:{}'",
                winning_profile.uacc.as_str(),
                class,
                winning_profile.pattern
            ));
        }
        (
            winning_profile.uacc,
            format!(
                "Default UACC {} applied on {}:{}",
                winning_profile.uacc.as_str(),
                class,
                winning_profile.pattern
            ),
        )
    }

    /// Evaluates an entire Chatybot PolicyRequest across all relevant resource classes.
    pub fn evaluate_request(&self, request: &PolicyRequest) -> PolicyDecision {
        let (decision, _) = self.evaluate_request_debug(request, false);
        decision
    }

    /// Evaluates an entire Chatybot PolicyRequest with optional debug tracing.
    pub fn evaluate_request_debug(
        &self,
        request: &PolicyRequest,
        debug: bool,
    ) -> (PolicyDecision, Vec<String>) {
        let mut trace = Vec::new();
        let user = self.resolve_user(request);

        if debug {
            trace.push(format!(
                "[RACF Debug] Begin request evaluation (Tool: '{}', User: '{}')",
                request.tool, user
            ));
            if let Some(groups) = self.user_groups.get(&user) {
                let mut sorted_grps: Vec<&String> = groups.iter().collect();
                sorted_grps.sort();
                let grp_str = sorted_grps
                    .iter()
                    .map(|s| s.as_str())
                    .collect::<Vec<_>>()
                    .join(", ");
                trace.push(format!(
                    "[RACF Debug] User '{}' connected groups: [{}]",
                    user, grp_str
                ));
            } else {
                trace.push(format!(
                    "[RACF Debug] User '{}' has no connected groups in RACF database",
                    user
                ));
            }
        }

        let mut evaluations: Vec<(ResourceClass, String, AccessLevel, String)> = Vec::new();

        // 1. Evaluate FACILITY class for the tool name
        let tool_name = &request.tool;
        let mut t_opt = if debug { Some(&mut trace) } else { None };
        let (tool_acc, tool_reason) =
            self.evaluate_resource_trace(&user, &ResourceClass::Facility, tool_name, &mut t_opt);
        evaluations.push((
            ResourceClass::Facility,
            tool_name.clone(),
            tool_acc,
            tool_reason,
        ));

        // 2. Evaluate DIR class if path-related parameters are present
        let path_keys = [
            "path",
            "filepath",
            "file_path",
            "target",
            "cwd",
            "directory",
            "dir",
            "filename",
            "destination",
            "source",
            "sourcefile",
            "destfile",
            "sourcepath",
            "destpath",
            "file",
        ];
        let mut sorted_param_keys: Vec<&String> = request.parameters.keys().collect();
        sorted_param_keys.sort();
        for key in sorted_param_keys {
            let key_lower = key.to_lowercase();
            let is_path_key = path_keys.contains(&key_lower.as_str())
                || key_lower.ends_with("path")
                || key_lower.ends_with("file")
                || key_lower.ends_with("dir")
                || key_lower.ends_with("target");
            if is_path_key {
                if let Some(val_str) = request.parameters.get(key).and_then(|v| v.as_str()) {
                    let mut candidate_paths = vec![val_str.to_string()];
                    for canon in canonicalize_path_if_exists(val_str) {
                        if !candidate_paths.contains(&canon) {
                            candidate_paths.push(canon);
                        }
                    }
                    for path_to_eval in candidate_paths {
                        let (dir_acc, dir_reason) =
                            self.evaluate_resource_trace(&user, &ResourceClass::Dir, &path_to_eval, &mut t_opt);
                        evaluations.push((
                            ResourceClass::Dir,
                            path_to_eval,
                            dir_acc,
                            dir_reason,
                        ));
                    }
                }
            }
        }

        // 3. Evaluate COMMAND class if tool is a command executor
        let tool_lower = tool_name.to_lowercase();
        let is_cmd_tool = tool_lower.contains("command")
            || tool_lower.contains("cmd")
            || tool_lower.contains("shell")
            || tool_lower.contains("exec")
            || tool_lower.contains("bash")
            || tool_lower.contains("terminal")
            || tool_lower.contains("subprocess")
            || tool_lower.contains("system");
        if is_cmd_tool {
            let cmd_keys = ["command", "cmd", "commandline", "CommandLine"];
            for key in &cmd_keys {
                if let Some(cmd_str) = request.parameters.get(*key).and_then(|v| v.as_str()) {
                    let (cmd_acc, cmd_reason) =
                        self.evaluate_resource_trace(&user, &ResourceClass::Command, cmd_str, &mut t_opt);
                    evaluations.push((
                        ResourceClass::Command,
                        cmd_str.to_string(),
                        cmd_acc,
                        cmd_reason,
                    ));
                }
            }
        }

        // 4. Evaluate CONTENT class (LLM Security Innovation: Payload & Content Inspection)
        if self.profiles.contains_key(&ResourceClass::Content) {
            let content_keys = [
                "content",
                "contents",
                "text",
                "codecontent",
                "code_content",
                "replacementcontent",
                "replacement_content",
                "targetcontent",
                "target_content",
                "data",
                "body",
                "payload",
                "patch",
                "diff",
            ];
            let mut candidate_contents: Vec<String> = Vec::new();
            for (key, val) in &request.parameters {
                let key_clean = key.to_lowercase().replace('_', "").replace('-', "");
                let is_content_key = content_keys
                    .iter()
                    .any(|ck| ck.replace('_', "") == key_clean)
                    || key_clean.ends_with("content")
                    || key_clean.ends_with("text")
                    || key_clean.ends_with("payload");

                if is_content_key {
                    if let Some(s) = val.as_str() {
                        candidate_contents.push(s.to_string());
                    }
                } else if key_clean == "replacementchunks" {
                    if let Some(arr) = val.as_array() {
                        for item in arr {
                            if let Some(obj) = item.as_object() {
                                for (chunk_k, chunk_v) in obj {
                                    let chunk_k_clean = chunk_k.to_lowercase().replace('_', "");
                                    if chunk_k_clean.contains("content") {
                                        if let Some(s) = chunk_v.as_str() {
                                            candidate_contents.push(s.to_string());
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            for content_snippet in candidate_contents {
                let (content_acc, content_reason) = self.evaluate_resource_trace(
                    &user,
                    &ResourceClass::Content,
                    &content_snippet,
                    &mut t_opt,
                );
                let display_snippet = if content_snippet.len() > 60 {
                    format!("{}...", &content_snippet[..60])
                } else {
                    content_snippet.clone()
                };
                evaluations.push((
                    ResourceClass::Content,
                    display_snippet,
                    content_acc,
                    content_reason,
                ));
            }
        }

        // 5. Evaluate PS class (Process & Task Control)
        if self.profiles.contains_key(&ResourceClass::Ps) {
            let is_ps_tool = tool_lower.contains("ps")
                || tool_lower.contains("kill")
                || tool_lower.contains("process")
                || tool_lower.contains("task")
                || tool_lower.contains("job");

            let ps_keys = [
                "process",
                "processname",
                "process_name",
                "proc",
                "pid",
                "targetpid",
                "target_pid",
                "taskid",
                "task_id",
                "jobid",
                "job_id",
            ];

            let mut candidate_ps: Vec<String> = Vec::new();
            for (key, val) in &request.parameters {
                let key_clean = key.to_lowercase().replace('_', "").replace('-', "");
                let is_ps_param = ps_keys.iter().any(|pk| pk.replace('_', "") == key_clean)
                    || key_clean.ends_with("pid")
                    || key_clean.ends_with("process")
                    || key_clean.ends_with("taskid");

                if is_ps_param {
                    if let Some(s) = val.as_str() {
                        candidate_ps.push(s.to_string());
                    } else if let Some(n) = val.as_i64() {
                        candidate_ps.push(n.to_string());
                    } else if let Some(n) = val.as_u64() {
                        candidate_ps.push(n.to_string());
                    }
                }
            }

            // Also inspect command arguments when running kill/pkill/killall
            if is_cmd_tool && candidate_ps.is_empty() {
                let cmd_keys = ["command", "cmd", "commandline", "CommandLine"];
                for key in &cmd_keys {
                    if let Some(cmd_str) = request.parameters.get(*key).and_then(|v| v.as_str()) {
                        let trimmed = cmd_str.trim();
                        let parts: Vec<&str> = trimmed.split_whitespace().collect();
                        if !parts.is_empty() {
                            let prog = parts[0];
                            if prog == "kill" || prog == "pkill" || prog == "killall" {
                                for arg in &parts[1..] {
                                    if !arg.starts_with('-') {
                                        candidate_ps.push(arg.to_string());
                                    }
                                }
                            }
                        }
                    }
                }
            }

            if is_ps_tool && candidate_ps.is_empty() {
                candidate_ps.push(tool_name.clone());
            }

            for ps_res in candidate_ps {
                let (ps_acc, ps_reason) =
                    self.evaluate_resource_trace(&user, &ResourceClass::Ps, &ps_res, &mut t_opt);
                evaluations.push((ResourceClass::Ps, ps_res, ps_acc, ps_reason));
            }
        }

        // Resolve overall verdict across all checks:
        // Any DENY -> DENY
        // Else any ASK -> ASK
        // Else -> ALLOW
        for (class, res, acc, reason) in &evaluations {
            if *acc == AccessLevel::Deny {
                let dec = PolicyDecision::deny(format!(
                    "RACF security violation on {}:{}. {}",
                    class, res, reason
                ));
                if debug {
                    trace.push(format!(
                        "[RACF Debug] Composite Verdict: DENY (Triggered by {}:{})",
                        class, res
                    ));
                }
                return (dec, trace);
            }
        }

        for (class, res, acc, reason) in &evaluations {
            if *acc == AccessLevel::Ask {
                let dec = PolicyDecision::ask(
                    format!("RACF authorization required on {}:{}. {}", class, res, reason),
                    "RACF Security Guard",
                    &format!("Authorization requested for user '{}' on {}: {}", user, class, res),
                    "medium",
                );
                if debug {
                    trace.push(format!(
                        "[RACF Debug] Composite Verdict: ASK (Triggered by {}:{})",
                        class, res
                    ));
                }
                return (dec, trace);
            }
        }

        // If all ALLOW:
        let summary_reason = evaluations
            .iter()
            .map(|(_, _, _, r)| r.as_str())
            .collect::<Vec<_>>()
            .join("; ");

        let dec = PolicyDecision::allow(if summary_reason.is_empty() {
            "RACF access permitted".to_string()
        } else {
            format!("RACF access permitted: {}", summary_reason)
        });
        if debug {
            trace.push("[RACF Debug] Composite Verdict: ALLOW (All checks passed)".to_string());
        }
        (dec, trace)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::parser::parse_racf_script;

    #[test]
    fn test_racf_group_and_user_precedence() {
        let script = r#"
            ADDGROUP DEVELOPER DATA('Developers')
            CONNECT alice GROUP(DEVELOPER)
            
            # Universal access is ASK, DEVELOPER gets ALLOW
            RDEFINE FACILITY git.* UACC(ASK)
            PERMIT git.* CLASS(FACILITY) ID(DEVELOPER) ACCESS(ALLOW)
            
            # Specific user override for bob
            PERMIT git.push CLASS(FACILITY) ID(bob) ACCESS(DENY)
        "#;
        let stmts = parse_racf_script(script).unwrap();
        let mut engine = RacfEngine::new();
        engine.load_statements(stmts);

        // alice is in DEVELOPER -> ALLOW
        let (acc, _) = engine.evaluate_resource("alice", &ResourceClass::Facility, "git.status");
        assert_eq!(acc, AccessLevel::Allow);

        // charlie is not in DEVELOPER -> UACC ASK
        let (acc, _) = engine.evaluate_resource("charlie", &ResourceClass::Facility, "git.status");
        assert_eq!(acc, AccessLevel::Ask);

        // bob has direct DENY on git.push
        let (acc, _) = engine.evaluate_resource("bob", &ResourceClass::Facility, "git.push");
        assert_eq!(acc, AccessLevel::Deny);
    }

    #[test]
    fn test_racf_directory_and_command_checks() {
        let script = r#"
            ADDGROUP DEVELOPER
            CONNECT jon GROUP(DEVELOPER)

            RDEFINE FACILITY run_command UACC(ALLOW)
            RDEFINE COMMAND git* UACC(ALLOW)
            RDEFINE COMMAND rm* UACC(DENY)
            RDEFINE COMMAND ps -ef* UACC(ALLOW)
            RDEFINE COMMAND ps -aef* UACC(DENY)
            RDEFINE DIR /etc/** UACC(DENY)
            RDEFINE DIR /workspace/** UACC(ALLOW)
        "#;
        let stmts = parse_racf_script(script).unwrap();
        let mut engine = RacfEngine::new();
        engine.load_statements(stmts);

        let mut req = PolicyRequest {
            tool: "run_command".to_string(),
            parameters: HashMap::new(),
            context: HashMap::new(),
            version: None,
            request_id: None,
            timestamp: None,
        };
        req.parameters.insert(
            "command".to_string(),
            serde_json::Value::String("git status".to_string()),
        );
        req.parameters.insert(
            "path".to_string(),
            serde_json::Value::String("/workspace/project".to_string()),
        );

        let decision = engine.evaluate_request(&req);
        assert_eq!(decision.status, "allow");

        // Attempt allowed ps -ef command
        req.parameters.insert(
            "command".to_string(),
            serde_json::Value::String("ps -ef | grep python".to_string()),
        );
        assert_eq!(engine.evaluate_request(&req).status, "allow");

        // Attempt blocked ps -aef command
        req.parameters.insert(
            "command".to_string(),
            serde_json::Value::String("ps -aef".to_string()),
        );
        assert_eq!(engine.evaluate_request(&req).status, "deny");

        // Attempt dangerous command
        req.parameters.insert(
            "command".to_string(),
            serde_json::Value::String("rm -rf /".to_string()),
        );
        let decision = engine.evaluate_request(&req);
        assert_eq!(decision.status, "deny");
    }

    #[test]
    fn test_racf_path_traversal_normalization() {
        let script = r#"
            RDEFINE FACILITY read_file UACC(ALLOW)
            RDEFINE DIR /etc/** UACC(DENY)
            RDEFINE DIR /var/log/** UACC(ALLOW)
        "#;
        let stmts = parse_racf_script(script).unwrap();
        let mut engine = RacfEngine::new();
        engine.load_statements(stmts);

        // Path traversal bypass attempt: /var/log/../../etc/passwd resolves to /etc/passwd
        let (acc, _) = engine.evaluate_resource("user", &ResourceClass::Dir, "/var/log/../../etc/passwd");
        assert_eq!(acc, AccessLevel::Deny);

        let (acc2, _) = engine.evaluate_resource("user", &ResourceClass::Dir, "/etc/../etc/shadow");
        assert_eq!(acc2, AccessLevel::Deny);
    }

    #[test]
    fn test_racf_tilde_expansion() {
        let script = r#"
            RDEFINE DIR ~/.ssh/** UACC(DENY)
            RDEFINE DIR ~/projects/** UACC(ALLOW)
        "#;
        let stmts = parse_racf_script(script).unwrap();
        let mut engine = RacfEngine::new();
        engine.load_statements(stmts);

        // Test with literal tilde path
        let (acc, _) = engine.evaluate_resource("user", &ResourceClass::Dir, "~/.ssh/id_rsa");
        assert_eq!(acc, AccessLevel::Deny);

        // Test with expanded home path if HOME/USERPROFILE is set
        if let Some(home) = std::env::var_os("HOME").or_else(|| std::env::var_os("USERPROFILE")) {
            let home_ssh = format!("{}/.ssh/id_rsa", home.to_string_lossy());
            let (acc_home, _) = engine.evaluate_resource("user", &ResourceClass::Dir, &home_ssh);
            assert_eq!(acc_home, AccessLevel::Deny);
        }
    }

    #[test]
    fn test_racf_keyword_class_syntax() {
        let script = r#"
            RDEFINE CLASS(FACILITY) git.* UACC(ASK)
            RDEFINE CLASS(DIR) /secret/** UACC(DENY)
        "#;
        let stmts = parse_racf_script(script).unwrap();
        let mut engine = RacfEngine::new();
        engine.load_statements(stmts);

        let (acc, _) = engine.evaluate_resource("user", &ResourceClass::Facility, "git.push");
        assert_eq!(acc, AccessLevel::Ask);

        let (acc_dir, _) = engine.evaluate_resource("user", &ResourceClass::Dir, "/secret/keys");
        assert_eq!(acc_dir, AccessLevel::Deny);
    }

    #[test]
    fn test_racf_content_payload_inspection() {
        let script = r#"
            RDEFINE FACILITY write_file UACC(ALLOW)
            RDEFINE DIR ./** UACC(ALLOW)

            # Block writing private keys or api tokens
            RDEFINE CONTENT *BEGIN*PRIVATE*KEY* UACC(DENY)
            RDEFINE CONTENT *api_key* UACC(DENY)
        "#;
        let stmts = parse_racf_script(script).unwrap();
        let mut engine = RacfEngine::new();
        engine.load_statements(stmts);

        // 1. Safe write passes
        let mut req_safe = PolicyRequest {
            tool: "write_file".to_string(),
            parameters: HashMap::new(),
            context: HashMap::new(),
            version: None,
            request_id: None,
            timestamp: None,
        };
        req_safe.parameters.insert("path".to_string(), serde_json::Value::String("hello.txt".to_string()));
        req_safe.parameters.insert("content".to_string(), serde_json::Value::String("Hello world from unit test".to_string()));
        let dec_safe = engine.evaluate_request(&req_safe);
        assert_eq!(dec_safe.status, "allow");

        // 2. Writing content with api_key is blocked
        let mut req_leak = PolicyRequest {
            tool: "write_file".to_string(),
            parameters: HashMap::new(),
            context: HashMap::new(),
            version: None,
            request_id: None,
            timestamp: None,
        };
        req_leak.parameters.insert("path".to_string(), serde_json::Value::String("app.env".to_string()));
        req_leak.parameters.insert("content".to_string(), serde_json::Value::String("export my_api_key=sk-123456789".to_string()));
        let dec_leak = engine.evaluate_request(&req_leak);
        assert_eq!(dec_leak.status, "deny");
        assert!(dec_leak.reason.contains("CONTENT"));

        // 3. Multi-line content with private key header is blocked
        let mut req_key = PolicyRequest {
            tool: "write_file".to_string(),
            parameters: HashMap::new(),
            context: HashMap::new(),
            version: None,
            request_id: None,
            timestamp: None,
        };
        req_key.parameters.insert("path".to_string(), serde_json::Value::String("id_rsa".to_string()));
        req_key.parameters.insert("content".to_string(), serde_json::Value::String("-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQ...\n-----END RSA PRIVATE KEY-----".to_string()));
        let dec_key = engine.evaluate_request(&req_key);
        assert_eq!(dec_key.status, "deny");
        assert!(dec_key.reason.contains("CONTENT"));
    }

    #[test]
    fn test_racf_default_deny_least_privilege() {
        let script = r#"
            ADDGROUP DEVELOPER DATA('Developers')
            CONNECT alice GROUP(DEVELOPER)

            RDEFINE FACILITY write_file UACC(ASK)
            PERMIT write_file CLASS(FACILITY) ID(DEVELOPER) ACCESS(ALLOW)

            # Global default deny
            RDEFINE DIR /** UACC(DENY)

            # Target blocks
            RDEFINE DIR ~/.ssh/** UACC(DENY)
            RDEFINE DIR **/*zaragoza* UACC(DENY)

            # Approved zones
            RDEFINE DIR ~/* UACC(DENY)
            PERMIT ~/* CLASS(DIR) ID(DEVELOPER) ACCESS(ALLOW)

            RDEFINE DIR ~/github/** UACC(DENY)
            PERMIT ~/github/** CLASS(DIR) ID(DEVELOPER) ACCESS(ALLOW)

            RDEFINE DIR ~/projects/** UACC(DENY)
            PERMIT ~/projects/** CLASS(DIR) ID(DEVELOPER) ACCESS(ALLOW)

            RDEFINE DIR ~/Downloads/** UACC(DENY)
            PERMIT ~/Downloads/** CLASS(DIR) ID(DEVELOPER) ACCESS(ALLOW)

            RDEFINE DIR **/scratch/** UACC(DENY)
            PERMIT **/scratch/** CLASS(DIR) ID(DEVELOPER) ACCESS(ALLOW)
        "#;
        let stmts = parse_racf_script(script).unwrap();
        let mut engine = RacfEngine::new();
        engine.load_statements(stmts);

        let mut req = PolicyRequest {
            tool: "write_file".to_string(),
            parameters: HashMap::new(),
            context: HashMap::new(),
            version: None,
            request_id: None,
            timestamp: None,
        };
        req.context.insert("user".to_string(), serde_json::Value::String("alice".to_string()));

        // 1. Outside approved areas -> DENY
        req.parameters.insert("path".to_string(), serde_json::Value::String("/var/log/test.log".to_string()));
        assert_eq!(engine.evaluate_request(&req).status, "deny");

        req.parameters.insert("path".to_string(), serde_json::Value::String("/tmp/test.txt".to_string()));
        assert_eq!(engine.evaluate_request(&req).status, "deny");

        // 2. Sensitive path inside home -> DENY
        let home = dirs_home().unwrap_or_else(|| "/Users/alice".to_string());
        req.parameters.insert("path".to_string(), serde_json::Value::String(format!("{}/.ssh/id_rsa", home)));
        assert_eq!(engine.evaluate_request(&req).status, "deny");

        // 3. Zaragoza pattern inside github and downloads -> DENY (leaf constraint beats directory wildcard)
        req.parameters.insert("path".to_string(), serde_json::Value::String(format!("{}/github/zaragoza.md", home)));
        assert_eq!(engine.evaluate_request(&req).status, "deny");

        req.parameters.insert("path".to_string(), serde_json::Value::String(format!("{}/Downloads/zaragoza.zip", home)));
        assert_eq!(engine.evaluate_request(&req).status, "deny");

        // 4. Approved areas for alice -> ALLOW
        req.parameters.insert("path".to_string(), serde_json::Value::String(format!("{}/notes.txt", home)));
        assert_eq!(engine.evaluate_request(&req).status, "allow");

        req.parameters.insert("path".to_string(), serde_json::Value::String(format!("{}/Downloads/manual.pdf", home)));
        assert_eq!(engine.evaluate_request(&req).status, "allow");

        req.parameters.insert("path".to_string(), serde_json::Value::String(format!("{}/github/my_repo/main.rs", home)));
        assert_eq!(engine.evaluate_request(&req).status, "allow");

        req.parameters.insert("path".to_string(), serde_json::Value::String(format!("{}/projects/app/Cargo.toml", home)));
        assert_eq!(engine.evaluate_request(&req).status, "allow");

        req.parameters.insert("path".to_string(), serde_json::Value::String("/anywhere/scratch/temp.c".to_string()));
        assert_eq!(engine.evaluate_request(&req).status, "allow");

        // 5. Unallowed subdirectories under home (Desktop, Documents) -> DENY
        req.parameters.insert("path".to_string(), serde_json::Value::String(format!("{}/Desktop/secret.txt", home)));
        assert_eq!(engine.evaluate_request(&req).status, "deny");

        req.parameters.insert("path".to_string(), serde_json::Value::String(format!("{}/Documents/taxes.pdf", home)));
        assert_eq!(engine.evaluate_request(&req).status, "deny");

        // 6. Unconnected user bob -> DENY on github
        req.context.insert("user".to_string(), serde_json::Value::String("bob".to_string()));
        req.parameters.insert("path".to_string(), serde_json::Value::String(format!("{}/github/my_repo/main.rs", home)));
        assert_eq!(engine.evaluate_request(&req).status, "deny");
    }

    #[test]
    fn test_racf_security_policy_self_protection() {
        let script = r#"
            ADDGROUP DEVELOPER DATA('Developers')
            CONNECT alice GROUP(DEVELOPER)

            RDEFINE FACILITY read_file UACC(ASK)
            PERMIT read_file CLASS(FACILITY) ID(DEVELOPER) ACCESS(ALLOW)
            RDEFINE FACILITY write_file UACC(ASK)
            PERMIT write_file CLASS(FACILITY) ID(DEVELOPER) ACCESS(ALLOW)

            # Global default deny
            RDEFINE DIR /** UACC(DENY)

            # Security policy files MUST be protected (DENY beats general approved workspaces)
            RDEFINE DIR **/*security.toml* UACC(DENY)
            RDEFINE DIR **/*racf* UACC(DENY)

            # Approved zones
            RDEFINE DIR ~/github/** UACC(DENY)
            PERMIT ~/github/** CLASS(DIR) ID(DEVELOPER) ACCESS(ALLOW)
            RDEFINE DIR ./** UACC(DENY)
            PERMIT ./** CLASS(DIR) ID(DEVELOPER) ACCESS(ALLOW)
        "#;
        let stmts = parse_racf_script(script).unwrap();
        let mut engine = RacfEngine::new();
        engine.load_statements(stmts);

        let mut req = PolicyRequest {
            tool: "write_file".to_string(),
            parameters: HashMap::new(),
            context: HashMap::new(),
            version: None,
            request_id: None,
            timestamp: None,
        };
        req.context.insert("user".to_string(), serde_json::Value::String("alice".to_string()));

        let home = dirs_home().unwrap_or_else(|| "/Users/alice".to_string());

        // 1. Regular file in github workspace is allowed
        req.parameters.insert("path".to_string(), serde_json::Value::String(format!("{}/github/app/main.rs", home)));
        assert_eq!(engine.evaluate_request(&req).status, "allow");

        // 2. Modifying security.toml in workspace is strictly DENIED
        req.parameters.insert("path".to_string(), serde_json::Value::String(format!("{}/github/app/security.toml", home)));
        let (dec, trace) = engine.evaluate_request_debug(&req, true);
        println!("TRACE:\n{}", trace.join("\n"));
        assert_eq!(dec.status, "deny");

        // 3. Modifying relative security.toml is strictly DENIED
        req.parameters.insert("path".to_string(), serde_json::Value::String("./security.toml".to_string()));
        assert_eq!(engine.evaluate_request(&req).status, "deny");

        // 4. Modifying any file with racf in name/path is strictly DENIED
        req.parameters.insert("path".to_string(), serde_json::Value::String(format!("{}/github/app/security.racf", home)));
        assert_eq!(engine.evaluate_request(&req).status, "deny");

        req.parameters.insert("path".to_string(), serde_json::Value::String("tools/racf-guard/examples/security.racf".to_string()));
        assert_eq!(engine.evaluate_request(&req).status, "deny");

        req.parameters.insert("path".to_string(), serde_json::Value::String("rules.racf".to_string()));
        assert_eq!(engine.evaluate_request(&req).status, "deny");

        // 5. Reading security policy files is also strictly DENIED
        req.tool = "read_file".to_string();
        req.parameters.insert("path".to_string(), serde_json::Value::String("security.toml".to_string()));
        assert_eq!(engine.evaluate_request(&req).status, "deny");

        req.parameters.insert("path".to_string(), serde_json::Value::String("security.racf".to_string()));
        assert_eq!(engine.evaluate_request(&req).status, "deny");
    }

    #[test]
    fn test_racf_ps_resource_class_evaluation() {
        let mut engine = RacfEngine::new();
        let policy = r#"
            ADDGROUP DEVELOPER DATA('Developers')
            CONNECT alice GROUP(DEVELOPER)
            RDEFINE FACILITY * UACC(ALLOW)
            RDEFINE COMMAND * UACC(ALLOW)
            RDEFINE PS * UACC(DENY)
            RDEFINE PS 1 UACC(DENY)
            RDEFINE PS sys_* UACC(DENY)
            PERMIT worker_* CLASS(PS) ID(DEVELOPER) ACCESS(ALLOW)
            PERMIT 12345 CLASS(PS) ID(DEVELOPER) ACCESS(ALLOW)
        "#;
        let stmts = parse_racf_script(policy).unwrap();
        engine.load_statements(stmts);

        // 1. Worker task allowed
        let mut req = PolicyRequest {
            tool: "manage_task".to_string(),
            parameters: HashMap::new(),
            context: HashMap::new(),
            version: None,
            request_id: None,
            timestamp: None,
        };
        req.context.insert("user".to_string(), serde_json::Value::String("alice".to_string()));
        req.parameters.insert("task_id".to_string(), serde_json::Value::String("worker_job1".to_string()));
        assert_eq!(engine.evaluate_request(&req).status, "allow");

        // 2. Sys task denied
        req.parameters.insert("task_id".to_string(), serde_json::Value::String("sys_daemon".to_string()));
        assert_eq!(engine.evaluate_request(&req).status, "deny");

        // 3. Process PID 1 via command kill -9 1 denied
        let mut req_cmd = PolicyRequest {
            tool: "run_command".to_string(),
            parameters: HashMap::new(),
            context: HashMap::new(),
            version: None,
            request_id: None,
            timestamp: None,
        };
        req_cmd.context.insert("user".to_string(), serde_json::Value::String("alice".to_string()));
        req_cmd.parameters.insert("command".to_string(), serde_json::Value::String("kill -9 1".to_string()));
        assert_eq!(engine.evaluate_request(&req_cmd).status, "deny");

        // 4. Allowed PID 12345
        req_cmd.parameters.insert("command".to_string(), serde_json::Value::String("kill -15 12345".to_string()));
        assert_eq!(engine.evaluate_request(&req_cmd).status, "allow");
    }
}

