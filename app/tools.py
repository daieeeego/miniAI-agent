"""Answers for each route. Scope: 全日本軟式野球連盟（全軟連）学童部の規定のみ.

Only facts with a published source are answered. Rules that each tournament decides are
sent back to the tournament rules instead of being guessed.
"""

import re
import unicodedata

from app.models import ActionResult, Route

SCOPE = "全軟連 学童部（小学生）の規定です。中学・高校・硬式は対象外です。"

SRC_PITCH_LIMIT = (
    "全軟連 競技に関する連盟特別規則《学童部（女子共）》7 学童部の投球数制限について"
    "（全軟野連発第223号、令和7年10月24日）"
)
SRC_PITCH_COUNTING = "全軟連「学童部(小学生)の投球数制限について」（2020年、競技者必携改正）"
SRC_2022 = "全軟連「令和4年度各種規程・ルールの変更について（通知）」令和4年11月25日"
SRC_REGULATIONS = "全日本軟式野球連盟規程細則"

COUNTING_RULES = (
    "数え方: けん制球・送球は数えない。ボークでも投球したものは数える。"
    "上限に達しても、その打者の打撃完了までは投球できる。"
    "タイブレークは1日の上限内で投球できる。"
    "特別継続試合は、もとの試合の球数を引き継ぎ残りだけ投球できる。"
)


def limits(grade: int) -> tuple[int, int]:
    """(1日, 1週間) の上限。4年生以下は 60 / 180、5・6年生は 70 / 210."""
    return (60, 180) if grade <= 4 else (70, 210)


def parse_pitch_question(message: str) -> tuple[int | None, int | None, int | None]:
    """学年、今日の投球数、今週の投球数を文章から読み取る。読めない項目は None."""
    text = unicodedata.normalize("NFKC", message)
    grade_match = re.search(r"(?<!\d)([1-6])\s*年|小学?\s*([1-6])(?!\d)", text)
    grade = int(grade_match.group(1) or grade_match.group(2)) if grade_match else None
    today = week = None
    previous_end = 0
    for match in re.finditer(r"(?<!\d)(\d{1,3})\s*球", text):
        # Only the words since the previous count describe this one.
        before = text[max(previous_end, match.start() - 8) : match.start()]
        previous_end = match.end()
        if "週" in before:
            week = week if week is not None else int(match.group(1))
        elif today is None:
            today = int(match.group(1))
    return grade, today, week


def pitch_count(message: str) -> ActionResult:
    grade, today, week = parse_pitch_question(message)
    lines = []
    if grade is None:
        lines.append("上限: 5・6年生は1日70球・1週間210球、4年生以下は1日60球・1週間180球。")
        if today is not None or week is not None:
            lines.append(
                "学年がわからないため残りの球数は出せません。学年を添えて質問してください。"
            )
    else:
        day_limit, week_limit = limits(grade)
        lines.append(f"{grade}年生の上限: 1日{day_limit}球、1週間{week_limit}球。")
        if today is not None:
            left = max(day_limit - today, 0)
            lines.append(f"今日あと{left}球（{today}/{day_limit}球）。")
        if week is not None:
            left = max(week_limit - week, 0)
            lines.append(f"今週あと{left}球（{week}/{week_limit}球、今日の分を含む前提）。")
        if today is not None and week is not None:
            lines.append("投げられるのは、今日と今週のどちらか少ない方までです。")
        if (today is not None and today >= day_limit) or (week is not None and week >= week_limit):
            lines.append("上限に達しています（投球中の打者の打撃完了までは投球できます）。")
    lines.append(COUNTING_RULES)
    lines.append(SCOPE)
    return ActionResult(
        tool="pitch_count",
        status="answered",
        message="\n".join(lines),
        sources=[SRC_PITCH_LIMIT, SRC_PITCH_COUNTING],
    )


FIXED_ANSWERS = {
    Route.GAME_RULES: ActionResult(
        tool="game_rules",
        status="check_tournament_rules",
        message=(
            "イニング数・試合時間・コールド・タイブレークは大会規定で決まります。"
            "連盟の公開資料では条文を確認できないため、大会要項か所属連盟に確認してください。\n"
            "特別継続試合は、もとの試合の球数と試合時間を引き継ぎ、残りだけで行います。\n" + SCOPE
        ),
        sources=[SRC_2022],
    ),
    Route.SUBSTITUTION: ActionResult(
        tool="substitution",
        status="check_tournament_rules",
        message=(
            "再出場（リエントリー）の可否と回数は大会規定で決まります。"
            "大会要項か所属連盟に確認してください。\n"
            "指名打者（DH）は学童部では導入されていません。チームの登録は25名までです。\n" + SCOPE
        ),
        sources=[SRC_2022, SRC_REGULATIONS],
    ),
    Route.SCORING: ActionResult(
        tool="scoring",
        status="not_covered",
        message=(
            "記録の付け方はチームや地域で記法が異なり、この版では根拠の資料を持っていません。"
            "スコアを付けている方や所属連盟に確認してください。"
        ),
    ),
    Route.PLAY_RULES: ActionResult(
        tool="play_rules",
        status="not_covered",
        message=(
            "プレーの判定（公認野球規則）は、この版では扱っていません。"
            "審判員や所属連盟に確認してください。"
        ),
    ),
    Route.GENERAL: ActionResult(
        tool="general",
        status="not_covered",
        message=(
            "野球のルールに関する質問として分類できませんでした。"
            "例: 「4年生が今日45球投げました。あと何球投げられる？」"
        ),
    ),
}


def execute_tool(route: Route | str, message: str) -> ActionResult:
    if route == "human_review":
        return ActionResult(
            tool="human_review", status="review_required", message="人間による確認が必要です"
        )
    route = Route(route)
    if route == Route.PITCH_COUNT:
        return pitch_count(message)
    return FIXED_ANSWERS[route].model_copy(deep=True)
