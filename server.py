from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response
import httpx
import os
import json
from pathlib import Path

app = FastAPI()

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"].strip()

BASE_DIR = Path(__file__).resolve().parent
INDEX_HTML_PATH = BASE_DIR / "templates" / "index.html"

REALTIME_MODEL = "gpt-realtime-mini"


# =========================
# PROMPT (SIMPLIFIED + STRICT)
# =========================
def build_prompt(
    caregiver_name,
    caregiver_role,
    child_name,
    child_age,
    other_caregiver_name,
    presenting_complaint,
):

    return f"""
You are a caregiver speaking to a doctor about your child.

IDENTITY:
- Your name is {caregiver_name}
- You are the child's {caregiver_role}
- Your child is {child_name}, aged {child_age}
- The other caregiver is {other_caregiver_name}

IMPORTANT:
- You are NOT a doctor
- You are NOT an assistant
- You are NOT a teacher
- You are NOT a chatbot

BEHAVIOUR RULES:
- Speak like a normal parent
- Use simple everyday language
- Answer only what is asked
- Keep answers short

CRITICAL RULES:
- NEVER ask the doctor what they want to know
- NEVER guide the conversation
- NEVER ask follow-up questions about symptoms
- NEVER say:
  "what would you like to know"
  "how can I help"
  "tell me more"
  "take your time"
  "let me know"
- If you are about to say one of these → DO NOT SPEAK

KNOWLEDGE RULE:
- You ALWAYS know the other caregiver’s name
- NEVER say you don’t know it

OPENING:
- If the doctor only greets → just greet back
- Do NOT give the complaint yet

COMPLAINT:
- Only give this when asked why you came:
"{presenting_complaint}"

UNCLEAR QUESTIONS:
- Only say "Can you explain what you mean?" if the question truly makes no sense
- Otherwise → answer normally

END:
- If doctor says they are done → say:
"Would you like to move to preceptor mode?"

Stay in character at all times.
""".strip()


# =========================
# ROUTES
# =========================
@app.get("/", response_class=HTMLResponse)
async def home():
    return HTMLResponse(INDEX_HTML_PATH.read_text())


@app.post("/session")
async def create_session(request: Request):
    try:
        offer_sdp = (await request.body()).decode("utf-8")

        qp = request.query_params

        caregiver_name = qp.get("caregiver_name", "Zanele")
        caregiver_role = qp.get("caregiver_role", "mother")
        child_name = qp.get("child_name", "the child")
        child_age = qp.get("child_age", "3 years")
        other_caregiver_name = qp.get("other_caregiver_name", "the father")
        presenting_complaint = qp.get(
            "presenting_complaint",
            "My child has been unwell for a few days."
        )

        prompt = build_prompt(
            caregiver_name,
            caregiver_role,
            child_name,
            child_age,
            other_caregiver_name,
            presenting_complaint,
        )

        session_config = {
            "type": "realtime",
            "model": REALTIME_MODEL,
            "instructions": prompt,
            "audio": {
                "input": {
                    "transcription": {
                        "model": "gpt-4o-mini-transcribe",
                        "language": "en",
                    },
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.45,
                        "prefix_padding_ms": 500,
                        "silence_duration_ms": 900,
                    },
                },
                "output": {
                    "voice": "marin",
                },
            },
        }

        async with httpx.AsyncClient() as client:
            files = {
                "sdp": (None, offer_sdp),
                "session": (None, json.dumps(session_config)),
            }

            r = await client.post(
                "https://api.openai.com/v1/realtime/calls",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                files=files,
            )

        return Response(content=r.text, media_type="application/sdp")

    except Exception as e:
        return Response(str(e), status_code=500)







