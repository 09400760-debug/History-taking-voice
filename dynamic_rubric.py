from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any
import random


# ============================================================
# DYNAMIC RUBRIC + SA COMMON CASE BANK
# Built from Wits Paeds Rubric Version 11 Sept 2024
# ============================================================


@dataclass
class RubricSection:
    key: str
    label: str
    max_marks: int
    always_core: bool = False
    usually_core: bool = False
    activation_tags: Set[str] = field(default_factory=set)
    min_age_months: Optional[int] = None
    max_age_months: Optional[int] = None
    guidance: str = ""


RUBRIC_SECTIONS: Dict[str, RubricSection] = {
    "main_complaint": RubricSection(
        key="main_complaint",
        label="Main Complaint & Development of Symptoms",
        max_marks=25,
        always_core=True,
        guidance=(
            "Assess whether the student explored onset, duration, progression, "
            "characteristics, triggers, relieving factors, severity, and impact on daily life. "
            "Strong performance should include at least 3 relevant follow-up questions."
        ),
    ),
    "danger_signs": RubricSection(
        key="danger_signs",
        label="Danger Signs",
        max_marks=2,
        always_core=True,
        guidance=(
            "Assess whether the student screened for important danger signs. "
            "Examples include convulsions, lethargy, vomiting everything, not taking feeds, "
            "and system-specific danger signs such as fast or difficult breathing."
        ),
    ),
    "involved_system": RubricSection(
        key="involved_system",
        label="Involved System Focused History",
        max_marks=5,
        usually_core=True,
        guidance=(
            "Assess depth and relevance of system-focused questions related to the presenting problem."
        ),
    ),
    "other_systems": RubricSection(
        key="other_systems",
        label="Other Systems Enquiry",
        max_marks=3,
        usually_core=True,
        guidance=(
            "Assess whether the student screened appropriately across other systems, "
            "including items such as sleep, bowel/urinary habits, weight loss, or screen time where relevant."
        ),
    ),
    "birth_history": RubricSection(
        key="birth_history",
        label="Birth History",
        max_marks=5,
        activation_tags={"neonate", "infant", "development", "failure_to_thrive", "congenital", "seizure"},
        max_age_months=24,
        guidance=(
            "Activate especially in neonates, infants, developmental concerns, poor growth, congenital concerns, or seizures. "
            "Assess antenatal, perinatal, neonatal history, maternal illness, HIV/syphilis testing, and Road to Health Booklet."
        ),
    ),
    "immunisation": RubricSection(
        key="immunisation",
        label="Immunization",
        max_marks=3,
        activation_tags={"infectious", "fever", "respiratory", "rash", "cns"},
        max_age_months=60,
        guidance=(
            "Activate in most younger children and infectious/rash/fever cases. "
            "Assess whether the student checked immunisation status or asked to review the Road to Health Booklet/card."
        ),
    ),
    "nutrition": RubricSection(
        key="nutrition",
        label="Nutrition",
        max_marks=3,
        activation_tags={"infant", "diarrhoea", "vomiting", "failure_to_thrive", "malnutrition", "infectious"},
        max_age_months=60,
        guidance=(
            "Activate for infants, feeding, diarrhoea/vomiting, growth concerns, and many infectious presentations. "
            "Assess breastfeeding, fluid intake, missed meals, feeding practices, and allergies/intolerances."
        ),
    ),
    "past_history": RubricSection(
        key="past_history",
        label="Past Medical, Surgical, Medications & Allergies History",
        max_marks=5,
        usually_core=True,
        guidance=(
            "Assess whether the student asked about past illnesses, admissions, surgery, medications, allergies, and traditional therapies."
        ),
    ),
    "family_history": RubricSection(
        key="family_history",
        label="Family Medical History",
        max_marks=3,
        usually_core=True,
        guidance=(
            "Assess whether the student asked about family illnesses, including TB exposure where relevant."
        ),
    ),
    "development": RubricSection(
        key="development",
        label="Developmental Milestones",
        max_marks=3,
        activation_tags={"development", "neurology", "neurodevelopment", "failure_to_thrive", "chronic"},
        max_age_months=72,
        guidance=(
            "Activate for younger children and especially developmental, neurological, chronic, and poor-growth cases. "
            "Assess gross motor, fine motor, language, and social milestones."
        ),
    ),
    "social_history": RubricSection(
        key="social_history",
        label="Social History & Travel",
        max_marks=3,
        activation_tags={"infectious", "tb", "chronic", "environment", "diarrhoea", "respiratory"},
        guidance=(
            "Assess dwelling, caregivers, siblings, grants/income, environmental exposures, travel, and relevant day-care/school context."
        ),
    ),
    "assessment": RubricSection(
        key="assessment",
        label="Assessment from History",
        max_marks=20,
        always_core=True,
        guidance=(
            "Assess whether the student gave a logical summary and differential diagnosis, "
            "including at least one reasonable alternative differential."
        ),
    ),
    "empathy": RubricSection(
        key="empathy",
        label="Empathy",
        max_marks=5,
        always_core=True,
        guidance=(
            "Assess whether the student acknowledged caregiver emotion, listened actively, and responded supportively."
        ),
    ),
    "communication": RubricSection(
        key="communication",
        label="Interview Technique, Communication Skills & Overall Impression",
        max_marks=15,
        always_core=True,
        guidance=(
            "Assess organisation, clarity, logical flow, open questions, summarising, and overall interview quality."
        ),
    ),
}


# ============================================================
# COMMON SOUTH AFRICAN PAEDIATRIC CASE BANK
# Keep these as common, realistic cases seen in SA practice
# ============================================================

COMMON_SA_CASE_BANK: List[Dict[str, Any]] = [
    {
        "id": "resp_001",
        "title": "Childhood pneumonia",
        "age_label": "2-year-old",
        "age_months": 24,
        "system": "Respiratory",
        "tags": {"infectious", "respiratory", "fever"},
        "context": (
            "You are speaking to the mother of a 2-year-old child with cough, fever, and fast breathing "
            "for 3 days. The child is drinking less than usual and has been less active."
        ),
    },
    {
        "id": "resp_002",
        "title": "Bronchiolitis",
        "age_label": "6-month-old",
        "age_months": 6,
        "system": "Respiratory",
        "tags": {"infectious", "respiratory", "infant"},
        "context": (
            "You are speaking to the caregiver of a 6-month-old infant with cough, difficulty breathing, "
            "poor feeding, and noisy breathing over 2 days."
        ),
    },
    {
        "id": "resp_003",
        "title": "Acute wheeze / viral-triggered wheeze",
        "age_label": "3-year-old",
        "age_months": 36,
        "system": "Respiratory",
        "tags": {"respiratory", "infectious"},
        "context": (
            "You are speaking to the mother of a 3-year-old with cough, wheeze, and shortness of breath "
            "that started after a cold."
        ),
    },
    {
        "id": "gi_001",
        "title": "Acute gastroenteritis with dehydration",
        "age_label": "1-year-old",
        "age_months": 12,
        "system": "Gastrointestinal",
        "tags": {"infectious", "diarrhoea", "vomiting", "infant"},
        "context": (
            "You are speaking to the caregiver of a 1-year-old with diarrhoea and vomiting for 2 days, "
            "reduced urine output, and poor oral intake."
        ),
    },
    {
        "id": "gi_002",
        "title": "Possible dysentery",
        "age_label": "4-year-old",
        "age_months": 48,
        "system": "Gastrointestinal",
        "tags": {"infectious", "diarrhoea", "fever"},
        "context": (
            "You are speaking to the parent of a 4-year-old with bloody diarrhoea, abdominal pain, "
            "and fever since yesterday."
        ),
    },
    {
        "id": "tb_001",
        "title": "Pulmonary TB exposure with symptoms",
        "age_label": "5-year-old",
        "age_months": 60,
        "system": "Respiratory",
        "tags": {"infectious", "tb", "respiratory", "chronic"},
        "context": (
            "You are speaking to the grandmother of a 5-year-old with chronic cough, weight loss, "
            "night sweats, and a household TB contact."
        ),
    },
    {
        "id": "hiv_001",
        "title": "Possible HIV-related recurrent infection",
        "age_label": "18-month-old",
        "age_months": 18,
        "system": "General Paediatrics",
        "tags": {"infectious", "chronic", "failure_to_thrive", "infant"},
        "context": (
            "You are speaking to the mother of an 18-month-old with poor weight gain, recurrent chest infections, "
            "oral thrush, and chronic diarrhoea."
        ),
    },
    {
        "id": "neuro_001",
        "title": "Febrile seizure",
        "age_label": "18-month-old",
        "age_months": 18,
        "system": "Neurology",
        "tags": {"fever", "neurology", "infectious", "seizure"},
        "context": (
            "You are speaking to the caregiver of an 18-month-old who had a convulsion with fever today "
            "after 2 days of upper respiratory symptoms."
        ),
    },
    {
        "id": "neuro_002",
        "title": "Meningitis / meningoencephalitis concern",
        "age_label": "6-year-old",
        "age_months": 72,
        "system": "Neurology",
        "tags": {"infectious", "cns", "fever"},
        "context": (
            "You are speaking to the parent of a 6-year-old with fever, headache, vomiting, "
            "and increasing drowsiness."
        ),
    },
    {
        "id": "neo_001",
        "title": "Possible neonatal sepsis",
        "age_label": "10-day-old",
        "age_months": 0,
        "system": "Neonatology",
        "tags": {"infectious", "neonate", "infant"},
        "context": (
            "You are speaking to the mother of a 10-day-old baby who is feeding poorly, "
            "sleepier than usual, and feels hot."
        ),
    },
    {
        "id": "nutrition_001",
        "title": "Severe acute malnutrition",
        "age_label": "14-month-old",
        "age_months": 14,
        "system": "Nutrition",
        "tags": {"malnutrition", "failure_to_thrive", "infectious", "infant"},
        "context": (
            "You are speaking to the caregiver of a 14-month-old with visible weight loss, "
            "swelling of the feet, poor appetite, and recurrent diarrhoea."
        ),
    },
    {
        "id": "gen_001",
        "title": "Measles-like illness / rash with fever",
        "age_label": "3-year-old",
        "age_months": 36,
        "system": "Infectious Diseases",
        "tags": {"infectious", "rash", "fever"},
        "context": (
            "You are speaking to the caregiver of a 3-year-old with fever, cough, red eyes, "
            "and a spreading rash."
        ),
    },
    {
        "id": "uti_001",
        "title": "Urinary tract infection",
        "age_label": "2-year-old",
        "age_months": 24,
        "system": "General Paediatrics",
        "tags": {"infectious", "fever"},
        "context": (
            "You are speaking to the parent of a 2-year-old with fever, vomiting, irritability, "
            "and pain when passing urine."
        ),
    },
    {
        "id": "ent_001",
        "title": "Acute otitis media",
        "age_label": "18-month-old",
        "age_months": 18,
        "system": "ENT",
        "tags": {"infectious", "fever"},
        "context": (
            "You are speaking to the mother of an 18-month-old with fever, crying, poor sleep, "
            "and pulling at the ear."
        ),
    },
    {
        "id": "dev_001",
        "title": "Speech and developmental delay",
        "age_label": "3-year-old",
        "age_months": 36,
        "system": "Neurodevelopment",
        "tags": {"development", "neurodevelopment", "chronic"},
        "context": (
            "You are speaking to the caregiver of a 3-year-old who is not speaking in sentences, "
            "has poor social interaction, and the preschool is concerned."
        ),
    },
]


# ============================================================
# RUBRIC ACTIVATION
# ============================================================

def _age_matches(section: RubricSection, age_months: int) -> bool:
    if section.min_age_months is not None and age_months < section.min_age_months:
        return False
    if section.max_age_months is not None and age_months > section.max_age_months:
        return False
    return True


def get_active_rubric(case_data: Dict[str, Any]) -> List[RubricSection]:
    """
    Determine which rubric sections are active for a given case.
    """
    age_months = int(case_data.get("age_months", 60))
    case_tags = set(case_data.get("tags", set()))

    active_sections: List[RubricSection] = []

    for section in RUBRIC_SECTIONS.values():
        if section.always_core:
            active_sections.append(section)
            continue

        if section.usually_core:
            active_sections.append(section)
            continue

        if section.activation_tags and (section.activation_tags & case_tags) and _age_matches(section, age_months):
            active_sections.append(section)

    return active_sections


def get_active_rubric_summary(case_data: Dict[str, Any]) -> Dict[str, Any]:
    active = get_active_rubric(case_data)
    total_possible = sum(s.max_marks for s in active)

    return {
        "sections": [
            {
                "key": s.key,
                "label": s.label,
                "max_marks": s.max_marks,
                "guidance": s.guidance,
            }
            for s in active
        ],
        "raw_total_possible": total_possible,
    }


def renormalise_score(raw_score: float, raw_total_possible: float) -> float:
    if raw_total_possible <= 0:
        return 0.0
    return round((raw_score / raw_total_possible) * 100, 1)


# ============================================================
# CASE SELECTION
# ============================================================

def choose_case(
    requested_system: Optional[str] = None,
    requested_title: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Choose a case from common SA paediatric illnesses.
    """
    candidates = COMMON_SA_CASE_BANK

    if requested_system and requested_system.lower() != "random":
        candidates = [
            c for c in candidates
            if c["system"].lower() == requested_system.lower()
        ] or candidates

    if requested_title:
        matches = [
            c for c in candidates
            if requested_title.lower() in c["title"].lower()
        ]
        if matches:
            candidates = matches

    return random.choice(candidates)


# ============================================================
# JSON SCHEMA FOR AI ASSESSOR
# ============================================================

def build_assessor_schema(case_data: Dict[str, Any]) -> Dict[str, Any]:
    active = get_active_rubric(case_data)
    raw_total = sum(s.max_marks for s in active)

    return {
        "case_metadata": {
            "case_id": case_data.get("id"),
            "title": case_data.get("title"),
            "age_label": case_data.get("age_label"),
            "age_months": case_data.get("age_months"),
            "system": case_data.get("system"),
            "tags": sorted(list(case_data.get("tags", []))),
            "context": case_data.get("context"),
        },
        "rubric": {
            "scoring_model": "dynamic_case_activated_rubric",
            "raw_total_possible": raw_total,
            "final_total_after_renormalisation": 100,
            "sections": [
                {
                    "key": s.key,
                    "label": s.label,
                    "max_marks": s.max_marks,
                    "guidance": s.guidance,
                }
                for s in active
            ],
        },
        "output_format": {
            "required_top_level_keys": [
                "case_summary",
                "scores",
                "raw_score_total",
                "raw_total_possible",
                "final_score_out_of_100",
                "strengths",
                "missed_opportunities",
                "overall_feedback",
            ],
            "scores_structure": {
                "section_key": {
                    "score": "number",
                    "max_marks": "number",
                    "reasoning": "string",
                }
            },
        },
    }


# ============================================================
# PROMPT BUILDERS
# ============================================================

def build_history_taking_system_prompt(case_data: Dict[str, Any]) -> str:
    """
    Prompt for the caregiver / simulated case side.
    """
    return f"""
You are role-playing a caregiver in a paediatric history-taking practice case.

CASE TYPE:
- Common South African childhood illness only.
- Keep the scenario realistic for routine paediatric training in South Africa.
- Favour common conditions such as pneumonia, bronchiolitis, acute diarrhoea with dehydration,
  TB exposure / pulmonary TB, HIV-related illness, febrile seizure, neonatal sepsis,
  malnutrition, UTI, otitis media, or developmental delay.

CURRENT CASE:
- Title: {case_data.get("title")}
- Age: {case_data.get("age_label")}
- System: {case_data.get("system")}
- Context: {case_data.get("context")}

ROLEPLAY RULES:
- Start naturally by greeting the student as doctor and introducing yourself and the child briefly.
- Do not volunteer the whole history at once.
- Only reveal information when asked.
- Answer like a real caregiver, not like a textbook.
- Show appropriate concern and realism.
- Keep answers short to moderate.
- If the student asks unclear or jargon-heavy questions, ask for clarification.
- Do not give the diagnosis unless specifically asked what you were told.
- Maintain internal consistency throughout the case.
""".strip()


def build_assessor_system_prompt(case_data: Dict[str, Any]) -> str:
    """
    Prompt for the assessor side.
    """
    schema = build_assessor_schema(case_data)
    active_sections = schema["rubric"]["sections"]
    raw_total_possible = schema["rubric"]["raw_total_possible"]

    section_lines = []
    for s in active_sections:
        section_lines.append(
            f"- {s['label']} ({s['max_marks']}): {s['guidance']}"
        )

    joined_sections = "\n".join(section_lines)

    return f"""
You are an expert assessor for a paediatric history-taking encounter using a dynamic Wits-style rubric.

IMPORTANT:
- Score ONLY the activated sections below.
- Do NOT penalise the student for rubric sections that are not activated for this case.
- After assigning raw section scores, calculate:
  final_score_out_of_100 = (raw_score_total / raw_total_possible) * 100
- Round the final score to 1 decimal place.

CASE:
- Title: {case_data.get("title")}
- Age: {case_data.get("age_label")}
- System: {case_data.get("system")}
- Context: {case_data.get("context")}

ACTIVATED RUBRIC SECTIONS:
{joined_sections}

RAW TOTAL POSSIBLE:
{raw_total_possible}

OUTPUT RULES:
- Return valid JSON only.
- Include these top-level keys exactly:
  case_summary
  scores
  raw_score_total
  raw_total_possible
  final_score_out_of_100
  strengths
  missed_opportunities
  overall_feedback

FOR EACH SECTION IN scores:
- include score
- include max_marks
- include reasoning

STYLE:
- Be fair, specific, and educational.
- Feedback should be practical and suitable for student learning.
- Reward relevant prioritisation and not just checklist behaviour.
""".strip()


# ============================================================
# HELPER FOR FRONT END DISPLAY
# ============================================================

def build_case_display_text(case_data: Dict[str, Any]) -> str:
    return (
        f"{case_data.get('title')} | {case_data.get('age_label')} | "
        f"{case_data.get('system')}\n\n"
        f"{case_data.get('context')}"
    )


# ============================================================
# SIMPLE TEST
# ============================================================

if __name__ == "__main__":
    case = choose_case(requested_system="Random")
    print("CASE:")
    print(build_case_display_text(case))
    print("\nACTIVE RUBRIC:")
    print(get_active_rubric_summary(case))
    print("\nASSESSOR PROMPT:")
    print(build_assessor_system_prompt(case))
