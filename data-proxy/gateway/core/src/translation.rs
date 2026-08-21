use serde::{Deserialize, Serialize};

use crate::{
    map_column_type, Column, DialectParser, GatewayCommand, GatewayError, GatewayResponse,
    GatewayResult, GatewayValue, ProtocolKind,
};

/// Controlled cross-protocol translation policy.
///
/// Default is disabled. When enabled, only an explicitly supported SQL subset
/// may cross dialects; everything else fails with a clear error.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct TranslationPolicyConfig {
    pub name: String,
    /// Must be true to allow cross-protocol access.
    #[serde(default)]
    pub enabled: bool,
    pub frontend_protocol: ProtocolKind,
    pub backend_protocol: ProtocolKind,
    /// Allowed statement kinds for this direction. Empty means default subset.
    #[serde(default)]
    pub allowed_statements: Vec<TranslationStatementKind>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TranslationStatementKind {
    Select,
    Insert,
    Update,
    Delete,
}

impl TranslationStatementKind {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Select => "select",
            Self::Insert => "insert",
            Self::Update => "update",
            Self::Delete => "delete",
        }
    }

    pub fn from_keyword(keyword: &str) -> Option<Self> {
        match keyword {
            "SELECT" | "WITH" | "VALUES" | "TABLE" | "SHOW" | "EXPLAIN" | "DESCRIBE" | "DESC" => {
                Some(Self::Select)
            }
            "INSERT" => Some(Self::Insert),
            "UPDATE" => Some(Self::Update),
            "DELETE" => Some(Self::Delete),
            _ => None,
        }
    }
}

impl Default for TranslationPolicyConfig {
    fn default() -> Self {
        Self {
            name: String::new(),
            enabled: false,
            frontend_protocol: ProtocolKind::MySql,
            backend_protocol: ProtocolKind::PostgreSql,
            allowed_statements: default_allowed_statements(),
        }
    }
}

pub fn default_allowed_statements() -> Vec<TranslationStatementKind> {
    vec![
        TranslationStatementKind::Select,
        TranslationStatementKind::Insert,
        TranslationStatementKind::Update,
        TranslationStatementKind::Delete,
    ]
}

/// Validate a full gateway command for a cross-protocol hop.
///
/// SQL-bearing commands are checked against the subset and rewritten for the
/// backend dialect. Statement lifecycle commands are gateway-local and pass
/// through after the translation policy itself has been validated.
pub fn prepare_cross_protocol_command(
    policy: &TranslationPolicyConfig,
    command: GatewayCommand,
    dialect: &dyn DialectParser,
) -> GatewayResult<GatewayCommand> {
    match command {
        GatewayCommand::Prepare { sql } => {
            check_translation_sql(policy, &sql, dialect)?;
            let sql =
                rewrite_sql_for_backend(&sql, &policy.frontend_protocol, &policy.backend_protocol)?;
            Ok(GatewayCommand::Prepare { sql })
        }
        GatewayCommand::Execute { statement_id, parameters } => {
            validate_translation_policy(policy, dialect)?;
            Ok(GatewayCommand::Execute { statement_id, parameters })
        }
        GatewayCommand::CloseStatement { statement_id } => {
            validate_translation_policy(policy, dialect)?;
            Ok(GatewayCommand::CloseStatement { statement_id })
        }
        GatewayCommand::DescribeSql { sql } => {
            check_translation_sql(policy, &sql, dialect)?;
            let sql =
                rewrite_sql_for_backend(&sql, &policy.frontend_protocol, &policy.backend_protocol)?;
            Ok(GatewayCommand::DescribeSql { sql })
        }
        GatewayCommand::Query { sql } => {
            check_translation_sql(policy, &sql, dialect)?;
            let rewritten =
                rewrite_sql_for_backend(&sql, &policy.frontend_protocol, &policy.backend_protocol)?;
            Ok(GatewayCommand::Query { sql: rewritten })
        }
        GatewayCommand::QueryParams { sql, parameters } => {
            check_translation_sql(policy, &sql, dialect)?;
            let (sql, parameters) = rewrite_sql_and_parameters_for_backend(
                &sql,
                parameters,
                &policy.frontend_protocol,
                &policy.backend_protocol,
            )?;
            Ok(GatewayCommand::QueryParams { sql, parameters })
        }
        GatewayCommand::UseDatabase { .. }
        | GatewayCommand::Begin
        | GatewayCommand::Commit
        | GatewayCommand::Rollback
        | GatewayCommand::Ping
        | GatewayCommand::Quit
        | GatewayCommand::ClientWire { .. }
        | GatewayCommand::PgBackendSync => Ok(command),
    }
}

/// Map resultset column types from backend dialect to frontend dialect.
pub fn map_response_types(
    response: GatewayResponse,
    backend: &ProtocolKind,
    frontend: &ProtocolKind,
) -> GatewayResponse {
    if backend == frontend {
        return response;
    }
    match response {
        GatewayResponse::ResultSet { columns, rows } => {
            let columns = map_columns(columns, backend, frontend);
            GatewayResponse::ResultSet { columns, rows }
        }
        GatewayResponse::TaggedResultSet { columns, rows, tag } => {
            let columns = map_columns(columns, backend, frontend);
            GatewayResponse::TaggedResultSet { columns, rows, tag }
        }
        GatewayResponse::Prepared { statement_id, parameter_count, columns } => {
            GatewayResponse::Prepared {
                statement_id,
                parameter_count,
                columns: map_columns(columns, backend, frontend),
            }
        }
        GatewayResponse::RowDescription { columns } => {
            GatewayResponse::RowDescription { columns: map_columns(columns, backend, frontend) }
        }
        other => other,
    }
}

fn map_columns(
    columns: Vec<Column>,
    backend: &ProtocolKind,
    frontend: &ProtocolKind,
) -> Vec<Column> {
    columns
        .into_iter()
        .map(|column| Column {
            name: column.name,
            data_type: map_column_type(&column.data_type, backend, frontend),
        })
        .collect()
}

/// Validate and classify one SQL statement for a cross-protocol hop.
pub fn check_translation_sql(
    policy: &TranslationPolicyConfig,
    sql: &str,
    dialect: &dyn DialectParser,
) -> GatewayResult<TranslationStatementKind> {
    validate_translation_policy(policy, dialect)?;

    let upper = sql.trim_start().to_ascii_uppercase();
    reject_unsupported_constructs(policy, &upper)?;

    let keyword = dialect.leading_keyword(sql).ok_or_else(|| {
        GatewayError::Unsupported(format!(
            "translation policy '{}': empty or unparseable SQL is not supported for {} -> {}",
            policy.name, policy.frontend_protocol, policy.backend_protocol
        ))
    })?;

    let kind = TranslationStatementKind::from_keyword(&keyword).ok_or_else(|| {
        GatewayError::Unsupported(format!(
            "translation policy '{}': statement kind '{}' is not in the supported subset for {} -> {} (allowed: {})",
            policy.name,
            keyword,
            policy.frontend_protocol,
            policy.backend_protocol,
            format_allowed(policy)
        ))
    })?;

    let allowed = if policy.allowed_statements.is_empty() {
        default_allowed_statements()
    } else {
        policy.allowed_statements.clone()
    };
    if !allowed.contains(&kind) {
        return Err(GatewayError::Unsupported(format!(
            "translation policy '{}': '{}' is not allowed (allowed: {})",
            policy.name,
            kind.as_str(),
            format_allowed(policy)
        )));
    }

    Ok(kind)
}

fn validate_translation_policy(
    policy: &TranslationPolicyConfig,
    dialect: &dyn DialectParser,
) -> GatewayResult<()> {
    if !policy.enabled {
        return Err(GatewayError::Configuration(format!(
            "translation policy '{}' is disabled; cross-protocol access is not allowed",
            policy.name
        )));
    }
    if policy.frontend_protocol == policy.backend_protocol {
        return Err(GatewayError::Configuration(format!(
            "translation policy '{}' has identical frontend/backend protocol '{}'",
            policy.name, policy.frontend_protocol
        )));
    }
    if dialect.dialect() != policy.frontend_protocol {
        return Err(GatewayError::Configuration(format!(
            "translation policy '{}' expects frontend protocol '{}', got '{:?}'",
            policy.name,
            policy.frontend_protocol,
            dialect.dialect()
        )));
    }
    Ok(())
}

/// Conservative SQL rewrite for the supported subset.
///
/// Only applies known-safe mechanical transforms. Unsupported vendor syntax is
/// rejected earlier by [`check_translation_sql`].
pub fn rewrite_sql_for_backend(
    sql: &str,
    frontend: &ProtocolKind,
    backend: &ProtocolKind,
) -> GatewayResult<String> {
    if frontend == backend {
        return Ok(sql.to_owned());
    }

    match (frontend, backend) {
        (ProtocolKind::MySql, ProtocolKind::PostgreSql) => rewrite_mysql_to_postgresql(sql),
        (ProtocolKind::PostgreSql, ProtocolKind::MySql) => rewrite_postgresql_to_mysql(sql),
        _ => Ok(sql.to_owned()),
    }
}

fn rewrite_sql_and_parameters_for_backend(
    sql: &str,
    parameters: Vec<GatewayValue>,
    frontend: &ProtocolKind,
    backend: &ProtocolKind,
) -> GatewayResult<(String, Vec<GatewayValue>)> {
    match (frontend, backend) {
        (ProtocolKind::MySql, ProtocolKind::PostgreSql) => {
            let (sql, references) = rewrite_mysql_placeholders(sql)?;
            let parameter_count = references.len();
            if parameter_count != parameters.len() {
                return Err(placeholder_error(format!(
                    "MySQL query expects {parameter_count} parameters, got {}",
                    parameters.len()
                )));
            }
            let mut sql = convert_backticks_to_double_quotes(&sql);
            sql = replace_ifnull_with_coalesce(&sql);
            sql = rewrite_mysql_limit_offset(&sql);
            Ok((sql, parameters))
        }
        (ProtocolKind::PostgreSql, ProtocolKind::MySql) => {
            let (sql, parameters) = rewrite_placeholders_pg_to_mysql(sql, &parameters)?;
            Ok((convert_double_quotes_to_backticks(&sql), parameters))
        }
        _ => Ok((sql.to_owned(), parameters)),
    }
}

fn rewrite_mysql_to_postgresql(sql: &str) -> GatewayResult<String> {
    let mut out = rewrite_placeholders_mysql_to_pg(sql)?;
    out = convert_backticks_to_double_quotes(&out);
    out = replace_ifnull_with_coalesce(&out);
    out = rewrite_mysql_limit_offset(&out);
    Ok(out)
}

fn rewrite_postgresql_to_mysql(sql: &str) -> GatewayResult<String> {
    // Prefer MySQL-native identifiers; COALESCE / LIMIT OFFSET are portable.
    let (sql, _) = rewrite_pg_placeholders(sql)?;
    Ok(convert_double_quotes_to_backticks(&sql))
}

/// Convert MySQL positional placeholders to PostgreSQL numbered placeholders.
///
/// Only SQL tokens are rewritten; quoted strings/identifiers, dollar-quoted
/// bodies, and comments are copied byte-for-byte.
pub fn rewrite_placeholders_mysql_to_pg(sql: &str) -> GatewayResult<String> {
    rewrite_mysql_placeholders(sql).map(|(sql, _)| sql)
}

/// Convert PostgreSQL numbered placeholders to MySQL positional placeholders
/// and expand/reorder parameter values in placeholder occurrence order.
pub fn rewrite_placeholders_pg_to_mysql(
    sql: &str,
    parameters: &[GatewayValue],
) -> GatewayResult<(String, Vec<GatewayValue>)> {
    let (sql, references) = rewrite_pg_placeholders(sql)?;
    let expected = references.iter().copied().max().unwrap_or(0);
    if expected != parameters.len() {
        return Err(placeholder_error(format!(
            "PostgreSQL query expects {expected} parameters, got {}",
            parameters.len()
        )));
    }
    let reordered = references.into_iter().map(|index| parameters[index - 1].clone()).collect();
    Ok((sql, reordered))
}

fn rewrite_mysql_placeholders(sql: &str) -> GatewayResult<(String, Vec<usize>)> {
    rewrite_placeholder_tokens(sql, PlaceholderKind::MySqlQuestion)
}

fn rewrite_pg_placeholders(sql: &str) -> GatewayResult<(String, Vec<usize>)> {
    let (sql, references) = rewrite_placeholder_tokens(sql, PlaceholderKind::PostgreSqlNumbered)?;
    let max = references.iter().copied().max().unwrap_or(0);
    if max > 0 {
        let mut seen = vec![false; max + 1];
        for index in &references {
            seen[*index] = true;
        }
        if let Some(missing) = (1..=max).find(|index| !seen[*index]) {
            return Err(placeholder_error(format!(
                "PostgreSQL placeholder index gap: ${missing} is not referenced"
            )));
        }
    }
    Ok((sql, references))
}

#[derive(Clone, Copy)]
enum PlaceholderKind {
    MySqlQuestion,
    PostgreSqlNumbered,
}

fn rewrite_placeholder_tokens(
    sql: &str,
    kind: PlaceholderKind,
) -> GatewayResult<(String, Vec<usize>)> {
    let bytes = sql.as_bytes();
    let mut out = String::with_capacity(sql.len());
    let mut references = Vec::new();
    let mut mysql_count = 0usize;
    let mut i = 0usize;

    while i < bytes.len() {
        if matches!(bytes[i], b'\'' | b'"' | b'`') {
            let end = quoted_end(sql, i, bytes[i])?;
            out.push_str(&sql[i..end]);
            i = end;
            continue;
        }
        if bytes[i] == b'-' && bytes.get(i + 1) == Some(&b'-') {
            let end = line_comment_end(sql, i + 2);
            out.push_str(&sql[i..end]);
            i = end;
            continue;
        }
        if bytes[i] == b'#' {
            let end = line_comment_end(sql, i + 1);
            out.push_str(&sql[i..end]);
            i = end;
            continue;
        }
        if bytes[i] == b'/' && bytes.get(i + 1) == Some(&b'*') {
            let end = block_comment_end(sql, i)?;
            out.push_str(&sql[i..end]);
            i = end;
            continue;
        }
        if bytes[i] == b'$' {
            if let Some(delimiter_end) = dollar_quote_delimiter_end(sql, i) {
                let delimiter = &sql[i..delimiter_end];
                let body_start = delimiter_end;
                let close = sql[body_start..].find(delimiter).ok_or_else(|| {
                    placeholder_error(format!("unterminated dollar quote {delimiter}"))
                })?;
                let end = body_start + close + delimiter.len();
                out.push_str(&sql[i..end]);
                i = end;
                continue;
            }
        }

        match kind {
            PlaceholderKind::MySqlQuestion if bytes[i] == b'?' => {
                mysql_count = mysql_count
                    .checked_add(1)
                    .ok_or_else(|| placeholder_error("too many MySQL placeholders".to_owned()))?;
                if mysql_count > u16::MAX as usize {
                    return Err(placeholder_error(format!(
                        "MySQL placeholder count exceeds {}",
                        u16::MAX
                    )));
                }
                out.push('$');
                out.push_str(&mysql_count.to_string());
                references.push(mysql_count);
                i += 1;
            }
            PlaceholderKind::PostgreSqlNumbered
                if bytes[i] == b'$' && bytes.get(i + 1).is_some_and(u8::is_ascii_digit) =>
            {
                if i > 0 && is_ident_byte(bytes[i - 1]) {
                    return Err(placeholder_error(
                        "PostgreSQL placeholder must be token-delimited".to_owned(),
                    ));
                }
                let mut j = i + 1;
                let mut index = 0usize;
                while j < bytes.len() && bytes[j].is_ascii_digit() {
                    index = index
                        .checked_mul(10)
                        .and_then(|value| value.checked_add((bytes[j] - b'0') as usize))
                        .ok_or_else(|| {
                            placeholder_error("PostgreSQL placeholder index overflow".to_owned())
                        })?;
                    j += 1;
                }
                if index == 0 || index > u16::MAX as usize {
                    return Err(placeholder_error(format!(
                        "PostgreSQL placeholder index ${index} is outside 1..={}",
                        u16::MAX
                    )));
                }
                if j < bytes.len() && is_ident_byte(bytes[j]) {
                    return Err(placeholder_error(
                        "PostgreSQL placeholder must be token-delimited".to_owned(),
                    ));
                }
                out.push('?');
                references.push(index);
                i = j;
            }
            _ => {
                let len = sql[i..].chars().next().expect("valid UTF-8").len_utf8();
                out.push_str(&sql[i..i + len]);
                i += len;
            }
        }
    }

    Ok((out, references))
}

fn quoted_end(sql: &str, start: usize, quote: u8) -> GatewayResult<usize> {
    let bytes = sql.as_bytes();
    let mut i = start + 1;
    while i < bytes.len() {
        if bytes[i] == b'\\' && i + 1 < bytes.len() {
            i += 1 + sql[i + 1..].chars().next().expect("valid UTF-8").len_utf8();
            continue;
        }
        if bytes[i] == quote {
            if bytes.get(i + 1) == Some(&quote) {
                i += 2;
                continue;
            }
            return Ok(i + 1);
        }
        i += sql[i..].chars().next().expect("valid UTF-8").len_utf8();
    }
    Err(placeholder_error(format!("unterminated {} quote", quote as char)))
}

fn line_comment_end(sql: &str, start: usize) -> usize {
    sql[start..].find('\n').map_or(sql.len(), |offset| start + offset + 1)
}

fn block_comment_end(sql: &str, start: usize) -> GatewayResult<usize> {
    let bytes = sql.as_bytes();
    let mut depth = 1usize;
    let mut i = start + 2;
    while i + 1 < bytes.len() {
        if bytes[i] == b'/' && bytes[i + 1] == b'*' {
            depth += 1;
            i += 2;
        } else if bytes[i] == b'*' && bytes[i + 1] == b'/' {
            depth -= 1;
            i += 2;
            if depth == 0 {
                return Ok(i);
            }
        } else {
            i += sql[i..].chars().next().expect("valid UTF-8").len_utf8();
        }
    }
    Err(placeholder_error("unterminated block comment".to_owned()))
}

fn dollar_quote_delimiter_end(sql: &str, start: usize) -> Option<usize> {
    let bytes = sql.as_bytes();
    let first = *bytes.get(start + 1)?;
    if first == b'$' {
        return Some(start + 2);
    }
    if !(first.is_ascii_alphabetic() || first == b'_') {
        return None;
    }
    let mut i = start + 2;
    while i < bytes.len() && (bytes[i].is_ascii_alphanumeric() || bytes[i] == b'_') {
        i += 1;
    }
    (bytes.get(i) == Some(&b'$')).then_some(i + 1)
}

fn placeholder_error(message: String) -> GatewayError {
    GatewayError::Protocol(format!("cross-protocol placeholder rewrite: {message}"))
}

fn convert_double_quotes_to_backticks(sql: &str) -> String {
    let bytes = sql.as_bytes();
    let mut out = String::with_capacity(sql.len());
    let mut i = 0;
    let mut in_single = false;

    while i < bytes.len() {
        let c = bytes[i] as char;
        if in_single {
            out.push(c);
            if c == '\'' {
                if i + 1 < bytes.len() && bytes[i + 1] == b'\'' {
                    out.push('\'');
                    i += 2;
                    continue;
                }
                in_single = false;
            }
            i += 1;
            continue;
        }

        match c {
            '\'' => {
                in_single = true;
                out.push(c);
                i += 1;
            }
            '"' => {
                // Convert "ident" -> `ident`, doubling internal backticks.
                i += 1;
                out.push('`');
                while i < bytes.len() {
                    let ch = bytes[i] as char;
                    if ch == '"' {
                        if i + 1 < bytes.len() && bytes[i + 1] == b'"' {
                            out.push('"');
                            i += 2;
                            continue;
                        }
                        i += 1;
                        break;
                    }
                    if ch == '`' {
                        out.push('`');
                        out.push('`');
                    } else {
                        out.push(ch);
                    }
                    i += 1;
                }
                out.push('`');
            }
            _ => {
                out.push(c);
                i += 1;
            }
        }
    }
    out
}

fn convert_backticks_to_double_quotes(sql: &str) -> String {
    let bytes = sql.as_bytes();
    let mut out = String::with_capacity(sql.len());
    let mut i = 0;
    let mut in_single = false;
    let mut in_double = false;

    while i < bytes.len() {
        let c = bytes[i] as char;
        if in_single {
            out.push(c);
            if c == '\'' {
                if i + 1 < bytes.len() && bytes[i + 1] == b'\'' {
                    out.push('\'');
                    i += 2;
                    continue;
                }
                in_single = false;
            }
            i += 1;
            continue;
        }
        if in_double {
            out.push(c);
            if c == '"' {
                if i + 1 < bytes.len() && bytes[i + 1] == b'"' {
                    out.push('"');
                    i += 2;
                    continue;
                }
                in_double = false;
            }
            i += 1;
            continue;
        }

        match c {
            '\'' => {
                in_single = true;
                out.push(c);
                i += 1;
            }
            '"' => {
                in_double = true;
                out.push(c);
                i += 1;
            }
            '`' => {
                // Convert `ident` -> "ident", doubling internal double-quotes.
                i += 1;
                out.push('"');
                while i < bytes.len() {
                    let ch = bytes[i] as char;
                    if ch == '`' {
                        if i + 1 < bytes.len() && bytes[i + 1] == b'`' {
                            out.push('`');
                            i += 2;
                            continue;
                        }
                        i += 1;
                        break;
                    }
                    if ch == '"' {
                        out.push('"');
                        out.push('"');
                    } else {
                        out.push(ch);
                    }
                    i += 1;
                }
                out.push('"');
            }
            _ => {
                out.push(c);
                i += 1;
            }
        }
    }
    out
}

fn replace_ifnull_with_coalesce(sql: &str) -> String {
    // Case-insensitive IFNULL( -> COALESCE(
    let upper = sql.to_ascii_uppercase();
    let mut out = String::with_capacity(sql.len());
    let mut i = 0;
    let bytes = sql.as_bytes();
    let upper_bytes = upper.as_bytes();

    while i < bytes.len() {
        if i + 6 < bytes.len()
            && &upper_bytes[i..i + 6] == b"IFNULL"
            && (i == 0 || !is_ident_byte(upper_bytes[i - 1]))
            && !is_ident_byte(upper_bytes[i + 6])
        {
            // Skip optional whitespace then require '('
            let mut j = i + 6;
            while j < bytes.len() && bytes[j].is_ascii_whitespace() {
                j += 1;
            }
            if j < bytes.len() && bytes[j] == b'(' {
                out.push_str("COALESCE");
                out.push_str(&sql[i + 6..j]);
                out.push('(');
                i = j + 1;
                continue;
            }
        }
        out.push(bytes[i] as char);
        i += 1;
    }
    out
}

fn is_ident_byte(b: u8) -> bool {
    b.is_ascii_alphanumeric() || b == b'_'
}

/// Rewrite MySQL `LIMIT offset, count` to `LIMIT count OFFSET offset`.
fn rewrite_mysql_limit_offset(sql: &str) -> String {
    let upper = sql.to_ascii_uppercase();
    let Some(limit_pos) = find_keyword(&upper, "LIMIT") else {
        return sql.to_owned();
    };

    let after_limit = limit_pos + 5;
    let rest = sql[after_limit..].trim_start();

    // Already OFFSET form or bare LIMIT n
    let upper_rest = rest.to_ascii_uppercase();
    if upper_rest.contains("OFFSET") {
        return sql.to_owned();
    }

    // Match: number , number
    let mut idx = 0;
    let chars: Vec<char> = rest.chars().collect();
    while idx < chars.len() && chars[idx].is_ascii_digit() {
        idx += 1;
    }
    if idx == 0 {
        return sql.to_owned();
    }
    let offset_end = idx;
    while idx < chars.len() && chars[idx].is_ascii_whitespace() {
        idx += 1;
    }
    if idx >= chars.len() || chars[idx] != ',' {
        return sql.to_owned();
    }
    idx += 1;
    while idx < chars.len() && chars[idx].is_ascii_whitespace() {
        idx += 1;
    }
    let count_start = idx;
    while idx < chars.len() && chars[idx].is_ascii_digit() {
        idx += 1;
    }
    if idx == count_start {
        return sql.to_owned();
    }
    let count_end = idx;
    // Trailing must not start another identifier digit glued
    let offset = chars[..offset_end].iter().collect::<String>();
    let count = chars[count_start..count_end].iter().collect::<String>();
    let tail: String = chars[count_end..].iter().collect();

    // Prefix ends before the original LIMIT keyword.
    format!("{}LIMIT {} OFFSET {}{}", &sql[..limit_pos], count, offset, tail)
}

fn find_keyword(upper_sql: &str, keyword: &str) -> Option<usize> {
    let mut i = 0;
    let bytes = upper_sql.as_bytes();
    let key = keyword.as_bytes();
    while i + key.len() <= bytes.len() {
        if &bytes[i..i + key.len()] == key {
            let before_ok = i == 0 || !is_ident_byte(bytes[i - 1]);
            let after = i + key.len();
            let after_ok = after >= bytes.len() || !is_ident_byte(bytes[after]);
            if before_ok && after_ok {
                return Some(i);
            }
        }
        i += 1;
    }
    None
}

fn format_allowed(policy: &TranslationPolicyConfig) -> String {
    let allowed = if policy.allowed_statements.is_empty() {
        default_allowed_statements()
    } else {
        policy.allowed_statements.clone()
    };
    allowed.iter().map(|k| k.as_str()).collect::<Vec<_>>().join(", ")
}

fn reject_unsupported_constructs(
    policy: &TranslationPolicyConfig,
    upper_sql: &str,
) -> GatewayResult<()> {
    let forbidden = [
        ("CREATE ", "DDL CREATE"),
        ("ALTER ", "DDL ALTER"),
        ("DROP ", "DDL DROP"),
        ("TRUNCATE ", "DDL TRUNCATE"),
        ("RENAME ", "DDL RENAME"),
        ("CALL ", "stored procedure CALL"),
        ("EXECUTE ", "EXECUTE/procedure"),
        ("COPY ", "PostgreSQL COPY"),
        ("LOAD DATA", "MySQL LOAD DATA"),
        ("LOAD XML", "MySQL LOAD XML"),
        ("HANDLER ", "MySQL HANDLER"),
        ("LOCK TABLES", "LOCK TABLES"),
        ("UNLOCK TABLES", "UNLOCK TABLES"),
        ("REPLACE INTO", "MySQL REPLACE"),
        ("ON DUPLICATE KEY", "MySQL ON DUPLICATE KEY"),
        ("RETURNING ", "PostgreSQL RETURNING (not mapped yet)"),
        ("::", "PostgreSQL cast operator ::"),
        ("ILIKE ", "PostgreSQL ILIKE"),
        ("REGEXP ", "MySQL REGEXP"),
        ("RLIKE ", "MySQL RLIKE"),
    ];

    for (needle, label) in forbidden {
        if upper_sql.contains(needle) {
            return Err(GatewayError::Unsupported(format!(
                "translation policy '{}': {} is not supported for {} -> {}",
                policy.name, label, policy.frontend_protocol, policy.backend_protocol
            )));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::HeuristicDialectParser;

    fn mysql_to_pg() -> TranslationPolicyConfig {
        TranslationPolicyConfig {
            name: "mysql-to-pg".into(),
            enabled: true,
            frontend_protocol: ProtocolKind::MySql,
            backend_protocol: ProtocolKind::PostgreSql,
            allowed_statements: default_allowed_statements(),
        }
    }

    fn pg_to_mysql() -> TranslationPolicyConfig {
        TranslationPolicyConfig {
            name: "pg-to-mysql".into(),
            enabled: true,
            frontend_protocol: ProtocolKind::PostgreSql,
            backend_protocol: ProtocolKind::MySql,
            allowed_statements: default_allowed_statements(),
        }
    }

    #[test]
    fn disabled_policy_rejects() {
        let mut policy = mysql_to_pg();
        policy.enabled = false;
        let dialect = HeuristicDialectParser::mysql();
        let err = check_translation_sql(&policy, "select 1", &dialect).unwrap_err();
        assert!(err.to_string().contains("disabled"));
    }

    #[test]
    fn allows_select_insert_update_delete() {
        let policy = mysql_to_pg();
        let dialect = HeuristicDialectParser::mysql();
        assert_eq!(
            check_translation_sql(&policy, "select * from t", &dialect).unwrap(),
            TranslationStatementKind::Select
        );
        assert_eq!(
            check_translation_sql(&policy, "insert into t values (1)", &dialect).unwrap(),
            TranslationStatementKind::Insert
        );
    }

    #[test]
    fn rejects_ddl_and_vendor_constructs() {
        let policy = mysql_to_pg();
        let dialect = HeuristicDialectParser::mysql();
        assert!(check_translation_sql(&policy, "drop table t", &dialect)
            .unwrap_err()
            .to_string()
            .contains("DDL DROP"));
        assert!(check_translation_sql(&policy, "load data infile 'x' into table t", &dialect)
            .unwrap_err()
            .to_string()
            .contains("LOAD DATA"));
        assert!(check_translation_sql(&policy, "select a::text from t", &dialect)
            .unwrap_err()
            .to_string()
            .contains("cast operator"));
    }

    #[test]
    fn rejects_disallowed_statement_kind() {
        let mut policy = mysql_to_pg();
        policy.allowed_statements = vec![TranslationStatementKind::Select];
        let dialect = HeuristicDialectParser::mysql();
        let err = check_translation_sql(&policy, "delete from t", &dialect).unwrap_err();
        assert!(err.to_string().contains("not allowed"));
    }

    #[test]
    fn rewrites_prepared_sql_and_allows_statement_lifecycle() {
        let policy = mysql_to_pg();
        let dialect = HeuristicDialectParser::mysql();
        let prepared = prepare_cross_protocol_command(
            &policy,
            GatewayCommand::Prepare { sql: "select `id` from t where id = ?".into() },
            &dialect,
        )
        .unwrap();
        assert_eq!(
            prepared,
            GatewayCommand::Prepare { sql: "select \"id\" from t where id = $1".into() }
        );
        assert_eq!(
            prepare_cross_protocol_command(
                &policy,
                GatewayCommand::Execute {
                    statement_id: "7".into(),
                    parameters: vec![GatewayValue::Integer(1)],
                },
                &dialect,
            )
            .unwrap(),
            GatewayCommand::Execute {
                statement_id: "7".into(),
                parameters: vec![GatewayValue::Integer(1)],
            }
        );
        assert_eq!(
            prepare_cross_protocol_command(
                &policy,
                GatewayCommand::CloseStatement { statement_id: "7".into() },
                &dialect,
            )
            .unwrap(),
            GatewayCommand::CloseStatement { statement_id: "7".into() }
        );
    }

    #[test]
    fn prepared_sql_still_rejects_unsupported_statements() {
        let policy = mysql_to_pg();
        let dialect = HeuristicDialectParser::mysql();
        let err = prepare_cross_protocol_command(
            &policy,
            GatewayCommand::Prepare { sql: "drop table t".into() },
            &dialect,
        )
        .unwrap_err();
        assert!(err.to_string().contains("DDL DROP"), "{err}");
    }

    #[test]
    fn mysql_placeholders_skip_literals_identifiers_and_comments() {
        let sql = "SELECT ?, '?', `?`, \"?\" /* ? */ -- ?\n# ?\n, ?";
        assert_eq!(
            rewrite_placeholders_mysql_to_pg(sql).unwrap(),
            "SELECT $1, '?', `?`, \"?\" /* ? */ -- ?\n# ?\n, $2"
        );
    }

    #[test]
    fn pg_placeholders_reorder_and_repeat_parameters() {
        let params =
            vec![GatewayValue::String("first".into()), GatewayValue::String("second".into())];
        let (sql, reordered) =
            rewrite_placeholders_pg_to_mysql("SELECT $2, $1, $2", &params).unwrap();
        assert_eq!(sql, "SELECT ?, ?, ?");
        assert_eq!(reordered, vec![params[1].clone(), params[0].clone(), params[1].clone()]);
    }

    #[test]
    fn pg_placeholders_skip_quoted_and_commented_regions() {
        let params = vec![GatewayValue::Integer(9)];
        let sql = "SELECT $1, '$2', \"$3\", $$ $4 $$, $tag$ $5 $tag$ /* $6 */ -- $7\n";
        let (rewritten, reordered) = rewrite_placeholders_pg_to_mysql(sql, &params).unwrap();
        assert_eq!(rewritten, "SELECT ?, '$2', \"$3\", $$ $4 $$, $tag$ $5 $tag$ /* $6 */ -- $7\n");
        assert_eq!(reordered, params);
    }

    #[test]
    fn pg_placeholder_gaps_and_arity_fail_closed() {
        let gap = rewrite_placeholders_pg_to_mysql(
            "SELECT $2",
            &[GatewayValue::Integer(1), GatewayValue::Integer(2)],
        )
        .unwrap_err();
        assert!(gap.to_string().contains("index gap"), "{gap}");

        let arity = rewrite_placeholders_pg_to_mysql("SELECT $1, $2", &[GatewayValue::Integer(1)])
            .unwrap_err();
        assert!(arity.to_string().contains("expects 2"), "{arity}");
    }

    #[test]
    fn query_params_are_rewritten_for_both_directions() {
        let mysql = prepare_cross_protocol_command(
            &mysql_to_pg(),
            GatewayCommand::QueryParams {
                sql: "SELECT `id` FROM t WHERE a = ? AND b = ?".into(),
                parameters: vec![GatewayValue::Integer(1), GatewayValue::Integer(2)],
            },
            &HeuristicDialectParser::mysql(),
        )
        .unwrap();
        assert_eq!(
            mysql,
            GatewayCommand::QueryParams {
                sql: "SELECT \"id\" FROM t WHERE a = $1 AND b = $2".into(),
                parameters: vec![GatewayValue::Integer(1), GatewayValue::Integer(2)],
            }
        );

        let postgres = prepare_cross_protocol_command(
            &pg_to_mysql(),
            GatewayCommand::QueryParams {
                sql: "SELECT \"id\" FROM t WHERE a = $2 OR b = $1 OR c = $2".into(),
                parameters: vec![GatewayValue::Integer(1), GatewayValue::Integer(2)],
            },
            &HeuristicDialectParser::postgresql(),
        )
        .unwrap();
        assert_eq!(
            postgres,
            GatewayCommand::QueryParams {
                sql: "SELECT `id` FROM t WHERE a = ? OR b = ? OR c = ?".into(),
                parameters: vec![
                    GatewayValue::Integer(2),
                    GatewayValue::Integer(1),
                    GatewayValue::Integer(2),
                ],
            }
        );
    }

    #[test]
    fn golden_rewrite_mysql_to_postgresql() {
        let cases = [
            (
                "SELECT `id`, IFNULL(name, '') FROM `users` LIMIT 10, 20",
                "SELECT \"id\", COALESCE(name, '') FROM \"users\" LIMIT 20 OFFSET 10",
            ),
            ("select ifnull(a, 0) from t", "select COALESCE(a, 0) from t"),
            ("SELECT * FROM t LIMIT 5", "SELECT * FROM t LIMIT 5"),
            ("SELECT * FROM t LIMIT 5 OFFSET 2", "SELECT * FROM t LIMIT 5 OFFSET 2"),
            (
                "INSERT INTO `t` (`a`) VALUES ('`keep`')",
                "INSERT INTO \"t\" (\"a\") VALUES ('`keep`')",
            ),
        ];
        for (input, expected) in cases {
            let out =
                rewrite_sql_for_backend(input, &ProtocolKind::MySql, &ProtocolKind::PostgreSql)
                    .unwrap();
            assert_eq!(out, expected, "input={input}");
        }
    }

    #[test]
    fn golden_rewrite_postgresql_to_mysql() {
        let cases = [
            (
                "SELECT \"id\", COALESCE(name, '') FROM \"users\" LIMIT 20 OFFSET 10",
                "SELECT `id`, COALESCE(name, '') FROM `users` LIMIT 20 OFFSET 10",
            ),
            (
                "INSERT INTO \"t\" (\"a\") VALUES ('\"keep\"')",
                "INSERT INTO `t` (`a`) VALUES ('\"keep\"')",
            ),
            ("SELECT * FROM t WHERE name = 'hello'", "SELECT * FROM t WHERE name = 'hello'"),
            (
                "UPDATE \"users\" SET \"name\" = 'x' WHERE \"id\" = 1",
                "UPDATE `users` SET `name` = 'x' WHERE `id` = 1",
            ),
        ];
        for (input, expected) in cases {
            let out =
                rewrite_sql_for_backend(input, &ProtocolKind::PostgreSql, &ProtocolKind::MySql)
                    .unwrap();
            assert_eq!(out, expected, "input={input}");
        }
    }

    #[test]
    fn maps_resultset_column_types() {
        let response = GatewayResponse::ResultSet {
            columns: vec![
                Column { name: "id".into(), data_type: "int4".into() },
                Column { name: "flag".into(), data_type: "bool".into() },
            ],
            rows: vec![vec![GatewayValue::Integer(1), GatewayValue::Boolean(true)]],
        };
        let mapped = map_response_types(response, &ProtocolKind::PostgreSql, &ProtocolKind::MySql);
        match mapped {
            GatewayResponse::ResultSet { columns, .. } => {
                assert_eq!(columns[0].data_type, "long");
                assert_eq!(columns[1].data_type, "tiny");
            }
            other => panic!("unexpected {other:?}"),
        }
    }

    #[test]
    fn maps_prepared_column_types() {
        let prepared = map_response_types(
            GatewayResponse::Prepared {
                statement_id: "7".into(),
                parameter_count: 1,
                columns: vec![Column { name: "id".into(), data_type: "int4".into() }],
            },
            &ProtocolKind::PostgreSql,
            &ProtocolKind::MySql,
        );
        match prepared {
            GatewayResponse::Prepared { columns, .. } => {
                assert_eq!(columns[0].data_type, "long");
            }
            other => panic!("unexpected {other:?}"),
        }
    }

    #[test]
    fn maps_row_description_column_types() {
        let described = map_response_types(
            GatewayResponse::RowDescription {
                columns: vec![Column { name: "flag".into(), data_type: "tiny".into() }],
            },
            &ProtocolKind::MySql,
            &ProtocolKind::PostgreSql,
        );
        match described {
            GatewayResponse::RowDescription { columns } => {
                assert_eq!(columns[0].data_type, "int2");
            }
            other => panic!("unexpected {other:?}"),
        }
    }

    #[test]
    fn maps_tagged_resultset_column_types() {
        let mapped = map_response_types(
            GatewayResponse::TaggedResultSet {
                columns: vec![Column { name: "payload".into(), data_type: "jsonb".into() }],
                rows: vec![vec![GatewayValue::String("{}".into())]],
                tag: "SELECT 1".into(),
            },
            &ProtocolKind::PostgreSql,
            &ProtocolKind::MySql,
        );
        match mapped {
            GatewayResponse::TaggedResultSet { columns, tag, .. } => {
                assert_eq!(columns[0].data_type, "var_string");
                assert_eq!(tag, "SELECT 1");
            }
            other => panic!("unexpected {other:?}"),
        }
    }

    #[test]
    fn prepare_query_rewrites_sql() {
        let policy = mysql_to_pg();
        let dialect = HeuristicDialectParser::mysql();
        let cmd = prepare_cross_protocol_command(
            &policy,
            GatewayCommand::Query { sql: "SELECT `id` FROM t LIMIT 1, 2".into() },
            &dialect,
        )
        .unwrap();
        assert_eq!(
            cmd,
            GatewayCommand::Query { sql: "SELECT \"id\" FROM t LIMIT 2 OFFSET 1".into() }
        );
    }
}
