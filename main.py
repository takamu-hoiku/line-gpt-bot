from flask import Flask, request
import os
import requests

app = Flask(__name__)

# Render の環境変数から LINE のアクセストークンを取得
LINE_ACCESS_TOKEN = os.environ.get("LINE_ACCESS_TOKEN")


@app.route("/", methods=["GET"])
def health_check():
    # Render / LINE の疎通確認用
    return "OK", 200


@app.route("/callback", methods=["POST", "GET"])
def callback():
    # LINE Verify 用（GET）
    if request.method == "GET":
        return "OK", 200

    # LINE からのイベント（POST）
    body = request.get_json(silent=True) or {}
    events = body.get("events", [])

    print("=== webhook received ===", flush=True)
    print(body, flush=True)

    for event in events:
        if event.get("type") != "message":
            continue

        message = event.get("message", {})
        if message.get("type") != "text":
            continue

        reply_token = event.get("replyToken")
        user_text = message.get("text", "")

        if reply_token:
            reply_message(
                reply_token,
                f"""せんぱいだよ😊
届いたよ。

「{user_text}」って言ってくれたんだね。

今日はどんな気持ち？"""
            )

    # LINE には必ず 200 を返す（失敗すると再送され続ける）
    return "OK", 200


def reply_message(reply_token: str, text: str):
    if not LINE_ACCESS_TOKEN:
        print("ERROR: LINE_ACCESS_TOKEN is empty", flush=True)
        return

    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "replyToken": reply_token,
        "messages": [
            {
                "type": "text",
                "text": text
            }
        ]
    }

    response = requests.post(url, headers=headers, json=payload, timeout=10)
    print("LINE reply status:", response.status_code, flush=True)
    print("LINE reply body:", response.text, flush=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
