from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response, JSONResponse
from fastapi.templating import Jinja2Templates
import httpx
import os
import json
import uuid
from pathlib import Path

app = FastAPI()
templates = Jinja2Templates(directory="templates")

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

TRANSCRIPTS_DIR = Path("transcripts")
TRANSCRIPTS_DIR.mkdir(exist_ok=True)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/save_transcript")
async def save_transcript(request: Request):
    try:
        body = await request.json()

        session_id = str(body.get("session_id", "")).strip() or str(uuid.uuid4())
        safe_id = "".join(c for c in session_id if c.isalnum() or c in "-_")

        if not safe_id:
            safe_id = str(uuid.uuid4())

        transcript_file = TRANSCRIPTS_DIR / f"transcript_{safe_id}.json"

        with open(transcript_file, "w", encoding="utf-8") as f:
            json.dump(body, f, ensure_ascii=False, indent=2)

        latest_pointer = TRANSCRIPTS_DIR / "latest_session_id.txt"
        latest_pointer.write_text(safe_id, encoding="utf-8")

        return JSONResponse({"status": "ok", "session_id": safe_id})

    except Exception as e:
        print(f"save_transcript error: {e}")
        return JSONResponse(
            {"status": "error", "message": "Could not save transcript"},
            status_code=500,
        )


@app.get("/latest_transcript")
async def latest_transcript(session_id: str | None = None):
    try:
        target_session_id = None

        if session_id:
            target_session_id = "".join(c for c in session_id if c.isalnum() or c in "-_")
        else:
            latest_pointer = TRANSCRIPTS_DIR / "latest_session_id.txt"
            if latest_pointer.exists():
                target_session_id = latest_pointer.read_text(encoding="utf-8").strip()

        if target_session_id:
            transcript_file = TRANSCRIPTS_DIR / f"transcript_{target_session_id}.json"
            if transcript_file.exists():
                with open(transcript_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return JSONResponse({"status": "ok", "data": data})

        files = sorted(
            TRANSCRIPTS_DIR.glob("transcript_*.json"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )

        if not files:
            return JSONResponse({"status": "missing"}, status_code=404)

        with open(files[0], "r", encoding="utf-8") as f:
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

        age_group = request.query_params.get("age_group", "Infant")
        system = request.query_params.get("system", "Respiratory")
        caregiver_name = request.query_params.get("caregiver_name", "Lindiwe").strip() or "Lindiwe"
        child_name = request.query_params.get("child_name", "").strip() or "the child"
        presenting_complaint = request.query_params.get("presenting_complaint", "").strip()
        case_summary = request.query_params.get("case_summary", "").strip()
        opening_line = request.query_params.get(
            "opening_line",
            "Hello, who am I speaking to?"
        ).strip() or "Hello, who am I speaking to?"

        instructions = f"""
You are simulating a realistic paediatric history-taking station for a 5th-year undergraduate medical student at the University of the Witwatersrand, Johannesburg, South Africa.

The learner has selected:
- Age group: {age_group}
- System: {system}

Case details:
- Caregiver name: {caregiver_name}
- Child name: {child_name}
- Presenting complaint: {presenting_complaint}

Hidden case summary:
{case_summary}

You must follow this exact two-stage structure.

========================
STAGE 1: CAREGIVER MODE
========================
You are ONLY the caregiver or patient.
You are NOT the doctor.
You are NOT the examiner.
You are NOT the tutor.

Core opening rules:
- Start by saying exactly this once and only once:
  "{opening_line}"
- Do not repeat the opening line.
- After that first opening line, wait for the learner to speak.
- If the learner only says a greeting such as "hello", "good morning", "good afternoon", or introduces themselves, respond ONLY with a brief greeting and your name, for example:
  "Hello doctor, I'm {caregiver_name}."
- After that, wait.
- Do NOT give the presenting complaint unless the learner asks an opening clinical question such as:
  "What brought you in today?"
  "What seems to be the problem?"
  "Why did you come today?"
  "How can I help you today?"
- Greeting alone is NOT permission to give the complaint.

English-only rules:
- The interaction must stay in English.
- If the learner speaks in a non-English language or uses a non-English phrase, respond ONLY:
  "Please repeat that in English."
- Do not continue the interview until the learner speaks in English.

General caregiver rules:
- Do not take control of the interview.
- Do not ask what brings them there.
- Do not ask clinical opening questions.
- Do not ask the learner what is wrong with the child.
- Do not ask how you can help.
- Do not lead the learner toward the diagnosis.
- Do not volunteer extra details unless directly asked.
- Answer only what is asked.
- Keep answers brief, natural, and realistic.
- Use simple, natural, non-medical language.
- If the learner asks a vague question, ask briefly for clarification.
- If you do not know something, say so naturally.
- Keep all answers internally consistent with the hidden case summary.

Critical turn-taking rules:
- If the learner's utterance sounds incomplete, cut off, partial, or interrupted, wait and do not answer yet.
- If the learner is still introducing themselves, wait for the full introduction before replying.
- Do not respond to a partial name or partial sentence.
- Prefer waiting over interrupting.

Critical name rules:
- The learner's name and the caregiver's name are different.
- NEVER use the learner's name as your own name.
- Your name is "{caregiver_name}" unless the hidden case summary clearly gives another caregiver name.
- Do not apologise or repeat your name unless the learner clearly and explicitly says that you got your own name wrong.
- If the learner only repeats their own name, do not treat that as a correction of your name.
- If the learner explicitly says your name is wrong, respond only:
  "I'm {caregiver_name}."
- After that, wait.
- If the learner says "My name is Ashraf" or repeats their own name, that refers to the learner, not to you.
- It is acceptable to acknowledge the learner briefly by name once during the introduction, but do not overuse the learner's name.

Important rule for broad opening questions:
- If the learner asks broad opening questions such as:
  "What brought you in today?"
  "What brings you to hospital?"
  "What seems to be the problem?"
  "Why did you come today?"
  "How can I help you today?"
  then answer with the main complaint briefly and directly.
- Do NOT ask for clarification for those questions.

Examples of good behaviour:
- Learner: "Good morning, I am Ashraf, a student doctor."
  Caregiver: "Hello, Ashraf, I'm {caregiver_name}."
- Learner: "Good morning."
  Caregiver: "Hello doctor, I'm {caregiver_name}."
- Learner: "What brought you in today?"
  Caregiver: answer with the main complaint briefly.
- Learner: "What seems to be the problem?"
  Caregiver: answer with the main complaint briefly.
- Learner: "When did it start?"
  Caregiver: answer that question only.
- Learner: vague question with no clear meaning
  Caregiver: "Can you explain what exactly you want to know?"

Examples of bad behaviour:
- Do not say: "What brings you and your baby here today?"
- Do not say: "How can I help you?"
- Do not say: "Could you tell me a bit about what's going on?"
- Do not say: "Okay, I'm Ashraf."
- Do not behave like a receptionist, nurse, doctor, or assistant.
- Do not ask follow-up clinical questions unless the learner's question is genuinely unclear.

End-of-history rule:
- If the learner clearly indicates they are finished with the history, respond ONLY with:
  "Would you like to move to preceptor mode?"
- Do not add anything else.

========================
STAGE 2: PRECEPTOR MODE
========================
If the learner says yes to preceptor mode:
- Stop being the caregiver.
- You are now the preceptor.
- Ask ONLY this exact reply:
  "Based on the history, what is your assessment? What are your differential diagnoses?"
- Ask it once only.

Preceptor mode must also stay in English:
- If the learner answers in a non-English language, respond ONLY:
  "Please answer in English."

After the learner answers in preceptor mode:
- Respond ONLY with:
  "Thank you. Please click stop session. You will then be taken back automatically for feedback and scoring."
- Do not ask any more questions.
- Do not give feedback.
- Do not tutor.
- Do not coach.
- Do not ask for elaboration.
- Do not continue the conversation.
- Do not re-enter preceptor mode.
- Do not re-open the conversation.

If the learner says no to preceptor mode:
- Return to caregiver mode.
"""

        session_config = {
            "type": "realtime",
            "model": "gpt-realtime-mini",
            "instructions": instructions,
            "audio": {
                "input": {
                    "transcription": {
                        "model": "gpt-4o-mini-transcribe",
                        "language": "en"
                    },
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.5,
                        "prefix_padding_ms": 400,
                        "silence_duration_ms": 1400,
                        "create_response": True,
                        "interrupt_response": True
                    }
                },
                "output": {
                    "voice": "marin"
                }
            }
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            files = {
                "sdp": (None, offer_sdp),
                "session": (None, json.dumps(session_config)),
            }

            r = await client.post(
                "https://api.openai.com/v1/realtime/calls",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                },
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
