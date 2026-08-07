use crate::ProtocolKind;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum UnsupportedSqlCapability {
    PostgresCopyProgram,
    PostgresCopyFile,
    PostgresDo,
    StoredProcedureCall,
    MysqlLoadData,
    MysqlOutfile,
    PostgresMaintenance,
    CrossDialectStatement,
    PrivilegedCatalogSession,
}

impl UnsupportedSqlCapability {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::PostgresCopyProgram => "postgres.copy_program",
            Self::PostgresCopyFile => "postgres.copy_file",
            Self::PostgresDo => "postgres.do",
            Self::StoredProcedureCall => "stored_procedure.call",
            Self::MysqlLoadData => "mysql.load_data",
            Self::MysqlOutfile => "mysql.outfile",
            Self::PostgresMaintenance => "postgres.maintenance",
            Self::CrossDialectStatement => "sql.cross_dialect",
            Self::PrivilegedCatalogSession => "sql.privileged_catalog_session",
        }
    }

    pub fn from_code(value: &str) -> Option<Self> {
        match value {
            "postgres.copy_program" => Some(Self::PostgresCopyProgram),
            "postgres.copy_file" => Some(Self::PostgresCopyFile),
            "postgres.do" => Some(Self::PostgresDo),
            "stored_procedure.call" => Some(Self::StoredProcedureCall),
            "mysql.load_data" => Some(Self::MysqlLoadData),
            "mysql.outfile" => Some(Self::MysqlOutfile),
            "postgres.maintenance" => Some(Self::PostgresMaintenance),
            "sql.cross_dialect" => Some(Self::CrossDialectStatement),
            "sql.privileged_catalog_session" => Some(Self::PrivilegedCatalogSession),
            _ => None,
        }
    }
}

pub fn classify_dangerous_sql(
    sql: &str,
    dialect: ProtocolKind,
) -> Option<UnsupportedSqlCapability> {
    let tokens = sql_tokens(sql, dialect);

    for statement in tokens.split(|token| token == ";") {
        if statement.is_empty() {
            continue;
        }
        if statement[0] == "COPY" && dialect == ProtocolKind::PostgreSql {
            if statement.iter().any(|token| token == "PROGRAM") {
                return Some(UnsupportedSqlCapability::PostgresCopyProgram);
            }
            if statement
                .windows(2)
                .any(|pair| matches!(pair[0].as_str(), "FROM" | "TO") && pair[1] == "<LITERAL>")
            {
                return Some(UnsupportedSqlCapability::PostgresCopyFile);
            }
        }
        if statement[0] == "DO" && dialect == ProtocolKind::PostgreSql {
            return Some(UnsupportedSqlCapability::PostgresDo);
        }
        if statement[0] == "CALL" {
            return Some(UnsupportedSqlCapability::StoredProcedureCall);
        }
        if statement.starts_with(&["LOAD".into(), "DATA".into()]) && dialect == ProtocolKind::MySql
        {
            return Some(UnsupportedSqlCapability::MysqlLoadData);
        }
        if statement
            .windows(2)
            .any(|pair| pair[0] == "INTO" && matches!(pair[1].as_str(), "OUTFILE" | "DUMPFILE"))
            && dialect == ProtocolKind::MySql
        {
            return Some(UnsupportedSqlCapability::MysqlOutfile);
        }
        if matches!(statement[0].as_str(), "VACUUM" | "ANALYZE")
            && dialect == ProtocolKind::PostgreSql
        {
            return Some(UnsupportedSqlCapability::PostgresMaintenance);
        }
        if is_cross_dialect(statement, dialect) {
            return Some(UnsupportedSqlCapability::CrossDialectStatement);
        }
        if is_privileged_catalog_or_session(statement, dialect) {
            return Some(UnsupportedSqlCapability::PrivilegedCatalogSession);
        }
    }
    None
}

fn is_cross_dialect(tokens: &[String], dialect: ProtocolKind) -> bool {
    match dialect {
        ProtocolKind::MySql => tokens.iter().any(|token| token == "::"),
        ProtocolKind::PostgreSql => {
            tokens.iter().any(|token| token == "<BACKTICK_IDENT>")
                || tokens.starts_with(&["SHOW".into(), "TABLES".into()])
        }
    }
}

fn is_privileged_catalog_or_session(tokens: &[String], dialect: ProtocolKind) -> bool {
    match dialect {
        ProtocolKind::MySql => {
            tokens.starts_with(&["SET".into(), "GLOBAL".into()])
                || tokens.starts_with(&["SET".into(), "PERSIST".into()])
                || tokens.starts_with(&["SET".into(), "PERSIST_ONLY".into()])
                || tokens.windows(2).any(|pair| pair[0] == "MYSQL" && pair[1] == "USER")
        }
        ProtocolKind::PostgreSql => {
            tokens.starts_with(&["ALTER".into(), "SYSTEM".into()])
                || tokens.starts_with(&["SET".into(), "SESSION".into(), "AUTHORIZATION".into()])
                || tokens.starts_with(&["SET".into(), "ROLE".into()])
                || tokens.iter().any(|token| matches!(token.as_str(), "PG_AUTHID" | "PG_SHADOW"))
        }
    }
}

fn sql_tokens(sql: &str, dialect: ProtocolKind) -> Vec<String> {
    let bytes = sql.as_bytes();
    let mut tokens = Vec::new();
    let mut index = 0;
    while index < bytes.len() {
        match bytes[index] {
            byte if byte.is_ascii_whitespace() => index += 1,
            b'-' if is_line_comment(bytes, index, dialect) => {
                index += 2;
                while index < bytes.len() && bytes[index] != b'\n' {
                    index += 1;
                }
            }
            b'#' if dialect == ProtocolKind::MySql => {
                index += 1;
                while index < bytes.len() && bytes[index] != b'\n' {
                    index += 1;
                }
            }
            b'/' if bytes.get(index + 1) == Some(&b'*') => {
                index += 2;
                while index + 1 < bytes.len() && !(bytes[index] == b'*' && bytes[index + 1] == b'/')
                {
                    index += 1;
                }
                index = (index + 2).min(bytes.len());
            }
            b'\'' => {
                let backslash =
                    dialect == ProtocolKind::MySql || is_postgresql_escape_string(bytes, index);
                index = skip_quoted(bytes, index + 1, b'\'', backslash);
                tokens.push("<LITERAL>".into());
            }
            b'"' => index = skip_quoted(bytes, index + 1, b'"', false),
            b'`' => {
                index = skip_quoted(bytes, index + 1, b'`', false);
                tokens.push("<BACKTICK_IDENT>".into());
            }
            b'$' if dialect == ProtocolKind::PostgreSql
                && dollar_quote_tag(bytes, index).is_some() =>
            {
                let (body, tag) = dollar_quote_tag(bytes, index).expect("checked above");
                index =
                    find_bytes(bytes, body, tag).map(|end| end + tag.len()).unwrap_or(bytes.len());
                tokens.push("<LITERAL>".into());
            }
            b':' if bytes.get(index + 1) == Some(&b':') => {
                tokens.push("::".into());
                index += 2;
            }
            b';' => {
                tokens.push(";".into());
                index += 1;
            }
            byte if byte.is_ascii_alphabetic() || byte == b'_' => {
                let start = index;
                index += 1;
                while index < bytes.len()
                    && (bytes[index].is_ascii_alphanumeric() || matches!(bytes[index], b'_' | b'$'))
                {
                    index += 1;
                }
                tokens.push(String::from_utf8_lossy(&bytes[start..index]).to_ascii_uppercase());
            }
            _ => index += 1,
        }
    }
    tokens
}

fn is_line_comment(bytes: &[u8], index: usize, dialect: ProtocolKind) -> bool {
    if bytes.get(index + 1) != Some(&b'-') {
        return false;
    }
    dialect == ProtocolKind::PostgreSql
        || bytes
            .get(index + 2)
            .is_none_or(|byte| byte.is_ascii_whitespace() || byte.is_ascii_control())
}

fn is_postgresql_escape_string(bytes: &[u8], quote: usize) -> bool {
    quote > 0
        && matches!(bytes[quote - 1], b'e' | b'E')
        && (quote == 1
            || !(bytes[quote - 2].is_ascii_alphanumeric()
                || matches!(bytes[quote - 2], b'_' | b'$')))
}

fn skip_quoted(bytes: &[u8], mut index: usize, quote: u8, backslash: bool) -> usize {
    while index < bytes.len() {
        if backslash && bytes[index] == b'\\' {
            index = (index + 2).min(bytes.len());
        } else if bytes[index] == quote {
            if bytes.get(index + 1) == Some(&quote) {
                index += 2;
            } else {
                return index + 1;
            }
        } else {
            index += 1;
        }
    }
    index
}

fn dollar_quote_tag(bytes: &[u8], start: usize) -> Option<(usize, &[u8])> {
    let mut end = start + 1;
    while end < bytes.len() && (bytes[end].is_ascii_alphanumeric() || bytes[end] == b'_') {
        end += 1;
    }
    if bytes.get(end) == Some(&b'$') {
        Some((end + 1, &bytes[start..=end]))
    } else {
        None
    }
}

fn find_bytes(haystack: &[u8], start: usize, needle: &[u8]) -> Option<usize> {
    haystack[start..]
        .windows(needle.len())
        .position(|window| window == needle)
        .map(|offset| start + offset)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn classifies_dangerous_capabilities() {
        let cases = [
            (
                "COPY t TO PROGRAM 'sentinel'",
                ProtocolKind::PostgreSql,
                UnsupportedSqlCapability::PostgresCopyProgram,
            ),
            (
                "COPY t TO '/sentinel'",
                ProtocolKind::PostgreSql,
                UnsupportedSqlCapability::PostgresCopyFile,
            ),
            (
                "DO $$ BEGIN NULL; END $$",
                ProtocolKind::PostgreSql,
                UnsupportedSqlCapability::PostgresDo,
            ),
            ("CALL p()", ProtocolKind::PostgreSql, UnsupportedSqlCapability::StoredProcedureCall),
            (
                "LOAD DATA INFILE '/sentinel' INTO TABLE t",
                ProtocolKind::MySql,
                UnsupportedSqlCapability::MysqlLoadData,
            ),
            (
                "SELECT 1 INTO OUTFILE '/sentinel'",
                ProtocolKind::MySql,
                UnsupportedSqlCapability::MysqlOutfile,
            ),
            ("VACUUM t", ProtocolKind::PostgreSql, UnsupportedSqlCapability::PostgresMaintenance),
            (
                "SELECT 1::integer",
                ProtocolKind::MySql,
                UnsupportedSqlCapability::CrossDialectStatement,
            ),
            (
                "SELECT `id` FROM t",
                ProtocolKind::PostgreSql,
                UnsupportedSqlCapability::CrossDialectStatement,
            ),
            (
                "SET GLOBAL max_connections = 10",
                ProtocolKind::MySql,
                UnsupportedSqlCapability::PrivilegedCatalogSession,
            ),
            (
                "ALTER SYSTEM SET work_mem = '1MB'",
                ProtocolKind::PostgreSql,
                UnsupportedSqlCapability::PrivilegedCatalogSession,
            ),
        ];
        for (sql, dialect, expected) in cases {
            assert_eq!(classify_dangerous_sql(sql, dialect), Some(expected), "{sql}");
        }
    }

    #[test]
    fn ignores_keywords_inside_comments_and_literals() {
        for sql in [
            "SELECT 'COPY t TO PROGRAM x'",
            "SELECT $$ LOAD DATA INFILE x $$",
            "SELECT 1 /* INTO OUTFILE x */",
            "SELECT 1 -- VACUUM t\n",
        ] {
            assert_eq!(classify_dangerous_sql(sql, ProtocolKind::PostgreSql), None, "{sql}");
            assert_eq!(classify_dangerous_sql(sql, ProtocolKind::MySql), None, "{sql}");
        }
    }

    #[test]
    fn applies_dialect_specific_quoting_and_comments() {
        let plain_postgresql = r"SELECT '\'; COPY t TO PROGRAM 'sentinel'";
        assert_eq!(
            classify_dangerous_sql(plain_postgresql, ProtocolKind::PostgreSql),
            Some(UnsupportedSqlCapability::PostgresCopyProgram)
        );
        assert_eq!(classify_dangerous_sql(plain_postgresql, ProtocolKind::MySql), None);

        let escaped_postgresql = r"SELECT E'\'COPY t TO PROGRAM sentinel'";
        assert_eq!(classify_dangerous_sql(escaped_postgresql, ProtocolKind::PostgreSql), None);

        let mysql_dash_operator = "SELECT 1--x\n; LOAD DATA INFILE '/sentinel' INTO TABLE t";
        assert_eq!(
            classify_dangerous_sql(mysql_dash_operator, ProtocolKind::MySql),
            Some(UnsupportedSqlCapability::MysqlLoadData)
        );
    }
}
