import io
import tarfile
import structlog
import uuid
import time
from requests.exceptions import RequestException
from docker.errors import DockerException, APIError
from app.core.sandbox.config import SANDBOX_PREFIX_NAME, DOCKER_WORKDIR, PROFILES
from app.core.sandbox.docker import ResourceLimits, DockerClientManager
from app.core.sandbox.exceptions import DockerError

logger = structlog.get_logger(__name__)


class _WorkingDirectory(object):
    def __init__(self, volume):
        self.volume = volume

    def __repr__(self):
        return "<WorkingDirectory: {}>".format(self.volume)


class Sandbox:
    def __init__(self, id_, container, realtime_limit=None):
        self.id_ = id_
        self.container = container
        self.realtime_limit = realtime_limit

    def __enter__(self):
        return self

    def __exit__(self, *args):
        # destroy(self)
        pass

    def __repr(self):
        return "<Sandbox: {} container={}>".format(self.id_, self.container.short_id)


class SandboxManager:

    def __init__(self, client: DockerClientManager):
        self.docker_client_manager = client

    def _create_sandbox_container(
        self,
        sandbox_id,
        image,
        command,
        limits: ResourceLimits,
        workdir=None,
        user=None,
        read_only=False,
        network_disabled=True,
    ):
        name = SANDBOX_PREFIX_NAME + sandbox_id

        mem_limit = str(limits["memory"]) + "m"

        volumes = (
            {
                workdir.volume: {
                    "bind": DOCKER_WORKDIR,
                    "mode": "rw",
                }
            }
            if workdir
            else None
        )

        ulimits = self.docker_client.create_ulimits(limits)

        environment = None

        log = logger.bind(sandbox_id=sandbox_id)

        log.info(
            "creating a new sandbox container",
            name=name,
            image=image,
            command=command,
            limits=limits,
            workdir=workdir,
            user=user,
            read_only=read_only,
            network_disabled=network_disabled,
        )

        try:
            c = self.docker_client.client.containers.create(
                image,
                command=command,
                user=user,
                stdin_open=True,
                environment=environment,
                network_disabled=network_disabled,
                name=name,
                working_dir=DOCKER_WORKDIR,
                volumes=volumes,
                read_only=read_only,
                mem_limit=mem_limit,
                memswap_limit=mem_limit,
                ulimits=ulimits,
                pids_limit=limits["processes"],
                log_config={"type": "none"},
            )

        except (RequestException, DockerException) as e:
            if isinstance(e, APIError) and e.response.status_code == 49:
                log.info("the container with give name is already created", name=name)
                c = {"id": name}
            else:
                log.exception("failed to create a sandbox container")
                raise DockerError(str(e))

        log.info("sandbox container created", container=c)

        return c

    def _write_files(container, files):
        docker_client_manager = DockerClientManager(retry_status_forcelist=(404, 500))
        docker_client = docker_client_manager.get_client()

        filtered_filenames = [file["name"] for file in files if "name" in file]

        log = logger.bind(files=filtered_filenames, container=container)
        log.info("writing files to working directory in container")

        mtime = int(time.time())

        files_written = []

        tarball_fileobj = io.BytesIO()

        with tarfile.open(fileobj=tarball_fileobj, mode="w") as tarball:
            for file in files:
                if not file.get("name") or not isinstance(file["name"], str):
                    continue
                content = file.get("content", b"")
                file_info = tarfile.TarInfo(name=file["name"])
                file_info.size = len(content)
                file_info.mtime = mtime
                tarball.addfile(file_info, fileobj=io.BytesIO(content))
                files_written.append(file["name"])

        try:
            docker_client.api.put_archive(
                container.id, DOCKER_WORKDIR, tarball_fileobj.getvalue()
            )
        except (RequestException, DockerException) as e:
            log.exception(
                "failed to extract an archive of files to the working directory in the container"
            )
            raise DockerError(str(e))
        log.info(
            "successfully written files to the working directory",
            files_written=files_written,
        )

    def create(
        self,
        profile_name,
        command=None,
        files=None,
        limits=None,
        workdir=None,
    ):
        if profile_name not in PROFILES:
            raise ValueError("profile not found: {0}".format(profile_name))

        if workdir is not None and not isinstance(workdir, _WorkingDirectory):
            raise ValueError(
                "invalid 'workdir', it should be created using 'working_directory' context manager"
            )

        sandbox_id = str(uuid.uuid4())

        profile = PROFILES[profile_name]

        command = command or profile.command or "true"
        command_list = ["/bin/sh", "-c", command]

        limits = self.docker_client.merge_limits_defaults(limits=limits)

        c = self._create_sandbox_container(
            sandbox_id=sandbox_id,
            image=profile.docker_image,
            command=command_list,
            limits=limits,
            workdir=workdir,
            user=profile.user,
            read_only=profile.read_only,
            network_disabled=profile.network_disabled,
        )

        if files:
            self._write_files(container=c, files=files)

    def start(sandbox, stdin=None):
        if stdin:
            if not isinstance(stdin, (bytes, str)):
                raise TypeError("'stdin' must be bytes or str")

            if isinstance(stdin, str):
                stdin = stdin.encode()

        log = logger.bind(sandbox=sandbox)
        log.info("starting the sandbox", stdin_size=len(stdin or ""))
        result = {
            "exit_code": None,
            "stdout": b"",
            "stderr": b"",
            "duration": None,
            "timeout": False,
            "oom_killed": False,
        }

        
