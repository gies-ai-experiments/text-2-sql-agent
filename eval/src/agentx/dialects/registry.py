"""
Dialect Registry - Configurations for all supported SQL dialects.

Each dialect has:
- sqlglot dialect name for parsing
- Built-in function list for validation
- Schema introspection settings
- Feature flags (CTE, window functions, etc.)
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Set, Dict, Any


class Dialect(Enum):
    """Supported SQL dialects."""
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"
    BIGQUERY = "bigquery"
    SNOWFLAKE = "snowflake"
    DUCKDB = "duckdb"
    MYSQL = "mysql"


@dataclass
class DialectConfig:
    """Configuration for a specific SQL dialect."""
    name: Dialect
    sqlglot_dialect: str  # sqlglot dialect name for parsing

    # Schema introspection
    default_schema: Optional[str]  # "public" for PG, None for SQLite
    supports_schemas: bool

    # Feature flags
    supports_cte: bool = True
    supports_window_functions: bool = True
    supports_json: bool = False
    supports_arrays: bool = False

    # Built-in functions valid for this dialect
    builtin_functions: Set[str] = field(default_factory=set)

    # Additional metadata
    description: str = ""


# =============================================================================
# SQLITE FUNCTIONS
# =============================================================================
SQLITE_FUNCTIONS: Set[str] = {
    # Aggregate functions
    "AVG", "COUNT", "GROUP_CONCAT", "MAX", "MIN", "SUM", "TOTAL",

    # Core functions
    "ABS", "CHANGES", "CHAR", "COALESCE", "GLOB", "HEX", "IFNULL",
    "IIF", "INSTR", "LAST_INSERT_ROWID", "LENGTH", "LIKE", "LIKELIHOOD",
    "LIKELY", "LOAD_EXTENSION", "LOWER", "LTRIM", "MAX", "MIN", "NULLIF",
    "PRINTF", "QUOTE", "RANDOM", "RANDOMBLOB", "REPLACE", "ROUND", "RTRIM",
    "SIGN", "SOUNDEX", "SQLITE_COMPILEOPTION_GET", "SQLITE_COMPILEOPTION_USED",
    "SQLITE_OFFSET", "SQLITE_SOURCE_ID", "SQLITE_VERSION", "SUBSTR", "SUBSTRING",
    "TOTAL_CHANGES", "TRIM", "TYPEOF", "UNICODE", "UNLIKELY", "UPPER", "ZEROBLOB",

    # Date/time functions
    "DATE", "TIME", "DATETIME", "JULIANDAY", "UNIXEPOCH", "STRFTIME",
    "TIMEDIFF", "CURRENT_DATE", "CURRENT_TIME", "CURRENT_TIMESTAMP",

    # Math functions (SQLite 3.35+)
    "ACOS", "ACOSH", "ASIN", "ASINH", "ATAN", "ATAN2", "ATANH",
    "CEIL", "CEILING", "COS", "COSH", "DEGREES", "EXP", "FLOOR",
    "LN", "LOG", "LOG10", "LOG2", "MOD", "PI", "POW", "POWER",
    "RADIANS", "SIN", "SINH", "SQRT", "TAN", "TANH", "TRUNC",

    # Window functions
    "ROW_NUMBER", "RANK", "DENSE_RANK", "NTILE", "LAG", "LEAD",
    "FIRST_VALUE", "LAST_VALUE", "NTH_VALUE",
    "CUME_DIST", "PERCENT_RANK",

    # JSON functions (SQLite 3.38+)
    "JSON", "JSON_ARRAY", "JSON_ARRAY_LENGTH", "JSON_EXTRACT",
    "JSON_INSERT", "JSON_OBJECT", "JSON_PATCH", "JSON_REMOVE",
    "JSON_REPLACE", "JSON_SET", "JSON_TYPE", "JSON_VALID",
    "JSON_QUOTE", "JSON_GROUP_ARRAY", "JSON_GROUP_OBJECT",

    # Type conversion
    "CAST", "TYPEOF",
}

# =============================================================================
# DUCKDB FUNCTIONS
# =============================================================================
DUCKDB_FUNCTIONS: Set[str] = {
    # Standard SQL
    "ABS", "AVG", "CEIL", "CEILING", "COUNT", "FLOOR", "MAX", "MIN",
    "ROUND", "SUM", "TRUNC",

    # String functions
    "CONCAT", "CONCAT_WS", "LENGTH", "LOWER", "LPAD", "LTRIM", "REPLACE",
    "REVERSE", "RIGHT", "RPAD", "RTRIM", "SPLIT_PART", "SUBSTR", "SUBSTRING",
    "TRIM", "UPPER", "ASCII", "CHR", "INSTR", "LEFT", "REPEAT", "TRANSLATE",
    "REGEXP_MATCHES", "REGEXP_REPLACE", "REGEXP_EXTRACT",

    # Date/time
    "CURRENT_DATE", "CURRENT_TIME", "CURRENT_TIMESTAMP", "NOW",
    "DATE_PART", "DATE_TRUNC", "DATE_DIFF", "DATE_ADD", "DATE_SUB",
    "EXTRACT", "EPOCH", "AGE", "MAKE_DATE", "MAKE_TIME", "MAKE_TIMESTAMP",
    "STRFTIME", "STRPTIME", "TO_TIMESTAMP", "YEAR", "MONTH", "DAY",
    "HOUR", "MINUTE", "SECOND", "DAYOFWEEK", "DAYOFYEAR", "WEEK", "QUARTER",

    # Aggregate functions
    "ARRAY_AGG", "BIT_AND", "BIT_OR", "BIT_XOR", "BOOL_AND", "BOOL_OR",
    "FIRST", "LAST", "LIST", "STRING_AGG", "LISTAGG", "GROUP_CONCAT",
    "HISTOGRAM", "MODE", "QUANTILE", "MEDIAN", "STDDEV", "VARIANCE",
    "STDDEV_POP", "STDDEV_SAMP", "VAR_POP", "VAR_SAMP",
    "APPROX_COUNT_DISTINCT", "APPROX_QUANTILE",

    # Window functions
    "ROW_NUMBER", "RANK", "DENSE_RANK", "NTILE", "LAG", "LEAD",
    "FIRST_VALUE", "LAST_VALUE", "NTH_VALUE",
    "CUME_DIST", "PERCENT_RANK",

    # Null handling
    "COALESCE", "IFNULL", "NULLIF", "NVL", "NVL2",

    # Conditional
    "CASE", "IF", "IIF", "GREATEST", "LEAST",

    # Type conversion
    "CAST", "TRY_CAST", "TYPEOF",

    # DuckDB-specific
    "READ_CSV", "READ_CSV_AUTO", "READ_PARQUET", "READ_JSON", "READ_JSON_AUTO",
    "GENERATE_SERIES", "RANGE", "UNNEST", "STRUCT_PACK", "STRUCT_EXTRACT",
    "LIST_VALUE", "LIST_EXTRACT", "LIST_ELEMENT", "LEN",
    "MAP", "MAP_EXTRACT", "ELEMENT_AT",
    "HASH", "MD5", "SHA256",
    "RANDOM", "SETSEED", "UUID",
    "DESCRIBE", "PRAGMA_TABLE_INFO",
}

# =============================================================================
# BIGQUERY FUNCTIONS
# =============================================================================
BIGQUERY_FUNCTIONS: Set[str] = {
    # Standard SQL
    "ABS", "AVG", "CEIL", "CEILING", "COUNT", "FLOOR", "MAX", "MIN",
    "MOD", "ROUND", "SUM", "TRUNC", "DIV", "IEEE_DIVIDE",
    "POWER", "POW", "SQRT", "EXP", "LN", "LOG", "LOG10",
    "SIGN", "IS_INF", "IS_NAN",

    # Safe math (BigQuery-specific)
    "SAFE_DIVIDE", "SAFE_MULTIPLY", "SAFE_NEGATE", "SAFE_ADD", "SAFE_SUBTRACT",

    # String functions
    "CONCAT", "LENGTH", "LOWER", "UPPER", "TRIM", "LTRIM", "RTRIM",
    "LPAD", "RPAD", "REPLACE", "REVERSE", "SUBSTR", "SUBSTRING",
    "SPLIT", "STARTS_WITH", "ENDS_WITH", "CONTAINS_SUBSTR",
    "LEFT", "RIGHT", "REPEAT", "FORMAT", "TO_CODE_POINTS", "CODE_POINTS_TO_STRING",
    "ASCII", "CHR", "UNICODE", "NORMALIZE", "NORMALIZE_AND_CASEFOLD",
    "REGEXP_CONTAINS", "REGEXP_EXTRACT", "REGEXP_EXTRACT_ALL", "REGEXP_REPLACE",
    "TRANSLATE", "INITCAP", "SOUNDEX",
    "BYTE_LENGTH", "CHAR_LENGTH", "CHARACTER_LENGTH", "OCTET_LENGTH",
    "COLLATE", "INSTR", "STRPOS",

    # Date/time functions
    "CURRENT_DATE", "CURRENT_TIME", "CURRENT_TIMESTAMP", "CURRENT_DATETIME",
    "DATE", "TIME", "DATETIME", "TIMESTAMP",
    "DATE_ADD", "DATE_SUB", "DATE_DIFF", "DATE_TRUNC",
    "TIME_ADD", "TIME_SUB", "TIME_DIFF", "TIME_TRUNC",
    "DATETIME_ADD", "DATETIME_SUB", "DATETIME_DIFF", "DATETIME_TRUNC",
    "TIMESTAMP_ADD", "TIMESTAMP_SUB", "TIMESTAMP_DIFF", "TIMESTAMP_TRUNC",
    "EXTRACT", "FORMAT_DATE", "FORMAT_TIME", "FORMAT_DATETIME", "FORMAT_TIMESTAMP",
    "PARSE_DATE", "PARSE_TIME", "PARSE_DATETIME", "PARSE_TIMESTAMP",
    "UNIX_DATE", "UNIX_SECONDS", "UNIX_MILLIS", "UNIX_MICROS",
    "TIMESTAMP_SECONDS", "TIMESTAMP_MILLIS", "TIMESTAMP_MICROS",
    "DATE_FROM_UNIX_DATE", "LAST_DAY",

    # Aggregate functions
    "ANY_VALUE", "ARRAY_AGG", "ARRAY_CONCAT_AGG", "AVG", "BIT_AND", "BIT_OR", "BIT_XOR",
    "COUNT", "COUNTIF", "LOGICAL_AND", "LOGICAL_OR", "MAX", "MIN", "STRING_AGG", "SUM",
    "CORR", "COVAR_POP", "COVAR_SAMP", "STDDEV", "STDDEV_POP", "STDDEV_SAMP",
    "VAR_POP", "VAR_SAMP", "VARIANCE",
    "APPROX_COUNT_DISTINCT", "APPROX_QUANTILES", "APPROX_TOP_COUNT", "APPROX_TOP_SUM",
    "HLL_COUNT.INIT", "HLL_COUNT.MERGE", "HLL_COUNT.MERGE_PARTIAL", "HLL_COUNT.EXTRACT",

    # Window functions
    "ROW_NUMBER", "RANK", "DENSE_RANK", "NTILE", "LAG", "LEAD",
    "FIRST_VALUE", "LAST_VALUE", "NTH_VALUE",
    "CUME_DIST", "PERCENT_RANK", "PERCENTILE_CONT", "PERCENTILE_DISC",

    # Array functions
    "ARRAY", "ARRAY_CONCAT", "ARRAY_LENGTH", "ARRAY_TO_STRING", "ARRAY_REVERSE",
    "GENERATE_ARRAY", "GENERATE_DATE_ARRAY", "GENERATE_TIMESTAMP_ARRAY",
    "ARRAY_FILTER", "ARRAY_TRANSFORM", "ARRAY_INCLUDES", "ARRAY_INCLUDES_ALL", "ARRAY_INCLUDES_ANY",
    "OFFSET", "ORDINAL", "SAFE_OFFSET", "SAFE_ORDINAL",

    # Struct functions
    "STRUCT",

    # JSON functions
    "JSON_EXTRACT", "JSON_EXTRACT_SCALAR", "JSON_EXTRACT_ARRAY", "JSON_EXTRACT_STRING_ARRAY",
    "JSON_QUERY", "JSON_QUERY_ARRAY", "JSON_VALUE", "JSON_VALUE_ARRAY",
    "TO_JSON", "TO_JSON_STRING", "PARSE_JSON", "JSON_TYPE",
    "JSON_SET", "JSON_STRIP_NULLS", "JSON_REMOVE", "JSON_KEYS", "JSON_ARRAY_LENGTH",
    "INT64", "FLOAT64", "BOOL", "STRING", "LAX_INT64", "LAX_FLOAT64", "LAX_BOOL", "LAX_STRING",

    # Geography functions
    "ST_GEOGPOINT", "ST_MAKELINE", "ST_MAKEPOLYGON", "ST_GEOGFROMTEXT", "ST_GEOGFROMGEOJSON",
    "ST_DISTANCE", "ST_AREA", "ST_LENGTH", "ST_PERIMETER", "ST_MAXDISTANCE",
    "ST_CONTAINS", "ST_COVEREDBY", "ST_COVERS", "ST_DISJOINT", "ST_DWITHIN",
    "ST_EQUALS", "ST_INTERSECTS", "ST_INTERSECTSBOX", "ST_TOUCHES", "ST_WITHIN",
    "ST_X", "ST_Y", "ST_CENTROID", "ST_BOUNDARY", "ST_BUFFER", "ST_BUFFERWITHTOLERANCE",
    "ST_CLOSESTPOINT", "ST_DIFFERENCE", "ST_INTERSECTION", "ST_SNAPTOGRID", "ST_SIMPLIFY", "ST_UNION",

    # Hash functions
    "FARM_FINGERPRINT", "MD5", "SHA1", "SHA256", "SHA512",

    # Conditional functions
    "CASE", "COALESCE", "IF", "IFNULL", "NULLIF", "IFF",
    "GREATEST", "LEAST",

    # Type conversion
    "CAST", "SAFE_CAST", "PARSE_BIGNUMERIC", "PARSE_NUMERIC",

    # Other
    "UNNEST", "GENERATE_UUID", "SESSION_USER", "ERROR",
    "BIT_COUNT", "NET.IP_FROM_STRING", "NET.SAFE_IP_FROM_STRING", "NET.IP_TO_STRING",
    "NET.IP_NET_MASK", "NET.IP_TRUNC", "NET.IPV4_FROM_INT64", "NET.IPV4_TO_INT64",
    "NET.HOST", "NET.PUBLIC_SUFFIX", "NET.REG_DOMAIN",
}

# =============================================================================
# POSTGRESQL FUNCTIONS
# =============================================================================
POSTGRESQL_FUNCTIONS: Set[str] = {
    # Aggregate functions
    "AVG", "BIT_AND", "BIT_OR", "BIT_XOR", "BOOL_AND", "BOOL_OR",
    "COUNT", "EVERY", "JSON_AGG", "JSONB_AGG", "JSON_OBJECT_AGG", "JSONB_OBJECT_AGG",
    "MAX", "MIN", "STRING_AGG", "SUM", "ARRAY_AGG", "XMLAGG",
    "CORR", "COVAR_POP", "COVAR_SAMP", "REGR_AVGX", "REGR_AVGY",
    "REGR_COUNT", "REGR_INTERCEPT", "REGR_R2", "REGR_SLOPE", "REGR_SXX",
    "REGR_SXY", "REGR_SYY", "STDDEV", "STDDEV_POP", "STDDEV_SAMP",
    "VARIANCE", "VAR_POP", "VAR_SAMP",
    "MODE", "PERCENTILE_CONT", "PERCENTILE_DISC",

    # Window functions
    "ROW_NUMBER", "RANK", "DENSE_RANK", "NTILE", "LAG", "LEAD",
    "FIRST_VALUE", "LAST_VALUE", "NTH_VALUE",
    "CUME_DIST", "PERCENT_RANK",

    # Math functions
    "ABS", "CBRT", "CEIL", "CEILING", "DEGREES", "DIV", "EXP", "FACTORIAL",
    "FLOOR", "GCD", "LCM", "LN", "LOG", "LOG10", "MIN_SCALE", "MOD",
    "PI", "POWER", "RADIANS", "ROUND", "SCALE", "SIGN", "SQRT",
    "TRIM_SCALE", "TRUNC", "WIDTH_BUCKET",
    "RANDOM", "SETSEED",
    "ACOS", "ACOSD", "ASIN", "ASIND", "ATAN", "ATAND", "ATAN2", "ATAN2D",
    "COS", "COSD", "COT", "COTD", "SIN", "SIND", "TAN", "TAND",
    "SINH", "COSH", "TANH", "ASINH", "ACOSH", "ATANH",

    # String functions
    "ASCII", "BIT_LENGTH", "BTRIM", "CHAR_LENGTH", "CHARACTER_LENGTH",
    "CHR", "CONCAT", "CONCAT_WS", "FORMAT", "INITCAP", "LEFT", "LENGTH",
    "LOWER", "LPAD", "LTRIM", "MD5", "OCTET_LENGTH", "OVERLAY",
    "PARSE_IDENT", "PG_CLIENT_ENCODING", "POSITION", "QUOTE_IDENT",
    "QUOTE_LITERAL", "QUOTE_NULLABLE", "REGEXP_COUNT", "REGEXP_INSTR",
    "REGEXP_LIKE", "REGEXP_MATCH", "REGEXP_MATCHES", "REGEXP_REPLACE",
    "REGEXP_SPLIT_TO_ARRAY", "REGEXP_SPLIT_TO_TABLE", "REGEXP_SUBSTR",
    "REPEAT", "REPLACE", "REVERSE", "RIGHT", "RPAD", "RTRIM",
    "SPLIT_PART", "STARTS_WITH", "STRING_TO_ARRAY", "STRING_TO_TABLE",
    "STRPOS", "SUBSTR", "SUBSTRING", "TO_ASCII", "TO_HEX", "TRANSLATE",
    "TRIM", "UNISTR", "UPPER",

    # Date/time functions
    "AGE", "CLOCK_TIMESTAMP", "CURRENT_DATE", "CURRENT_TIME", "CURRENT_TIMESTAMP",
    "DATE_BIN", "DATE_PART", "DATE_TRUNC", "EXTRACT", "ISFINITE",
    "JUSTIFY_DAYS", "JUSTIFY_HOURS", "JUSTIFY_INTERVAL",
    "LOCALTIME", "LOCALTIMESTAMP", "MAKE_DATE", "MAKE_INTERVAL",
    "MAKE_TIME", "MAKE_TIMESTAMP", "MAKE_TIMESTAMPTZ", "NOW",
    "STATEMENT_TIMESTAMP", "TIMEOFDAY", "TRANSACTION_TIMESTAMP",
    "TO_CHAR", "TO_DATE", "TO_NUMBER", "TO_TIMESTAMP",

    # Conditional
    "COALESCE", "NULLIF", "GREATEST", "LEAST", "CASE",

    # Type conversion
    "CAST", "TO_CHAR", "TO_DATE", "TO_NUMBER", "TO_TIMESTAMP",

    # JSON functions
    "TO_JSON", "TO_JSONB", "ARRAY_TO_JSON", "ROW_TO_JSON",
    "JSON_BUILD_ARRAY", "JSONB_BUILD_ARRAY", "JSON_BUILD_OBJECT", "JSONB_BUILD_OBJECT",
    "JSON_OBJECT", "JSONB_OBJECT", "JSON_ARRAY", "JSON_ARRAYAGG", "JSON_OBJECTAGG",
    "JSON_ARRAY_ELEMENTS", "JSONB_ARRAY_ELEMENTS", "JSON_ARRAY_ELEMENTS_TEXT", "JSONB_ARRAY_ELEMENTS_TEXT",
    "JSON_ARRAY_LENGTH", "JSONB_ARRAY_LENGTH",
    "JSON_EACH", "JSONB_EACH", "JSON_EACH_TEXT", "JSONB_EACH_TEXT",
    "JSON_EXTRACT_PATH", "JSONB_EXTRACT_PATH", "JSON_EXTRACT_PATH_TEXT", "JSONB_EXTRACT_PATH_TEXT",
    "JSON_OBJECT_KEYS", "JSONB_OBJECT_KEYS",
    "JSON_POPULATE_RECORD", "JSONB_POPULATE_RECORD", "JSON_POPULATE_RECORDSET", "JSONB_POPULATE_RECORDSET",
    "JSON_TO_RECORD", "JSONB_TO_RECORD", "JSON_TO_RECORDSET", "JSONB_TO_RECORDSET",
    "JSONB_SET", "JSONB_SET_LAX", "JSONB_INSERT", "JSONB_PATH_EXISTS",
    "JSONB_PATH_MATCH", "JSONB_PATH_QUERY", "JSONB_PATH_QUERY_ARRAY",
    "JSONB_PATH_QUERY_FIRST", "JSONB_PRETTY", "JSONB_STRIP_NULLS",
    "JSON_TYPEOF", "JSONB_TYPEOF",

    # Array functions
    "ARRAY_AGG", "ARRAY_APPEND", "ARRAY_CAT", "ARRAY_DIMS", "ARRAY_FILL",
    "ARRAY_LENGTH", "ARRAY_LOWER", "ARRAY_NDIMS", "ARRAY_POSITION",
    "ARRAY_POSITIONS", "ARRAY_PREPEND", "ARRAY_REMOVE", "ARRAY_REPLACE",
    "ARRAY_TO_STRING", "ARRAY_UPPER", "CARDINALITY", "STRING_TO_ARRAY",
    "UNNEST", "GENERATE_SERIES", "GENERATE_SUBSCRIPTS",

    # Other
    "ENCODE", "DECODE", "GET_BIT", "GET_BYTE", "SET_BIT", "SET_BYTE",
    "SHA224", "SHA256", "SHA384", "SHA512",
    "CURRENT_USER", "CURRENT_ROLE", "CURRENT_SCHEMA", "CURRENT_CATALOG",
    "SESSION_USER", "USER",
}

# =============================================================================
# SNOWFLAKE FUNCTIONS
# =============================================================================
SNOWFLAKE_FUNCTIONS: Set[str] = {
    # Aggregate functions
    "ANY_VALUE", "APPROX_COUNT_DISTINCT", "APPROX_PERCENTILE", "APPROX_TOP_K",
    "ARRAY_AGG", "AVG", "BITAND_AGG", "BITOR_AGG", "BITXOR_AGG",
    "BOOLAND_AGG", "BOOLOR_AGG", "CORR", "COUNT", "COUNT_IF",
    "COVAR_POP", "COVAR_SAMP", "GROUPING", "GROUPING_ID",
    "HASH_AGG", "HLL", "HLL_ACCUMULATE", "HLL_COMBINE", "HLL_ESTIMATE", "HLL_EXPORT", "HLL_IMPORT",
    "KURTOSIS", "LISTAGG", "MAX", "MEDIAN", "MIN", "MINHASH",
    "MINHASH_COMBINE", "MODE", "OBJECT_AGG", "PERCENTILE_CONT", "PERCENTILE_DISC",
    "REGR_AVGX", "REGR_AVGY", "REGR_COUNT", "REGR_INTERCEPT", "REGR_R2",
    "REGR_SLOPE", "REGR_SXX", "REGR_SXY", "REGR_SYY", "REGR_VALX", "REGR_VALY",
    "SKEW", "STDDEV", "STDDEV_POP", "STDDEV_SAMP", "SUM",
    "VAR_POP", "VAR_SAMP", "VARIANCE", "VARIANCE_POP", "VARIANCE_SAMP",

    # Window functions
    "CONDITIONAL_CHANGE_EVENT", "CONDITIONAL_TRUE_EVENT",
    "CUME_DIST", "DENSE_RANK", "FIRST_VALUE", "LAG", "LAST_VALUE", "LEAD",
    "NTH_VALUE", "NTILE", "PERCENT_RANK", "RANK", "RATIO_TO_REPORT", "ROW_NUMBER",
    "WIDTH_BUCKET",

    # Math functions
    "ABS", "ACOS", "ACOSH", "ASIN", "ASINH", "ATAN", "ATAN2", "ATANH",
    "CBRT", "CEIL", "CEILING", "COS", "COSH", "COT", "DEGREES",
    "DIV0", "DIV0NULL", "EXP", "FACTORIAL", "FLOOR", "HAVERSINE",
    "LN", "LOG", "MOD", "PI", "POWER", "POW", "RADIANS", "RANDOM",
    "ROUND", "SIGN", "SIN", "SINH", "SQRT", "SQUARE", "TAN", "TANH",
    "TRUNC", "TRUNCATE",

    # String functions
    "ASCII", "BASE64_DECODE_BINARY", "BASE64_DECODE_STRING", "BASE64_ENCODE",
    "BIT_LENGTH", "CHAR", "CHARINDEX", "CHR", "COLLATE", "COLLATION",
    "COMPRESS", "CONCAT", "CONCAT_WS", "CONTAINS", "DECOMPRESS_BINARY", "DECOMPRESS_STRING",
    "EDITDISTANCE", "ENDSWITH", "HEX_DECODE_BINARY", "HEX_DECODE_STRING", "HEX_ENCODE",
    "INITCAP", "INSERT", "JAROWINKLER_SIMILARITY", "LEFT", "LENGTH", "LEN",
    "LOWER", "LPAD", "LTRIM", "MD5", "MD5_BINARY", "MD5_HEX",
    "MD5_NUMBER_LOWER64", "MD5_NUMBER_UPPER64", "OCTET_LENGTH", "PARSE_IP",
    "PARSE_URL", "POSITION", "REGEXP", "REGEXP_COUNT", "REGEXP_INSTR",
    "REGEXP_LIKE", "REGEXP_REPLACE", "REGEXP_SUBSTR", "REGEXP_SUBSTR_ALL",
    "REPEAT", "REPLACE", "REVERSE", "RIGHT", "RPAD", "RTRIM", "RTRIMMED_LENGTH",
    "SHA1", "SHA1_BINARY", "SHA1_HEX", "SHA2", "SHA2_BINARY", "SHA2_HEX",
    "SOUNDEX", "SOUNDEX_P123", "SPACE", "SPLIT", "SPLIT_PART", "SPLIT_TO_TABLE",
    "STARTSWITH", "STRTOK", "STRTOK_SPLIT_TO_TABLE", "STRTOK_TO_ARRAY",
    "SUBSTR", "SUBSTRING", "TRANSLATE", "TRIM", "TRY_BASE64_DECODE_BINARY",
    "TRY_BASE64_DECODE_STRING", "TRY_HEX_DECODE_BINARY", "TRY_HEX_DECODE_STRING",
    "UNICODE", "UPPER",

    # Date/time functions
    "ADD_MONTHS", "CONVERT_TIMEZONE", "CURRENT_DATE", "CURRENT_TIME", "CURRENT_TIMESTAMP",
    "DATE_FROM_PARTS", "DATE_PART", "DATE_TRUNC", "DATEADD", "DATEDIFF",
    "DAYNAME", "EXTRACT", "GETDATE", "HOUR", "LAST_DAY", "LOCALTIMESTAMP",
    "MINUTE", "MONTH", "MONTHNAME", "NEXT_DAY", "PREVIOUS_DAY", "QUARTER",
    "SECOND", "SYSDATE", "TIME_FROM_PARTS", "TIME_SLICE", "TIMEADD", "TIMEDIFF",
    "TIMESTAMP_FROM_PARTS", "TIMESTAMPADD", "TIMESTAMPDIFF", "TO_DATE", "TO_TIME",
    "TO_TIMESTAMP", "TO_TIMESTAMP_LTZ", "TO_TIMESTAMP_NTZ", "TO_TIMESTAMP_TZ",
    "TRUNC", "TRY_TO_DATE", "TRY_TO_TIME", "TRY_TO_TIMESTAMP",
    "TRY_TO_TIMESTAMP_LTZ", "TRY_TO_TIMESTAMP_NTZ", "TRY_TO_TIMESTAMP_TZ",
    "WEEK", "WEEKISO", "YEAR", "YEAROFWEEK", "YEAROFWEEKISO",

    # Conditional
    "BOOLAND", "BOOLNOT", "BOOLOR", "BOOLXOR",
    "CASE", "COALESCE", "DECODE", "EQUAL_NULL", "GREATEST", "IFF",
    "IFNULL", "LEAST", "NULLIF", "NULLIFZERO", "NVL", "NVL2",
    "REGR_VALX", "REGR_VALY", "ZEROIFNULL",

    # Conversion
    "CAST", "TO_ARRAY", "TO_BINARY", "TO_BOOLEAN", "TO_CHAR", "TO_VARCHAR",
    "TO_DECIMAL", "TO_DOUBLE", "TO_NUMBER", "TO_NUMERIC", "TO_OBJECT",
    "TO_VARIANT", "TRY_CAST", "TRY_TO_BINARY", "TRY_TO_BOOLEAN",
    "TRY_TO_DECIMAL", "TRY_TO_DOUBLE", "TRY_TO_NUMBER", "TRY_TO_NUMERIC",

    # Semi-structured data
    "ARRAY_APPEND", "ARRAY_CAT", "ARRAY_COMPACT", "ARRAY_CONSTRUCT",
    "ARRAY_CONSTRUCT_COMPACT", "ARRAY_CONTAINS", "ARRAY_DISTINCT", "ARRAY_EXCEPT",
    "ARRAY_FLATTEN", "ARRAY_GENERATE_RANGE", "ARRAY_INSERT", "ARRAY_INTERSECTION",
    "ARRAY_MAX", "ARRAY_MIN", "ARRAY_POSITION", "ARRAY_PREPEND", "ARRAY_REMOVE",
    "ARRAY_REMOVE_AT", "ARRAY_REVERSE", "ARRAY_SIZE", "ARRAY_SLICE",
    "ARRAY_SORT", "ARRAY_TO_STRING", "ARRAY_UNIQUE_AGG", "ARRAYS_OVERLAP",
    "AS_ARRAY", "AS_BINARY", "AS_BOOLEAN", "AS_CHAR", "AS_DATE", "AS_DECIMAL",
    "AS_DOUBLE", "AS_INTEGER", "AS_NUMBER", "AS_OBJECT", "AS_REAL", "AS_TIME",
    "AS_TIMESTAMP_LTZ", "AS_TIMESTAMP_NTZ", "AS_TIMESTAMP_TZ", "AS_VARCHAR",
    "CHECK_JSON", "CHECK_XML", "FLATTEN", "GET", "GET_IGNORE_CASE", "GET_PATH",
    "IS_ARRAY", "IS_BINARY", "IS_BOOLEAN", "IS_CHAR", "IS_DATE", "IS_DATE_VALUE",
    "IS_DECIMAL", "IS_DOUBLE", "IS_INTEGER", "IS_NULL_VALUE", "IS_OBJECT",
    "IS_REAL", "IS_TIME", "IS_TIMESTAMP_LTZ", "IS_TIMESTAMP_NTZ", "IS_TIMESTAMP_TZ",
    "IS_VARCHAR", "JSON_EXTRACT_PATH_TEXT", "OBJECT_CONSTRUCT", "OBJECT_CONSTRUCT_KEEP_NULL",
    "OBJECT_DELETE", "OBJECT_INSERT", "OBJECT_KEYS", "OBJECT_PICK",
    "PARSE_JSON", "PARSE_XML", "STRIP_NULL_VALUE", "TRY_PARSE_JSON",
    "TYPEOF", "XMLGET",

    # Utility
    "CURRENT_ACCOUNT", "CURRENT_AVAILABLE_ROLES", "CURRENT_CLIENT",
    "CURRENT_DATABASE", "CURRENT_IP_ADDRESS", "CURRENT_REGION", "CURRENT_ROLE",
    "CURRENT_SCHEMA", "CURRENT_SCHEMAS", "CURRENT_SESSION", "CURRENT_STATEMENT",
    "CURRENT_TRANSACTION", "CURRENT_USER", "CURRENT_VERSION", "CURRENT_WAREHOUSE",
    "GET_DDL", "HASH", "LAST_QUERY_ID", "LAST_TRANSACTION", "LOCALTIME",
    "SYSTEM$TYPEOF", "UUID_STRING",
}


# =============================================================================
# DIALECT CONFIGURATIONS
# =============================================================================

DIALECT_CONFIGS: Dict[Dialect, DialectConfig] = {
    Dialect.SQLITE: DialectConfig(
        name=Dialect.SQLITE,
        sqlglot_dialect="sqlite",
        default_schema=None,
        supports_schemas=False,
        supports_cte=True,
        supports_window_functions=True,
        supports_json=True,
        supports_arrays=False,
        builtin_functions=SQLITE_FUNCTIONS,
        description="SQLite - Lightweight embedded database"
    ),

    Dialect.DUCKDB: DialectConfig(
        name=Dialect.DUCKDB,
        sqlglot_dialect="duckdb",
        default_schema="main",
        supports_schemas=True,
        supports_cte=True,
        supports_window_functions=True,
        supports_json=True,
        supports_arrays=True,
        builtin_functions=DUCKDB_FUNCTIONS,
        description="DuckDB - Fast analytical database"
    ),

    Dialect.BIGQUERY: DialectConfig(
        name=Dialect.BIGQUERY,
        sqlglot_dialect="bigquery",
        default_schema=None,  # Uses project.dataset.table
        supports_schemas=True,
        supports_cte=True,
        supports_window_functions=True,
        supports_json=True,
        supports_arrays=True,
        builtin_functions=BIGQUERY_FUNCTIONS,
        description="Google BigQuery - Cloud data warehouse"
    ),

    Dialect.POSTGRESQL: DialectConfig(
        name=Dialect.POSTGRESQL,
        sqlglot_dialect="postgres",
        default_schema="public",
        supports_schemas=True,
        supports_cte=True,
        supports_window_functions=True,
        supports_json=True,
        supports_arrays=True,
        builtin_functions=POSTGRESQL_FUNCTIONS,
        description="PostgreSQL - Advanced open source database"
    ),

    Dialect.SNOWFLAKE: DialectConfig(
        name=Dialect.SNOWFLAKE,
        sqlglot_dialect="snowflake",
        default_schema="PUBLIC",
        supports_schemas=True,
        supports_cte=True,
        supports_window_functions=True,
        supports_json=True,
        supports_arrays=True,
        builtin_functions=SNOWFLAKE_FUNCTIONS,
        description="Snowflake - Cloud data platform"
    ),

    Dialect.MYSQL: DialectConfig(
        name=Dialect.MYSQL,
        sqlglot_dialect="mysql",
        default_schema=None,  # MySQL uses databases, not schemas
        supports_schemas=False,
        supports_cte=True,  # MySQL 8.0+
        supports_window_functions=True,  # MySQL 8.0+
        supports_json=True,
        supports_arrays=False,
        builtin_functions=set(),  # TODO: Add MySQL functions
        description="MySQL - Popular open source database"
    ),
}


def get_dialect_config(dialect: str) -> DialectConfig:
    """
    Get configuration for a dialect by name.

    Args:
        dialect: Dialect name (e.g., "sqlite", "bigquery", "postgresql")

    Returns:
        DialectConfig for the specified dialect

    Raises:
        ValueError: If dialect is not supported
    """
    try:
        dialect_enum = Dialect(dialect.lower())
        return DIALECT_CONFIGS[dialect_enum]
    except (ValueError, KeyError):
        supported = ", ".join(d.value for d in Dialect)
        raise ValueError(f"Unsupported dialect: {dialect}. Supported: {supported}")


def get_supported_dialects() -> list:
    """Get list of all supported dialect names."""
    return [d.value for d in Dialect]
