"""Custom exceptions for Mythos."""


class MythosError(Exception):
    """Base exception for all Mythos errors."""


class ParseError(MythosError):
    """Raised when XML parsing fails."""

    def __init__(self, path, reason=""):
        self.path = path
        self.reason = reason
        super().__init__(f"Failed to parse {path}: {reason}")


class ValidationError(MythosError):
    """Raised when input data fails validation."""

    def __init__(self, field, value, reason=""):
        self.field = field
        self.value = value
        super().__init__(f"Validation failed for {field}={value}: {reason}")


class ExportError(MythosError):
    """Raised when report export fails."""

    def __init__(self, format, path, reason=""):
        self.format = format
        self.path = path
        super().__init__(f"Export to {format} failed at {path}: {reason}")
