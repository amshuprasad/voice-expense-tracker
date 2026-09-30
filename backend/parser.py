from datetime import datetime, timedelta, date
import requests
import dateparser
from datetime import datetime, timedelta
import re
import json
import logging
import os
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

# OLLAMA CONFIG
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:4b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))

CURRENCY_ALIASES = r"(?:₹|rs\.?|inr|rupees?|bucks?)"

def extract_amount(text: str):
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

def extract_date(text: str):
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

def call_ollama(prompt: str) -> dict:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
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
    if data.get("error"):
        raise RuntimeError(
            f"Ollama error: {data['error']}"
        )
    raw_response = data.get("response")
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

    try:
        return json.loads(raw_response)
    except json.JSONDecodeError:
        cleaned = raw_response.strip()
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

def extract_expense_with_ai(text: str) -> dict:
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

def parse_expense_text(text: str) -> dict:
    if not text or not text.strip():
        raise ValueError(
            "Expense text cannot be empty"
        )

    text = text.strip()

    logger.info(
        "Parsing expense text: %s",
        text
    )

    amount = extract_amount(text)
    date = extract_date(text)
    logger.info(
        "Extracted amount=%s date=%s",
        amount,
        date
    )
    ai_result = extract_expense_with_ai(text)
    logger.info(
        "AI expense result: %s",
        ai_result
    )
    return {
        "raw_text": text,
        "amount": amount,
        "category": ai_result["category"],
        "description": ai_result["description"],
        "date": date,
        "people": ai_result["people"],
    }


QUERY_PATTERN = re.compile(
    r"\b(how much"
    r"|what (?:did|have) i (?:spend|spent)"
    r"|what (?:is|was) my (?:total|spending)"
    r"|total (?:spent|spending|expenses?)"
    r"|show (?:me )?(?:my )?(?:expenses|spending))\b",
    re.IGNORECASE,
)

ALL_TIME_PATTERN = re.compile(
    r"\b(till|until) (today|now|date)\b|\bso far\b|\bin total\b"
    r"|\btotally\b|\boverall\b|\baltogether\b",
    re.IGNORECASE,
)

DATE_SETTINGS = {"PREFER_DATES_FROM": "past", "DATE_ORDER": "DMY"}


def is_query(text: str) -> bool:
    return bool(QUERY_PATTERN.search(text))


def _parse_day(fragment: str):
    fragment = re.sub(r"\b(on|the|of)\b", " ", fragment,
                      flags=re.IGNORECASE).strip()
    parsed = dateparser.parse(fragment, settings=DATE_SETTINGS)
    return parsed.date() if parsed else None


def extract_date_range(text: str):
    """Returns (start_iso | None, end_iso). start=None means all time."""
    today = date.today()
    lower = text.lower()

    # 1. Explicit range: "from X to Y" / "between X and Y"
    m = re.search(
        r"(?:from|between)\s+(.+?)\s+(?:to|till|until|and)\s+(.+?)(?:[?.!]|$)",
        lower,
    )
    if m:
        s, e = _parse_day(m.group(1)), _parse_day(m.group(2))
        if s and e:
            if s > e:
                s, e = e, s
            return s.isoformat(), e.isoformat()

    # 2. All time: "totally", "so far", "till today"
    if ALL_TIME_PATTERN.search(lower):
        return None, today.isoformat()

    # 3. Relative periods
    if "yesterday" in lower:
        d = (today - timedelta(days=1)).isoformat()
        return d, d
    if "today" in lower:
        return today.isoformat(), today.isoformat()
    if "last week" in lower:
        start = today - timedelta(days=today.weekday() + 7)
        return start.isoformat(), (start + timedelta(days=6)).isoformat()
    if "this week" in lower:
        return (today - timedelta(days=today.weekday())).isoformat(), today.isoformat()
    if "last month" in lower:
        end = today.replace(day=1) - timedelta(days=1)
        return end.replace(day=1).isoformat(), end.isoformat()
    if "this month" in lower:
        return today.replace(day=1).isoformat(), today.isoformat()
    if "this year" in lower:
        return today.replace(month=1, day=1).isoformat(), today.isoformat()
    m = re.search(r"last (\d+) days?", lower)
    if m:
        n = int(m.group(1))
        return (today - timedelta(days=n - 1)).isoformat(), today.isoformat()

    # 4. Single date: "on 5th September", "on 12/09/2026"
    m = re.search(r"\bon\s+(.+?)(?:[?.!]|$)", lower)
    if m:
        d = _parse_day(m.group(1))
        if d:
            return d.isoformat(), d.isoformat()

    # 5. Default: all time
    return None, today.isoformat()


def describe_range(start, end) -> str:
    if start is None:
        return f"in total (till {end})"
    if start == end:
        return f"on {start}"
    return f"from {start} to {end}"
