from __future__ import annotations

import os
import json
import requests
from flask import Flask, request, abort
from openai import OpenAI

app = Flask(__name__)

# ====== Environment Variables ======
LINE_ACCESS_TOKEN = os.environ.get("LINE_ACCESS_TOKEN", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")  # Renderで設定推奨

if not LINE_ACCESS_TOKEN:
    print("WARN: LINE_ACCESS_TOKEN is empty.")
if not OPENAI_API_KEY:
    print("WARN: OPENAI_API_KEY is empty.")

client = OpenAI(api_key=OPENAI_API_KEY)

# ====== Senpai GPT System Prompt ======
SYSTEM_PROMPT = """
あなたは「優しくて頼れる保育士の先輩」です。
後輩や同僚が本音をこぼせるように、あたたかく、柔らかく、話しやすい雰囲気で対応してください。

・一つの質問を丁寧に投げかける
・共感やねぎらいの言葉を必ず添える
・相手の言葉を要約・言い換えて「聞いている感」を出す
・堅苦しい表現は使わない
・会話は一問一答で進める

終盤では、相手の状況に応じて以下の選択肢を提示してください（押しつけない）：
・もう少し気持ちを整理する
・具体的な対策を一緒に考える
・誰かに伝える言葉を一緒に作る
・今日はここで終わる

最後は必ず
「話してくれてありがとう。またいつでも来てね。」
で締めてください。
""".strip()


# ====== Helpers ======
def line_reply(reply_token: str, text: str) -> None:
    """Reply to LINE using replyToken (valid for a short time)."""
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text[:5000]}],  # LINE text limit safety
    }

    res = requests.post(url, headers=headers, json=payload, timeout=10)
    print("LINE reply status:", res.status_code, res.text[:200])


def ask_senpai_gpt(user_text: str) -> str:
    """Generate a senpai-style response using OpenAI."""
    # 軽いガード（空文字対策）
    user_text = (user_text or "").strip()
    if not user_text:
        return "ごめんね、メッセージが空っぽみたい🙏 もう一回だけ送ってもらえる？"

    # できるだけ「毎回同じ返事」になりにくいように、会話の流れを促す一言を加える
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ]

    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=0.7,
    )

    content = resp.choices[0].message.content
    return (content or "").strip() or "ごめんね、うまく言葉にできなかった🙏 もう一回だけ送ってもらえる？"


# ====== Routes ======
@app.get("/")
def healthcheck():
    return "OK", 200


@app.post("/callback")
def callback():
    """
    LINE webhook endpoint.
    Expects JSON like: {"events":[...]}
    """
    body = request.get_json(silent=True)
    if not body:
        abort(400, "Invalid JSON")

    print("=== callback hit ===")
    # print(json.dumps(body, ensure_ascii=False)[:2000])  # 必要ならコメント外す

    events = body.get("events", [])
    for event in events:
        if event.get("type") != "message":
            continue

        message = event.get("message", {})
        if message.get("type") != "text":
            continue

        reply_token = event.get("replyToken")
        user_text = message.get("text", "")

        print("USER SAID:", user_text)

        if not reply_token:
            continue

        try:
            ai_reply = ask_senpai_gpt(user_text)
        except Exception as e:
            print("OpenAI error:", repr(e))
            ai_reply = "ごめんね、いま少し調子が悪いみたい🙏 もう一回だけ送ってもらえる？"

        try:
            line_reply(reply_token, ai_reply)
        except Exception as e:
            print("LINE reply error:", repr(e))

    return "OK", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    # Renderのログに出る WARNING は気にしなくてOK（本番はgunicorn推奨だけど、まず動けばOK）
    app.run(host="0.0.0.0", port=port)
