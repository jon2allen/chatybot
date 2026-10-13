use crate::ast::{AccessLevel, ResourceClass, Statement};

/// Parse a string of RACF statements line-by-line.
pub fn parse_racf_script(input: &str) -> Result<Vec<Statement>, String> {
    let mut statements = Vec::new();
    for (line_idx, raw_line) in input.lines().enumerate() {
        let line_num = line_idx + 1;
        let line = raw_line.trim();

        // Skip blank lines or comments (#, *, /*)
        if line.is_empty()
            || line.starts_with('#')
            || line.starts_with('*')
            || line.starts_with("//")
            || line.starts_with("/*")
        {
            continue;
        }

        match parse_line(line, line_num) {
            Ok(stmt) => statements.push(stmt),
            Err(e) => return Err(format!("Line {}: {}", line_num, e)),
        }
    }
    Ok(statements)
}

fn parse_line(line: &str, line_num: usize) -> Result<Statement, String> {
    let tokens = tokenize_line(line);
    if tokens.is_empty() {
        return Err("No tokens found".to_string());
    }

    let cmd = tokens[0].to_uppercase();
    match cmd.as_str() {
        "ADDGROUP" => parse_addgroup(&tokens[1..], line_num),
        "CONNECT" => parse_connect(&tokens[1..], line_num),
        "RDEFINE" => parse_rdefine(&tokens[1..], line_num),
        "PERMIT" => parse_permit(&tokens[1..], line_num),
        "SETROPTS" => Ok(Statement::SetrOpts {
            raw: line.to_string(),
        }),
        _ => Err(format!("Unknown command '{}'", cmd)),
    }
}

/// Tokenize a line respecting parens and quotes:
/// e.g. `PERMIT git.* CLASS(FACILITY) ID(DEVELOPER) ACCESS(ALLOW)`
/// -> `["PERMIT", "git.*", "CLASS(FACILITY)", "ID(DEVELOPER)", "ACCESS(ALLOW)"]`
fn tokenize_line(line: &str) -> Vec<String> {
    let mut tokens = Vec::new();
    let mut current = String::new();
    let mut in_paren = 0;
    let mut in_single_quote = false;
    let mut in_double_quote = false;

    for ch in line.chars() {
        match ch {
            '\'' if !in_double_quote => {
                in_single_quote = !in_single_quote;
                current.push(ch);
            }
            '"' if !in_single_quote => {
                in_double_quote = !in_double_quote;
                current.push(ch);
            }
            '(' if !in_single_quote && !in_double_quote => {
                in_paren += 1;
                current.push(ch);
            }
            ')' if !in_single_quote && !in_double_quote => {
                if in_paren > 0 {
                    in_paren -= 1;
                }
                current.push(ch);
            }
            c if c.is_whitespace() && in_paren == 0 && !in_single_quote && !in_double_quote => {
                if !current.is_empty() {
                    tokens.push(current);
                    current = String::new();
                }
            }
            c => current.push(c),
        }
    }
    if !current.is_empty() {
        tokens.push(current);
    }
    tokens
}

fn clean_token(token: &str) -> String {
    token.trim().trim_matches('\'').trim_matches('"').to_string()
}

/// Extracts value from `KEYWORD(value)`
fn extract_kw_arg(token: &str, keyword: &str) -> Option<String> {
    let upper = token.to_uppercase();
    let prefix = format!("{}(", keyword.to_uppercase());
    if upper.starts_with(&prefix) && token.ends_with(')') {
        let inside = &token[prefix.len()..token.len() - 1];
        // Strip single quotes if present
        let trimmed = inside.trim();
        if trimmed.starts_with('\'') && trimmed.ends_with('\'') && trimmed.len() >= 2 {
            Some(trimmed[1..trimmed.len() - 1].to_string())
        } else {
            Some(trimmed.to_string())
        }
    } else {
        None
    }
}

// ADDGROUP <GROUP> [DATA('<DESC>')]
fn parse_addgroup(args: &[String], line_num: usize) -> Result<Statement, String> {
    if args.is_empty() {
        return Err(format!("ADDGROUP requires group name on line {}", line_num));
    }
    let group = args[0].trim().to_string();
    let mut data = None;
    for arg in &args[1..] {
        if let Some(val) = extract_kw_arg(arg, "DATA") {
            data = Some(val);
        }
    }
    Ok(Statement::AddGroup { group, data })
}

// CONNECT <USER> GROUP(<GROUP>)
fn parse_connect(args: &[String], line_num: usize) -> Result<Statement, String> {
    if args.is_empty() {
        return Err(format!("CONNECT requires user name on line {}", line_num));
    }
    let user = args[0].trim().to_string();
    let mut group = None;
    for arg in &args[1..] {
        if let Some(val) = extract_kw_arg(arg, "GROUP") {
            group = Some(val);
        }
    }
    let group = group.ok_or_else(|| format!("CONNECT missing GROUP(...) on line {}", line_num))?;
    Ok(Statement::Connect { user, group })
}

// RDEFINE <CLASS> <PROFILE> [UACC(<ACCESS>)]
// Also supports: RDEFINE <PROFILE> CLASS(<CLASS>) [UACC(<ACCESS>)]
// and RDEFINE CLASS(<CLASS>) <PROFILE> [UACC(<ACCESS>)]
fn parse_rdefine(args: &[String], line_num: usize) -> Result<Statement, String> {
    if args.is_empty() {
        return Err(format!("RDEFINE requires arguments on line {}", line_num));
    }
    let mut class: Option<ResourceClass> = None;
    let mut profile: Option<String> = None;
    let mut uacc = AccessLevel::Deny;

    for arg in args {
        if let Some(val) = extract_kw_arg(arg, "CLASS") {
            class = Some(ResourceClass::from_str(&val));
        } else if let Some(val) = extract_kw_arg(arg, "UACC") {
            uacc = AccessLevel::from_str(&val)
                .ok_or_else(|| format!("Unknown UACC value '{}' on line {}", val, line_num))?;
        } else {
            // Positional argument
            let cleaned = clean_token(arg);
            if class.is_none() && profile.is_none() {
                let candidate = ResourceClass::from_str(&cleaned);
                if matches!(
                    candidate,
                    ResourceClass::Facility
                        | ResourceClass::Dir
                        | ResourceClass::Command
                        | ResourceClass::Ps
                        | ResourceClass::Content
                ) {
                    class = Some(candidate);
                } else {
                    profile = Some(cleaned);
                }
            } else if profile.is_none() {
                profile = Some(cleaned);
            } else if class.is_none() {
                class = Some(ResourceClass::from_str(&cleaned));
            } else if let Some(existing) = profile.as_mut() {
                // Multi-word positional profile name (e.g. `ps -ef*`)
                existing.push(' ');
                existing.push_str(&cleaned);
            }
        }
    }

    let class = class.ok_or_else(|| format!("RDEFINE missing CLASS on line {}", line_num))?;
    let profile = profile.ok_or_else(|| format!("RDEFINE missing profile on line {}", line_num))?;

    Ok(Statement::RDefine {
        class,
        profile,
        uacc,
    })
}

// PERMIT <PROFILE> CLASS(<CLASS>) ID(<ID>) ACCESS(<ACCESS>)
fn parse_permit(args: &[String], line_num: usize) -> Result<Statement, String> {
    if args.is_empty() {
        return Err(format!("PERMIT requires profile on line {}", line_num));
    }
    let mut profile_parts = Vec::new();
    let mut class = None;
    let mut id = None;
    let mut access = AccessLevel::Allow;

    for arg in args {
        if let Some(val) = extract_kw_arg(arg, "CLASS") {
            class = Some(ResourceClass::from_str(&val));
        } else if let Some(val) = extract_kw_arg(arg, "ID") {
            id = Some(val);
        } else if let Some(val) = extract_kw_arg(arg, "ACCESS") {
            access = AccessLevel::from_str(&val)
                .ok_or_else(|| format!("Unknown ACCESS value '{}' on line {}", val, line_num))?;
        } else {
            profile_parts.push(clean_token(arg));
        }
    }

    if profile_parts.is_empty() {
        return Err(format!("PERMIT missing profile on line {}", line_num));
    }
    let profile = profile_parts.join(" ");

    let class = class.ok_or_else(|| format!("PERMIT missing CLASS(...) on line {}", line_num))?;
    let id = id.ok_or_else(|| format!("PERMIT missing ID(...) on line {}", line_num))?;

    Ok(Statement::Permit {
        profile,
        class,
        id,
        access,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_comments_and_addgroup() {
        let script = r#"
            # Comment
            ADDGROUP DEVELOPER DATA('Engineering team')
            CONNECT jon2allen GROUP(DEVELOPER)
        "#;
        let stmts = parse_racf_script(script).unwrap();
        assert_eq!(stmts.len(), 2);
        assert_eq!(
            stmts[0],
            Statement::AddGroup {
                group: "DEVELOPER".to_string(),
                data: Some("Engineering team".to_string())
            }
        );
        assert_eq!(
            stmts[1],
            Statement::Connect {
                user: "jon2allen".to_string(),
                group: "DEVELOPER".to_string()
            }
        );
    }

    #[test]
    fn test_parse_rdefine_and_permit() {
        let script = r#"
            RDEFINE FACILITY git.* UACC(ASK)
            PERMIT git.* CLASS(FACILITY) ID(DEVELOPER) ACCESS(ALLOW)
            PERMIT git.status CLASS(FACILITY) ID(jon2allen) ACCESS(ALLOW)
        "#;
        let stmts = parse_racf_script(script).unwrap();
        assert_eq!(stmts.len(), 3);
        assert_eq!(
            stmts[0],
            Statement::RDefine {
                class: ResourceClass::Facility,
                profile: "git.*".to_string(),
                uacc: AccessLevel::Ask
            }
        );
        assert_eq!(
            stmts[1],
            Statement::Permit {
                profile: "git.*".to_string(),
                class: ResourceClass::Facility,
                id: "DEVELOPER".to_string(),
                access: AccessLevel::Allow
            }
        );
    }
}
