from python.helpers.api import ApiHandler, Request, Response
from python.helpers import errors
from python.helpers.preclusion import Preclusion, default_policy, Verdict


class RsfsPreclude(ApiHandler):
    """
    Evaluate intended actions against the Preclusion policy WITHOUT running them.

    Request body:
        {
          "commands": ["rm -rf /", ...],
          "paths": [{"path": "/etc/hosts", "operation": "write"}, ...]
        }
    """

    @classmethod
    def get_methods(cls) -> list[str]:
        return ["POST"]

    async def process(self, input: dict, request: Request) -> dict | Response:
        try:
            guard = Preclusion(default_policy())
            results = []

            for cmd in input.get("commands", []) or []:
                results.append(_as_dict(guard.evaluate_command(cmd)))

            for entry in input.get("paths", []) or []:
                if isinstance(entry, dict):
                    path = entry.get("path", "")
                    op = entry.get("operation", "write")
                else:
                    path, op = str(entry), "write"
                results.append(_as_dict(guard.evaluate_path(path, operation=op)))

            vetoed = sum(1 for r in results if r["verdict"] == Verdict.VETO.value)
            return {
                "success": True,
                "decisions": results,
                "vetoed": vetoed,
                "clear": vetoed == 0,
            }

        except Exception as e:
            return {"success": False, "error": errors.error_text(e)}


def _as_dict(d) -> dict:
    return {
        "verdict": d.verdict.value,
        "action": d.action,
        "reason": d.reason,
        "rule": d.rule,
        "allowed": d.allowed,
    }
