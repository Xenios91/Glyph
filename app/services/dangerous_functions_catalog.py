"""Catalog of dangerous/insecure C library functions for binary analysis.

This module provides a data-driven catalog of functions considered insecure
or dangerous, organized by vulnerability category. Each entry includes the
function name, severity level, CWE reference, description, and a safe
alternative recommendation.

The catalog is used by the DangerousFunctionScanner to identify potentially
vulnerable code patterns in decompiled binaries.
"""

from dataclasses import dataclass
from typing import Final, Literal

Severity = Literal["Critical", "High", "Medium", "Low"]


@dataclass(frozen=True)
class DangerousFunctionEntry:
    """A single entry in the dangerous function catalog.

    Attributes:
        name: The function name as it appears in decompiled code.
        category: Vulnerability category (e.g., "Buffer Overflow").
        severity: Risk level — Critical, High, Medium, or Low.
        cwe: CWE identifier (e.g., "CWE-120").
        description: Why this function is dangerous.
        safe_alternative: Recommended replacement function(s).
    """

    name: str
    category: str
    severity: Severity
    cwe: str
    description: str
    safe_alternative: str


# ---------------------------------------------------------------------------
# Catalog entries by category
# ---------------------------------------------------------------------------

_BUFFER_OVERFLOW: list[DangerousFunctionEntry] = [
    DangerousFunctionEntry(
        name="gets",
        category="Buffer Overflow",
        severity="Critical",
        cwe="CWE-120",
        description="Reads a line from stdin with no bounds checking. The buffer can always be overflowed, making this function inherently unsafe.",
        safe_alternative="fgets()",
    ),
    DangerousFunctionEntry(
        name="strcpy",
        category="Buffer Overflow",
        severity="High",
        cwe="CWE-120",
        description="Copies a string without checking the destination buffer size. If the source is longer than the destination, a buffer overflow occurs.",
        safe_alternative="strncpy(), strlcpy(), or strcpy_s()",
    ),
    DangerousFunctionEntry(
        name="strcat",
        category="Buffer Overflow",
        severity="High",
        cwe="CWE-120",
        description="Concatenates strings without checking the destination buffer size. Can overflow the destination buffer if the combined length exceeds its capacity.",
        safe_alternative="strncat(), strlcat(), or strcat_s()",
    ),
    DangerousFunctionEntry(
        name="sprintf",
        category="Buffer Overflow",
        severity="High",
        cwe="CWE-120",
        description="Formats data into a buffer without bounds checking. If the formatted output exceeds the buffer size, a buffer overflow occurs.",
        safe_alternative="snprintf() or sprintf_s()",
    ),
    DangerousFunctionEntry(
        name="vsprintf",
        category="Buffer Overflow",
        severity="High",
        cwe="CWE-120",
        description="Variadic version of sprintf with no bounds checking. Subject to the same overflow risks as sprintf.",
        safe_alternative="vsnprintf() or vsprintf_s()",
    ),
    DangerousFunctionEntry(
        name="scanf",
        category="Buffer Overflow",
        severity="High",
        cwe="CWE-120",
        description="When used with %s format specifier, reads unbounded input into a buffer. Can be exploited to overflow the target buffer.",
        safe_alternative="Use width limiters (e.g., %255s) or fgets() with sscanf()",
    ),
    DangerousFunctionEntry(
        name="wcscpy",
        category="Buffer Overflow",
        severity="High",
        cwe="CWE-120",
        description="Wide-character version of strcpy. Copies without bounds checking.",
        safe_alternative="wcsncpy(), or wcscpy_s()",
    ),
    DangerousFunctionEntry(
        name="wcscat",
        category="Buffer Overflow",
        severity="High",
        cwe="CWE-120",
        description="Wide-character version of strcat. Concatenates without bounds checking.",
        safe_alternative="wcsncat(), or wcscat_s()",
    ),
    DangerousFunctionEntry(
        name="wvsprintf",
        category="Buffer Overflow",
        severity="High",
        cwe="CWE-120",
        description="Wide-character variadic sprintf with no bounds checking.",
        safe_alternative="vswprintf() with explicit buffer size",
    ),
    DangerousFunctionEntry(
        name="_snprintf",
        category="Buffer Overflow",
        severity="Medium",
        cwe="CWE-120",
        description="Platform-specific snprintf variant that may not null-terminate the output buffer when the output would exceed the given size.",
        safe_alternative="snprintf() with explicit null-termination check",
    ),
    DangerousFunctionEntry(
        name="read",
        category="Buffer Overflow",
        severity="Medium",
        cwe="CWE-120",
        description="Low-level I/O that reads bytes without bounds awareness. If the caller does not validate the count parameter, buffer overflow is possible.",
        safe_alternative="Validate count against buffer size before calling",
    ),
    DangerousFunctionEntry(
        name="recv",
        category="Buffer Overflow",
        severity="Medium",
        cwe="CWE-120",
        description="Receives data on a socket. If the length parameter exceeds the buffer size, a buffer overflow occurs.",
        safe_alternative="Validate length parameter against buffer size",
    ),
    DangerousFunctionEntry(
        name="recvfrom",
        category="Buffer Overflow",
        severity="Medium",
        cwe="CWE-120",
        description="Receives data from a specific socket address. Buffer overflow possible if len parameter is not validated.",
        safe_alternative="Validate len parameter against buffer size",
    ),
]

_FORMAT_STRING: list[DangerousFunctionEntry] = [
    DangerousFunctionEntry(
        name="printf",
        category="Format String",
        severity="High",
        cwe="CWE-134",
        description="When called with a user-controlled string as the format argument (e.g., printf(user_input)), it can leak stack data or cause crashes via %n.",
        safe_alternative='Always use a literal format string: printf("%s", user_input)',
    ),
    DangerousFunctionEntry(
        name="fprintf",
        category="Format String",
        severity="High",
        cwe="CWE-134",
        description="Same format string vulnerability as printf but writes to a file stream.",
        safe_alternative='Always use a literal format string: fprintf(fp, "%s", user_input)',
    ),
    DangerousFunctionEntry(
        name="sprintf",
        category="Format String",
        severity="High",
        cwe="CWE-134",
        description="In addition to buffer overflow risks, is vulnerable to format string attacks when the format is user-controlled.",
        safe_alternative="snprintf() with a literal format string",
    ),
    DangerousFunctionEntry(
        name="snprintf",
        category="Format String",
        severity="Medium",
        cwe="CWE-134",
        description="While it prevents buffer overflow, still vulnerable to format string attacks if the format argument is user-controlled.",
        safe_alternative="Always use a literal format string",
    ),
    DangerousFunctionEntry(
        name="syslog",
        category="Format String",
        severity="High",
        cwe="CWE-134",
        description="Logs a message to the system log. If the format parameter is user-controlled, it enables format string attacks.",
        safe_alternative='syslog(priority, "%s", user_input)',
    ),
    DangerousFunctionEntry(
        name="vprintf",
        category="Format String",
        severity="High",
        cwe="CWE-134",
        description="Variadic printf variant. Vulnerable to format string attacks if format is derived from untrusted input.",
        safe_alternative="Use a literal format string",
    ),
    DangerousFunctionEntry(
        name="vfprintf",
        category="Format String",
        severity="High",
        cwe="CWE-134",
        description="Variadic fprintf variant. Same format string risks as vprintf.",
        safe_alternative="Use a literal format string",
    ),
    DangerousFunctionEntry(
        name="vsprintf",
        category="Format String",
        severity="High",
        cwe="CWE-134",
        description="Variadic sprintf. Combines buffer overflow and format string risks.",
        safe_alternative="vsnprintf() with a literal format string",
    ),
    DangerousFunctionEntry(
        name="vsnprintf",
        category="Format String",
        severity="Medium",
        cwe="CWE-134",
        description="While it prevents buffer overflow, still vulnerable to format string attacks.",
        safe_alternative="Always use a literal format string",
    ),
]

_INTEGER_OVERFLOW: list[DangerousFunctionEntry] = [
    DangerousFunctionEntry(
        name="atoi",
        category="Integer Overflow",
        severity="Medium",
        cwe="CWE-190",
        description="Converts a string to an integer with no overflow detection. Returns INT_MAX or INT_MIN silently on overflow, leading to undefined behavior.",
        safe_alternative="strtol() with explicit range checking",
    ),
    DangerousFunctionEntry(
        name="atol",
        category="Integer Overflow",
        severity="Medium",
        cwe="CWE-190",
        description="Converts a string to a long with no overflow detection.",
        safe_alternative="strtol() with explicit range checking",
    ),
    DangerousFunctionEntry(
        name="atoll",
        category="Integer Overflow",
        severity="Medium",
        cwe="CWE-190",
        description="Converts a string to a long long with no overflow detection.",
        safe_alternative="strtoll() with explicit range checking",
    ),
    DangerousFunctionEntry(
        name="atof",
        category="Integer Overflow",
        severity="Medium",
        cwe="CWE-190",
        description="Converts a string to a double. Can silently overflow or lose precision.",
        safe_alternative="strtod() with errno checking",
    ),
    DangerousFunctionEntry(
        name="strtoul",
        category="Integer Overflow",
        severity="Medium",
        cwe="CWE-190",
        description="Converts a string to unsigned long. Caller must check errno for ERANGE to detect overflows.",
        safe_alternative="strtoul() with explicit errno/ERANGE checking",
    ),
    DangerousFunctionEntry(
        name="strtol",
        category="Integer Overflow",
        severity="Medium",
        cwe="CWE-190",
        description="Converts a string to long. Caller must check errno for ERANGE to detect overflows.",
        safe_alternative="strtol() with explicit errno/ERANGE checking",
    ),
]

_RACE_CONDITION: list[DangerousFunctionEntry] = [
    DangerousFunctionEntry(
        name="tmpnam",
        category="Race Condition",
        severity="Medium",
        cwe="CWE-377",
        description="Generates a temporary file name but does not create the file. Another process can create the file between the name generation and the actual file creation.",
        safe_alternative="mkstemp() which atomically creates the file",
    ),
    DangerousFunctionEntry(
        name="tempnam",
        category="Race Condition",
        severity="Medium",
        cwe="CWE-377",
        description="Similar to tmpnam but allows directory and prefix hints. Still subject to TOCTOU race conditions.",
        safe_alternative="mkstemp()",
    ),
    DangerousFunctionEntry(
        name="mktemp",
        category="Race Condition",
        severity="Medium",
        cwe="CWE-377",
        description="Generates a unique filename from a template. Subject to TOCTOU races between name generation and file creation.",
        safe_alternative="mkstemp() or tmpfile()",
    ),
]

_CRYPTOGRAPHIC: list[DangerousFunctionEntry] = [
    DangerousFunctionEntry(
        name="MD5_Init",
        category="Cryptographic Weakness",
        severity="Medium",
        cwe="CWE-328",
        description="Initializes MD5 hash computation. MD5 is cryptographically broken and vulnerable to collision attacks.",
        safe_alternative="SHA-256 or SHA-3 via SHA256_Init()",
    ),
    DangerousFunctionEntry(
        name="MD5_Update",
        category="Cryptographic Weakness",
        severity="Medium",
        cwe="CWE-328",
        description="Updates MD5 hash state. MD5 should not be used for security-critical hashing.",
        safe_alternative="SHA256_Update()",
    ),
    DangerousFunctionEntry(
        name="MD5_Final",
        category="Cryptographic Weakness",
        severity="Medium",
        cwe="CWE-328",
        description="Finalizes MD5 hash computation.",
        safe_alternative="SHA256_Final()",
    ),
    DangerousFunctionEntry(
        name="SHA1_Init",
        category="Cryptographic Weakness",
        severity="Medium",
        cwe="CWE-328",
        description="Initializes SHA-1 hash computation. SHA-1 is deprecated and vulnerable to collision attacks (SHAttered).",
        safe_alternative="SHA256_Init()",
    ),
    DangerousFunctionEntry(
        name="DES_set_key",
        category="Cryptographic Weakness",
        severity="Medium",
        cwe="CWE-328",
        description="Sets a DES encryption key. DES uses a 56-bit key which is trivially brute-forceable.",
        safe_alternative="AES via AES_set_encrypt_key()",
    ),
    DangerousFunctionEntry(
        name="DES_ecb_encrypt",
        category="Cryptographic Weakness",
        severity="Medium",
        cwe="CWE-328",
        description="Performs DES encryption in ECB mode. Both DES and ECB mode are insecure.",
        safe_alternative="AES in CBC or GCM mode",
    ),
    DangerousFunctionEntry(
        name="RC4_setkey",
        category="Cryptographic Weakness",
        severity="Medium",
        cwe="CWE-328",
        description="Initializes RC4 stream cipher. RC4 has known biases and is deprecated for TLS and other protocols.",
        safe_alternative="AES-CTR or ChaCha20",
    ),
    DangerousFunctionEntry(
        name="rand",
        category="Cryptographic Weakness",
        severity="Medium",
        cwe="CWE-330",
        description="Returns pseudo-random numbers using a predictable algorithm. Not suitable for cryptographic purposes.",
        safe_alternative="getrandom(), /dev/urandom, or CSPRNG",
    ),
    DangerousFunctionEntry(
        name="srand",
        category="Cryptographic Weakness",
        severity="Low",
        cwe="CWE-330",
        description="Seeds the pseudo-random number generator. Often seeded with time(), making output predictable.",
        safe_alternative="Use a CSPRNG seeded from /dev/urandom",
    ),
]

_COMMAND_INJECTION: list[DangerousFunctionEntry] = [
    DangerousFunctionEntry(
        name="system",
        category="Command Injection",
        severity="Critical",
        cwe="CWE-78",
        description="Executes a command via the system shell. If the command string contains user input, it allows arbitrary command execution.",
        safe_alternative="execve() with explicit argument vector, or a whitelist of allowed commands",
    ),
    DangerousFunctionEntry(
        name="popen",
        category="Command Injection",
        severity="Critical",
        cwe="CWE-78",
        description="Opens a process by creating a pipe and executing a shell command. Vulnerable to command injection if the command includes user input.",
        safe_alternative="fork() + execve() with explicit arguments",
    ),
    DangerousFunctionEntry(
        name="exec",
        category="Command Injection",
        severity="High",
        cwe="CWE-78",
        description="Executes a program. If the path or arguments include unvalidated user input, it can lead to command injection.",
        safe_alternative="execve() with fully validated arguments",
    ),
    DangerousFunctionEntry(
        name="execvp",
        category="Command Injection",
        severity="High",
        cwe="CWE-78",
        description="Searches PATH and executes a program. Vulnerable to command injection if program name or args contain user input.",
        safe_alternative="Use absolute paths with execve() and validate all arguments",
    ),
    DangerousFunctionEntry(
        name="execl",
        category="Command Injection",
        severity="High",
        cwe="CWE-78",
        description="Executes a program with explicit arguments. Still dangerous if any argument is derived from untrusted input.",
        safe_alternative="Validate and sanitize all arguments before calling",
    ),
    DangerousFunctionEntry(
        name="execlp",
        category="Command Invocation",
        severity="High",
        cwe="CWE-78",
        description="Like execl but searches PATH. PATH manipulation can cause execution of unintended programs.",
        safe_alternative="Use absolute paths with execve()",
    ),
    DangerousFunctionEntry(
        name="execv",
        category="Command Injection",
        severity="High",
        cwe="CWE-78",
        description="Executes a program with a vector of arguments. Dangerous with unvalidated input.",
        safe_alternative="Validate all arguments before calling",
    ),
    DangerousFunctionEntry(
        name="execvpe",
        category="Command Injection",
        severity="High",
        cwe="CWE-78",
        description="Executes a program with custom environment. Still vulnerable if program name or args are untrusted.",
        safe_alternative="Validate all inputs and use absolute paths",
    ),
]

_PATH_TRAVERSAL: list[DangerousFunctionEntry] = [
    DangerousFunctionEntry(
        name="chdir",
        category="Path Traversal",
        severity="High",
        cwe="CWE-22",
        description="Changes the current working directory. If the path includes unvalidated user input, an attacker can traverse to arbitrary directories.",
        safe_alternative="Validate and canonicalize paths before calling",
    ),
    DangerousFunctionEntry(
        name="chmod",
        category="Path Traversal",
        severity="High",
        cwe="CWE-22",
        description="Changes file permissions. If the path is user-controlled, an attacker can modify permissions on arbitrary files.",
        safe_alternative="Validate and canonicalize the path",
    ),
    DangerousFunctionEntry(
        name="chown",
        category="Path Traversal",
        severity="High",
        cwe="CWE-22",
        description="Changes file ownership. User-controlled paths allow ownership changes on arbitrary files.",
        safe_alternative="Validate and canonicalize the path",
    ),
    DangerousFunctionEntry(
        name="rename",
        category="Path Traversal",
        severity="Medium",
        cwe="CWE-22",
        description="Renames a file. User-controlled paths can cause unintended files to be renamed.",
        safe_alternative="Validate both old and new paths",
    ),
    DangerousFunctionEntry(
        name="unlink",
        category="Path Traversal",
        severity="High",
        cwe="CWE-22",
        description="Deletes a file. If the path is user-controlled, an attacker can delete arbitrary files.",
        safe_alternative="Validate and canonicalize the path",
    ),
    DangerousFunctionEntry(
        name="rmdir",
        category="Path Traversal",
        severity="Medium",
        cwe="CWE-22",
        description="Removes a directory. User-controlled paths allow deletion of arbitrary directories.",
        safe_alternative="Validate and canonicalize the path",
    ),
]

_MEMORY_CORRUPTION: list[DangerousFunctionEntry] = [
    DangerousFunctionEntry(
        name="memalign",
        category="Memory Corruption",
        severity="Medium",
        cwe="CWE-762",
        description="Allocates aligned memory. Misuse can lead to memory corruption if the returned pointer is not properly freed with free().",
        safe_alternative="Ensure paired free() calls or use posix_memalign()",
    ),
    DangerousFunctionEntry(
        name="realloc",
        category="Memory Corruption",
        severity="Medium",
        cwe="CWE-762",
        description="Reallocates memory. If the original pointer is dangling or the size calculation overflows, memory corruption occurs.",
        safe_alternative="Check size for overflow and store result in a new pointer",
    ),
    DangerousFunctionEntry(
        name="free",
        category="Memory Corruption",
        severity="Medium",
        cwe="CWE-416",
        description="Frees allocated memory. Double-free or use-after-free bugs can cause arbitrary code execution.",
        safe_alternative="Set pointer to NULL after free() and track allocation state",
    ),
    DangerousFunctionEntry(
        name="memcpy",
        category="Memory Corruption",
        severity="Medium",
        cwe="CWE-120",
        description="Copies memory region. If the size parameter is incorrect or source/destination overlap, memory corruption occurs.",
        safe_alternative="Validate size parameter and use memmove() for overlapping regions",
    ),
    DangerousFunctionEntry(
        name="memmove",
        category="Memory Corruption",
        severity="Low",
        cwe="CWE-120",
        description="Safer than memcpy for overlapping regions, but incorrect size parameters still cause corruption.",
        safe_alternative="Validate size parameter against actual buffer sizes",
    ),
    DangerousFunctionEntry(
        name="memset",
        category="Memory Corruption",
        severity="Low",
        cwe="CWE-120",
        description="Fills memory with a byte value. Incorrect size can cause out-of-bounds writes.",
        safe_alternative="Validate size parameter against buffer size",
    ),
]

_INFORMATION_LEAK: list[DangerousFunctionEntry] = [
    DangerousFunctionEntry(
        name="getenv",
        category="Information Leak",
        severity="Low",
        cwe="CWE-200",
        description="Retrieves environment variables which may contain sensitive information like passwords or tokens.",
        safe_alternative="Avoid relying on environment variables for secrets; use a secure credential store",
    ),
    DangerousFunctionEntry(
        name="getpwuid",
        category="Information Leak",
        severity="Low",
        cwe="CWE-200",
        description="Returns password file entry for a given UID. Can leak user information.",
        safe_alternative="Getpwuid_r() with explicit buffer management",
    ),
    DangerousFunctionEntry(
        name="getlogin",
        category="Information Leak",
        severity="Low",
        cwe="CWE-200",
        description="Returns the current login name. Can be used to enumerate users.",
        safe_alternative="getlogin_r() with buffer size control",
    ),
    DangerousFunctionEntry(
        name="getpid",
        category="Information Leak",
        severity="Low",
        cwe="CWE-200",
        description="Returns the process ID. Can aid in process targeting for attacks.",
        safe_alternative="Generally safe but avoid exposing PID in external interfaces",
    ),
    DangerousFunctionEntry(
        name="gethostname",
        category="Information Leak",
        severity="Low",
        cwe="CWE-200",
        description="Returns the hostname. Can leak internal network information.",
        safe_alternative="Avoid exposing hostname in external responses",
    ),
]

_THREAD_SAFETY: list[DangerousFunctionEntry] = [
    DangerousFunctionEntry(
        name="strtok",
        category="Thread Safety",
        severity="Low",
        cwe="CWE-479",
        description="Uses a static internal buffer, making it non-reentrant and unsafe in multi-threaded programs.",
        safe_alternative="strtok_r() or strtok_s()",
    ),
    DangerousFunctionEntry(
        name="gmtime",
        category="Thread Safety",
        severity="Low",
        cwe="CWE-479",
        description="Returns a pointer to a static buffer. Not thread-safe.",
        safe_alternative="gmtime_r()",
    ),
    DangerousFunctionEntry(
        name="localtime",
        category="Thread Safety",
        severity="Low",
        cwe="CWE-479",
        description="Returns a pointer to a static buffer. Not thread-safe.",
        safe_alternative="localtime_r()",
    ),
    DangerousFunctionEntry(
        name="ctime",
        category="Thread Safety",
        severity="Low",
        cwe="CWE-479",
        description="Returns a pointer to a static buffer. Not thread-safe.",
        safe_alternative="ctime_r()",
    ),
    DangerousFunctionEntry(
        name="asctime",
        category="Thread Safety",
        severity="Low",
        cwe="CWE-479",
        description="Returns a pointer to a static buffer. Not thread-safe.",
        safe_alternative="asctime_r()",
    ),
]

_NETWORK_SECURITY: list[DangerousFunctionEntry] = [
    DangerousFunctionEntry(
        name="bind",
        category="Network Security",
        severity="Low",
        cwe="CWE-200",
        description="Binds a socket to an address. Binding to 0.0.0.0 exposes the service on all interfaces.",
        safe_alternative="Bind to specific interfaces and use firewall rules",
    ),
    DangerousFunctionEntry(
        name="listen",
        category="Network Security",
        severity="Low",
        cwe="CWE-200",
        description="Puts a socket in listening state. Backlog parameter controls pending connection queue.",
        safe_alternative="Set an appropriate backlog and implement connection rate limiting",
    ),
    DangerousFunctionEntry(
        name="accept",
        category="Network Security",
        severity="Low",
        cwe="CWE-200",
        description="Accepts incoming connections. Without proper validation, can be exploited for resource exhaustion.",
        safe_alternative="Validate client address and implement connection limits",
    ),
]


# ---------------------------------------------------------------------------
# Build flat lookup and category index
# ---------------------------------------------------------------------------

# All entries combined (preserves order for iteration)
_ALL_ENTRIES: Final[list[DangerousFunctionEntry]] = (
    _BUFFER_OVERFLOW
    + _FORMAT_STRING
    + _INTEGER_OVERFLOW
    + _RACE_CONDITION
    + _CRYPTOGRAPHIC
    + _COMMAND_INJECTION
    + _PATH_TRAVERSAL
    + _MEMORY_CORRUPTION
    + _INFORMATION_LEAK
    + _THREAD_SAFETY
    + _NETWORK_SECURITY
)

# Case-insensitive lookup: "strcpy" -> entry, "STRCPY" -> same entry
FUNCTION_LOOKUP: Final[dict[str, DangerousFunctionEntry]] = {entry.name.lower(): entry for entry in _ALL_ENTRIES}

# Category -> list of entries
CATEGORY_INDEX: Final[dict[str, list[DangerousFunctionEntry]]] = {}
for entry in _ALL_ENTRIES:
    CATEGORY_INDEX.setdefault(entry.category, []).append(entry)


def get_entry(function_name: str) -> DangerousFunctionEntry | None:
    """Look up a dangerous function entry by name (case-insensitive).

    Args:
        function_name: The function name to look up.

    Returns:
        The catalog entry if found, otherwise None.
    """
    return FUNCTION_LOOKUP.get(function_name.lower())


def get_all_entries() -> list[DangerousFunctionEntry]:
    """Return all catalog entries.

    Returns:
        List of all DangerousFunctionEntry instances.
    """
    return list(_ALL_ENTRIES)


def get_categories() -> list[str]:
    """Return all vulnerability categories in the catalog.

    Returns:
        Sorted list of category names.
    """
    return sorted(CATEGORY_INDEX.keys())


def get_entries_by_category(category: str) -> list[DangerousFunctionEntry]:
    """Return all entries for a given category.

    Args:
        category: Category name (e.g., "Buffer Overflow").

    Returns:
        List of entries in that category, or empty list if category not found.
    """
    return CATEGORY_INDEX.get(category, [])


def get_severity_order(severity: Severity) -> int:
    """Return numeric sort order for a severity level.

    Lower numbers indicate higher severity.

    Args:
        severity: The severity level string.

    Returns:
        Integer sort order (Critical=0, High=1, Medium=2, Low=3).
    """
    order_map: dict[str, int] = {
        "Critical": 0,
        "High": 1,
        "Medium": 2,
        "Low": 3,
    }
    return order_map.get(severity, 99)
