from faster_whisper import WhisperModel
import logging

logger = logging.getLogger(__name__)


_model = None
MODEL_SIZE = "base"

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


def transcribe_audio(file_path: str) -> str:
    """
    Transcribe an audio file locally.

    Supports formats such as:
        wav
        mp3
        webm
        m4a
    """

    model = get_model()

    logger.info(
        "Transcribing audio file: %s",
        file_path,
    )

    segments, info = model.transcribe(
        file_path,
        language="en",
        beam_size=5,
    )

    text = " ".join(
        segment.text.strip()
        for segment in segments
    ).strip()

    logger.info(
        "Transcription completed. Detected language: %s",
        info.language,
    )

    return text


