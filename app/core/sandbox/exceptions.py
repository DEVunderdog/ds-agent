class SandboxError(Exception):
    """base calss for custom exceptions raised by sandbox"""

class DockerError(SandboxError):
    """an error occurred with the underlying docker system in sandbox"""