from flask import Flask, request
import os
import requests

app = Flask(__name__)

LINE_ACCESS_TOKEN = os.environ.get("LINE_ACCESS_TOKEN", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")

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

@app.get("/")
def health():
    return "OK", 200

@app.post("/callback")
def callback():
    body = request.get_json(silent=True) or {}
    events = body.get("events", [])

    for event in events:
        if event.get("type") != "message":
            continue

        msg = event.get("message", {})
        if msg.get("type") != "text":
            continue

        reply_token = event.get("replyToken")
        user_text = (msg.get("text") or "").strip()

        if not reply_token or not user_text:
            continue

        ai_reply = ask_senpai_gpt(user_text)
        reply_message(reply_token, ai_reply)

    return "OK", 200

def ask_senpai_gpt(user_text: str) -> str:
    if not OPENAI_API_KEY:
        return "（設定チェック）OPENAI_API_KEY がまだ入ってないみたい🙏 RenderのEnvironmentを確認してね。"

    url = "https://api.openai.com/v1/responses"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENAI_MODEL,
        "instructions": SYSTEM_PROMPT,
        "input": user_text,
    }

    r = requests.post(url, headers=headers, json=payload, timeout=20)
    print("OpenAI status:", r.status_code, flush=True)

    if r.status_code >= 400:
        print("OpenAI error body:", r.text, flush=True)
        return "ごめんね、今ちょっと返事づくりでつまずいた🙏 もう一回だけ送ってもらえる？"

    data = r.json()
    return extract_output_text(data) or "うんうん、話してくれてありがとう。いま一番しんどいのは、どの部分？"

def extract_output_text(data: dict) -> str:
    for item in data.get("output", []):
        if item.get("type") == "message":
            for c in item.get("content", []):
                if c.get("type") == "output_text":
                    return c.get("text", "")
    return ""

def reply_message(reply_token: str, text: str) -> None:
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
    if res.status_code >= 400:
        print("LINE reply body:", res.text, flush=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
