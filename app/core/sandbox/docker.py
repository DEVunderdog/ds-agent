import structlog
import docker
from typing import TypedDict, Any, List, Optional
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from threading import Lock
from docker.types import Ulimit
from app.core.sandbox import config

logger = structlog.get_logger(__name__)

if hasattr(Retry.DEFAULT, "allowed_methods"):
    _ANY_METHOD = {"allowed_methods": False}
else:
    _ANY_METHOD = {"method_whitelist": False}


class ResourceLimits(TypedDict):
    cputime: Any
    file_size: Any


class DockerClient:
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

    def create_ulimits(limits: ResourceLimits) -> Optional[List]:
        ulimits = []

        if limits["cputime"]:
            cpu = limits["cputime"]
            ulimits.append(Ulimit(name="cpu", soft=cpu, hard=cpu))

        if limits["file_size"]:
            fsize = limits["file_size"]
            ulimits.append(Ulimit(name="fsize", soft=fsize, hard=fsize))
        return ulimits or None
