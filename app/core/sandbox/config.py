DOCKER_MAX_READ_RETRIES = 5
DOCKER_URL = None
DOCKER_TIMEOUT = 30
DOCKER_MAX_TOTAL_RETRIES = 9
DOCKER_MAX_CONNECT_RETRIES = 5
DOCKER_BACKOFF_FACTOR = 0.2
DOCKER_WORKDIR = "sandbox"

SANDBOX_PREFIX_NAME = "agentic-sandbox"

CPU_TO_REAL_TIME_FACTOR = 5

DEFAULT_USER = "root"
IS_CONFIGURED = False
PROFILES = {}
DOCKER_URL = None


class Profile(object):
    def __init__(
        self,
        name,
        docker_image,
        command=None,
        user=DEFAULT_USER,
        read_only=False,
        network_disabled=True,
    ):
        self.name = name
        self.docker_image = docker_image
        self.command = command
        self.user = user
        self.read_only = read_only
        self.network_disabled = network_disabled


def configure(profiles=None, docker_url=None):
    global IS_CONFIGURED, PROFILES, DOCKER_URL

    IS_CONFIGURED = True

    if isinstance(profiles, dict):
        profiles_map = {
            name: Profile(name, **profile_kwargs)
            for name, profile_kwargs in profiles.items()
        }
    else:
        profiles_map = {profile.name: profile for profile in profiles or []}

    PROFILES.update(profiles_map)
    DOCKER_URL = docker_url
