from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response, JSONResponse
from fastapi.templating import Jinja2Templates
import httpx
import os
import json
from pathlib import Path
from datetime import datetime, timezone

app = FastAPI()
templates = Jinja2Templates(directory="templates")

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

TRANSCRIPTS_DIR = Path("transcripts")
TRANSCRIPTS_DIR.mkdir(exist_ok=True)

PRECEPTOR_INVITE_LINE = "Would you like to move to preceptor mode?"
DIAGNOSIS_QUESTION = "What is your diagnosis?"
DIFFERENTIALS_QUESTION = "What are your differential diagnoses?"
FEEDBACK_QUESTION = "Would you like to receive your assessment now?"

# Voice choices chosen by us
FEMALE_VOICE = "marin"
MALE_VOICE = "cedar"


def now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_session_id(session_id: str) -> str:
    return "".join(c for c in str(session_id).strip() if c.isalnum() or c in "-_")


def parse_iso_datetime(value: str | None):
    if not value:
        return None
    try:
        cleaned = str(value).strip()
        if cleaned.endswith("Z"):
            cleaned = cleaned.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    except Exception:
        return None


def compute_duration_seconds(started_at: str | None, ended_at: str | None):
    start_dt = parse_iso_datetime(started_at)
    end_dt = parse_iso_datetime(ended_at)
    if not start_dt or not end_dt:
        return None
    try:
        return max(0, int((end_dt - start_dt).total_seconds()))
    except Exception:
        return None


def choose_voice(caregiver_gender: str) -> str:
    g = str(caregiver_gender or "").strip().lower()
    if g == "male":
        return MALE_VOICE
    return FEMALE_VOICE


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/save_transcript")
async def save_transcript(request: Request):
    try:
        body = await request.json()

        session_id = str(body.get("session_id", "")).strip()
        safe_id = safe_session_id(session_id)

        if not safe_id:
            return JSONResponse(
                {"status": "error", "message": "Missing session_id"},
                status_code=400,
            )

        transcript_file = TRANSCRIPTS_DIR / f"transcript_{safe_id}.json"

        started_at = body.get("started_at")
        ended_at = body.get("ended_at") or now_iso_utc()
        duration_seconds = body.get("duration_seconds")

        if duration_seconds is None:
            duration_seconds = compute_duration_seconds(started_at, ended_at)

        transcript_payload = {
            "session_id": safe_id,
            "study_number": body.get("study_number"),
            "interaction_mode": body.get("interaction_mode"),
            "age_group": body.get("age_group"),
            "system": body.get("system"),
            "caregiver_name": body.get("caregiver_name"),
            "caregiver_gender": body.get("caregiver_gender"),
            "caregiver_role": body.get("caregiver_role"),
            "child_name": body.get("child_name"),
            "presenting_complaint": body.get("presenting_complaint"),
            "case_summary": body.get("case_summary"),
            "opening_line": body.get("opening_line"),
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_seconds": duration_seconds,
            "session_completed": body.get("session_completed", False),
            "timeout_reason": body.get("timeout_reason"),
            "transcript_lines": body.get("transcript_lines", []),
            "transcript_text": body.get("transcript_text", ""),
            "saved_at": now_iso_utc(),
        }

        with open(transcript_file, "w", encoding="utf-8") as f:
            json.dump(transcript_payload, f, ensure_ascii=False, indent=2)

        return JSONResponse(
            {
                "status": "ok",
                "session_id": safe_id,
                "file": str(transcript_file),
            }
        )

    except Exception as e:
        print(f"save_transcript error: {e}")
        return JSONResponse(
            {"status": "error", "message": "Could not save transcript"},
            status_code=500,
        )


@app.get("/latest_transcript")
async def latest_transcript(session_id: str | None = None):
    try:
        if not session_id:
            return JSONResponse(
                {"status": "error", "message": "session_id is required"},
                status_code=400,
            )

        safe_id = safe_session_id(session_id)
        transcript_file = TRANSCRIPTS_DIR / f"transcript_{safe_id}.json"

        if not transcript_file.exists():
            return JSONResponse({"status": "missing"}, status_code=404)

        with open(transcript_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return JSONResponse({"status": "ok", "data": data})

    except Exception as e:
        print(f"latest_transcript error: {e}")
        return JSONResponse(
            {"status": "error", "message": "Could not load transcript"},
            status_code=500,
        )


@app.post("/session")
async def create_session(request: Request):
    try:
        offer_sdp = await request.body()
        offer_sdp = offer_sdp.decode("utf-8")

        age_group = request.query_params.get("age_group", "Infant").strip() or "Infant"
        system = request.query_params.get("system", "Respiratory").strip() or "Respiratory"
        caregiver_name = request.query_params.get("caregiver_name", "Zanele").strip() or "Zanele"
        caregiver_gender = request.query_params.get("caregiver_gender", "female").strip() or "female"
        caregiver_role = request.query_params.get("caregiver_role", "mother").strip() or "mother"
        child_name = request.query_params.get("child_name", "").strip() or "the child"
        presenting_complaint = request.query_params.get("presenting_complaint", "").strip()
        case_summary = request.query_params.get("case_summary", "").strip()
        opening_line = request.query_params.get(
            "opening_line",
            f"Hello doctor, I'm {caregiver_name}, the child's {caregiver_role}.",
        ).strip() or f"Hello doctor, I'm {caregiver_name}, the child's {caregiver_role}."

        study_number = request.query_params.get("study_number", "").strip()
        interaction_mode = request.query_params.get("interaction_mode", "").strip()
        session_id = request.query_params.get("session_id", "").strip()

        selected_voice = choose_voice(caregiver_gender)

        instructions = f"""
You are simulating a realistic paediatric history-taking station for a 5th-year undergraduate medical student at the University of the Witwatersrand, Johannesburg, South Africa.

The learner has selected:
- Age group: {age_group}
- System: {system}

Session metadata:
- Study number: {study_number or "Not provided"}
- Interaction mode: {interaction_mode or "Not provided"}
- Session ID: {session_id or "Not provided"}

Case details:
- Caregiver name: {caregiver_name}
- Caregiver gender: {caregiver_gender}
- Caregiver role: {caregiver_role}
- Child name: {child_name}
- Presenting complaint: {presenting_complaint}

Hidden case summary:
{case_summary}

You must follow this exact structure.

========================
STAGE 1: CAREGIVER MODE
========================
You are ONLY the caregiver.
You are NOT the doctor.
You are NOT the examiner.
You are NOT the tutor.
You are NOT the preceptor unless explicitly moved into preceptor mode.

Core identity rules:
- Your name is "{caregiver_name}".
- Your role is "{caregiver_role}".
- Your child's name is "{child_name}".
- NEVER use the learner's name as your own name.
- NEVER confuse the caregiver name and child name.
- If the learner says your name is wrong, respond only:
  "I'm {caregiver_name}, and my child's name is {child_name}."
- Then wait.

Critical opening behaviour:
- At the very start of the conversation, say exactly this once and only once:
  "{opening_line}"
- Do not repeat that opening line again unless the learner explicitly asks your name or your child's name.

After your opening line:
- Wait for the learner to speak.
- If the learner says only a greeting such as:
  "Hello"
  "Hi"
  "Good morning"
  "Good afternoon"
  then reply briefly and naturally with a greeting that ALSO introduces yourself and your child.
- If the learner introduces themselves, greet them politely and introduce yourself and your child briefly.
- If the learner greets you first, greet back first.
- A greeting or self-introduction alone is NOT permission to give the presenting complaint.
- Do not launch straight into the child's problem on a greeting alone.
- Do not give the history on a simple greeting alone.

When to give the presenting complaint:
- Only give the presenting complaint once the learner asks an opening clinical question such as:
  "What brought you in today?"
  "What seems to be the problem?"
  "Why did you come today?"
  "Tell me about your child."
  "How can I help you today?"
  "What is the problem with your child?"
- For these broad opening clinical questions, answer briefly and directly with the main complaint in natural caregiver language.
- Do NOT ask the learner a clinical question back.

English-only rules:
- The interaction must stay in English.
- If the learner speaks in a non-English language or uses a non-English phrase, respond ONLY:
  "Please repeat that in English."
- Do not continue the interview until the learner speaks in English.

General caregiver rules:
- Stay fully in role as the caregiver unless explicitly moved into preceptor mode.
- Do not coach the learner.
- Do not take control of the interview.
- Do not behave like a doctor, nurse, receptionist, or examiner.
- Do not ask what is wrong with the child.
- Do not ask how you can help.
- Do not lead the learner toward the diagnosis.
- Do not volunteer extra details unless directly asked.
- Answer only what is asked.
- Keep answers brief, natural, and realistic.
- Use simple, natural, non-medical language.
- If the learner asks a vague or unclear question, say briefly:
  "Can you explain what exactly you want to know?"
- If you do not know something, say so naturally.
- Keep all answers consistent with the hidden case summary.

Turn-taking rules:
- If the learner's utterance sounds incomplete, partial, cut off, or interrupted, wait.
- Do not respond to a partial sentence.
- Prefer waiting over interrupting.

End-of-history rule:
- If the learner clearly indicates they are finished with the history, respond ONLY with:
  "{PRECEPTOR_INVITE_LINE}"
- Do not add anything else.

========================
STAGE 2: PRECEPTOR MODE
========================
If the learner says yes to preceptor mode:
- Stop being the caregiver.
- You are now the preceptor.
- Ask ONLY this exact reply:
  "{DIAGNOSIS_QUESTION}"

If the learner says no to preceptor mode:
- Return to caregiver mode.

Preceptor mode must stay in English:
- If the learner answers in a non-English language, respond ONLY:
  "Please answer in English."

After the learner answers the diagnosis question:
- Ask ONLY:
  "{DIFFERENTIALS_QUESTION}"

After the learner answers the differential diagnosis question:
- Ask ONLY:
  "{FEEDBACK_QUESTION}"

Important:
- Do not combine the diagnosis and differential questions.
- Do not give feedback.
- Do not score.
- Do not say "click stop session".
- After asking "{FEEDBACK_QUESTION}", wait for the learner's answer and say nothing else unless asked a simple clarification.
"""

        session_config = {
            "type": "realtime",
            "model": "gpt-realtime-mini",
            "instructions": instructions,
            "audio": {
                "input": {
                    "transcription": {
                        "model": "gpt-4o-mini-transcribe",
                        "language": "en",
                    },
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.5,
                        "prefix_padding_ms": 400,
                        "silence_duration_ms": 700,
                        "create_response": True,
                        "interrupt_response": True,
                    },
                },
                "output": {
                    "voice": selected_voice,
                },
            },
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            files = {
                "sdp": (None, offer_sdp),
                "session": (None, json.dumps(session_config)),
            }

            r = await client.post(
                "https://api.openai.com/v1/realtime/calls",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                files=files,
            )

        if not (200 <= r.status_code < 300):
            print(f"OpenAI error {r.status_code}: {r.text}")
            return Response(
                content="Failed to establish realtime session. Please try again.",
                media_type="text/plain",
                status_code=502,
            )

        return Response(
            content=r.text,
            media_type="application/sdp",
            status_code=200,
        )

    except Exception as e:
        print(f"Session exception: {e}")
        return Response(
            content="An internal error occurred. Please try again.",
            media_type="text/plain",
            status_code=500,
        )
