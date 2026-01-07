class SandboxError(Exception):
    """base class for custom exceptions raised by sandbox"""

class ResourceLimitExceeded(SandboxError):
    """raised when timeout or memory limit is hit."""

class DockerOperationsError(SandboxError):
    """wraps underlying docker API errors"""


