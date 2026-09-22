from faster_whisper import WhisperModel
from better_profanity import profanity
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

profanity.load_censor_words()

_model = None
MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")

def get_model() -> WhisperModel:
    global _model

    if _model is None:
        logger.info(
            "Loading Whisper model: %s",
            MODEL_SIZE,
        )

        _model = WhisperModel(
            MODEL_SIZE,
            device="cpu",
            compute_type="int8",
        )

        logger.info("Whisper model loaded")

    return _model


def transcribe_audio(file_path: str) -> tuple[str, bool]:
    """
    Transcribe an audio file locally.
    Returns (cleaned_text, was_flagged)
    """

    model = get_model()

    logger.info("Transcribing audio file: %s", file_path)

    segments, info = model.transcribe(
        file_path,
        language="en",
        beam_size=5,
    )

    raw_text = " ".join(
        segment.text.strip()
        for segment in segments
    ).strip()

    logger.info(
        "Transcription completed. Detected language: %s",
        info.language,
    )

    cleaned_text, flagged = clean_transcript(raw_text)

    if flagged:
        logger.warning("Profanity detected and censored in transcript")

    return cleaned_text, flagged


def clean_transcript(text: str) -> tuple[str, bool]:
    """Returns (cleaned_text, was_flagged)"""
    contains_bad_words = profanity.contains_profanity(text)
    cleaned = profanity.censor(text)  # replaces bad words with ****
    return cleaned, contains_bad_words
