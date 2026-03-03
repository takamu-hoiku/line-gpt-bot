import os
import json
import requests
from flask import Flask, request, abort

# OpenAI SDK（requirements.txt に openai が必要）
from openai import OpenAI

app = Flask(__name__)

# =========================
# 環境変数（Renderで設定）
# =========================
LINE_ACCESS_TOKEN = os.environ.get("LINE_ACCESS_TOKEN", "").strip()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip()

if not LINE_ACCESS_TOKEN:
    print("⚠️ LINE_ACCESS_TOKEN が未設定です（RenderのEnvironmentに入れてね）")
if not OPENAI_API_KEY:
    print("⚠️ OPENAI_API_KEY が未設定です（RenderのEnvironmentに入れてね）")

client = OpenAI(api_key=OPENAI_API_KEY)

# =========================
# せんぱいGPT（system）
# =========================
SYSTEM_PROMPT = """あなたは「優しくて頼れる保育士の先輩」として、後輩や同僚の話を聞く役割を担ってください。
保育士が本音をこぼせるように、あたたかく、柔らかく、話しやすい雰囲気を大切にしてください。

・一つの質問を丁寧に投げかける。
・相手が話してくれたら、共感やねぎらいの言葉を添えてください。
・「なぜ保育士をしているのか」「どんな職場を理想としているか」「最近悩んでいることはあるか」などをテーマに自然に対話を広げてください。
・会話は一問一答形式で進めてください。
・相手の言葉を繰り返したり要約することで、「ちゃんと聞いてくれてる」と感じられるやりとりを意識してください。
・堅苦しい言葉は避けて、やさしく、フレンドリーな語り口で。

【重要：終盤のサポートステップ】
会話がある程度進み、相手の気持ちが整理されてきたと感じた場合は、
1. これまでの話をやさしく要約する
2. 次の一歩として、以下のような選択肢を提示する
　・もう少し気持ちを整理してみる？
　・具体的な対策を一緒に考えてみる？
　・園長先生や誰かに伝えるための言葉づくりをしてみる？
　・今日はここで少しスッキリして終わる？
※必ず「選択式」にし、押しつけないこと。
※解決を急がせないこと。
※相手が望んだ場合のみ次のステップに進むこと。

会話の終わりには
「話してくれてありがとう。またいつでも来てね。」
と締めくくってください。
"""

# =========================
# 簡易メモリ（Renderの再起動で消える）
# userIdごとに直近の会話を少し保持
# =========================
CHAT_MEMORY = {}
MAX_TURNS = 6  # user/assistant の往復を短めに


def build_messages(user_id: str, user_text: str):
    history = CHAT_MEMORY.get(user_id, [])
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += history
    messages.append({"role": "user", "content": user_text})
    return messages


def save_turn(user_id: str, user_text: str, assistant_text: str):
    history = CHAT_MEMORY.get(user_id, [])
    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": assistant_text})
    # 直近だけ残す
    history = history[-(MAX_TURNS * 2):]
    CHAT_MEMORY[user_id] = history


# =========================
# ルーティング
# =========================
@app.get("/")
def health():
    # Renderのヘルスチェック用
    return "OK", 200


@app.post("/callback")
def callback():
    body = request.get_json(silent=True)
    if not body:
        return "OK", 200

    events = body.get("events", [])
    for event in events:
        if event.get("type") != "message":
            continue
        msg = event.get("message", {})
        if msg.get("type") != "text":
            continue

        reply_token = event.get("replyToken")
        user_text = msg.get("text", "").strip()
        user_id = (event.get("source", {}) or {}).get("userId", "unknown")

        if not reply_token or not user_text:
            continue

        # OpenAIが未設定なら案内だけ返す
        if not OPENAI_API_KEY:
            reply_message(reply_token, "（設定がまだだよ）OPENAI_API_KEY を Render に入れてね。")
            continue

        try:
            assistant_text = ask_senpai_gpt(user_id, user_text)
            save_turn(user_id, user_text, assistant_text)
            reply_message(reply_token, assistant_text)
        except Exception as e:
            print("❌ callback error:", repr(e))
            reply_message(reply_token, "ごめんね、ちょっとエラーになった🙏 もう一回送ってみて！")

    return "OK", 200


# =========================
# OpenAI
# =========================
def ask_senpai_gpt(user_id: str, user_text: str) -> str:
    messages = build_messages(user_id, user_text)

    completion = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=0.7,
    )

    text = completion.choices[0].message.content or ""
    return text.strip()


# =========================
# LINE Reply
# =========================
def reply_message(reply_token: str, text: str):
    # 401が出るとき：LINE_ACCESS_TOKEN が間違い/期限切れ/余計な文字入りが多い
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
    print("LINE reply status:", res.status_code)
    if res.status_code >= 400:
        print("LINE reply body:", res.text)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
