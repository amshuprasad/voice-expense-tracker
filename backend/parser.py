import requests
import dateparser
from datetime import datetime, timedelta
import re
import json
import logging

logger = logging.getLogger(__name__)


# OLLAMA CONFIG
OLLAMA_URL = "http://localhost:11434/api/generate"

OLLAMA_MODEL = "qwen3:4b"

OLLAMA_TIMEOUT = 120


# ============================================================
# CURRENCY
# ============================================================

CURRENCY_ALIASES = r"(?:₹|rs\.?|inr|rupees?|bucks?)"


# ============================================================
# AMOUNT EXTRACTION
# ============================================================

def extract_amount(text: str):
    """
    Extract the first monetary/numeric amount.

    Examples:
        ₹450
        ₹1,250
        rs 450
        rs. 450
        450 rupees
        450 INR
        5,000
        1,25,000
        450.50
        450
    """

    number = r"\d[\d,]*(?:\.\d+)?"

    pattern = (
        rf"{CURRENCY_ALIASES}\s*({number})"
        rf"|({number})\s*{CURRENCY_ALIASES}"
        rf"|({number})"
    )

    match = re.search(
        pattern,
        text,
        re.IGNORECASE
    )

    if not match:
        return None

    amount_str = next(
        group
        for group in match.groups()
        if group
    )

    try:
        return round(
            float(amount_str.replace(",", "")),
            2
        )

    except ValueError:
        return None


# ============================================================
# DATE EXTRACTION
# ============================================================

def extract_date(text: str):
    """
    Extract expense date.

    Examples:
        today
        yesterday
        last Monday
        5th September
        September 5
        2026-09-05

    Defaults to today.
    """

    lower = text.lower()

    if "yesterday" in lower:
        return (
            datetime.now() - timedelta(days=1)
        ).date().isoformat()

    if "today" in lower or "tonight" in lower:
        return datetime.now().date().isoformat()

    parsed = dateparser.parse(
        text,
        settings={
            "PREFER_DATES_FROM": "past"
        }
    )

    if parsed:
        return parsed.date().isoformat()

    return datetime.now().date().isoformat()


# ============================================================
# OLLAMA
# ============================================================

def call_ollama(prompt: str) -> dict:
    """
    Call local Ollama and return parsed JSON.

    Qwen3:
    - Thinking is disabled
    - JSON response is requested
    - No cloud API is used
    """

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",

        # Important for Qwen3.
        # Prevents the model from spending the response
        # on reasoning/thinking instead of returning JSON.
        "think": False,

        "options": {
            "temperature": 0.1,
            "num_ctx": 4096,
        },
    }

    logger.info(
        "Calling Ollama model=%s",
        OLLAMA_MODEL
    )

    try:

        response = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=OLLAMA_TIMEOUT,
        )

        logger.info(
            "Ollama HTTP status=%s",
            response.status_code
        )

        response.raise_for_status()

    except requests.exceptions.ConnectionError as exc:

        logger.exception(
            "Cannot connect to Ollama"
        )

        raise RuntimeError(
            "Cannot connect to Ollama. "
            "Make sure Ollama is running at "
            "http://localhost:11434"
        ) from exc

    except requests.exceptions.Timeout as exc:

        logger.exception(
            "Ollama request timed out"
        )

        raise RuntimeError(
            "Ollama request timed out."
        ) from exc

    except requests.exceptions.RequestException as exc:

        logger.exception(
            "Ollama request failed"
        )

        raise RuntimeError(
            f"Ollama request failed: {exc}"
        ) from exc

    try:

        data = response.json()

    except ValueError as exc:

        raise RuntimeError(
            "Ollama returned invalid JSON: "
            f"{response.text[:1000]}"
        ) from exc

    # --------------------------------------------------------
    # OLLAMA ERROR
    # --------------------------------------------------------

    if data.get("error"):

        raise RuntimeError(
            f"Ollama error: {data['error']}"
        )

    # --------------------------------------------------------
    # RESPONSE
    # --------------------------------------------------------

    raw_response = data.get("response")

    # Qwen3 may return thinking separately.
    # Log it so we can diagnose problems.
    if data.get("thinking"):

        logger.info(
            "Ollama thinking: %s",
            str(data["thinking"])[:1000]
        )

    if raw_response is None:

        raise RuntimeError(
            "Ollama response field is missing. "
            f"Full response: {data}"
        )

    raw_response = raw_response.strip()

    if not raw_response:

        raise RuntimeError(
            "Ollama returned an empty response. "
            f"Full response: {data}"
        )

    logger.info(
        "Ollama generated: %s",
        raw_response
    )

    # --------------------------------------------------------
    # PARSE JSON
    # --------------------------------------------------------

    try:

        return json.loads(raw_response)

    except json.JSONDecodeError:

        cleaned = raw_response.strip()

        # Remove markdown code fences if present.
        cleaned = re.sub(
            r"^```json\s*",
            "",
            cleaned,
            flags=re.IGNORECASE
        )

        cleaned = re.sub(
            r"\s*```$",
            "",
            cleaned
        )

        try:

            return json.loads(cleaned)

        except json.JSONDecodeError as exc:

            raise RuntimeError(
                "Ollama returned text that is not valid JSON: "
                f"{raw_response}"
            ) from exc


# ============================================================
# DYNAMIC AI EXPENSE EXTRACTION
# ============================================================

def extract_expense_with_ai(text: str) -> dict:
    """
    Dynamically understand the expense.

    There is NO hard-coded category list.

    Ollama determines the category based on
    the semantic meaning of the expense.
    """

    prompt = f"""
You are an intelligent personal finance expense parser.

Analyze the COMPLETE user statement and extract structured
expense information.

USER INPUT:
{text}

IMPORTANT RULES:

1. Understand the complete meaning of the sentence.
2. Dynamically infer the most appropriate category.
3. Do NOT use a predefined category keyword list.
4. Do NOT classify based only on one keyword.
5. Categories can be any appropriate category.
6. Do not force expenses into common categories.
7. Use the context of the entire sentence.
8. Category should be short and meaningful.
9. Description should describe what the money was spent on.
10. Extract a person's name only when explicitly mentioned.
11. Never invent a person's name.
12. If no person is mentioned, return null.
13. Return ONLY valid JSON.
14. Do not return markdown.
15. Do not return explanations.

Examples:

Input:
Spent 1200 on badminton with Rahul yesterday

Output:
{{
    "category": "Sports",
    "description": "Badminton",
    "people": "Rahul"
}}

Input:
Paid 850 for my haircut

Output:
{{
    "category": "Personal Care",
    "description": "Haircut",
    "people": null
}}

Input:
Bought a mechanical keyboard for 3200

Output:
{{
    "category": "Electronics",
    "description": "Mechanical keyboard",
    "people": null
}}

Input:
Spent 900 on my dog's grooming

Output:
{{
    "category": "Pets",
    "description": "Dog grooming",
    "people": null
}}

Input:
Paid 4500 for apartment maintenance

Output:
{{
    "category": "Home",
    "description": "Apartment maintenance",
    "people": null
}}

Input:
Had dinner with Arjun for 750

Output:
{{
    "category": "Food",
    "description": "Dinner",
    "people": "Arjun"
}}

Input:
I spent 40 rupees on chocolates

Output:
{{
    "category": "Food",
    "description": "Chocolates",
    "people": null
}}

Now analyze this expense:

{text}

Return EXACTLY this JSON structure:

{{
    "category": "string",
    "description": "string",
    "people": "string or null"
}}
"""

    result = call_ollama(prompt)

    # --------------------------------------------------------
    # VALIDATE RESULT
    # --------------------------------------------------------

    category = result.get("category")
    description = result.get("description")
    people = result.get("people")

    if not category:
        category = "Other"

    if not description:
        description = text

    if people:
        people = str(people).strip()
    else:
        people = None

    return {
        "category": str(category).strip(),
        "description": str(description).strip(),
        "people": people,
    }


# ============================================================
# MAIN PARSER
# ============================================================

def parse_expense_text(text: str) -> dict:
    """
    Convert natural language expense text into
    structured expense data.
    """

    if not text or not text.strip():

        raise ValueError(
            "Expense text cannot be empty"
        )

    text = text.strip()

    logger.info(
        "Parsing expense text: %s",
        text
    )

    # --------------------------------------------------------
    # DETERMINISTIC EXTRACTION
    # --------------------------------------------------------

    amount = extract_amount(text)

    date = extract_date(text)

    logger.info(
        "Extracted amount=%s date=%s",
        amount,
        date
    )

    # --------------------------------------------------------
    # AI SEMANTIC EXTRACTION
    # --------------------------------------------------------

    ai_result = extract_expense_with_ai(text)

    logger.info(
        "AI expense result: %s",
        ai_result
    )

    # --------------------------------------------------------
    # FINAL RESULT
    # --------------------------------------------------------

    return {
        "raw_text": text,
        "amount": amount,
        "category": ai_result["category"],
        "description": ai_result["description"],
        "date": date,
        "people": ai_result["people"],
    }
