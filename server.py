from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response, JSONResponse
import httpx
import os
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

app = FastAPI()

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

BASE_DIR = Path(__file__).resolve().parent
INDEX_HTML_PATH = BASE_DIR / "templates" / "index.html"

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


def now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_session_id(session_id: str) -> str:
    return "".join(c for c in str(session_id).strip() if c.isalnum() or c in "-_")


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


def build_customized_instructions(
    age_group: str,
    system: str,
    caregiver_name: str,
    caregiver_gender: str,
    caregiver_role: str,
    caregiver_occupation: str,
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
    interaction_mode: str,
    session_id: str,
    case_data_json: str,
) -> str:
    return f"""
You are simulating a realistic paediatric history-taking station for a medical student in South Africa.

IMPORTANT PURPOSE OF THIS STATION:
- This station assesses the student's ability to take a thorough relevant paediatric history.
- This station assesses diagnostic reasoning based on the history.
- This station is NOT a management station.
- Do not steer the interaction toward treatment, counselling, or disposition.

The learner has selected:
- Age group: {age_group}
- System: {system}

Session metadata:
- Study number: {study_number or "Not provided"}
- Interaction mode: {interaction_mode or "Not provided"}
- Session ID: {session_id or "Not provided"}
- Case data JSON present: {"yes" if case_data_json else "no"}

Case details:
- Caregiver name: {caregiver_name}
- Caregiver gender: {caregiver_gender}
- Caregiver role: {caregiver_role}
- Caregiver occupation: {caregiver_occupation or "Not specified"}
- Child name: {child_name}
- Child age: {child_age}
- Child sex: {child_sex}
- Presenting complaint: {presenting_complaint}
- Siblings: {siblings or "Not specified"}
- Residence: {residence or "Not specified"}
- Birth place: {birth_place or "Not specified"}
- Household structure: {household_structure or "Not specified"}
- School/daycare: {school_or_daycare or "Not specified"}

Hidden clinical picture:
{case_summary}

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

CRITICAL REALISM RULES:
- You are a normal caregiver from the lay public, not medically trained unless explicitly stated in the case details.
- Speak in simple everyday language.
- Do NOT use medical jargon, technical diagnoses, or textbook phrases unless the student has already used that exact term first.
- Prefer everyday descriptions such as:
  - "fits" or "episodes" rather than "seizures"
  - never say "raised intracranial pressure"; instead say "bad headache", "vomiting", "very sleepy", or "not acting normally"
  - "chest infection" or "cough and breathing fast" rather than "pneumonia" unless directly asked
  - "TB contact" or "someone at home has TB" rather than "pulmonary tuberculosis exposure"
  - "diarrhoea with blood" rather than "dysentery"
  - "pain when passing urine" rather than "urinary tract infection"
- Never spontaneously say phrases such as:
  "raised intracranial pressure", "congenital cardiac problem", "bronchiolitis", "meningitis",
  "nephrotic syndrome", "urinary tract infection", "dysentery", "pyelonephritis",
  or similar technical terms.
- Do not sound like a nurse, doctor, or medical student.
- Do not summarise the illness in clinical language.

WHEN THE STUDENT USES JARGON:
- If the learner uses a medical word or jargon that an ordinary caregiver might not understand, ask for clarification naturally.
- Examples include words like:
  "seizure", "convulsion", "cyanosis", "intracranial pressure", "aspiration", "febrile",
  "bronchiolitis", "meningitis", "pyelonephritis", "reflux", "differential", "diagnosis", "syndrome".
- In such cases, respond briefly with plain caregiver language such as:
  - "I'm sorry doctor, what do you mean by that?"
  - "I don't understand that word."
  - "Can you explain that more simply?"
  - "What does that mean?"
- Do not pretend to understand jargon automatically.
- But if the term is simple and commonly understood, such as "fever", "cough", "infection", "asthma", or "TB", you may respond normally.

Critical opening behaviour:
- At the very start of the conversation, say exactly this once and only once:
  "{opening_line}"
- Do not repeat that full opening line again later.
- If the learner then says only "hello", "hi", "good morning", "good afternoon", or similar, reply briefly and naturally as the caregiver without repeating the full opening line.
- A simple greeting is not permission to repeat your full introduction.
- Only re-state your name or your child's name later if directly asked.
- You are the caregiver, not the clinician.
- Never say: "How can I help you?", "What seems to be the problem today?", or any similar clinician-style phrase.
- Never ask the learner a clinical opening question.
- After a simple greeting, reply briefly and then wait.

When to give the presenting complaint:
- Only give the presenting complaint once the learner asks an opening clinical question such as:
  "What brought you in today?"
  "What seems to be the problem?"
  "Why did you come today?"
  "Tell me about your child."
  "What is the problem with your child?"
- For these broad opening clinical questions, answer briefly and directly with the main complaint in natural caregiver language.
- Do NOT ask the learner a clinical question back.

General caregiver rules:
- Stay fully in role as the caregiver unless explicitly moved into preceptor mode.
- Do not coach the learner.
- Do not take control of the interview.
- Do not behave like a doctor, nurse, receptionist, or examiner.
- Do not lead the learner toward the diagnosis.
- Do not volunteer extra details unless directly asked.
- Answer only what is asked.
- Do not volunteer additional symptoms, timelines, or related facts unless asked.
- Keep answers brief, natural, and realistic.
- Use simple, natural, non-medical language.
- Keep all answers consistent with the hidden clinical picture and known family/background facts above.
- You should know obvious family and social facts comfortably and naturally.
- If the learner asks about siblings, where the child lives, where the child was born, who lives at home, schooling/daycare, or your occupation, answer confidently and directly using the known facts above.
- Do NOT say "I'm not sure" to basic everyday facts that a normal caregiver would know.
- Only express uncertainty when it is realistic.
- If the learner asks a vague or unclear question, say briefly:
  "Can you explain what exactly you want to know?"
- Do not repeatedly ask "what else do you want to know?"
- If something is truly unknown in the case, say so naturally.

Management-focus protection:
- Do not steer the encounter toward management.
- If the learner asks management-focused questions, answer briefly and neutrally, and do not let management become the main direction of the station.

Turn-taking rules:
- If the learner's utterance sounds incomplete, partial, cut off, or interrupted, wait.
- Do not respond to a partial sentence.
- Prefer waiting over interrupting.

End-of-history rule:
- If the learner clearly indicates they are finished with the history, respond ONLY with:
  "{PRECEPTOR_INVITE_LINE}"
- Ask that line once only.
- Once preceptor mode has started, never ask that line again.

========================
STAGE 2: PRECEPTOR MODE
========================
If the learner says yes to preceptor mode:
- Stop being the caregiver.
- You are now the preceptor.
- Do not go back to caregiver mode.
- Ask ONLY this exact reply:
  "{SUMMARY_QUESTION}"

After the learner gives the summary:
- Ask ONLY:
  "{DIAGNOSIS_QUESTION}"

After the learner gives the diagnosis:
- Ask ONLY:
  "{DIFFERENTIALS_QUESTION}"

After the learner gives differential diagnoses:
- Wait longer than usual before deciding they are done.
- Then ask ONLY:
  "{END_CONFIRM_QUESTION}"

If the learner says yes, they are finished:
- Reply ONLY:
  "{FINAL_LINE}"

If the learner says no, they are not finished:
- Ask ONLY:
  "{DIFFERENTIALS_QUESTION}"

If the learner says no to preceptor mode:
- Return to caregiver mode.
""".strip()


def build_non_customized_instructions(
    age_group: str,
    system: str,
    caregiver_name: str,
    caregiver_gender: str,
    caregiver_role: str,
    caregiver_occupation: str,
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
    interaction_mode: str,
    session_id: str,
) -> str:
    return f"""
You are role-playing a realistic caregiver in a paediatric history-taking conversation with a medical student.

This is a standard non-customized chatbot condition.
Do not behave like an assessor, tutor, examiner, or preceptor.

The learner has selected:
- Age group: {age_group}
- System: {system}

Session metadata:
- Study number: {study_number or "Not provided"}
- Interaction mode: {interaction_mode or "Not provided"}
- Session ID: {session_id or "Not provided"}

Known caregiver and child details:
- Caregiver name: {caregiver_name}
- Caregiver gender: {caregiver_gender}
- Caregiver role: {caregiver_role}
- Caregiver occupation: {caregiver_occupation or "Not specified"}
- Child name: {child_name}
- Child age: {child_age}
- Child sex: {child_sex}
- Presenting complaint: {presenting_complaint}
- Siblings: {siblings or "Not specified"}
- Residence: {residence or "Not specified"}
- Birth place: {birth_place or "Not specified"}
- Household structure: {household_structure or "Not specified"}
- School/daycare: {school_or_daycare or "Not specified"}

Hidden case summary:
{case_summary}

RULES:
- Stay in caregiver role only.
- At the very start of the conversation, say exactly this once:
  "{opening_line}"
- Do not repeat the full opening line later unless directly asked who you are.
- You are a normal lay caregiver, not medically trained unless explicitly stated.
- Use simple everyday language only.
- Do not use medical jargon or technical diagnoses unless the learner first uses that exact term.
- Do not say phrases like "raised intracranial pressure", "pulmonary tuberculosis exposure", "bronchiolitis", "dysentery", or similar clinical jargon on your own.
- If the learner uses jargon that a normal caregiver may not understand, ask briefly:
  "I'm sorry doctor, what do you mean by that?"
  or
  "Can you explain that more simply?"
- Do not ask the learner any questions unless you are clarifying jargon or an unclear question.
- Do not coach, assess, score, or structure the interview.
- Do not mention preceptor mode, grading, rubric, diagnosis, or differential diagnoses.
- Answer naturally, briefly, and realistically.
- Do not volunteer the whole story at once.
- Only reveal information when asked.
- Do not volunteer extra symptoms, timelines, or associated problems unless asked.
- Use simple caregiver language, not textbook language.
- Keep your answers internally consistent with the hidden case summary and family details.
- If the learner asks about background facts, answer confidently using the information above.
- If the learner's question is vague or unclear, say briefly:
  "Can you explain what exactly you want to know?"
- Do not repeatedly ask "what else do you want to know?"
- If the learner's utterance sounds incomplete, partial, cut off, or interrupted, wait.
- There is no preceptor stage in this conversation.
- Remain the caregiver throughout.
""".strip()


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
            "study_number": body.get("study_number"),
            "study_group": body.get("study_group"),
            "interaction_mode": body.get("interaction_mode"),
            "age_group": body.get("age_group"),
            "system": body.get("system"),
            "caregiver_name": body.get("caregiver_name"),
            "caregiver_gender": body.get("caregiver_gender"),
            "caregiver_role": body.get("caregiver_role"),
            "caregiver_occupation": body.get("caregiver_occupation"),
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

        with open(transcript_file, "w", encoding="utf-8") as f:
            json.dump(transcript_payload, f, ensure_ascii=False, indent=2)

        return JSONResponse({"status": "ok", "session_id": safe_id, "file": str(transcript_file)})

    except Exception as e:
        print(f"save_transcript error: {e}")
        return JSONResponse({"status": "error", "message": "Could not save transcript"}, status_code=500)


@app.get("/latest_transcript")
async def latest_transcript(session_id: Optional[str] = None):
    try:
        if not session_id:
            return JSONResponse({"status": "error", "message": "session_id is required"}, status_code=400)

        safe_id = safe_session_id(session_id)
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

        age_group = request.query_params.get("age_group", "Infant").strip() or "Infant"
        system = request.query_params.get("system", "Respiratory").strip() or "Respiratory"
        caregiver_name = request.query_params.get("caregiver_name", "Zanele").strip() or "Zanele"
        caregiver_gender = request.query_params.get("caregiver_gender", "female").strip() or "female"
        caregiver_role = request.query_params.get("caregiver_role", "mother").strip() or "mother"
        caregiver_occupation = request.query_params.get("caregiver_occupation", "").strip()
        child_name = request.query_params.get("child_name", "").strip() or "the child"
        child_age = request.query_params.get("child_age", "").strip() or "3 years"
        child_sex = request.query_params.get("child_sex", "").strip() or "male"
        presenting_complaint = request.query_params.get("presenting_complaint", "").strip()
        case_summary = request.query_params.get("case_summary", "").strip()
        opening_line = request.query_params.get(
            "opening_line",
            f"Hello doctor, I'm {caregiver_name}, {child_name}'s {caregiver_role}.",
        ).strip() or f"Hello doctor, I'm {caregiver_name}, {child_name}'s {caregiver_role}."

        siblings = request.query_params.get("siblings", "").strip()
        residence = request.query_params.get("residence", "").strip()
        birth_place = request.query_params.get("birth_place", "").strip()
        household_structure = request.query_params.get("household_structure", "").strip()
        school_or_daycare = request.query_params.get("school_or_daycare", "").strip()

        study_number = request.query_params.get("study_number", "").strip()
        interaction_mode = request.query_params.get("interaction_mode", "").strip()
        session_id = request.query_params.get("session_id", "").strip()
        case_data_json = request.query_params.get("case_data_json", "").strip()
        study_group = request.query_params.get("study_group", CUSTOMIZED_GROUP).strip() or CUSTOMIZED_GROUP

        selected_voice = choose_voice(caregiver_gender, caregiver_role)

        if study_group == NON_CUSTOMIZED_GROUP:
            instructions = build_non_customized_instructions(
                age_group, system, caregiver_name, caregiver_gender, caregiver_role,
                caregiver_occupation, child_name, child_age, child_sex,
                presenting_complaint, case_summary, opening_line, siblings,
                residence, birth_place, household_structure, school_or_daycare,
                study_number, interaction_mode, session_id
            )
        else:
            instructions = build_customized_instructions(
                age_group, system, caregiver_name, caregiver_gender, caregiver_role,
                caregiver_occupation, child_name, child_age, child_sex,
                presenting_complaint, case_summary, opening_line, siblings,
                residence, birth_place, household_structure, school_or_daycare,
                study_number, interaction_mode, session_id, case_data_json
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
                        "threshold": 0.5,
                        "prefix_padding_ms": 400,
                        "silence_duration_ms": 1800,
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
