from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class Profile:
    name: str
    image: str
    command: str
    user: str = "root"
    ready_only: bool = False
    network_disabled: bool = True

    env: Dict[str, str] = field(default_factory=dict)


@dataclass
class SandboxConfig:
    docker_url: Optional[str] = None
    timeout: int = 30
    max_retries: int = 5
    workdir: str = "/sandbox"
    sandbox_prefix: str = "agent-sandbox-"
    cpu_to_realtime_factor: int = 5

    default_memory_mb: int = 128
    default_cpu_period: int = 100000
    default_cpu_quota: int = 50000

    profiles: Dict[str, Profile] = field(default_factory=dict)

    def add_profile(self, profile: Profile):
        self.profiles[profile.name] = profile

    def get_profile(self, name: str) -> Profile:
        if name not in self.profiles:
            raise ValueError(f"profile '{name}' not configured")
        return self.profiles[name]
