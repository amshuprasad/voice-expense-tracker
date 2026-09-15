# import shutil
# import tempfile
# import os

# from fastapi import FastAPI, HTTPException, UploadFile, File
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel
# from typing import Optional

# from parser import parse_expense_text
# from whisper_service import transcribe_audio
# import database as db

# app = FastAPI(title="Voice Expense Tracker API")

# # Allow the Next.js dev server (and any origin in prod - tighten this
# # once you deploy) to call this API.
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# db.init_db()


# class TextInput(BaseModel):
#     text: str


# class ExpenseIn(BaseModel):
#     raw_text: str
#     amount: float
#     category: str
#     description: str
#     date: str
#     people: Optional[str] = None


# @app.get("/")
# def root():
#     return {"status": "ok", "service": "voice-expense-tracker"}


# @app.post("/parse-expense")
# def parse_expense(payload: TextInput):
#     """Takes the transcribed voice text and returns structured fields
#     for the user to confirm/edit before saving."""
#     if not payload.text or not payload.text.strip():
#         raise HTTPException(status_code=400, detail="Empty text")
#     parsed = parse_expense_text(payload.text)
#     if parsed["amount"] is None:
#         raise HTTPException(
#             status_code=422,
#             detail="Could not detect an amount. Try saying it more clearly, e.g. 'Spent 450 on dinner'.",
#         )
#     return parsed


# @app.post("/transcribe-expense")
# async def transcribe_expense(audio: UploadFile = File(...)):
#     suffix = os.path.splitext(audio.filename or "clip.webm")[1] or ".webm"
#     print("suffix", suffix)

#     with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
#         shutil.copyfileobj(audio.file, tmp)
#         tmp_path = tmp.name

#     try:
#         print("tmp_path", tmp_path)
#         text = transcribe_audio(tmp_path)
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Transcription failed: {e}")
#     finally:
#         os.remove(tmp_path)

#     if not text.strip():
#         raise HTTPException(status_code=422, detail="Couldn't hear anything - try again")

#     parsed = parse_expense_text(text)
#     if parsed["amount"] is None:
#         raise HTTPException(
#             status_code=422,
#             detail=f"Heard: \"{text}\" - but couldn't detect an amount. Try again.",
#         )
#     return parsed


# @app.post("/expenses")
# def create_expense(expense: ExpenseIn):
#     expense_id = db.insert_expense(expense.model_dump())
#     return {"id": expense_id, **expense.model_dump()}


# @app.get("/expenses")
# def get_expenses(limit: int = 100):
#     return db.list_expenses(limit)


# @app.delete("/expenses/{expense_id}")
# def remove_expense(expense_id: int):
#     db.delete_expense(expense_id)
#     return {"deleted": expense_id}


# @app.get("/summary")
# def get_summary():
#     return db.summary_by_category()


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


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="Voice Expense Tracker API",
    version="2.0.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# DATABASE
# ============================================================

db.init_db()


# ============================================================
# REQUEST MODELS
# ============================================================

class TextInput(BaseModel):
    text: str


class ExpenseIn(BaseModel):
    raw_text: str
    amount: float
    category: str
    description: str
    date: str
    people: Optional[str] = None


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "voice-expense-tracker",
        "ai": "local-ollama",
        "speech": "local-faster-whisper",
    }


# ============================================================
# TEXT -> EXPENSE
# ============================================================

@app.post("/parse-expense")
def parse_expense(payload: TextInput):
    """
    Parse already-transcribed text.

    Example:

    {
        "text": "Spent 1200 on badminton with Rahul yesterday"
    }
    """

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


# ============================================================
# AUDIO -> WHISPER -> EXPENSE
# ============================================================

@app.post("/transcribe-expense")
async def transcribe_expense(
    audio: UploadFile = File(...)
):
    """
    Complete voice pipeline:

        Audio
          ↓
        Whisper
          ↓
        Transcript
          ↓
        Ollama
          ↓
        Structured expense
    """

    suffix = (
        os.path.splitext(
            audio.filename or "clip.webm"
        )[1]
        or ".webm"
    )

    tmp_path = None

    try:
        # ----------------------------------------------------
        # Save uploaded audio temporarily
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Whisper transcription
        # ----------------------------------------------------

        text = transcribe_audio(
            tmp_path
        )

        if not text.strip():
            raise HTTPException(
                status_code=422,
                detail=(
                    "Couldn't hear anything. "
                    "Please try speaking again."
                ),
            )

        logger.info(
            "Transcript: %s",
            text,
        )

        # ----------------------------------------------------
        # AI expense parsing
        # ----------------------------------------------------

        parsed = parse_expense_text(
            text
        )

        # ----------------------------------------------------
        # Amount validation
        # ----------------------------------------------------

        if parsed["amount"] is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    f'Heard: "{text}" '
                    "but couldn't detect an amount."
                ),
            )

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
        # ----------------------------------------------------
        # Delete temporary audio file
        # ----------------------------------------------------

        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


# ============================================================
# CREATE EXPENSE
# ============================================================

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


# ============================================================
# GET EXPENSES
# ============================================================

@app.get("/expenses")
def get_expenses(
    limit: int = 100
):
    return db.list_expenses(limit)


# ============================================================
# DELETE EXPENSE
# ============================================================

@app.delete("/expenses/{expense_id}")
def remove_expense(
    expense_id: int
):
    db.delete_expense(expense_id)

    return {
        "deleted": expense_id
    }


# ============================================================
# SUMMARY
# ============================================================

@app.get("/summary")
def get_summary():
    return db.summary_by_category()


