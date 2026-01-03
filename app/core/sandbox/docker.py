import errno
import os
import structlog
import docker
import socket
import select
import time
import struct
from typing import TypedDict, Any, List, Optional
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from threading import Lock
from docker.types import Ulimit
from docker import constants as docker_const
from app.core.sandbox import config

logger = structlog.get_logger(__name__)

ERRNO_RECOVERABLE = (errno.EINTR, errno.EDEADLK, errno.EWOULDBLOCK)

if hasattr(Retry.DEFAULT, "allowed_methods"):
    _ANY_METHOD = {"allowed_methods": False}
else:
    _ANY_METHOD = {"method_whitelist": False}


class ResourceLimits(TypedDict):
    cputime: Any
    realtime: Any
    file_size: Any
    memory: Any
    processes: Any


DEFAULT_LIMITS: ResourceLimits = {
    "cputime": 1,
    "realtime": 5,
    "memory": 64,
    "processes": -1,
}


class DockerClientManager:
    _instances = {}
    _lock = Lock()

    def __new__(cls, base_url=None, retry_read=None, retry_status_forcelist=(500,)):
        if retry_read is None:
            retry_read = config.DOCKER_MAX_READ_RETRIES

        client_key = (retry_read, retry_status_forcelist)

        if client_key not in cls._instances:
            with cls._lock:
                if client_key not in cls._instances:
                    # having an empty object to call class
                    instance = super().__new__(cls)
                    instance._initialize_client(
                        base_url, retry_read, retry_status_forcelist
                    )
                    cls._instances[client_key] = instance

        return cls._instances[client_key]

    def _initialize_client(self, base_url, retry_read, retry_status_forcelist):
        self.client = docker.DockerClient(
            base_url=base_url or config.DOCKER_URL,
            timeout=config.DOCKER_TIMEOUT,
        )

        retries = Retry(
            total=config.DOCKER_MAX_TOTAL_RETRIES,
            connect=config.DOCKER_MAX_CONNECT_RETRIES,
            read=retry_read,
            status_forcelist=retry_status_forcelist,
            backoff_factor=config.DOCKER_BACKOFF_FACTOR,
            raise_on_status=False,
            **_ANY_METHOD,
        )

        http_adapter = HTTPAdapter(max_retries=retries)
        self.client.api.mount("http://", http_adapter)

    def get_client(self):
        return self.client

    @classmethod
    def clear_instances(cls):
        with cls._lock:
            cls._instances.clear()

    def create_ulimits(self, limits: ResourceLimits) -> Optional[List]:
        ulimits = []

        if limits["cputime"]:
            cpu = limits["cputime"]
            ulimits.append(Ulimit(name="cpu", soft=cpu, hard=cpu))

        if limits["file_size"]:
            fsize = limits["file_size"]
            ulimits.append(Ulimit(name="fsize", soft=fsize, hard=fsize))
        return ulimits or None

    def merge_limits_defaults(self, limits: ResourceLimits) -> ResourceLimits:
        if not limits:
            return DEFAULT_LIMITS

        is_realtime_specified = "realtime" in limits

        for limit_name, default_value in DEFAULT_LIMITS.items():
            if limit_name not in limits:
                limits[limit_name] = default_value
        if not is_realtime_specified:
            limits["realtime"] = limits["cputime"] * config.CPU_TO_REAL_TIME_FACTOR

        return limits

    def demultiplex_docker_stream(self, data):
        """
        [stream][0][0][0][length]

        >B describes the type of stream
        xxx means skipping three bytes
        L means length of stream

        In this manner Docker sends the stream
        """
        data_length = len(data)
        stdout_chunks = []
        stderr_chunks = []
        walker = 0

        while data_length - walker >= 8:
            header = data[walker : walker + docker_const.STREAM_HEADER_SIZE_BYTES]
            stream_type, length = struct.unpack_from(">BxxxL", header)
            start = walker + docker_const.STREAM_HEADER_SIZE_BYTES
            end = start + length
            walker = end

            if stream_type == 1:
                stdout_chunks.append(data[start:end])
            elif stream_type == 2:
                stderr_chunks.append(data[start:end])

        return b"".join(stdout_chunks), b"".join(stderr_chunks)

    def _socket_read(self, sock, n=4096):
        try:
            data = os.read(sock.fileno(), n)
        except EnvironmentError as e:
            if e.errno in ERRNO_RECOVERABLE:
                return b""
            raise e
        if data:
            return data

    def _socket_write(self, sock, data):
        try:
            return os.write(sock.fileno(), data)
        except EnvironmentError as e:
            if e.errno in ERRNO_RECOVERABLE:
                return 0
            raise e

    def docker_communicate(
        self, container, stdin=None, start_container=True, timeout=None
    ):
        docker_client_manager = DockerClientManager(retry_status_forcelist=(404, 500))
        docker_client = docker_client_manager.get_client()

        log = logger.bind(container=container)

        params = {
            "stdin": 1,
            "stdout": 1,
            "stderr": 1,
            "stream": 1,
            "logs": 0,
        }

        sock = docker_client.api.attach_socket(container.id, params=params)
        sock._sock.setblocking(False)
        log.info(
            "attached to the container",
            params=params,
            fd=sock.fileno(),
            timeout=timeout,
        )

        if not stdin:
            log.debug("there is not input data, shut down the write half of the socket")
            sock._sock.shutdown(socket.SHUT_WR)

        if start_container:
            container.start()
            log.info("container started")

        stream_data = b""
        start_time = time.time()

        while timeout is None or time.time() - start_time < timeout:
            read_ready, write_ready, _ = select.select([sock], [sock], [], 1)
            is_io_active = False
            if read_ready:
                is_io_active = True
                try:
                    data = self._socket_read(sock=sock)
                except ConnectionResetError:
                    log.warning(
                        "connection reset caught on reading the container output stream, break communication"
                    )
                    break

                if data is None:
                    log.debug("container output reached EOF, closing the socket")
                    break
                stream_data += data

            if write_ready and stdin:
                is_io_active = True
                try:
                    written = self._socket_write(sock, stdin)
                except BrokenPipeError:
                    log.warning(
                        "broken pipe caught on writing to stdin, break communication"
                    )
                    break

                stdin = stdin[written:]
                if not stdin:
                    log.debug(
                        "all input data has been sent, shut down the write half of the socket"
                    )
                    sock._sock.shutdown(socket.SHUT_WR)

            if not is_io_active:
                time.sleep(0.05)
        else:
            sock.close()
            raise TimeoutError("container did not terminate after timeout seconds")
        sock.close()
        return self.demultiplex_docker_stream(stream_data)
