# """
# Free, self-hosted speech-to-text using faster-whisper (a fast
# CTranslate2 reimplementation of OpenAI's open-source Whisper model).

# No API key, no per-minute cost, no internet dependency after the
# model weights are downloaded once. Runs entirely on your own CPU.

# Model sizes (pick based on your machine): tiny, base, small, medium, large-v3
# - tiny/base: fast, fine for short sentences like expense logging
# - small+: more accurate, slower, needs more RAM

# The model is loaded lazily (on first transcription request) so the
# API starts up instantly and only pays the load cost when actually
# used.
# """
# from faster_whisper import WhisperModel

# _model = None

# # "base" is a good accuracy/speed tradeoff for short expense sentences
# # on a CPU-only machine. Change to "tiny" for lower-end hardware, or
# # "small"/"medium" if you have more RAM/CPU and want better accuracy.
# MODEL_SIZE = "base"


# def get_model() -> WhisperModel:
#     global _model
#     if _model is None:
#         # compute_type="int8" keeps CPU RAM/CPU usage low and free of
#         # any GPU requirement.
#         _model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
#     return _model


# def transcribe_audio(file_path: str) -> str:
#     """Transcribes an audio file (wav/mp3/webm/m4a/etc - ffmpeg handles
#     the decoding under the hood) and returns the plain text transcript."""
#     model = get_model()
#     print(file_path)
#     segments, _info = model.transcribe(file_path, language="en", beam_size=5)
#     return " ".join(segment.text.strip() for segment in segments).strip()


from faster_whisper import WhisperModel
import logging
"""
Free, self-hosted speech-to-text using faster-whisper.

Audio -> text happens completely locally.

No API key.
No per-minute cost.
No cloud transcription.

The Whisper model is downloaded once and then runs locally.
"""


logger = logging.getLogger(__name__)


_model = None


# Good balance for short expense sentences.
#
# tiny  -> fastest
# base  -> recommended starting point
# small -> better accuracy, slower
# medium -> higher resource usage
#
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


