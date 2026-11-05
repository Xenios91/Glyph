"""Catalog of malware behavior signatures for binary analysis.

This module provides a data-driven catalog of behaviors commonly associated
with malware, organized by behavior category. Each entry includes a stable
signature id, a human-readable behavior name, severity level, the detection
method used to find it, the patterns to match, a description of what the
behavior means, and an optional MITRE ATT&CK technique reference.

The catalog is used by the BehavioralScanner to identify potentially
malicious behaviors in decompiled binaries.

Pattern semantics per detection method:
    - ``api_call``: each pattern is an API name; the scanner matches a real
      call (``name(``) plus a function-pointer fallback (``= name`` /
      ``&name`` outside string literals).
    - ``string_pattern``: each pattern is a case-insensitive regex matched
      only against string literals (quoted segments) in the decompiled code.
    - ``code_heuristic``: each pattern is a compound regex matched over the
      normalized function body (e.g., two APIs co-occurring in one function).
    - ``import_check``: reserved for a future version; no v1 entries use it.
"""

from dataclasses import dataclass
from typing import Final, Literal

Severity = Literal["Critical", "High", "Medium", "Low"]
DetectionMethod = Literal["api_call", "string_pattern", "code_heuristic", "import_check"]


@dataclass(frozen=True)
class BehavioralSignatureEntry:
    """A single entry in the behavioral signature catalog.

    Attributes:
        signature_id: Stable identifier (e.g., "BEHAV-001").
        name: Human-readable behavior name.
        category: Behavior category (e.g., "Anti-Debugging", "Persistence").
        severity: Risk level — Critical, High, Medium, or Low.
        detection_method: How the signature is detected.
        patterns: Patterns to match, interpreted per detection method.
        description: What the behavior means and why it matters.
        mitre_technique: Optional MITRE ATT&CK technique id (e.g., "T1055").

    """

    signature_id: str
    name: str
    category: str
    severity: Severity
    detection_method: DetectionMethod
    patterns: tuple[str, ...]
    description: str
    mitre_technique: str = ""


# ---------------------------------------------------------------------------
# Catalog entries by category
# ---------------------------------------------------------------------------

_ANTI_DEBUGGING: list[BehavioralSignatureEntry] = [
    BehavioralSignatureEntry(
        signature_id="BEHAV-001",
        name="Debugger presence check",
        category="Anti-Debugging",
        severity="Critical",
        detection_method="api_call",
        patterns=("IsDebuggerPresent",),
        description=(
            "Checks whether a debugger is attached to the current process. A common "
            "first step in anti-debugging evasion, used by malware to alter its "
            "behavior when analyzed."
        ),
    ),
    BehavioralSignatureEntry(
        signature_id="BEHAV-002",
        name="Remote debugger check",
        category="Anti-Debugging",
        severity="High",
        detection_method="api_call",
        patterns=("CheckRemoteDebuggerPresent",),
        description=(
            "Queries whether a remote debugger is attached to the process. Used by "
            "malware to detect interactive debugging sessions."
        ),
    ),
    BehavioralSignatureEntry(
        signature_id="BEHAV-003",
        name="Process debug-port query",
        category="Anti-Debugging",
        severity="High",
        detection_method="api_call",
        patterns=("NtQueryInformationProcess",),
        description=(
            "Queries process information that can reveal a debugger via the process "
            "debug port. A common low-level anti-debugging technique."
        ),
    ),
    BehavioralSignatureEntry(
        signature_id="BEHAV-004",
        name="Debug output abuse",
        category="Anti-Debugging",
        severity="Low",
        detection_method="api_call",
        patterns=("OutputDebugString",),
        description=(
            "Writes debug output to a debugger. In malware this is often used to "
            "exfiltrate data to a debugger or to probe for one via timing "
            "differences."
        ),
    ),
]

_ANTI_SANDBOX_ANTI_VM: list[BehavioralSignatureEntry] = [
    BehavioralSignatureEntry(
        signature_id="BEHAV-005",
        name="VM/hypervisor string fingerprint",
        category="Anti-Sandbox / Anti-VM",
        severity="Medium",
        detection_method="string_pattern",
        patterns=(r"VMware|VirtualBox|VBox|QEMU|Xen|Hyper-V|Wine|sandbox",),
        description=(
            "Probes for virtualization and sandbox vendor strings. Malware uses "
            "these fingerprints to detect virtual machines and sandbox "
            "environments and evade analysis."
        ),
        mitre_technique="T1082",
    ),
    BehavioralSignatureEntry(
        signature_id="BEHAV-006",
        name="BIOS/hardware registry probe",
        category="Anti-Sandbox / Anti-VM",
        severity="High",
        detection_method="string_pattern",
        patterns=(r"SystemBiosVendor|SystemBiosDate|HARDWARE\\DESCRIPTION\\System\\BIOS",),
        description=(
            "Reads BIOS and hardware identifiers from the registry to fingerprint "
            "the underlying hardware. Used to detect virtualized or emulated "
            "environments."
        ),
        mitre_technique="T1012",
    ),
    BehavioralSignatureEntry(
        signature_id="BEHAV-007",
        name="Timing-based evasion",
        category="Anti-Sandbox / Anti-VM",
        severity="Medium",
        detection_method="code_heuristic",
        patterns=(
            r"(?:\bGetTickCount\s*[(]|\bQueryPerformanceCounter\s*[(]).*?\b(?:if|while)\b"
            r"|(?:\bif\b|\bwhile\b).*?(?:\bGetTickCount\s*[(]|\bQueryPerformanceCounter\s*[(])",
        ),
        description=(
            "Measures execution time and branches on the result. Timing checks are "
            "a classic way for malware to detect single-stepping, breakpoints, and "
            "slow sandbox environments."
        ),
    ),
    BehavioralSignatureEntry(
        signature_id="BEHAV-008",
        name="Device enumeration",
        category="Anti-Sandbox / Anti-VM",
        severity="Medium",
        detection_method="api_call",
        patterns=("SetupDiGetClassDevs",),
        description=(
            "Enumerates installed hardware devices. Malware uses device lists to "
            "fingerprint the environment and detect emulated or virtualized "
            "hardware."
        ),
        mitre_technique="T1082",
    ),
]

_PROCESS_INJECTION: list[BehavioralSignatureEntry] = [
    BehavioralSignatureEntry(
        signature_id="BEHAV-009",
        name="Remote process memory write",
        category="Process Injection",
        severity="Critical",
        detection_method="api_call",
        patterns=("WriteProcessMemory",),
        description=(
            "Writes data into the memory of another process. A core primitive of "
            "process injection used to implant shellcode in a target process."
        ),
        mitre_technique="T1055",
    ),
    BehavioralSignatureEntry(
        signature_id="BEHAV-010",
        name="Remote thread creation",
        category="Process Injection",
        severity="Critical",
        detection_method="api_call",
        patterns=("CreateRemoteThread",),
        description=(
            "Creates a thread in another process. Combined with remote memory "
            "writes, this is the classic injection technique for executing code "
            "in a target process."
        ),
        mitre_technique="T1055",
    ),
    BehavioralSignatureEntry(
        signature_id="BEHAV-011",
        name="Cross-process memory allocation",
        category="Process Injection",
        severity="High",
        detection_method="api_call",
        patterns=("VirtualAllocEx",),
        description=(
            "Allocates memory in another process. Typically the first step of a "
            "process injection sequence, before code is written and executed."
        ),
        mitre_technique="T1055",
    ),
]

_CREDENTIAL_HARVESTING: list[BehavioralSignatureEntry] = [
    BehavioralSignatureEntry(
        signature_id="BEHAV-012",
        name="Credential store access",
        category="Credential Harvesting",
        severity="High",
        detection_method="string_pattern",
        patterns=(r"Login Data|cookies|keychain|wallet|id_rsa|\.ssh|Credentials",),
        description=(
            "References well-known credential store locations (browser login "
            "data, cookies, keychains, wallets, SSH keys). Indicates harvesting "
            "of stored credentials."
        ),
        mitre_technique="T1555",
    ),
    BehavioralSignatureEntry(
        signature_id="BEHAV-013",
        name="Secret string probing",
        category="Credential Harvesting",
        severity="Medium",
        detection_method="string_pattern",
        patterns=(r"password|api_key|token|AWS_SECRET",),
        description=(
            "References secret-related strings such as passwords, API keys, and "
            "tokens. Suggests the binary probes for or exfiltrates secrets."
        ),
        mitre_technique="T1552",
    ),
    BehavioralSignatureEntry(
        signature_id="BEHAV-014",
        name="Identity enumeration",
        category="Credential Harvesting",
        severity="Medium",
        detection_method="api_call",
        patterns=("GetUserName", "GetComputerName", "GetDomainName"),
        description=(
            "Retrieves the current user, computer, and domain names. Malware uses "
            "identity enumeration to tailor its behavior and report on the "
            "target."
        ),
        mitre_technique="T1033",
    ),
]

_NETWORK_C2: list[BehavioralSignatureEntry] = [
    BehavioralSignatureEntry(
        signature_id="BEHAV-015",
        name="Hardcoded C2 address",
        category="Network C2",
        severity="High",
        detection_method="string_pattern",
        patterns=(r"https?://|\b(?:\d{1,3}\.){3}\d{1,3}\b",),
        description=(
            "Contains hardcoded IP addresses or http(s) URLs. Often indicates a "
            "hardcoded command-and-control endpoint."
        ),
        mitre_technique="T1071",
    ),
    BehavioralSignatureEntry(
        signature_id="BEHAV-016",
        name="Raw socket beaconing",
        category="Network C2",
        severity="High",
        detection_method="code_heuristic",
        patterns=(
            r"\bconnect\s*\(.*?\b(?:send|recv)\s*\("
            r"|\b(?:send|recv)\s*\(.*?\bconnect\s*\(",
        ),
        description=(
            "Connects a socket and sends or receives data within the same "
            "function. A raw network beaconing pattern typical of C2 "
            "communication."
        ),
        mitre_technique="T1071",
    ),
    BehavioralSignatureEntry(
        signature_id="BEHAV-017",
        name="WinHTTP C2 usage",
        category="Network C2",
        severity="Medium",
        detection_method="api_call",
        patterns=("HttpOpen", "HttpSendRequest"),
        description=(
            "Uses the WinHTTP API to open and send HTTP requests. Commonly used "
            "by malware for C2 communication that bypasses some proxy and "
            "firewall rules."
        ),
        mitre_technique="T1071.001",
    ),
    BehavioralSignatureEntry(
        signature_id="BEHAV-018",
        name="Browser user-agent spoofing",
        category="Network C2",
        severity="Low",
        detection_method="string_pattern",
        patterns=(r"Mozilla/",),
        description=(
            "Contains browser user-agent strings. Spoofing a browser user-agent "
            "helps malware C2 traffic blend in with normal web traffic."
        ),
        mitre_technique="T1071.001",
    ),
]

_PERSISTENCE: list[BehavioralSignatureEntry] = [
    BehavioralSignatureEntry(
        signature_id="BEHAV-019",
        name="Registry run-key persistence",
        category="Persistence",
        severity="High",
        detection_method="string_pattern",
        patterns=(r"CurrentVersion\\Run(Once)?",),
        description=(
            "References the registry Run/RunOnce keys. Writing to these keys "
            "causes the malware to execute at user logon."
        ),
        mitre_technique="T1547.001",
    ),
    BehavioralSignatureEntry(
        signature_id="BEHAV-020",
        name="Windows service installation",
        category="Persistence",
        severity="High",
        detection_method="api_call",
        patterns=("CreateService", "OpenSCManager", "StartService"),
        description=(
            "Creates, opens, or starts Windows services. Installing a service is "
            "a common persistence mechanism that survives reboots."
        ),
        mitre_technique="T1543.003",
    ),
    BehavioralSignatureEntry(
        signature_id="BEHAV-021",
        name="Scheduled task / WMI subscription",
        category="Persistence",
        severity="High",
        detection_method="string_pattern",
        patterns=(r"schtasks|__EventFilter|__EventConsumer",),
        description=(
            "References scheduled task tools or WMI event subscription classes. "
            "Used to schedule malware execution or subscribe to system events."
        ),
        mitre_technique="T1053.005",
    ),
]

_OBFUSCATION_ANTI_ANALYSIS: list[BehavioralSignatureEntry] = [
    BehavioralSignatureEntry(
        signature_id="BEHAV-022",
        name="Dynamic API resolution",
        category="Obfuscation / Anti-Analysis",
        severity="High",
        detection_method="api_call",
        patterns=("GetProcAddress",),
        description=(
            "Resolves API functions at runtime via GetProcAddress. Obfuscates "
            "the binary's imports and can hide malicious API usage from static "
            "analysis."
        ),
        mitre_technique="T1027",
    ),
    BehavioralSignatureEntry(
        signature_id="BEHAV-023",
        name="Runtime code protection/modification",
        category="Obfuscation / Anti-Analysis",
        severity="Medium",
        detection_method="api_call",
        patterns=("VirtualProtect",),
        description=(
            "Changes the memory protection of code regions at runtime. Used to "
            "make decoded code executable or to hide code from analysis."
        ),
        mitre_technique="T1027",
    ),
    BehavioralSignatureEntry(
        signature_id="BEHAV-024",
        name="Encoded/indirect command execution",
        category="Obfuscation / Anti-Analysis",
        severity="Critical",
        detection_method="string_pattern",
        patterns=(
            r"powershell\s+-enc|cmd\s+/c|rundll32|regsvr32\s+/s\s+/u\s+/i|certutil\s+-decode",
        ),
        description=(
            "References encoded or indirect command execution strings (e.g., "
            "powershell -enc, cmd /c, rundll32, regsvr32, certutil -decode). A "
            "common living-off-the-land execution technique."
        ),
        mitre_technique="T1059.001",
    ),
]


# ---------------------------------------------------------------------------
# Build flat lookup and category index
# ---------------------------------------------------------------------------

# All entries combined (preserves order for iteration)
_ALL_ENTRIES: Final[list[BehavioralSignatureEntry]] = (
    _ANTI_DEBUGGING
    + _ANTI_SANDBOX_ANTI_VM
    + _PROCESS_INJECTION
    + _CREDENTIAL_HARVESTING
    + _NETWORK_C2
    + _PERSISTENCE
    + _OBFUSCATION_ANTI_ANALYSIS
)

# Case-insensitive lookup by behavior name and by stable signature id:
# "debugger presence check" -> entry, "BEHAV-001" -> same entry.
SIGNATURE_LOOKUP: Final[dict[str, BehavioralSignatureEntry]] = {}
for _entry in _ALL_ENTRIES:
    SIGNATURE_LOOKUP.setdefault(_entry.name.lower(), _entry)
    SIGNATURE_LOOKUP.setdefault(_entry.signature_id.lower(), _entry)

# Category -> list of entries
CATEGORY_INDEX: Final[dict[str, list[BehavioralSignatureEntry]]] = {}
for _entry in _ALL_ENTRIES:
    CATEGORY_INDEX.setdefault(_entry.category, []).append(_entry)


def get_entry(signature_id_or_name: str) -> BehavioralSignatureEntry | None:
    """Look up a behavioral signature entry by id or name.

    The lookup is case-insensitive and accepts either a stable signature id
    (e.g., "BEHAV-001") or a human-readable behavior name.

    Args:
        signature_id_or_name: The signature id or behavior name to look up.

    Returns:
        The catalog entry if found, otherwise None.

    """
    return SIGNATURE_LOOKUP.get(signature_id_or_name.lower())


def get_all_entries() -> list[BehavioralSignatureEntry]:
    """Return all catalog entries.

    Returns:
        List of all BehavioralSignatureEntry instances.

    """
    return list(_ALL_ENTRIES)


def get_categories() -> list[str]:
    """Return all behavior categories in the catalog.

    Returns:
        Sorted list of category names.

    """
    return sorted(CATEGORY_INDEX.keys())


def get_entries_by_category(category: str) -> list[BehavioralSignatureEntry]:
    """Return all entries for a given category.

    Args:
        category: Category name (e.g., "Anti-Debugging").

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
