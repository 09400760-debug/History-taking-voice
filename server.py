from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response, JSONResponse
import httpx
import os
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

app = FastAPI()

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"].strip()
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    or os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
    or os.environ.get("SUPABASE_KEY", "").strip()
)
SUPABASE_TRANSCRIPTS_TABLE = (
    os.environ.get("SUPABASE_TRANSCRIPTS_TABLE", "history_voice_transcripts").strip()
    or "history_voice_transcripts"
)

BASE_DIR = Path(__file__).resolve().parent
INDEX_HTML_PATH = BASE_DIR / "templates" / "index.html"

# Local fallback only. Do not rely on this for durable study data.
TRANSCRIPTS_DIR = BASE_DIR / "transcripts"
TRANSCRIPTS_DIR.mkdir(exist_ok=True)

PRECEPTOR_INVITE_LINE = "Would you like to move to preceptor mode?"
SUMMARY_QUESTION = "Please summarise the case briefly in one or two sentences."
DIAGNOSIS_QUESTION = "What is your most likely diagnosis?"
DIFFERENTIALS_QUESTION = "What are your main differential diagnoses?"
END_CONFIRM_QUESTION = "Are you finished and ready for feedback?"
FINAL_LINE = "Thank you. I will now generate your feedback."

FEMALE_VOICE = "marin"
MALE_VOICE = "cedar"
REALTIME_MODEL = "gpt-realtime-mini"

CUSTOMIZED_GROUP = "customized"
NON_CUSTOMIZED_GROUP = "non_customized"


# =========================
# Helpers
# =========================
def now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_session_id(session_id: str) -> str:
    return "".join(c for c in str(session_id).strip() if c.isalnum() or c in "-_")


def normalize_email(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip().lower()
    return cleaned or None


def parse_iso_datetime(value: Optional[str]):
    if not value:
        return None
    try:
        cleaned = str(value).strip()
        if cleaned.endswith("Z"):
            cleaned = cleaned.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    except Exception:
        return None


def compute_duration_seconds(started_at: Optional[str], ended_at: Optional[str]):
    start_dt = parse_iso_datetime(started_at)
    end_dt = parse_iso_datetime(ended_at)
    if not start_dt or not end_dt:
        return None
    try:
        return max(0, int((end_dt - start_dt).total_seconds()))
    except Exception:
        return None


def choose_voice(caregiver_gender: str, caregiver_role: str) -> str:
    gender = str(caregiver_gender or "").strip().lower()
    role = str(caregiver_role or "").strip().lower()

    if gender == "male":
        return MALE_VOICE
    if gender == "female":
        return FEMALE_VOICE
    if any(word in role for word in ["father", "grandfather", "uncle", "male"]):
        return MALE_VOICE
    return FEMALE_VOICE


def bool_env_ready() -> bool:
    return bool(SUPABASE_URL and SUPABASE_SERVICE_KEY and SUPABASE_TRANSCRIPTS_TABLE)


def default_other_caregiver_role(primary_role: str) -> str:
    role = str(primary_role or "").strip().lower()
    mapping = {
        "mother": "father",
        "father": "mother",
        "grandmother": "mother",
        "grandfather": "father",
        "aunt": "mother",
        "uncle": "father",
    }
    return mapping.get(role, "parent")


async def save_payload_to_supabase(transcript_payload: dict) -> tuple[bool, str]:
    if not bool_env_ready():
        return False, (
            "Supabase env vars missing. Add SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY "
            "(or SUPABASE_SERVICE_KEY) on Render."
        )

    row = {
        "session_id": transcript_payload.get("session_id"),
        "student_email": transcript_payload.get("student_email"),
        "study_number": transcript_payload.get("study_number"),
        "study_group": transcript_payload.get("study_group"),
        "interaction_mode": transcript_payload.get("interaction_mode"),
        "age_group": transcript_payload.get("age_group"),
        "system": transcript_payload.get("system"),
        "caregiver_name": transcript_payload.get("caregiver_name"),
        "caregiver_gender": transcript_payload.get("caregiver_gender"),
        "caregiver_role": transcript_payload.get("caregiver_role"),
        "caregiver_occupation": transcript_payload.get("caregiver_occupation"),
        "other_caregiver_name": transcript_payload.get("other_caregiver_name"),
        "other_caregiver_role": transcript_payload.get("other_caregiver_role"),
        "child_name": transcript_payload.get("child_name"),
        "child_age": transcript_payload.get("child_age"),
        "child_sex": transcript_payload.get("child_sex"),
        "presenting_complaint": transcript_payload.get("presenting_complaint"),
        "case_summary": transcript_payload.get("case_summary"),
        "opening_line": transcript_payload.get("opening_line"),
        "siblings": transcript_payload.get("siblings"),
        "residence": transcript_payload.get("residence"),
        "birth_place": transcript_payload.get("birth_place"),
        "household_structure": transcript_payload.get("household_structure"),
        "school_or_daycare": transcript_payload.get("school_or_daycare"),
        "case_data_json": transcript_payload.get("case_data_json"),
        "started_at": transcript_payload.get("started_at"),
        "ended_at": transcript_payload.get("ended_at"),
        "duration_seconds": transcript_payload.get("duration_seconds"),
        "session_completed": transcript_payload.get("session_completed", False),
        "timeout_reason": transcript_payload.get("timeout_reason"),
        "transcript_lines": transcript_payload.get("transcript_lines", []),
        "transcript_text": transcript_payload.get("transcript_text", ""),
        "saved_at": transcript_payload.get("saved_at"),
        "payload": transcript_payload,
    }

    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/{SUPABASE_TRANSCRIPTS_TABLE}"
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=representation",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, headers=headers, content=json.dumps([row], default=str))

    if 200 <= response.status_code < 300:
        return True, "ok"

    return False, f"Supabase error {response.status_code}: {response.text}"


# =========================
# Prompt builders
# =========================
def build_customized_instructions(
    age_group: str,
    system: str,
    caregiver_name: str,
    caregiver_gender: str,
    caregiver_role: str,
    caregiver_occupation: str,
    other_caregiver_name: str,
    other_caregiver_role: str,
    child_name: str,
    child_age: str,
    child_sex: str,
    presenting_complaint: str,
    case_summary: str,
    opening_line: str,
    siblings: str,
    residence: str,
    birth_place: str,
    household_structure: str,
    school_or_daycare: str,
    study_number: str,
    student_email: str,
    interaction_mode: str,
    session_id: str,
    case_data_json: str,
) -> str:
    if other_caregiver_name:
        other_caregiver_line = (
            f'- The other caregiver is "{other_caregiver_name}", who is the child\'s {other_caregiver_role}.'
        )
    else:
        other_caregiver_line = (
            "- You know the other caregiver's name and role as an ordinary family fact."
        )

    return f"""
You are simulating a realistic paediatric history-taking station for a medical student in South Africa.

This station is for history-taking and diagnostic reasoning only.
It is not a management station.

The learner has selected:
- Age group: {age_group}
- System: {system}

Session metadata:
- Study number: {study_number or "Not provided"}
- Student email: {student_email or "Not provided"}
- Interaction mode: {interaction_mode or "Not provided"}
- Session ID: {session_id or "Not provided"}
- Case data JSON present: {"yes" if case_data_json else "no"}

Known case details:
- Your name is {caregiver_name}
- Your gender is {caregiver_gender}
- Your role is {caregiver_role}
- Your occupation is {caregiver_occupation or "not specified"}
- Your child is {child_name}
- Your child is {child_age} old
- Your child is {child_sex}
- Presenting complaint: {presenting_complaint}
- Siblings: {siblings or "not specified"}
- Residence: {residence or "not specified"}
- Birth place: {birth_place or "not specified"}
- Household structure: {household_structure or "not specified"}
- School/daycare: {school_or_daycare or "not specified"}
{other_caregiver_line}

Hidden clinical picture:
{case_summary}

========================
CAREGIVER MODE
========================
You are ONLY the caregiver.

You are NOT:
- a doctor
- an assistant
- a tutor
- an examiner
- a chatbot
- a facilitator

Identity rules:
- Never confuse your own name with the child's name.
- Never use the learner's name as your own.
- If the learner gets your or the child's name wrong, say only:
  "I'm {caregiver_name}, and my child's name is {child_name}."
- Then stop.

Opening rule:
- At the very start of the conversation, say exactly this once:
  "{opening_line}"
- Say it once only.
- Never repeat the full opening line later unless directly asked who you are.

How to behave:
- Speak like a real parent or caregiver.
- Use simple everyday language.
- Answer only what is asked.
- Keep answers short and natural.
- Stay focused on your child only.

You must NEVER:
- guide the interview
- help the doctor structure the consultation
- suggest what the doctor should do
- give advice such as checking notes, records, or tests
- ask the doctor what they want to know
- ask follow-up symptom questions
- act like a receptionist or assistant

Never say phrases such as:
- "How can I help you?"
- "Please let me know how I can help."
- "What would you like to know?"
- "What would you like to know about her?"
- "Tell me more."
- "Please go ahead."
- "Take your time."
- "Let me know."
- "We can explore that further."
- "Is there anything else you'd like to share?"
If you are about to say one of these, do not say it.

If the learner only greets:
- Reply briefly as a caregiver, for example "Hello doctor." or "Good evening, doctor."
- Do not reveal the complaint yet.

Only reveal the presenting complaint when the learner asks why you came, what the problem is, or asks a broad opening clinical question.

Family and social knowledge:
- You know ordinary family facts.
- You know the other caregiver's name.
- You know who lives at home.
- You know siblings, occupation, residence, birth place, and school/daycare details if those are part of ordinary family knowledge.
- Never say:
  "I don't have that information."
  "I haven't mentioned that before."
  "I do not have that detail right now."
- If asked about the other caregiver, answer naturally and confidently.

Handling strange or irrelevant questions:
- If a question is strange, irrelevant, nonsensical, or clearly not about your child, say briefly:
  "I'm not sure how that relates to my child."
- Do not try to answer bizarre questions as if they are valid.
- Do not invent meaning for nonsense questions.

Handling unclear questions:
- Only say "Can you explain what exactly you want to know?" if the question is truly incomprehensible.
- If the question is understandable, answer it.

Consistency rules:
- Keep all answers consistent with the hidden clinical picture and the known facts above.
- Never give two different answers to the same question.
- Never restart an answer halfway and change it.
- Speak only once per learner turn.
- Never produce more than one answer for one learner turn.
- If the learner's utterance sounds incomplete, partial, interrupted, or cut off, wait rather than responding.

End-of-history rule:
- Only say "{PRECEPTOR_INVITE_LINE}" if the learner clearly indicates they are finished with the history.
- Do not offer preceptor mode unless the learner clearly signals that they are done.

========================
PRECEPTOR MODE
========================
Only enter preceptor mode if the learner clearly says yes to preceptor mode.

Once preceptor mode starts:
- Stop being the caregiver.
- Become the preceptor.
- Keep replies short and exact.
- Do not add filler or encouragement.

Preceptor flow:
1. If learner clearly says yes to preceptor mode:
   reply ONLY:
   "{SUMMARY_QUESTION}"

2. After a clear one- or two-sentence summary:
   reply ONLY:
   "{DIAGNOSIS_QUESTION}"

3. If the summary is unclear:
   reply ONLY:
   "Please provide a clear one- or two-sentence summary before we continue."

4. After a clear most likely diagnosis:
   reply ONLY:
   "{DIFFERENTIALS_QUESTION}"

5. If the diagnosis is unclear:
   reply ONLY:
   "Please state your single most likely diagnosis."

6. After clear differentials:
   reply ONLY:
   "{END_CONFIRM_QUESTION}"

7. If the differentials are unclear:
   reply ONLY:
   "Please list your main differential diagnoses."

8. For final confirmation:
   - If yes, reply ONLY:
     "{FINAL_LINE}"
   - If no, reply ONLY:
     "{DIFFERENTIALS_QUESTION}"
   - If unclear, reply ONLY:
     "Please answer yes or no."

If the learner says no to preceptor mode before preceptor mode has started:
- Return to caregiver mode.
""".strip()


def build_non_customized_instructions(
    age_group: str,
    system: str,
    caregiver_name: str,
    caregiver_gender: str,
    caregiver_role: str,
    caregiver_occupation: str,
    other_caregiver_name: str,
    other_caregiver_role: str,
    child_name: str,
    child_age: str,
    child_sex: str,
    presenting_complaint: str,
    case_summary: str,
    opening_line: str,
    siblings: str,
    residence: str,
    birth_place: str,
    household_structure: str,
    school_or_daycare: str,
    study_number: str,
    student_email: str,
    interaction_mode: str,
    session_id: str,
) -> str:
    if other_caregiver_name:
        other_caregiver_line = (
            f'- The other caregiver is "{other_caregiver_name}", who is the child\'s {other_caregiver_role}.'
        )
    else:
        other_caregiver_line = (
            "- You know the other caregiver's name and role as an ordinary family fact."
        )

    return f"""
You are role-playing a realistic caregiver in a paediatric history-taking conversation with a medical student.

This is the standard non-customized condition.
Remain the caregiver throughout.

The learner has selected:
- Age group: {age_group}
- System: {system}

Session metadata:
- Study number: {study_number or "Not provided"}
- Student email: {student_email or "Not provided"}
- Interaction mode: {interaction_mode or "Not provided"}
- Session ID: {session_id or "Not provided"}

Known case details:
- Your name is {caregiver_name}
- Your role is {caregiver_role}
- Your occupation is {caregiver_occupation or "not specified"}
- Your child is {child_name}
- Your child is {child_age} old
- Your child is {child_sex}
- Presenting complaint: {presenting_complaint}
- Siblings: {siblings or "not specified"}
- Residence: {residence or "not specified"}
- Birth place: {birth_place or "not specified"}
- Household structure: {household_structure or "not specified"}
- School/daycare: {school_or_daycare or "not specified"}
{other_caregiver_line}

Hidden clinical picture:
{case_summary}

Rules:
- Stay in caregiver role only.
- At the very start, say exactly this once:
  "{opening_line}"
- Do not repeat the full opening line later unless directly asked who you are.
- On a simple greeting, greet back briefly and do not reveal the complaint yet.
- Speak like a real parent or caregiver.
- Use simple everyday language only.
- Answer only what is asked.
- Keep answers short and natural.
- Never behave like an assistant, chatbot, tutor, or facilitator.
- Never guide the interview.
- Never ask the learner what they want to know.
- Never ask doctor-style follow-up questions.
- Never give advice.
- Never say:
  "How can I help you?"
  "Please let me know how I can help."
  "What would you like to know?"
  "Tell me more."
  "Please go ahead."
  "Take your time."
  "Let me know."
  "Is there anything else you'd like to share?"
- Only reveal the presenting complaint when the learner asks why you came or asks a broad opening clinical question.
- You know ordinary family facts, including the other caregiver's name.
- Never say:
  "I don't have that information."
  "I haven't mentioned that before."
  "I do not have that detail right now."
- If a question is strange or irrelevant, say briefly:
  "I'm not sure how that relates to my child."
- Only say "Can you explain what exactly you want to know?" if the question is truly incomprehensible.
- Keep answers consistent with the hidden clinical picture and the known facts above.
- Never give two different answers to the same question.
- Speak only once per learner turn.
- If the learner's utterance sounds partial or interrupted, wait.
- Do not mention preceptor mode, diagnosis, scoring, or feedback.
""".strip()


# =========================
# Routes
# =========================
@app.get("/", response_class=HTMLResponse)
async def home():
    try:
        html = INDEX_HTML_PATH.read_text(encoding="utf-8")
        return HTMLResponse(content=html, status_code=200)
    except Exception as e:
        return HTMLResponse(content=f"Could not load index.html. Detail: {str(e)}", status_code=500)


@app.head("/")
async def home_head():
    return Response(status_code=200)


@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)


@app.post("/save_transcript")
async def save_transcript(request: Request):
    try:
        body = await request.json()

        session_id = str(body.get("session_id", "")).strip()
        safe_id = safe_session_id(session_id)

        if not safe_id:
            return JSONResponse({"status": "error", "message": "Missing session_id"}, status_code=400)

        transcript_file = TRANSCRIPTS_DIR / f"transcript_{safe_id}.json"

        started_at = body.get("started_at")
        ended_at = body.get("ended_at") or now_iso_utc()
        duration_seconds = body.get("duration_seconds")

        if duration_seconds is None:
            duration_seconds = compute_duration_seconds(started_at, ended_at)

        transcript_payload = {
            "session_id": safe_id,
            "student_email": normalize_email(body.get("student_email")),
            "study_number": body.get("study_number"),
            "study_group": body.get("study_group"),
            "interaction_mode": body.get("interaction_mode"),
            "age_group": body.get("age_group"),
            "system": body.get("system"),
            "caregiver_name": body.get("caregiver_name"),
            "caregiver_gender": body.get("caregiver_gender"),
            "caregiver_role": body.get("caregiver_role"),
            "caregiver_occupation": body.get("caregiver_occupation"),
            "other_caregiver_name": body.get("other_caregiver_name"),
            "other_caregiver_role": body.get("other_caregiver_role"),
            "child_name": body.get("child_name"),
            "child_age": body.get("child_age"),
            "child_sex": body.get("child_sex"),
            "presenting_complaint": body.get("presenting_complaint"),
            "case_summary": body.get("case_summary"),
            "opening_line": body.get("opening_line"),
            "siblings": body.get("siblings"),
            "residence": body.get("residence"),
            "birth_place": body.get("birth_place"),
            "household_structure": body.get("household_structure"),
            "school_or_daycare": body.get("school_or_daycare"),
            "case_data_json": body.get("case_data_json"),
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_seconds": duration_seconds,
            "session_completed": body.get("session_completed", False),
            "timeout_reason": body.get("timeout_reason"),
            "transcript_lines": body.get("transcript_lines", []),
            "transcript_text": body.get("transcript_text", ""),
            "saved_at": now_iso_utc(),
        }

        supabase_ok, supabase_message = await save_payload_to_supabase(transcript_payload)

        local_saved = False
        local_error = None
        try:
            with open(transcript_file, "w", encoding="utf-8") as f:
                json.dump(transcript_payload, f, ensure_ascii=False, indent=2)
            local_saved = True
        except Exception as e:
            local_error = str(e)
            print(f"Local transcript save error: {e}")

        if supabase_ok:
            return JSONResponse(
                {
                    "status": "ok",
                    "session_id": safe_id,
                    "saved_to_supabase": True,
                    "saved_to_local": local_saved,
                    "local_file": str(transcript_file) if local_saved else None,
                    "supabase_table": SUPABASE_TRANSCRIPTS_TABLE,
                }
            )

        return JSONResponse(
            {
                "status": "warning",
                "session_id": safe_id,
                "saved_to_supabase": False,
                "supabase_error": supabase_message,
                "saved_to_local": local_saved,
                "local_file": str(transcript_file) if local_saved else None,
                "local_error": local_error,
            },
            status_code=207 if local_saved else 500,
        )

    except Exception as e:
        print(f"save_transcript error: {e}")
        return JSONResponse({"status": "error", "message": "Could not save transcript"}, status_code=500)


@app.get("/latest_transcript")
async def latest_transcript(session_id: Optional[str] = None):
    try:
        if not session_id:
            return JSONResponse({"status": "error", "message": "session_id is required"}, status_code=400)

        safe_id = safe_session_id(session_id)

        if bool_env_ready():
            url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/{SUPABASE_TRANSCRIPTS_TABLE}"
            headers = {
                "apikey": SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                "Accept": "application/json",
            }
            params = {
                "select": "payload",
                "session_id": f"eq.{safe_id}",
                "limit": "1",
            }
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(url, headers=headers, params=params)

            if 200 <= response.status_code < 300:
                rows = response.json()
                if rows:
                    payload = rows[0].get("payload") or {}
                    return JSONResponse({"status": "ok", "data": payload})

        transcript_file = TRANSCRIPTS_DIR / f"transcript_{safe_id}.json"
        if not transcript_file.exists():
            return JSONResponse({"status": "missing"}, status_code=404)

        with open(transcript_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return JSONResponse({"status": "ok", "data": data})

    except Exception as e:
        print(f"latest_transcript error: {e}")
        return JSONResponse({"status": "error", "message": "Could not load transcript"}, status_code=500)


@app.post("/session")
async def create_session(request: Request):
    try:
        offer_sdp = (await request.body()).decode("utf-8")
        qp = request.query_params

        age_group = qp.get("age_group", "Infant").strip() or "Infant"
        system = qp.get("system", "Respiratory").strip() or "Respiratory"
        caregiver_name = qp.get("caregiver_name", "Zanele").strip() or "Zanele"
        caregiver_gender = qp.get("caregiver_gender", "female").strip() or "female"
        caregiver_role = qp.get("caregiver_role", "mother").strip() or "mother"
        caregiver_occupation = qp.get("caregiver_occupation", "").strip()
        child_name = qp.get("child_name", "").strip() or "the child"
        child_age = qp.get("child_age", "").strip() or "3 years"
        child_sex = qp.get("child_sex", "").strip() or "male"
        presenting_complaint = qp.get("presenting_complaint", "").strip()
        case_summary = qp.get("case_summary", "").strip()
        opening_line = qp.get(
            "opening_line",
            f"Hello doctor, I'm {caregiver_name}, {child_name}'s {caregiver_role}. This is {child_name}, my {child_age} old {'son' if child_sex == 'male' else 'daughter'}.",
        ).strip() or f"Hello doctor, I'm {caregiver_name}, {child_name}'s {caregiver_role}. This is {child_name}, my {child_age} old {'son' if child_sex == 'male' else 'daughter'}."

        siblings = qp.get("siblings", "").strip()
        residence = qp.get("residence", "").strip()
        birth_place = qp.get("birth_place", "").strip()
        household_structure = qp.get("household_structure", "").strip()
        school_or_daycare = qp.get("school_or_daycare", "").strip()

        other_caregiver_name = qp.get("other_caregiver_name", "").strip()
        other_caregiver_role = qp.get("other_caregiver_role", "").strip() or default_other_caregiver_role(caregiver_role)

        study_number = qp.get("study_number", "").strip()
        student_email = normalize_email(qp.get("student_email", ""))
        interaction_mode = qp.get("interaction_mode", "").strip()
        session_id = qp.get("session_id", "").strip()
        case_data_json = qp.get("case_data_json", "").strip()
        study_group = qp.get("study_group", CUSTOMIZED_GROUP).strip() or CUSTOMIZED_GROUP

        selected_voice = choose_voice(caregiver_gender, caregiver_role)

        if study_group == NON_CUSTOMIZED_GROUP:
            instructions = build_non_customized_instructions(
                age_group,
                system,
                caregiver_name,
                caregiver_gender,
                caregiver_role,
                caregiver_occupation,
                other_caregiver_name,
                other_caregiver_role,
                child_name,
                child_age,
                child_sex,
                presenting_complaint,
                case_summary,
                opening_line,
                siblings,
                residence,
                birth_place,
                household_structure,
                school_or_daycare,
                study_number,
                student_email or "",
                interaction_mode,
                session_id,
            )
        else:
            instructions = build_customized_instructions(
                age_group,
                system,
                caregiver_name,
                caregiver_gender,
                caregiver_role,
                caregiver_occupation,
                other_caregiver_name,
                other_caregiver_role,
                child_name,
                child_age,
                child_sex,
                presenting_complaint,
                case_summary,
                opening_line,
                siblings,
                residence,
                birth_place,
                household_structure,
                school_or_daycare,
                study_number,
                student_email or "",
                interaction_mode,
                session_id,
                case_data_json,
            )

        session_config = {
            "type": "realtime",
            "model": REALTIME_MODEL,
            "instructions": instructions,
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
                "session": (None, json.dumps(session_config, default=str)),
            }

            r = await client.post(
                "https://api.openai.com/v1/realtime/calls",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                files=files,
            )

        if not (200 <= r.status_code < 300):
            print(f"OpenAI error {r.status_code}: {r.text}")
            return Response(
                content=f"Failed to establish realtime session. Detail: {r.text}",
                media_type="text/plain",
                status_code=502,
            )

        return Response(content=r.text, media_type="application/sdp", status_code=200)

    except Exception as e:
        print(f"Session exception: {e}")
        return Response(
            content=f"An internal error occurred. Please try again. Detail: {str(e)}",
            media_type="text/plain",
            status_code=500,
        )







