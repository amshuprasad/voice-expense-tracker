import database as db
from whisper_service import transcribe_audio
from parser import parse_expense_text
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException, UploadFile, File
from typing import Optional
import tempfile
import shutil
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

app = FastAPI(
    title="Voice Expense Tracker API",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger(__name__)
db.init_db()

class TextInput(BaseModel):
    text: str


class ExpenseIn(BaseModel):
    raw_text: str
    amount: float
    category: str
    description: str
    date: str
    people: Optional[str] = None

@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "voice-expense-tracker",
        "ai": "local-ollama",
        "speech": "local-faster-whisper",
    }

@app.post("/parse-expense")
def parse_expense(payload: TextInput):

    if not payload.text or not payload.text.strip():
        raise HTTPException(
            status_code=400,
            detail="Empty text",
        )

    try:
        parsed = parse_expense_text(
            payload.text
        )

    except Exception as exc:
        logger.exception(
            "Expense parsing failed"
        )

        raise HTTPException(
            status_code=500,
            detail=f"Expense parsing failed: {exc}",
        )

    if parsed["amount"] is None:
        raise HTTPException(
            status_code=422,
            detail=(
                "Could not detect an amount. "
                "Try saying something like "
                "'Spent 450 on dinner'."
            ),
        )

    return parsed


@app.post("/transcribe-expense")
async def transcribe_expense(
    audio: UploadFile = File(...)
):

    suffix = (
        os.path.splitext(
            audio.filename or "clip.webm"
        )[1]
        or ".webm"
    )

    tmp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            delete=False,
        ) as tmp:

            shutil.copyfileobj(
                audio.file,
                tmp,
            )

            tmp_path = tmp.name

        logger.info(
            "Audio uploaded: %s",
            audio.filename,
        )

        cleaned_text, flagged = transcribe_audio(tmp_path)

        if not cleaned_text.strip():
            raise HTTPException(
                status_code=422,
                detail=(
                    "Couldn't hear anything. "
                    "Please try speaking again."
                ),
            )

        if flagged:
            logger.warning(
                "Profanity detected in transcript, censored"
            )

        logger.info(
            "Transcript: %s",
            cleaned_text,
        )

        parsed = parse_expense_text(cleaned_text)

        if parsed["amount"] is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    f'Heard: "{cleaned_text}" '
                    "but couldn't detect an amount."
                ),
            )

        parsed["flagged"] = flagged

        return parsed

    except HTTPException:
        raise

    except Exception as exc:
        logger.exception(
            "Voice expense processing failed"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"Voice expense processing failed: {exc}"
            ),
        )

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

@app.post("/expenses")
def create_expense(
    expense: ExpenseIn
):
    expense_id = db.insert_expense(
        expense.model_dump()
    )

    return {
        "id": expense_id,
        **expense.model_dump(),
    }

@app.get("/expenses")
def get_expenses(
    limit: int = 100
):
    return db.list_expenses(limit)


@app.delete("/expenses/{expense_id}")
def remove_expense(
    expense_id: int
):
    db.delete_expense(expense_id)

    return {
        "deleted": expense_id
    }

@app.get("/summary")
def get_summary():
    return db.summary_by_category()


