from flask import Flask, request
import os
import requests

app = Flask(__name__)

LINE_ACCESS_TOKEN = os.environ.get("LINE_ACCESS_TOKEN")

@app.route("/callback", methods=["POST"])
def callback():
    body = request.get_json(force=True)
    events = body.get("events", [])

    for event in events:
        if event.get("type") == "message":
            reply_token = event.get("replyToken")
            msg = event.get("message", {}).get("text", "")

            if reply_token:
                reply_message(reply_token, f"せんぱいだよ😊\n届いたよ！\n\n「{msg}」って言ってくれたんだね。")

    return "OK"

def reply_message(reply_token, text):
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text}]
    }
    requests.post(url, headers=headers, json=data)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
