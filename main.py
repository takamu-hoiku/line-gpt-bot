import os
import requests
from flask import Flask, request

app = Flask(__name__)

# =========================
# 環境変数
# =========================
LINE_ACCESS_TOKEN = os.environ.get("LINE_ACCESS_TOKEN", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")

# 簡易セッション（無料Render想定：再起動で消えてOK）
SESSIONS = {}  # user_id -> [{"role": "user"/"assistant", "content": "..."}]


# =========================
# ヘルスチェック
# =========================
@app.get("/")
def health():
    return "OK", 200


# =========================
# LINE Webhook
# =========================
@app.route("/callback", methods=["POST", "GET"])
def callback():
    # Verify対策
    if request.method == "GET":
        return "OK", 200

    body = request.get_json(silent=True) or {}
    events = body.get("events", [])

    for event in events:
        if event.get("type") != "message":
            continue

        message = event.get("message", {})
        if message.get("type") != "text":
            continue

        reply_token = event.get("replyToken")
        user_text = message.get("text", "").strip()
        user_id = (event.get("source", {}) or {}).get("userId", "unknown")

        if not reply_token:
            continue

        # 危険サインがあれば即セーフティ返信
        if looks_like_crisis(user_text):
            reply_message(
                reply_token,
                "話してくれてありがとう。\n"
                "もし今『自分を傷つけたい』気持ちが強いなら、今は一人で抱えないでね。\n"
                "近くの信頼できる人や、緊急時は110/119など、まず安全を優先してね。\n\n"
                "よければ、いま誰か近くにいるかだけ教えて。"
            )
            continue

        reply_text = generate_senpai_reply(user_id, user_text)
        reply_message(reply_token, reply_text)

    return "OK", 200


# =========================
# 危険サイン検知（簡易）
# =========================
def looks_like_crisis(text: str) -> bool:
    t = text.replace(" ", "").replace("　", "")
    keywords = [
        "死にたい", "消えたい", "自殺", "もう無理", "終わりにしたい",
        "殺して", "リスカ", "自傷"
    ]
    return any(k in t for k in keywords)


# =========================
# 終盤判定
# =========================
def should_wrap_up(history: list, user_text: str) -> bool:
    t = (user_text or "").replace(" ", "").replace("　", "")
    wrap_keywords = [
        "整理できた", "整理できそう", "落ち着いた", "少し落ち着いた",
        "スッキリした", "話してよかった", "ありがとう",
        "前向き", "決めた", "わかった", "もう大丈夫"
    ]

    progressed = len(history) >= 8  # だいたい4往復
    keyword_hit = any(k in t for k in wrap_keywords)

    return progressed or keyword_hit


# =========================
# せんぱいGPT生成
# =========================
def generate_senpai_reply(user_id: str, user_text: str) -> str:
    # APIキー未設定時のフォールバック
    if not OPENAI_API_KEY:
        return (
            "せんぱいだよ😊\n"
            "話してくれてありがとう。\n\n"
            "無理に整理しなくて大丈夫だよ。\n"
            "いま一番しんどいところから教えてもらっていい？"
        )

    history = SESSIONS.get(user_id, [])
    history = history[-10:]

    base_instructions = """
あなたは「優しくて頼れる保育士の先輩」です。
後輩や同僚の話を聞き、気持ちを整理する手助けをします。

【話し方】
・あたたかく、柔らかく、フレンドリー
・否定、説教、決めつけはしない
・専門用語は使わない

【進め方】
・返信は短め（3〜6行）
・最初に共感やねぎらいを入れる
・相手の言葉を一文で要約または繰り返す
・質問は必ず1つだけ（一問一答）
・解決を急がない
""".strip()

    wrapup_instructions = """
【終盤モード】
相手の気持ちが整理されてきた前提で進めてください。

必ずこの順番で：
1) ここまでの話をやさしく要約（2〜3行）
2) 次の一歩を選択式で提示（1つの質問として）
   ・もう少し気持ちを整理してみる？
   ・具体的な対策を一緒に考えてみる？
   ・誰かに伝えるための言葉づくりをしてみる？
   ・今日はここで少しスッキリして終わる？
3) 最後は必ず
「話してくれてありがとう。またいつでも来てね。」
で締める
""".strip()

    wrap_mode = should_wrap_up(history, user_text)
    instructions = base_instructions + ("\n\n" + wrapup_instructions if wrap_mode else "")

    url = "https://api.openai.com/v1/responses"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": OPENAI_MODEL,
        "instructions": instructions,
        "input": history + [{"role": "user", "content": user_text}],
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=20)
        if res.status_code >= 400:
            return (
                "ごめんね、ちょっと考えがまとまらなかった🙏\n"
                "もう一回、いちばん伝えたいことだけ送ってもらえる？"
            )

        data = res.json()
        reply = extract_output_text(data)

        if not reply:
            reply = (
                "うん、話してくれてありがとう。\n"
                "いま一番重たいのは、どのあたりかな？"
            )

        SESSIONS[user_id] = (history + [
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": reply},
        ])[-20:]

        return reply

    except requests.exceptions.RequestException:
        return (
            "ごめんね、今ちょっと不安定みたい🙏\n"
            "少しだけ時間をおいて、もう一回送ってもらえる？"
        )


def extract_output_text(data: dict) -> str:
    for item in data.get("output", []):
        if item.get("type") == "message":
            for c in item.get("content", []):
                if c.get("type") == "output_text":
                    return c.get("text", "")
    return ""


# =========================
# LINE返信
# =========================
def reply_message(reply_token: str, text: str):
    if not LINE_ACCESS_TOKEN:
        print("LINE_ACCESS_TOKEN is empty", flush=True)
        return

    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text}],
    }

    res = requests.post(url, headers=headers, json=payload, timeout=10)
    print("LINE reply status:", res.status_code, flush=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
