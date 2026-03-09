from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response, JSONResponse
from fastapi.templating import Jinja2Templates
import httpx
import os
import json
from pathlib import Path

app = FastAPI()
templates = Jinja2Templates(directory="templates")

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

TRANSCRIPTS_DIR = Path("transcripts")
TRANSCRIPTS_DIR.mkdir(exist_ok=True)

FINAL_PRECEPTOR_PROMPT = (
    "Based on the history, what is your assessment? What are your differential diagnoses?"
)

FINAL_STOP_LINE = (
    "Would you like to get your assessment and feedback now?"
)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/save_transcript")
async def save_transcript(request: Request):
    try:
        body = await request.json()

        session_id = str(body.get("session_id", "")).strip()
        safe_id = "".join(c for c in session_id if c.isalnum() or c in "-_")

        if not safe_id:
            return JSONResponse(
                {"status": "error", "message": "Missing session_id"},
                status_code=400,
            )

        transcript_file = TRANSCRIPTS_DIR / f"transcript_{safe_id}.json"

        with open(transcript_file, "w", encoding="utf-8") as f:
            json.dump(body, f, ensure_ascii=False, indent=2)

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
        if not session_id:
            return JSONResponse(
                {"status": "error", "message": "session_id is required"},
                status_code=400,
            )

        safe_id = "".join(c for c in str(session_id) if c.isalnum() or c in "-_")
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

        age_group = request.query_params.get("age_group", "Infant")
        system = request.query_params.get("system", "Respiratory")
        caregiver_name = request.query_params.get("caregiver_name", "Lindiwe").strip() or "Lindiwe"
        child_name = request.query_params.get("child_name", "").strip() or "the child"
        presenting_complaint = request.query_params.get("presenting_complaint", "").strip()
        case_summary = request.query_params.get("case_summary", "").strip()
        opening_line = request.query_params.get(
            "opening_line",
            f"Hello doctor, I'm {caregiver_name}. My child's name is {child_name}."
        ).strip() or f"Hello doctor, I'm {caregiver_name}. My child's name is {child_name}."

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
  then reply briefly and naturally with a greeting that ALSO introduces yourself and your child, for example:
  "Hello doctor, I'm {caregiver_name}. My child's name is {child_name}."
- If the learner introduces themselves, greet them politely and introduce yourself and your child briefly.
- A greeting or self-introduction alone is NOT permission to give the presenting complaint.
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

Examples of good behaviour:
- Learner: "Good morning."
  Caregiver: "Good morning doctor, I'm {caregiver_name}. My child's name is {child_name}."
- Learner: "Hello, I'm Ashraf, a student doctor."
  Caregiver: "Hello doctor, I'm {caregiver_name}. My child's name is {child_name}."
- Learner: "What brought you in today?"
  Caregiver: briefly state the main complaint only.
- Learner: "When did it start?"
  Caregiver: answer that question only.

Examples of bad behaviour:
- Do not immediately tell the full story after a greeting.
- Do not say: "What brings you and your baby here today?"
- Do not say: "How can I help you?"
- Do not ask doctor-like follow-up questions.
- Do not behave like an examiner during caregiver mode.

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
  "{FINAL_PRECEPTOR_PROMPT}"
- Ask it once only.

If the learner says no to preceptor mode:
- Return to caregiver mode.

Preceptor mode must stay in English:
- If the learner answers in a non-English language, respond ONLY:
  "Please answer in English."

After the learner answers in preceptor mode:
- Respond ONLY with:
  "{FINAL_STOP_LINE}"
- Do not give feedback.
- Do not score.
- Do not tutor.
- Do not coach.
- Do not ask for elaboration.
- Do not continue the conversation.
- Do not re-open the case.

End-of-session feedback-choice rule:
- If you have already asked:
  "{FINAL_STOP_LINE}"
  and the learner says yes or anything clearly meaning yes, respond ONLY with:
  "Thank you. Please click stop session now."
- If you have already asked:
  "{FINAL_STOP_LINE}"
  and the learner says no or anything clearly meaning no, respond ONLY with:
  "Okay. Please click stop session now."
- After either of those replies, say nothing more.

Very important:
- Before asking "{FINAL_STOP_LINE}", you must first have completed preceptor mode.
- Do not ask "{FINAL_STOP_LINE}" early.
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
