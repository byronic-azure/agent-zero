from python.helpers.api import ApiHandler, Request, Response
from python.helpers import errors, settings, runtime
from python.helpers.docker import DockerContainerManager
from python.helpers.print_style import PrintStyle
import docker


class ContainersConnect(ApiHandler):
    """API endpoint to connect to a live Docker container for code execution."""

    @classmethod
    def get_methods(cls) -> list[str]:
        return ["POST"]

    async def process(self, input: dict, request: Request) -> dict | Response:
        try:
            container_id = input.get("container_id")
            ssh_password = input.get("ssh_password", "")

            if not container_id:
                return {
                    "success": False,
                    "error": "container_id is required"
                }

            # Get Docker client
            client = docker.from_env()

            # Find the container
            try:
                container = client.containers.get(container_id)
            except docker.errors.NotFound:
                return {
                    "success": False,
                    "error": f"Container {container_id} not found"
                }

            # Check if container is running
            if container.status != "running":
                return {
                    "success": False,
                    "error": f"Container {container.name} is not running (status: {container.status})"
                }

            # Get SSH port mapping
            ssh_port = None
            if container.ports.get("22/tcp"):
                ssh_port = container.ports["22/tcp"][0].get("HostPort")

            if not ssh_port:
                return {
                    "success": False,
                    "error": f"Container {container.name} does not have SSH port (22) exposed"
                }

            # Get web port mapping (optional)
            web_port = None
            if container.ports.get("80/tcp"):
                web_port = container.ports["80/tcp"][0].get("HostPort")

            # Update settings to connect to this container
            current_settings = settings.get_settings()

            # Determine the SSH host address
            # If running in Docker, use host.docker.internal or gateway
            # If running natively, use localhost
            ssh_host = "localhost"
            if runtime.is_dockerized():
                # When running inside Docker, need to reach the host's Docker containers
                # Use host.docker.internal on Mac/Windows, or the gateway IP on Linux
                try:
                    import socket
                    # Try host.docker.internal first
                    socket.gethostbyname("host.docker.internal")
                    ssh_host = "host.docker.internal"
                except socket.gaierror:
                    # Fall back to the Docker gateway IP
                    ssh_host = "172.17.0.1"

            # Build the connection configuration
            connection_config = {
                "container_id": container.id,
                "container_name": container.name,
                "ssh_host": ssh_host,
                "ssh_port": int(ssh_port),
                "ssh_user": "root",
                "ssh_password": ssh_password,
                "web_port": int(web_port) if web_port else None,
            }

            # Store the connection info
            settings.set_settings_delta({
                "shell_interface": "ssh",
                "rfc_url": ssh_host,
                "rfc_port_ssh": int(ssh_port),
                "rfc_port_http": int(web_port) if web_port else current_settings.get("rfc_port_http", 55080),
                "live_container_id": container.id,
                "live_container_name": container.name,
            })

            PrintStyle(
                background_color="green", font_color="white", padding=True
            ).print(f"Connected to container: {container.name} (SSH port: {ssh_port})")

            return {
                "success": True,
                "message": f"Successfully connected to container {container.name}",
                "connection": connection_config,
                "container": {
                    "id": container.id,
                    "short_id": container.short_id,
                    "name": container.name,
                    "status": container.status,
                    "image": str(container.image.tags[0]) if container.image.tags else str(container.image.id)[:12],
                }
            }

        except Exception as e:
            PrintStyle.error(f"Failed to connect to container: {errors.error_text(e)}")
            return {
                "success": False,
                "error": errors.error_text(e)
            }
