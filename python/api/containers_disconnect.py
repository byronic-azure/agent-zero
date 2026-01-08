from python.helpers.api import ApiHandler, Request, Response
from python.helpers import errors, settings, runtime
from python.helpers.print_style import PrintStyle


class ContainersDisconnect(ApiHandler):
    """API endpoint to disconnect from the current container."""

    @classmethod
    def get_methods(cls) -> list[str]:
        return ["POST"]

    async def process(self, input: dict, request: Request) -> dict | Response:
        try:
            current_settings = settings.get_settings()

            # Get current connection for logging
            previous_container_id = current_settings.get("live_container_id", "")
            previous_container_name = current_settings.get("live_container_name", "")

            if not previous_container_id:
                return {
                    "success": True,
                    "message": "No container was connected",
                    "was_connected": False,
                }

            # Clear the connection settings and revert to default shell interface
            settings.set_settings_delta({
                "live_container_id": "",
                "live_container_name": "",
                "shell_interface": "local" if runtime.is_dockerized() else "ssh",
            })

            PrintStyle(
                background_color="yellow", font_color="black", padding=True
            ).print(f"Disconnected from container: {previous_container_name}")

            return {
                "success": True,
                "message": f"Successfully disconnected from container {previous_container_name}",
                "was_connected": True,
                "previous_connection": {
                    "container_id": previous_container_id,
                    "container_name": previous_container_name,
                }
            }

        except Exception as e:
            PrintStyle.error(f"Failed to disconnect from container: {errors.error_text(e)}")
            return {
                "success": False,
                "error": errors.error_text(e)
            }
