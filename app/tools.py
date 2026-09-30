from app.models import ActionResult, Route


def execute_tool(route: Route | str) -> ActionResult:
    """v0.1 simulates dispatch only; no cloud API or database is called."""
    if route == "human_review":
        return ActionResult(
            tool="human_review", status="review_required", message="人間による確認が必要です"
        )
    route = Route(route)
    return ActionResult(
        tool=f"{route.value}_tool",
        status="simulated",
        message=f"{route.value} のダミーツールへ振り分けました",
    )
