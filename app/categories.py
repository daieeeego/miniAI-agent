"""Single definition of each route, shared by MockJev, LiveJev and the GPT prompt."""

from app.models import Route

CRITERIA = {
    Route.PITCH_COUNT: "投球数制限: 1日・1週間の上限、残りの球数、投球数の数え方",
    Route.GAME_RULES: "試合の進行: イニング数、試合時間、コールド、延長、タイブレーク、継続試合",
    Route.SUBSTITUTION: "選手交代: 代打、代走、再出場（リエントリー）、指名打者、登録人数",
    Route.SCORING: "記録: スコアブックの付け方、記号、打点や失策の記録",
    Route.PLAY_RULES: "プレーの判定: アウト・セーフ、ボーク、インフィールドフライ、妨害など",
    Route.GENERAL: "上記に該当しない質問、野球のルール以外の質問",
}

# Teaching stub only: keyword hits are not model confidence.
KEYWORDS = {
    Route.PITCH_COUNT: r"球数|投球数|投球制限|何球|\d+\s*球|ピッチャー|投手",
    Route.GAME_RULES: r"イニング|回制|コールド|延長|タイブレーク|試合時間|継続試合|引き分け",
    Route.SUBSTITUTION: r"交代|代打|代走|再出場|リエントリー|指名打者|dh|登録|ベンチ入り",
    Route.SCORING: r"スコアブック|スコア|記録|記号|書き方|記入|打点|失策",
    Route.PLAY_RULES: (
        r"アウト|セーフ|ボーク|インフィールドフライ|振り逃げ|タッチアップ|妨害|フェア|ファウル"
    ),
}


def prompt_criteria() -> str:
    return "\n".join(f"- {route.value}: {text}" for route, text in CRITERIA.items())
