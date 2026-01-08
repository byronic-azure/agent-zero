from python.helpers.api import ApiHandler, Request, Response
from python.helpers import errors
from python.helpers.docker import DockerContainerManager


class ContainersList(ApiHandler):
    """API endpoint to list available Docker containers."""

    @classmethod
    def get_methods(cls) -> list[str]:
        return ["GET", "POST"]

    async def process(self, input: dict, request: Request) -> dict | Response:
        try:
            # Get optional image filter from input
            image_filter = input.get("image", "agent0ai/agent-zero")

            # Create a temporary manager to list containers
            manager = DockerContainerManager(
                image=image_filter,
                name="",  # Not needed for listing
                ports=None,
                volumes=None,
                logger=None
            )

            containers = manager.get_image_containers()

            # Also get all running containers if no specific image filter
            all_containers = []
            if manager.client:
                for container in manager.client.containers.list(all=True):
                    container_info = {
                        "id": container.id,
                        "short_id": container.short_id,
                        "name": container.name,
                        "status": container.status,
                        "image": str(container.image.tags[0]) if container.image.tags else str(container.image.id)[:12],
                        "ports": container.ports,
                        "web_port": (container.ports.get("80/tcp") or [{}])[0].get("HostPort"),
                        "ssh_port": (container.ports.get("22/tcp") or [{}])[0].get("HostPort"),
                    }
                    all_containers.append(container_info)

            return {
                "success": True,
                "filtered_containers": containers,
                "all_containers": all_containers,
                "image_filter": image_filter
            }

        except Exception as e:
            return {
                "success": False,
                "error": errors.error_text(e),
                "filtered_containers": [],
                "all_containers": []
            }
