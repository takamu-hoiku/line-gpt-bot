from flask import Flask, request
import os
import requests

app = Flask(__name__)

# 環境変数（Renderで設定済みのはず）
LINE_ACCESS_TOKEN = os.environ.get("LINE_ACCESS_TOKEN", "")

@app.get("/")
def health():
    return "OK", 200

@app.post("/callback")
def callback():
    body = request.get_json(silent=True) or {}
    events = body.get("events", [])

    print("=== callback hit ===", flush=True)

    for event in events:
        if event.get("type") != "message":
            continue

        message = event.get("message", {})
        if message.get("type") != "text":
            continue

        reply_token = event.get("replyToken")
        user_text = message.get("text", "")

        print("USER SAID:", user_text, flush=True)

        if reply_token:
            reply_message(
                reply_token,
                "せんぱいだよ😊\n\n"
                "ちゃんと届いてるよ。\n"
                "いまは連動チェック中だから、まずはここまで！"
            )

    return "OK", 200

def reply_message(reply_token, text):
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "replyToken": reply_token,
        "messages": [
            {"type": "text", "text": text}
        ]
    }

    res = requests.post(url, headers=headers, json=payload)
    print("LINE reply status:", res.status_code, flush=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
