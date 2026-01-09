from dataclasses import dataclass, field
from typing import Dict, Optional, List


@dataclass
class Profile:
    name: str
    image: str
    user: str = "sandbox"

    read_only: bool = False
    network_disabled: bool = True
    mem_limit_mb: int = 1000
    cpu_period: int = 100000
    cpu_quota: int = 50000

    base_image: str = "python:3.12-slim"
    system_packages: List[str] = field(default_factory=list)
    python_packages: List[str] = field(default_factory=list)

    env: Dict[str, str] = field(default_factory=dict)


@dataclass
class SandboxConfig:
    docker_url: Optional[str] = None
    timeout: int = 30
    workdir: str = "/sandbox"
    sandbox_prefix: str = "agent-box-"
    max_session_ttl = 3600

    profiles: Dict[str, Profile] = field(default_factory=dict)

    def add_profiles(self, profile: Profile):
        self.profiles[profile.name] = profile

    def get_profile(self, name: str) -> Profile:
        if name not in self.profiles:
            raise ValueError(f"profile '{name}' not found.")

        return self.profiles[name]
