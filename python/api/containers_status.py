from python.helpers.api import ApiHandler, Request, Response
from python.helpers import errors, settings, runtime
from python.helpers.docker import DockerContainerManager
import docker


class ContainersStatus(ApiHandler):
    """API endpoint to get the current container connection status."""

    @classmethod
    def get_methods(cls) -> list[str]:
        return ["GET", "POST"]

    async def process(self, input: dict, request: Request) -> dict | Response:
        try:
            current_settings = settings.get_settings()

            # Get current connection settings
            live_container_id = current_settings.get("live_container_id", "")
            live_container_name = current_settings.get("live_container_name", "")
            shell_interface = current_settings.get("shell_interface", "local")
            ssh_host = current_settings.get("rfc_url", "localhost")
            ssh_port = current_settings.get("rfc_port_ssh", 55022)

            # Check if we have a live container configured
            is_connected = bool(live_container_id)
            container_status = None
            container_info = None

            if live_container_id:
                try:
                    client = docker.from_env()
                    container = client.containers.get(live_container_id)
                    container_status = container.status

                    # Get current port mappings
                    current_ssh_port = None
                    current_web_port = None
                    if container.ports.get("22/tcp"):
                        current_ssh_port = container.ports["22/tcp"][0].get("HostPort")
                    if container.ports.get("80/tcp"):
                        current_web_port = container.ports["80/tcp"][0].get("HostPort")

                    container_info = {
                        "id": container.id,
                        "short_id": container.short_id,
                        "name": container.name,
                        "status": container.status,
                        "image": str(container.image.tags[0]) if container.image.tags else str(container.image.id)[:12],
                        "ssh_port": int(current_ssh_port) if current_ssh_port else None,
                        "web_port": int(current_web_port) if current_web_port else None,
                        "is_running": container.status == "running",
                    }
                except docker.errors.NotFound:
                    is_connected = False
                    container_status = "not_found"
                except Exception as e:
                    is_connected = False
                    container_status = f"error: {str(e)}"

            # Test SSH connection if configured for SSH
            ssh_test_result = None
            if shell_interface == "ssh" and is_connected and container_info and container_info.get("is_running"):
                try:
                    manager = DockerContainerManager(
                        image="",
                        name="",
                        ports=None,
                        volumes=None,
                        logger=None
                    )
                    # Note: We can't test without password, so just check if port is reachable
                    import socket
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(2)
                    result = sock.connect_ex((ssh_host, int(container_info.get("ssh_port", ssh_port))))
                    sock.close()
                    ssh_test_result = {
                        "port_open": result == 0,
                        "host": ssh_host,
                        "port": container_info.get("ssh_port", ssh_port)
                    }
                except Exception as e:
                    ssh_test_result = {
                        "port_open": False,
                        "error": str(e)
                    }

            return {
                "success": True,
                "is_connected": is_connected,
                "connection": {
                    "container_id": live_container_id,
                    "container_name": live_container_name,
                    "container_status": container_status,
                    "shell_interface": shell_interface,
                    "ssh_host": ssh_host,
                    "ssh_port": ssh_port,
                },
                "container": container_info,
                "ssh_test": ssh_test_result,
                "is_dockerized": runtime.is_dockerized(),
            }

        except Exception as e:
            return {
                "success": False,
                "error": errors.error_text(e),
                "is_connected": False,
            }
