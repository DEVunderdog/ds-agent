import docker
import select
import time
import structlog
from typing import Dict, Optional, Any
from docker.models.containers import Container
from docker.errors import APIError, DockerException
from app.core.sandbox.config import SandboxConfig
from app.core.sandbox.exceptions import DockerOperationsError, ResourceLimitExceeded
from app.core.sandbox.stream_parser import StreamParser

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
        except DockerException as e:
            raise DockerOperationsError(f"failed to initialize docker client: {e}")

    def create_container(
        self,
        image: str,
        command: list,
        limits: Dict[str, Any],
        **kwargs,
    ) -> Container:
        try:
            mem_limit = f"{limits.get('memory', self.config.default_memory_mb)}m"

            return self.client.containers.create(
                image=image,
                command=command,
                mem_limit=mem_limit,
                memswap_limit=mem_limit,
                pids_limit=limits.get("processes", 100),
                **kwargs,
            )
        except APIError as e:
            raise DockerOperationsError(f"API error creating container: {e}")

    def put_archive(self, container: Container, path: str, data: bytes):
        try:
            container.put_archive(path, data)
        except APIError as e:
            raise DockerOperationsError(f"failed to copy files to container: {e}")

    def run_with_timeout(
        self,
        container: Container,
        stdin: Optional[bytes] = None,
        timeout: int = 10,
    ) -> Dict[str, Any]:
        log = logger.bind(container_id=container.short_id)

        params = {
            "stdin": 1,
            "stdout": 1,
            "stderr": 1,
            "stream": 1,
            "logs": 0,
        }

        try:
            sock = self.client.api.attach_socket(container.id, params=params)
            sock._sock.setblocking(False)
        except Exception as e:
            raise DockerOperationsError(f"failed to fetch attach socket: {e}")

        try:
            container.start()
        except APIError as e:
            sock.close()
            raise DockerOperationsError(f"failed to start container: {e}")

        stream_parser = StreamParser(header=DockerService.STREAM_HEADER_SIZE)

        start_time = time.time()

        stdin_view = memoryview(stdin) if stdin else None

        try:
            while True:
                if time.time() - start_time > timeout:
                    raise ResourceLimitExceeded(f"execution exceeded {timeout}s")

                write_list = [sock] if stdin_view else []
                r_ready, w_ready, _ = select.select([sock], write_list, [], 0.1)

                if not r_ready and not w_ready:
                    container.reload()
                    if container.status == "exited":
                        break
                    continue

                if r_ready:
                    try:
                        data = sock.recv(4096)
                        if not data:
                            break

                        stream_parser.feed(data=data)

                    except ConnectionResetError:
                        break

                if w_ready and stdin_view:
                    try:
                        sent = sock.send(stdin_view)
                        stdin_view = stdin_view[sent:]
                    except BrokenPipeError:
                        stdin_view = None
        except ResourceLimitExceeded:
            log.warning("timeout reached, killing container")
            try:
                container.kill()
            except Exception:
                pass

            output, err = stream_parser.get_output()
            return {
                "timeout": True,
                "stdout": output,
                "stderr": err,
                "exit_code": -1,
            }

        finally:
            sock.close()

        container.reload()
        state = container.attrs.get("State", {})

        out, err = stream_parser.get_output()

        return {
            "timeout": False,
            "exit_code": state.get("ExitCode"),
            "oom_killed": state.get("OOMKilled", False),
            "stdout": out,
            "stderr": err,
            "duration": time.time() - start_time,
        }

    def cleanup_container(self, container: Container):
        try:
            container.remove(force=True)
        except Exception as e:
            logger.error(f"failed to remove container {container.short_id}: {e}")
