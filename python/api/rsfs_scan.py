from python.helpers.api import ApiHandler, Request, Response
from python.helpers import errors
from python.helpers.rsfs import build_default_swarm


class RsfsScan(ApiHandler):
    """
    Run the Recursive State Feedback Swarm (RSFS) over one or more drive
    regions and return its findings and tamper-evident integrity chain.

    Request body:
        {
          "roots": ["/path/to/watch", ...],   # required, non-empty
          "max_rounds": 4,                      # optional (default 4)
          "commands": ["rm -rf /tmp/x", ...]    # optional, audited by Preclusion
        }
    """

    @classmethod
    def get_methods(cls) -> list[str]:
        return ["POST"]

    async def process(self, input: dict, request: Request) -> dict | Response:
        try:
            roots = input.get("roots") or []
            if not isinstance(roots, list) or not roots:
                return {"success": False, "error": "provide a non-empty 'roots' list"}

            max_rounds = int(input.get("max_rounds", 4))
            max_rounds = max(1, min(max_rounds, 16))

            commands = input.get("commands") or []
            command_source = (lambda: list(commands)) if commands else None

            swarm = build_default_swarm(roots, command_source=command_source)
            rounds = swarm.run(max_rounds=max_rounds, stop_on_converge=True)
            report = swarm.report()

            return {
                "success": True,
                "report": report,
                "rounds": [
                    {
                        "round": r.round,
                        "observations": len(r.observations),
                        "new_alerts": r.new_alerts,
                        "chain_head": r.chain_head,
                        "converged": r.converged,
                    }
                    for r in rounds
                ],
            }

        except Exception as e:
            return {"success": False, "error": errors.error_text(e)}
