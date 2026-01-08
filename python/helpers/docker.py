import time
import docker
import atexit
from typing import Optional
from python.helpers.files import get_abs_path
from python.helpers.errors import format_error
from python.helpers.print_style import PrintStyle
from python.helpers.log import Log

class DockerContainerManager:
    def __init__(self, image: str, name: str, ports: Optional[dict[str, int]] = None, volumes: Optional[dict[str, dict[str, str]]] = None,logger: Log|None=None):
        self.logger = logger
        self.image = image
        self.name = name
        self.ports = ports
        self.volumes = volumes
        self.init_docker()
                
    def init_docker(self):
        self.client = None
        while not self.client:
            try:
                self.client = docker.from_env()
                self.container = None
            except Exception as e:
                err = format_error(e)
                if ("ConnectionRefusedError(61," in err or "Error while fetching server API version" in err):
                    PrintStyle.hint("Connection to Docker failed. Is docker or Docker Desktop running?") # hint for user
                    if self.logger:self.logger.log(type="hint", content="Connection to Docker failed. Is docker or Docker Desktop running?")
                    PrintStyle.error(err)
                    if self.logger:self.logger.log(type="error", content=err)
                    time.sleep(5) # try again in 5 seconds
                else: raise
        return self.client
                            
    def cleanup_container(self) -> None:
        if self.container:
            try:
                self.container.stop()
                self.container.remove()
                PrintStyle.standard(f"Stopped and removed the container: {self.container.id}")
                if self.logger: self.logger.log(type="info", content=f"Stopped and removed the container: {self.container.id}")
            except Exception as e:
                PrintStyle.error(f"Failed to stop and remove the container: {e}")
                if self.logger: self.logger.log(type="error", content=f"Failed to stop and remove the container: {e}")

    def get_image_containers(self):
        if not self.client: self.client = self.init_docker()
        containers = self.client.containers.list(all=True, filters={"ancestor": self.image})
        infos = []
        for container in containers:
            infos.append({                
                "id": container.id,
                "name": container.name,
                "status": container.status,
                "image": container.image,
                "ports": container.ports,
                "web_port": (container.ports.get("80/tcp") or [{}])[0].get("HostPort"),
                "ssh_port": (container.ports.get("22/tcp") or [{}])[0].get("HostPort"),
                # "volumes": container.volumes,
                # "data_folder": container.volumes["/a0"],
            })
        return infos

    def start_container(self) -> None:
        if not self.client: self.client = self.init_docker()
        existing_container = None
        for container in self.client.containers.list(all=True):
            if container.name == self.name:
                existing_container = container
                break

        if existing_container:
            if existing_container.status != 'running':
                PrintStyle.standard(f"Starting existing container: {self.name} for safe code execution...")
                if self.logger: self.logger.log(type="info", content=f"Starting existing container: {self.name} for safe code execution...", temp=True)
                
                existing_container.start()
                self.container = existing_container
                time.sleep(2) # this helps to get SSH ready
                
            else:
                self.container = existing_container
                # PrintStyle.standard(f"Container with name '{self.name}' is already running with ID: {existing_container.id}")
        else:
            PrintStyle.standard(f"Initializing docker container {self.name} for safe code execution...")
            if self.logger: self.logger.log(type="info", content=f"Initializing docker container {self.name} for safe code execution...", temp=True)

            self.container = self.client.containers.run(
                self.image,
                detach=True,
                ports=self.ports, # type: ignore
                name=self.name,
                volumes=self.volumes, # type: ignore
            ) 
            # atexit.register(self.cleanup_container)
            PrintStyle.standard(f"Started container with ID: {self.container.id}")
            if self.logger: self.logger.log(type="info", content=f"Started container with ID: {self.container.id}")
            time.sleep(5) # this helps to get SSH ready

    def get_container_by_id(self, container_id: str):
        """Get a container by its ID or name."""
        if not self.client:
            self.client = self.init_docker()
        try:
            return self.client.containers.get(container_id)
        except docker.errors.NotFound:
            return None

    def get_container_connection_info(self, container_id: str) -> Optional[dict]:
        """Get connection information for a specific container."""
        container = self.get_container_by_id(container_id)
        if not container:
            return None

        ssh_port = None
        web_port = None

        if container.ports.get("22/tcp"):
            ssh_port = container.ports["22/tcp"][0].get("HostPort")
        if container.ports.get("80/tcp"):
            web_port = container.ports["80/tcp"][0].get("HostPort")

        return {
            "id": container.id,
            "short_id": container.short_id,
            "name": container.name,
            "status": container.status,
            "image": str(container.image.tags[0]) if container.image.tags else str(container.image.id)[:12],
            "ssh_port": int(ssh_port) if ssh_port else None,
            "web_port": int(web_port) if web_port else None,
            "ssh_available": ssh_port is not None and container.status == "running",
        }

    def get_all_containers(self, running_only: bool = False) -> list[dict]:
        """Get all containers with their connection information."""
        if not self.client:
            self.client = self.init_docker()

        containers = self.client.containers.list(all=not running_only)
        result = []

        for container in containers:
            ssh_port = None
            web_port = None

            if container.ports.get("22/tcp"):
                ssh_port = container.ports["22/tcp"][0].get("HostPort")
            if container.ports.get("80/tcp"):
                web_port = container.ports["80/tcp"][0].get("HostPort")

            result.append({
                "id": container.id,
                "short_id": container.short_id,
                "name": container.name,
                "status": container.status,
                "image": str(container.image.tags[0]) if container.image.tags else str(container.image.id)[:12],
                "ssh_port": int(ssh_port) if ssh_port else None,
                "web_port": int(web_port) if web_port else None,
                "ssh_available": ssh_port is not None and container.status == "running",
            })

        return result

    def test_ssh_connection(self, host: str, port: int, username: str, password: str, timeout: int = 5) -> tuple[bool, str]:
        """Test SSH connection to a container."""
        try:
            import paramiko
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                hostname=host,
                port=port,
                username=username,
                password=password,
                timeout=timeout,
                allow_agent=False,
                look_for_keys=False
            )
            client.close()
            return True, "SSH connection successful"
        except Exception as e:
            return False, f"SSH connection failed: {str(e)}"
