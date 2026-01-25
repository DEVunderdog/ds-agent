import select
import time
from typing import Any, Dict, Optional

import docker
import structlog
from docker.errors import APIError, DockerException, NotFound
from docker.models.containers import Container

from app.core.sandbox.config import Profile, SandboxConfig
from app.core.sandbox.exceptions import DockerOperationsError
from app.core.sandbox.utility import StreamParser

logger = structlog.get_logger(__name__)


class DockerService:

    STREAM_HEADER_SIZE = 8

    def __init__(self, config: SandboxConfig):
        self.config = config
        try:
            self.client = docker.DockerClient(
                base_url=config.docker_url,
                timeout=config.timeout,
            )
            self.api = self.client.api
        except DockerException as e:
            raise DockerOperationsError(f"failed to initialize docker client: {e}")

    def spawn_container(self, name: str, profile: Profile, workdir: str) -> Container:
        try:
            container = self.client.containers.run(
                image=profile.image,
                command=f"sleep {self.config.max_session_ttl}",
                name=name,
                detach=True,
                user=profile.user,
                working_dir=workdir,
                network_disabled=profile.network_disabled,
                read_only=profile.read_only,
                mem_limit=f"{profile.mem_limit_mb}m",
                cpu_period=profile.cpu_period,
                cpu_quota=profile.cpu_quota,
                environment=profile.env,
                auto_remove=True,
            )

            return container
        except APIError as e:
            raise DockerOperationsError(f"failed to spawn container: {e}")

    def exec_command(
        self,
        container: Container,
        cmd: list,
        stdin: Optional[bytes] = None,
        timeout: int = 10,
        env: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        try:
            exec_instance = self.api.exec_create(
                container.id,
                cmd=cmd,
                stdin=bool(stdin),
                stdout=True,
                stderr=True,
                environment=env,
            )

            exec_id = exec_instance["Id"]

            sock = self.api.exec_start(
                exec_id=exec_id,
                detach=False,
                socket=True,
            )
            if hasattr(sock, "_sock"):
                sock._sock.setblocking(False)

        except APIError as e:
            raise DockerOperationsError(f"exec create failed: {e}")

        parser = StreamParser()
        start_time = time.time()
        stdin_view = memoryview(stdin) if stdin else None
        timed_out = False

        try:
            while True:
                if time.time() - start_time > timeout:
                    timed_out = True
                    break

                w_list = [sock] if stdin_view else []
                r_ready, w_ready, _ = select.select([sock], w_list, [], 0.1)

                inspect = self.api.exec_inspect(exec_id)
                is_running = inspect.get("running", False)

                if not r_ready and not w_ready and not is_running:
                    break

                if r_ready:
                    try:
                        data = sock.recv(4096)
                        if not data:
                            break
                        parser.feed(data)
                    except (OSError, ConnectionResetError):
                        break

                if w_ready and stdin_view:
                    try:
                        sent = sock.send(stdin_view)
                        stdin_view = stdin_view[sent:]
                    except (OSError, BrokenPipeError):
                        stdin_view = None

        finally:
            sock.close()

        stdout, stderr = parser.get_output()
        final_inspect = self.api.exec_inspect(exec_id)
        exit_code = final_inspect.get("ExitCode")

        if timed_out:
            logger.warning("command timed out", exec_id=exec_id)

        return {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "timed_out": timed_out,
            "duration": time.time() - start_time,
        }

    def copy_to(self, container: Container, path: str, tar_data: bytes):
        try:
            container.put_archive(path, tar_data)
        except APIError as e:
            raise DockerOperationsError(f"copy to container failed: {e}")

    def copy_from(self, container: Container, path: str) -> bytes:
        try:
            stream, _ = container.get_archive(path)
            data = b"".join(chunk for chunk in stream)
            return data
        except (NotFound, APIError) as e:
            raise DockerOperationsError(f"copy from container failed: {e}")

    def remove_container(self, container: Container):
        try:
            container.remove(force=True)
        except Exception as e:
            logger.exception(f"error while removing container: {e}")
