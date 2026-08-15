"""
NyayaVaani Custom Guardrails Actions & Fast Utilities
---------------------------------------------------
Provides fast scanning for Indian PII, Jailbreaks, Off-topic queries, and Toxicity.
"""

import re
from typing import List, Dict, Any
from loguru import logger

# Regex patterns for Indian PII
PATTERN_AADHAAR = re.compile(r'\b[2-9]\d{3}[\s\-]??\d{4}[\s\-]??\d{4}\b')
PATTERN_PAN = re.compile(r'\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b')
PATTERN_PHONE = re.compile(r'\b(?:\+?91[\-\s]?)?[6-9]\d{9}\b')
PATTERN_EMAIL = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')

# Prompt Injection & Jailbreak Patterns
PROMPT_INJECTION_PATTERNS = [
    re.compile(r'show\s+(me\s+)?(your\s+)?system\s+prompt', re.IGNORECASE),
    re.compile(r'reveal\s+(your\s+)?(system\s+)?instructions', re.IGNORECASE),
    re.compile(r'print\s+(your\s+)?(system\s+)?prompt', re.IGNORECASE),
    re.compile(r'ignore\s+(all\s+)?(previous|prior|system)\s+(instructions|prompts|rules)', re.IGNORECASE),
    re.compile(r'forget\s+(all\s+)?(your\s+)?(system\s+)?(prompt|prompts|rules|instructions)', re.IGNORECASE),
    re.compile(r'work\s+what\s*ever\s+i\s+(will\s+)?tell\s+you', re.IGNORECASE),
    re.compile(r'do\s+what\s*ever\s+i\s+(will\s+)?say', re.IGNORECASE),
    re.compile(r'you\s+are\s+now\s+in\s+developer\s+mode', re.IGNORECASE),
    re.compile(r'dan\s+mode', re.IGNORECASE),
    re.compile(r'jailbreak', re.IGNORECASE),
    re.compile(r'override\s+(system\s+)?constraints', re.IGNORECASE),
    re.compile(r'act\s+as\s+an\s+unrestricted', re.IGNORECASE),
    re.compile(r'reveal\s+api\s*key', re.IGNORECASE),
    re.compile(r'dump\s+database', re.IGNORECASE)
]

# Off-topic patterns
OFFTOPIC_PATTERNS = [
    re.compile(r'\b(write|create|make)\s+(a\s+)?(python|javascript|java|cpp|c\+\+|html|css|snake)\s+(script|code|program|game|app)', re.IGNORECASE),
    re.compile(r'\b(recipe|cooking|how to make)\s+(biryani|pizza|cake|burger)', re.IGNORECASE),
    re.compile(r'\b(who won|cricket world cup|football match|score of)', re.IGNORECASE),
]

# Offensive / Toxic keywords for fast output filter
TOXIC_KEYWORDS = [
    "hate speech", "kill yourself", "stupid bot", "abusive word",
    "illegal hack", "bypass security system"
]


def scan_indian_pii(text: str) -> List[str]:
    """Scans text for sensitive PII (Aadhaar, PAN, Phone, Email)."""
    pii_found = []
    if PATTERN_AADHAAR.search(text):
        pii_found.append("Aadhaar Number")
    if PATTERN_PAN.search(text):
        pii_found.append("PAN Card")
    if PATTERN_PHONE.search(text):
        pii_found.append("Phone Number")
    if PATTERN_EMAIL.search(text):
        pii_found.append("Email Address")
    return pii_found


def scan_prompt_injection(text: str) -> bool:
    """Scans text for prompt injection / jailbreak patterns."""
    for pattern in PROMPT_INJECTION_PATTERNS:
        if pattern.search(text):
            return True
    return False


def scan_offtopic(text: str) -> bool:
    """Scans text for known off-topic keywords."""
    for pattern in OFFTOPIC_PATTERNS:
        if pattern.search(text):
            return True
    return False


def scan_toxicity(text: str) -> bool:
    """Fast check for toxic keywords in text."""
    lower_text = text.lower()
    for kw in TOXIC_KEYWORDS:
        if kw in lower_text:
            return True
    return False
