import uuid
import structlog
from typing import List, Dict, Union, Optional, Any

from app.core.sandbox.config import SandboxConfig, Profile
from app.core.sandbox.docker_client import DockerService
from app.core.sandbox.utility import create_archive, extract_file_from_archive
from app.core.sandbox.image_manager import ImageManager

logger = structlog.get_logger(__name__)


class Sandbox:
    def __init__(
        self,
        config: SandboxConfig,
        service: DockerService,
        profile_name: str,
    ):
        self.config = config
        self.service = service
        self.profile = config.get_profile(profile_name)
        self.id = str(uuid.uuid4())
        self.container_name = f"{config.sandbox_prefix}{self.id}"
        self.container = None
        self._is_alive = False

    def start(self):
        logger.info("starting sandbox", id=self.id, profile=self.profile.name)

        self.container = self.service.spawn_container(
            name=self.container_name,
            profile=self.profile,
            workdir=self.config.workdir,
        )

        self._is_alive = True

    def stop(self):
        if self.container:
            logger.info("stopping sandbox", id=self.id)
            self.service.remove_container(self.container)
            self._is_alive = False

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def write_files(self, files: List[Dict[str, Union[str, bytes]]]):
        if not self._is_alive:
            raise RuntimeError("sandbox is not running")

        logger.debug("writing files", count=len(files))

        tar_data = create_archive(files)
        self.service.copy_to(self.container, self.config.workdir, tar_data)

    def read_file(self, relative_path: str) -> bytes:
        if not self._is_alive:
            raise RuntimeError("sandbox is not running")

        full_path = f"{self.config.workdir}/{relative_path}"
        tar_data = self.service.copy_from(self.container, full_path)

        filename = relative_path.split("/")[-1]
        return extract_file_from_archive(tar_data, filename)

    def exec(
        self,
        command: str,
        stdin: Optional[str] = None,
        timeout: Optional[int] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        if not self._is_alive:
            raise RuntimeError("sandbox is not running")

        timeout = timeout or self.config.timeout

        cmd_list = ["/bin/sh", "-c", command]
        stdin_bytes = stdin.encode("utf-8") if stdin else None

        result = self.service.exec_command(
            self.container,
            cmd=cmd_list,
            stdin=stdin_bytes,
            timeout=timeout,
            env=env,
        )

        return {
            "stdout": result["stdout"].decode("utf-8", errors="replace"),
            "stderr": result["stderr"].decode("utf-8", errors="replace"),
            "exit_code": result["exit_code"],
            "timed_out": result["timed_out"],
            "duration": result["duration"],
        }


class SandboxManager:
    def __init__(
        self,
        config: SandboxConfig,
    ):
        self.config = config
        self.docker_service = DockerService(config)

        self.image_manager = ImageManager(config, self.docker_service)

    def register_default_profiles(self):

        ds_profile = Profile(
            name="data-science",
            image="sandbox-ds:v1",
            user="sandbox",
            base_image="python:3.12-slim",
            system_packages=["build-essential", "git"],
            python_packages=["numpy", "pandas", "scikit-learn", "orjson"],
            mem_limit_mb=512,
        )

        self.config.add_profiles(ds_profile)

    def ensure_image(self, profile_name: str):
        self.image_manager.build_profile(profile_name)

    def create(self, profile_name: str) -> Sandbox:
        self.ensure_image(profile_name)

        return Sandbox(self.config, self.docker_service, profile_name)
