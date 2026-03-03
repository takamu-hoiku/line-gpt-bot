from flask import Flask, request
import os
import requests
from openai import OpenAI

app = Flask(__name__)

# 環境変数
LINE_ACCESS_TOKEN = os.environ.get("LINE_ACCESS_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# せんぱいGPTの人格（systemプロンプト）
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
"""

@app.route("/callback", methods=["POST"])
def callback():
    body = request.get_json(force=True)
    events = body.get("events", [])

    for event in events:
        if event.get("type") == "message":
            reply_token = event.get("replyToken")
            user_message = event.get("message", {}).get("text", "")

            if reply_token and user_message:
                ai_reply = ask_senpai_gpt(user_message)
                reply_message(reply_token, ai_reply)

    return "OK"

def ask_senpai_gpt(user_text):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text}
        ],
        temperature=0.7,
    )
    return response.choices[0].message.content

def reply_message(reply_token, text):
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "replyToken": reply_token,
        "messages": [
            {"type": "text", "text": text}
        ]
    }

    res = requests.post(url, headers=headers, json=data)
    print("LINE reply status:", res.status_code)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
