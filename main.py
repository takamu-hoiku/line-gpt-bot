import os
import time
import hmac
import hashlib
import logging
import requests
from flask import Flask, request, abort

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# ========== ENV ==========
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN", "")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Renderの無料環境だと再起動で消えるので、まずは簡易メモリ（後でDB/Redisにできる）
SESSION = {}  # { user_id: [ {"role":"user","content":"..."}, {"role":"assistant","content":"..."} ] }

# ========== Helpers ==========
def verify_line_signature(body: bytes, signature: str) -> bool:
    if not LINE_CHANNEL_SECRET or not signature:
        return False
    mac = hmac.new(LINE_CHANNEL_SECRET.encode("utf-8"), body, hashlib.sha256).digest()
    expected = hashlib.base64.b64encode(mac).decode("utf-8") if hasattr(hashlib, "base64") else None
    # 上のbase64が環境で無い場合に備えて安全に実装
    import base64
    expected = base64.b64encode(mac).decode("utf-8")
    return hmac.compare_digest(expected, signature)

def reply_message(reply_token: str, text: str) -> None:
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    data = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text}],
    }
    r = requests.post(url, headers=headers, json=data, timeout=10)
    if r.status_code >= 400:
        app.logger.error(f"LINE reply failed: {r.status_code} {r.text}")

def openai_senpai_reply(user_id: str, user_text: str) -> str:
    """
    OpenAI Responses APIに投げて、せんぱい口調で返す
    """
    if not OPENAI_API_KEY:
        return "ごめんね…OPENAI_API_KEY がまだ設定されてないみたい🙏 RenderのEnvironmentで入れてみて！"

    # 直近の履歴を少しだけ持つ（多すぎると重くなるので）
    history = SESSION.get(user_id, [])
    history = history[-10:]

    system_instructions = (
        "あなたは『優しくて頼れる保育士の先輩』です。"
        "あたたかく柔らかい口調で、相手が本音を話しやすい雰囲気を作ってください。"
        "基本は短めに返し、最後に『質問を1つだけ』して会話を進めてください。"
        "説教せず、決めつけず、安心感を最優先に。"
    )

    # OpenAI Responses API
    url = "https://api.openai.com/v1/responses"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    # Responses APIは input に会話を渡せます。instructions でシステム指示も渡せます。 :contentReference[oaicite:1]{index=1}
    payload = {
        "model": "gpt-4.1",
        "instructions": system_instructions,
        "input": history + [{"role": "user", "content": user_text}],
    }

    r = requests.post(url, headers=headers, json=payload, timeout=20)
    if r.status_code >= 400:
        app.logger.error(f"OpenAI error: {r.status_code} {r.text}")
        return "ごめんね…今ちょっと頭が真っ白になっちゃった🙏 もう一回だけ送ってもらえる？"

    data = r.json()

    # output_text を取り出す（Responses APIの返りは複数形式がありえるので堅めに）
    reply_text = None
    for item in data.get("output", []):
        if item.get("type") == "message":
            for c in item.get("content", []):
                if c.get("type") == "output_text":
                    reply_text = c.get("text")
                    break
    if not reply_text:
        # 最低限のフォールバック
        reply_text = "うんうん、聞かせてくれてありがとう。いま一番しんどいのは、どの部分？"

    # 保存（簡易）
    SESSION[user_id] = (history + [{"role": "user", "content": user_text}, {"role": "assistant", "content": reply_text}])[-20:]
    return reply_text

# ========== Routes ==========
@app.get("/")
def health():
    return "OK", 200

@app.post("/callback")
def callback():
    body_bytes = request.get_data()
    signature = request.headers.get("X-Line-Signature", "")

    # 署名検証（最初はOFFでも動くけど、ON推奨）
    if LINE_CHANNEL_SECRET and signature:
        if not verify_line_signature(body_bytes, signature):
            abort(400)

    body = request.get_json(force=True, silent=True) or {}
    events = body.get("events", [])

    for event in events:
        if event.get("type") != "message":
            continue

        message = event.get("message", {})
        if message.get("type") != "text":
            continue

        reply_token = event.get("replyToken")
        user_id = (event.get("source", {}) or {}).get("userId", "unknown")
        user_text = message.get("text", "")

        if reply_token:
            # ここで“せんぱいGPT”生成
            text = openai_senpai_reply(user_id, user_text)
            reply_message(reply_token, text)

    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
