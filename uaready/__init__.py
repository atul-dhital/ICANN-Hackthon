"""UAReady — internationalised email & domain validation toolkit.

Standards: SMTPUTF8 (RFC 6531), EAI (RFC 6532), IDNA2008 (RFC 5891), UTS#46, NFC.
"""

from .validator import (
    validate_email,
    validate_domain,
    lookup_mx,
    resolve_a,
    ValidationResult,
)
from .errors import MESSAGES, DEFAULT_LANG

__version__ = "0.1.0"

__all__ = [
    "validate_email",
    "validate_domain",
    "lookup_mx",
    "resolve_a",
    "ValidationResult",
    "MESSAGES",
    "DEFAULT_LANG",
    "__version__",
]
