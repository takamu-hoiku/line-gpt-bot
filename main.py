from __future__ import annotations
import os
import requests
from flask import Flask, request, abort

app = Flask(__name__)

# =========================
# 環境変数
# =========================
LINE_ACCESS_TOKEN = os.environ.get("LINE_ACCESS_TOKEN", "")
DIFY_API_KEY = os.environ.get("DIFY_API_KEY", "")
DIFY_API_URL = "https://api.dify.ai/v1/chat-messages"

# 会話ID保持
conversation_ids = {}


# =========================
# LINE返信
# =========================
def line_reply(reply_token: str, text: str) -> None:
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text[:5000]}],
    }

    res = requests.post(url, headers=headers, json=payload, timeout=10)
    print("LINE reply status:", res.status_code, res.text[:200], flush=True)


# =========================
# Difyに問い合わせ
# =========================
def ask_dify(user_id: str, user_text: str) -> str:
    headers = {
        "Authorization": f"Bearer {DIFY_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "inputs": {},
        "query": user_text,
        "response_mode": "blocking",
        "conversation_id": conversation_ids.get(user_id, ""),
        "user": user_id,
    }

    res = requests.post(DIFY_API_URL, headers=headers, json=payload, timeout=10)

    print("Dify status:", res.status_code, flush=True)

    try:
        data = res.json()
    except Exception as e:
        print("Dify JSON error:", repr(e), flush=True)
        return "ごめんね、AIの応答がうまく受け取れなかった🙏"

    print("Dify response:", data, flush=True)

    # 会話ID更新
    conversation_ids[user_id] = data.get("conversation_id", "")

    # レスポンス取得（複数パターン対応）
    if "answer" in data:
        return data["answer"]

    try:
        return data["data"]["outputs"]["text"]
    except Exception:
        return "ごめんね、うまく答えられなかった🙏"


# =========================
# ヘルスチェック
# =========================
@app.get("/")
def healthcheck():
    return "OK", 200


# =========================
# LINE Webhook（ここが超重要）
# =========================
@app.post("/callback")
def callback():
    print("=== callback hit ===", flush=True)

    body = request.get_json(silent=True)
    if not body:
        abort(400)

    events = body.get("events", [])

    for event in events:
        if event.get("type") != "message":
            continue

        message = event.get("message", {})
        if message.get("type") != "text":
            continue

        reply_token = event.get("replyToken")
        user_id = event.get("source", {}).get("userId", "unknown")
        user_text = message.get("text", "")

        print("受信メッセージ:", user_text, flush=True)

        if not reply_token:
            continue

        # Dify処理
        try:
            ai_reply = ask_dify(user_id, user_text)
        except Exception as e:
            print("Dify error:", repr(e), flush=True)
            ai_reply = "ごめんね、いま少し調子が悪いみたい🙏"

        # LINE返信
        try:
            line_reply(reply_token, ai_reply)
        except Exception as e:
            print("LINE reply error:", repr(e), flush=True)

    return "OK", 200


# =========================
# 起動
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
