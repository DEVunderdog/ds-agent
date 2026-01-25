import io

import structlog

from app.core.sandbox.config import Profile, SandboxConfig
from app.core.sandbox.docker_client import DockerService

logger = structlog.get_logger(__name__)


class ImageManager:
    def __init__(self, docker_service: DockerService, config: SandboxConfig):
        self.config = config
        self.docker = docker_service

    def _generate_dockerfile(self, profile: Profile) -> str:
        workdir = self.config.workdir
        user = profile.user

        sys_deps_str = " ".join(profile.system_packages)
        py_deps_str = " ".join(profile.python_packages)

        dockerfile = [f"FROM {profile.base_image}"]

        if user != "root":
            dockerfile.append(f"RUN groupadd -r {user} && useradd -r -g {user} {user}")

        if profile.system_packages:
            dockerfile.append(
                f"RUN apt-get update && apt-get install -y --no-install-recommends {sys_deps_str} "
                "&& rm -rf /var/lib/apt/lists/*"
            )

        if profile.python_packages:
            dockerfile.append(f"RUN pip install --no-cache-dir {py_deps_str}")

        dockerfile.append(f"WORKDIR {workdir}")

        if user != "root":
            dockerfile.append(f"RUN chown -R {user}:{user} {workdir}")
            dockerfile.append(f"USER {user}")

        dockerfile.append('CMD ["python3"]')

        return "\n".join(dockerfile)

    def build_profile(self, profile_name: str, force_rebuild: bool = False) -> str:
        profile = self.config.get_profile(profile_name)
        tag = profile.image

        if not force_rebuild:
            try:
                self.docker.client.images.get(tag)
                logger.debug("image already exists", tag=tag, profile=profile_name)
                return tag
            except Exception as e:
                logger.warning(f"image not found: {e}")

        logger.info("building image environment", tag=tag, profile=profile_name)

        dockerfile_content = self._generate_dockerfile(profile)

        logger.debug("generated dockerfile", content=dockerfile_content)

        f = io.BytesIO(dockerfile_content.encode("utf-8"))

        try:
            self.docker.client.images.build(
                fileobj=f,
                tag=tag,
                rm=True,
                forcerm=True,
            )

            logger.info("build successful", tag=tag)
            return tag
        except Exception as e:
            logger.exception("build failed", error=str(e))
            raise e
