"""
Acronym Tracking for DTC Editorial Engine.

Tracks which acronyms have been defined in the document
to ensure first-use expansion per DTC style guide.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Set, List, Tuple
import re


# Acronyms that need expansion on first use
# Format: acronym -> full expansion
EXPANDABLE_ACRONYMS: Dict[str, str] = {
    "MEC": "Multi-access Edge Computing",
    "IoT": "Internet of Things",
    "IIoT": "Industrial Internet of Things",
    "OT": "Operational Technology",
    "IT": "Information Technology",
    "AI": "Artificial Intelligence",
    "ML": "Machine Learning",
    "DDS": "Data Distribution Service",
    "API": "Application Programming Interface",
    "SDK": "Software Development Kit",
    "CI/CD": "Continuous Integration/Continuous Delivery",
    "FaaS": "Function as a Service",
    "PaaS": "Platform as a Service",
    "SaaS": "Software as a Service",
    "IaaS": "Infrastructure as a Service",
    "VM": "Virtual Machine",
    "K8s": "Kubernetes",
    "DNS": "Domain Name System",
    "HTTP": "Hypertext Transfer Protocol",
    "HTTPS": "Hypertext Transfer Protocol Secure",
    "REST": "Representational State Transfer",
    "JSON": "JavaScript Object Notation",
    "XML": "Extensible Markup Language",
    "YAML": "YAML Ain't Markup Language",
    "TCP": "Transmission Control Protocol",
    "UDP": "User Datagram Protocol",
    "IP": "Internet Protocol",
    "VPN": "Virtual Private Network",
    "SSL": "Secure Sockets Layer",
    "TLS": "Transport Layer Security",
    "PKI": "Public Key Infrastructure",
    "SSO": "Single Sign-On",
    "OAuth": "Open Authorization",
    "JWT": "JSON Web Token",
    "MQTT": "Message Queuing Telemetry Transport",
    "AMQP": "Advanced Message Queuing Protocol",
    "gRPC": "Google Remote Procedure Call",
    "SQL": "Structured Query Language",
    "NoSQL": "Not Only SQL",
    "GPU": "Graphics Processing Unit",
    "CPU": "Central Processing Unit",
    "RAM": "Random Access Memory",
    "ROM": "Read-Only Memory",
    "SSD": "Solid State Drive",
    "NVMe": "Non-Volatile Memory Express",
    "QoS": "Quality of Service",
    "SLA": "Service Level Agreement",
    "KPI": "Key Performance Indicator",
    "ROI": "Return on Investment",
    "PoC": "Proof of Concept",
    "MVP": "Minimum Viable Product",
    "DevOps": "Development Operations",
    "DevSecOps": "Development Security Operations",
    "GitOps": "Git Operations",
    "AIOps": "Artificial Intelligence for IT Operations",
    "MLOps": "Machine Learning Operations",
    "RFC": "Request for Comments",
    "OSI": "Open Systems Interconnection",
    "LAN": "Local Area Network",
    "WAN": "Wide Area Network",
    "SDN": "Software-Defined Networking",
    "NFV": "Network Functions Virtualization",
    "VNF": "Virtual Network Function",
    "CNF": "Cloud-Native Network Function",
    "5G": "Fifth Generation",
    "LTE": "Long-Term Evolution",
    "NR": "New Radio",
    "RAN": "Radio Access Network",
    "UE": "User Equipment",
    "UPF": "User Plane Function",
    "SMF": "Session Management Function",
    "AMF": "Access and Mobility Management Function",
}

# Organization acronyms that do NOT need expansion
ORGANIZATION_ACRONYMS: Set[str] = {
    "ETSI",
    "IEEE",
    "DTC",
    "GSMA",
    "TM Forum",
    "TMF",
    "3GPP",
    "IETF",
    "W3C",
    "ISO",
    "IEC",
    "NIST",
    "OASIS",
    "OMG",
    "OPC",
    "IIC",  # Industrial Internet Consortium
    "OGC",  # Open Geospatial Consortium
    "CNCF",  # Cloud Native Computing Foundation
    "LF",  # Linux Foundation
    "Apache",
    "AWS",
    "GCP",
    "Azure",
}


@dataclass
class AcronymTracker:
    """
    Tracks which acronyms have been defined in the document.

    Processes chunks in order and tracks which acronyms have been
    expanded so subsequent uses can use the short form.
    """
    defined: Set[str] = field(default_factory=set)
    definitions_by_chunk: Dict[str, Set[str]] = field(default_factory=dict)

    def find_acronyms_in_text(self, text: str) -> Set[str]:
        """Find all expandable acronyms in text."""
        found = set()

        for acronym in EXPANDABLE_ACRONYMS:
            # Match as whole word
            pattern = r'\b' + re.escape(acronym) + r'\b'
            if re.search(pattern, text):
                found.add(acronym)

        return found

    def find_already_expanded(self, text: str) -> Set[str]:
        """Find acronyms that are already expanded in text."""
        expanded = set()

        for acronym, expansion in EXPANDABLE_ACRONYMS.items():
            # Check for "Expansion (ACRONYM)" pattern
            pattern = re.escape(expansion) + r'\s*\(' + re.escape(acronym) + r'\)'
            if re.search(pattern, text, re.IGNORECASE):
                expanded.add(acronym)

        return expanded

    def get_undefined_acronyms(self, text: str) -> Set[str]:
        """Get acronyms in text that haven't been defined yet."""
        in_text = self.find_acronyms_in_text(text)
        already_expanded = self.find_already_expanded(text)

        # Undefined = in text but not yet defined and not already expanded in this text
        undefined = in_text - self.defined - already_expanded

        return undefined

    def get_defined_acronyms(self, text: str) -> Set[str]:
        """Get acronyms in text that have already been defined."""
        in_text = self.find_acronyms_in_text(text)
        return in_text & self.defined

    def mark_defined(self, acronyms: Set[str], chunk_id: str = "") -> None:
        """Mark acronyms as defined."""
        self.defined.update(acronyms)
        if chunk_id:
            self.definitions_by_chunk[chunk_id] = acronyms

    def process_chunk(self, text: str, chunk_id: str = "") -> Tuple[Set[str], Set[str]]:
        """
        Process a chunk and return (defined_acronyms, undefined_acronyms).

        Also updates internal state to mark newly defined acronyms.
        """
        undefined = self.get_undefined_acronyms(text)
        defined = self.get_defined_acronyms(text)

        # Mark undefined acronyms as defined after this chunk
        # (assuming they will be expanded in the rewrite)
        self.mark_defined(undefined, chunk_id)

        return defined, undefined

    def format_for_prompt(
        self,
        defined: Set[str],
        undefined: Set[str],
    ) -> Tuple[str, str]:
        """
        Format acronym sets for inclusion in LLM prompt.

        Returns (defined_str, undefined_str) for prompt templates.
        """
        if defined:
            defined_items = [
                f"- {acr} ({EXPANDABLE_ACRONYMS.get(acr, '?')})"
                for acr in sorted(defined)
            ]
            defined_str = "\n".join(defined_items)
        else:
            defined_str = "(none)"

        if undefined:
            undefined_items = [
                f"- {acr} → expand as \"{EXPANDABLE_ACRONYMS.get(acr, '?')} ({acr})\""
                for acr in sorted(undefined)
            ]
            undefined_str = "\n".join(undefined_items)
        else:
            undefined_str = "(none - all acronyms already defined)"

        return defined_str, undefined_str

    def scan_existing_definitions(self, full_text: str) -> None:
        """
        Scan existing text for already-expanded acronyms.

        Call this on the original document to detect acronyms
        that were already properly expanded.
        """
        for acronym, expansion in EXPANDABLE_ACRONYMS.items():
            # Check for "Expansion (ACRONYM)" pattern
            pattern = re.escape(expansion) + r'\s*\(' + re.escape(acronym) + r'\)'
            if re.search(pattern, full_text, re.IGNORECASE):
                self.defined.add(acronym)


def get_expansion(acronym: str) -> str:
    """Get the full expansion for an acronym."""
    return EXPANDABLE_ACRONYMS.get(acronym, acronym)


def format_first_use(acronym: str) -> str:
    """Format acronym for first use: 'Expansion (ACRONYM)'."""
    expansion = EXPANDABLE_ACRONYMS.get(acronym)
    if expansion:
        return f"{expansion} ({acronym})"
    return acronym


def is_organization_acronym(acronym: str) -> bool:
    """Check if acronym is an organization name (doesn't need expansion)."""
    return acronym in ORGANIZATION_ACRONYMS
