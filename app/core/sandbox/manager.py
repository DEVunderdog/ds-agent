import io
import tarfile
import uuid
import structlog
import time
from typing import List, Dict, Optional, Union, Any
from app.core.sandbox.config import SandboxConfig, Profile
from app.core.sandbox.docker_client import DockerService
from app.core.sandbox.exceptions import SandboxError

logger = structlog.get_logger(__name__)


class SandboxSession:
    def __init__(
        self,
        container_id: str,
        container,
        docker_service: DockerService,
        workdir: str,
    ):
        self.id = container_id
        self.container = container
        self.docker_service = docker_service
        self.workdir = workdir

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.destroy()

    def destroy(self):
        logger.info("destroying sandbox", id=self.id)
        self.docker_service.cleanup_container(self.container)

    def write_files(self, files: List[Dict[str, Union[str, bytes]]]):
        tar_stream = io.BytesIO()

        with tarfile.open(fileobj=tar_stream, mode="w") as tar:
            for f in files:
                name = f["name"]
                content = f["content"]

                if isinstance(content, str):
                    content = content.encode("utf-8")

                info = tarfile.TarInfo(name=name)
                info.size = len(content)
                info.mtime = int(time.time())
                tar.addfile(info, io.BytesIO(content))

        tar_stream.seek(0)
        self.docker_service.put_archive(
            self.container, self.workdir, tar_stream.getvalue()
        )

    def run(
        self, stdin: Optional[Union[str, bytes]] = None, timeout: int = 10
    ) -> Dict[str, Any]:
        if isinstance(stdin, str):
            stdin = stdin.encode("utf-8")

        result = self.docker_service.run_with_timeout(
            self.container,
            stdin=stdin,
            timeout=timeout,
        )

        result["stdout_err"] = result["stdout"].decode("utf-8", errors="replace")
        result["stdout_err"] = result["stderr"].decode("utf-8", errors="replace")

        return result


class SandboxManager:
    def __init__(self, config: SandboxConfig):
        self.config = config
        self.docker = DockerService(config)

    def create(
        self,
        profile_name: str,
        command_override: Optional[str] = None,
        files: Optional[List[Dict]] = None,
    ) -> SandboxSession:

        profile = self.config.get_profile(profile_name)
        sandbox_id = str(uuid.uuid4())
        name = f"{self.config.sandbox_prefix}{sandbox_id}"

        cmd = command_override or profile.command

        docker_cmd = ["/bin/sh", "-c", cmd]

        logger.info("Creating Sandbox", name=name, profile=profile_name)

        container = self.docker.create_container(
            image=profile.image,
            command=docker_cmd,
            name=name,
            user=profile.user,
            working_dir=self.config.workdir,
            network_disabled=profile.network_disabled,
            read_only=profile.read_only,
            stdin_open=True,  # Interactive mode support
            limits={
                "memory": self.config.default_memory_mb,
                # Realtime limit is handled by the python controller,
                # but we set docker limits too
            },
        )

        session = SandboxSession(
            sandbox_id, container, self.docker, self.config.workdir
        )

        if files:
            session.write_files(files)

        return session

    def run_ephemeral(
        self,
        profile_name: str,
        command: str,
        files: Optional[List] = None,
        stdin: Optional[str] = None,
    ) -> Dict:
        """
        One-shot execution: Create -> Run -> Destroy.
        """
        with self.create(profile_name, command_override=command, files=files) as box:
            return box.run(stdin=stdin, timeout=self.config.timeout)
