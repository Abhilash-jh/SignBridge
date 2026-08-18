"""
views.py — Django API views for SignBridge.

Endpoints
---------
POST /api/translate/
    Body (multipart/form-data):
        mode  : "text" | "mic" | "file" | "video"
        text  : str   (required when mode == "text")
        audio : file  (required when mode == "mic" or "file")
        video : file  (required when mode == "video"; audio track is extracted)

    Response (JSON):
        {
          "transcript" : str,
          "sequence"   : [
              {
                "word"  : str,
                "type"  : "word" | "fingerspell",
                "images": [url, ...]
              }, ...
          ],
          "strip_b64"  : str | null,    # base64 PNG of the sign strip (if Pillow available)
          "audio_b64"  : str | null,    # base64 MP3/WAV of TTS (if gTTS/pyttsx3 available)
          "audio_mime" : str | null      # "audio/mpeg" or "audio/wav"
        }

POST /api/tts/
    Body (JSON):  { "text": "Hello world" }
    Response (JSON): { "audio_b64": str, "mime": str }

GET /api/history/
    Response (JSON): { "items": [ { id, mode, transcript, token_count, ... }, ... ] }

Installation
------------
    pip install django SpeechRecognition Pillow requests gtts pydub
    # For microphone support on Linux: sudo apt-get install portaudio19-dev && pip install pyaudio
    # For video audio extraction:      sudo apt-get install ffmpeg
"""

import base64
import io
import json
import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .models import TranslationLog

logger = logging.getLogger(__name__)

# ── Optional dependency imports ───────────────────────────────────────────────

try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False
    logger.warning("SpeechRecognition not installed. Audio transcription disabled.")

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logger.warning("Pillow not installed. Sign strip generation disabled.")

try:
    import requests as http_requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logger.warning("requests not installed. Remote image fetching disabled.")

try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False
    logger.warning("gTTS not installed. Text-to-speech (online) disabled.")

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False
    logger.warning("pyttsx3 not installed. Text-to-speech (offline) disabled.")

# ── Constants ─────────────────────────────────────────────────────────────────

CACHE_DIR = Path(tempfile.gettempdir()) / "asl_cache"
CACHE_DIR.mkdir(exist_ok=True)

WORD_SIGN_URLS: dict[str, str] = {
    "hello":      "https://www.handspeak.com/word/search/lib/word/hello.jpg",
    "thank":      "https://www.handspeak.com/word/search/lib/word/thank-you.jpg",
    "you":        "https://www.handspeak.com/word/search/lib/word/you.jpg",
    "please":     "https://www.handspeak.com/word/search/lib/word/please.jpg",
    "sorry":      "https://www.handspeak.com/word/search/lib/word/sorry.jpg",
    "yes":        "https://www.handspeak.com/word/search/lib/word/yes.jpg",
    "no":         "https://www.handspeak.com/word/search/lib/word/no.jpg",
    "help":       "https://www.handspeak.com/word/search/lib/word/help.jpg",
    "water":      "https://www.handspeak.com/word/search/lib/word/water.jpg",
    "food":       "https://www.handspeak.com/word/search/lib/word/food.jpg",
    "name":       "https://www.handspeak.com/word/search/lib/word/name.jpg",
    "good":       "https://www.handspeak.com/word/search/lib/word/good.jpg",
    "bad":        "https://www.handspeak.com/word/search/lib/word/bad.jpg",
    "love":       "https://www.handspeak.com/word/search/lib/word/love.jpg",
    "friend":     "https://www.handspeak.com/word/search/lib/word/friend.jpg",
    "family":     "https://www.handspeak.com/word/search/lib/word/family.jpg",
    "work":       "https://www.handspeak.com/word/search/lib/word/work.jpg",
    "home":       "https://www.handspeak.com/word/search/lib/word/home.jpg",
    "school":     "https://www.handspeak.com/word/search/lib/word/school.jpg",
    "learn":      "https://www.handspeak.com/word/search/lib/word/learn.jpg",
    "understand": "https://www.handspeak.com/word/search/lib/word/understand.jpg",
    "where":      "https://www.handspeak.com/word/search/lib/word/where.jpg",
    "what":       "https://www.handspeak.com/word/search/lib/word/what.jpg",
    "who":        "https://www.handspeak.com/word/search/lib/word/who.jpg",
    "when":       "https://www.handspeak.com/word/search/lib/word/when.jpg",
    "how":        "https://www.handspeak.com/word/search/lib/word/how.jpg",
    "morning":    "https://www.handspeak.com/word/search/lib/word/morning.jpg",
    "night":      "https://www.handspeak.com/word/search/lib/word/night.jpg",
    "today":      "https://www.handspeak.com/word/search/lib/word/today.jpg",
    "tomorrow":   "https://www.handspeak.com/word/search/lib/word/tomorrow.jpg",
    "book":       "https://www.handspeak.com/word/search/lib/word/book.jpg",
    "time":       "https://www.handspeak.com/word/search/lib/word/time.jpg",
    "come":       "https://www.handspeak.com/word/search/lib/word/come.jpg",
    "go":         "https://www.handspeak.com/word/search/lib/word/go.jpg",
    "eat":        "https://www.handspeak.com/word/search/lib/word/eat.jpg",
    "drink":      "https://www.handspeak.com/word/search/lib/word/drink.jpg",
    "sleep":      "https://www.handspeak.com/word/search/lib/word/sleep.jpg",
    "think":      "https://www.handspeak.com/word/search/lib/word/think.jpg",
    "feel":       "https://www.handspeak.com/word/search/lib/word/feel.jpg",
    "want":       "https://www.handspeak.com/word/search/lib/word/want.jpg",
    "need":       "https://www.handspeak.com/word/search/lib/word/need.jpg",
    "know":       "https://www.handspeak.com/word/search/lib/word/know.jpg",
    "see":        "https://www.handspeak.com/word/search/lib/word/see.jpg",
    "hear":       "https://www.handspeak.com/word/search/lib/word/hear.jpg",
    "speak":      "https://www.handspeak.com/word/search/lib/word/speak.jpg",
    "happy":      "https://www.handspeak.com/word/search/lib/word/happy.jpg",
    "sad":        "https://www.handspeak.com/word/search/lib/word/sad.jpg",
    "angry":      "https://www.handspeak.com/word/search/lib/word/angry.jpg",
    "sick":       "https://www.handspeak.com/word/search/lib/word/sick.jpg",
    "tired":      "https://www.handspeak.com/word/search/lib/word/tired.jpg",
    "car":        "https://www.handspeak.com/word/search/lib/word/car.jpg",
    "house":      "https://www.handspeak.com/word/search/lib/word/house.jpg",
    "money":      "https://www.handspeak.com/word/search/lib/word/money.jpg",
    "day":        "https://www.handspeak.com/word/search/lib/word/day.jpg",
    "week":       "https://www.handspeak.com/word/search/lib/word/week.jpg",
    "month":      "https://www.handspeak.com/word/search/lib/word/month.jpg",
    "year":       "https://www.handspeak.com/word/search/lib/word/year.jpg",
    "number":     "https://www.handspeak.com/word/search/lib/word/number.jpg",
    "color":      "https://www.handspeak.com/word/search/lib/word/color.jpg",
}

ALPHABET = "abcdefghijklmnopqrstuvwxyz"

DIGIT_MAP = {
    "0": "zero", "1": "one",   "2": "two",   "3": "three",
    "4": "four",  "5": "five",  "6": "six",   "7": "seven",
    "8": "eight", "9": "nine",
}

THUMB_SIZE = (160, 160)

# ── Text pipeline helpers ─────────────────────────────────────────────────────

def normalise(text: str) -> list[str]:
    """Lowercase, strip punctuation, convert single digits to words."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s\-]", "", text)
    tokens = []
    for word in text.split():
        tokens.append(DIGIT_MAP.get(word, word))
    return [t for t in tokens if t]


def _download(url: str, dest: Path) -> bool:
    """Fetch url to dest file. Returns True on success."""
    if not REQUESTS_AVAILABLE:
        return False
    try:
        r = http_requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            dest.write_bytes(r.content)
            return True
    except Exception as exc:
        logger.debug("Download failed for %s: %s", url, exc)
    return False


def get_sign_path(word: str) -> Optional[Path]:
    """Return cached local image path for a whole-word sign, or None."""
    cache_path = CACHE_DIR / f"word_{word}.jpg"
    if cache_path.exists():
        return cache_path
    url = WORD_SIGN_URLS.get(word)
    if url and _download(url, cache_path):
        return cache_path
    return None


def get_letter_path(letter: str) -> Optional[Path]:
    """Return cached local image path for a fingerspelling letter."""
    if letter not in ALPHABET:
        return None
    cache_path = CACHE_DIR / f"letter_{letter}.gif"
    if cache_path.exists():
        return cache_path
    url = f"https://www.lifeprint.com/asl101/fingerspelling/abc-gifs/{letter}.gif"
    if _download(url, cache_path):
        return cache_path
    return None


def build_sequence(tokens: list[str]) -> list[dict]:
    """
    Map tokens to sign entries.
    Each entry: { word, type, images: [url,...], _paths: [Path|None,...] }
    """
    sequence = []
    for word in tokens:
        local = get_sign_path(word)
        if local:
            url = WORD_SIGN_URLS.get(word, "")
            sequence.append({
                "word":    word,
                "type":    "word",
                "images":  [url],
                "_paths":  [local],
            })
        else:
            letter_urls, letter_paths = [], []
            for ch in word:
                lpath = get_letter_path(ch)
                lurl = (
                    f"https://www.lifeprint.com/asl101/fingerspelling/abc-gifs/{ch}.gif"
                    if ch in ALPHABET else ""
                )
                letter_urls.append(lurl)
                letter_paths.append(lpath)
            sequence.append({
                "word":   word,
                "type":   "fingerspell",
                "images": letter_urls,
                "_paths": letter_paths,
            })
    return sequence


def create_strip_b64(sequence: list[dict]) -> Optional[str]:
    """
    Compose sign images into a horizontal PNG strip.
    Returns base64-encoded PNG string, or None if Pillow unavailable.
    """
    if not PIL_AVAILABLE:
        return None

    images, labels = [], []

    for entry in sequence:
        for idx, path in enumerate(entry["_paths"]):
            label = (
                entry["word"].upper()
                if entry["type"] == "word"
                else (entry["word"][idx].upper() if idx < len(entry["word"]) else "?")
            )
            if path and path.exists():
                try:
                    img = Image.open(path).convert("RGB")
                    img.thumbnail(THUMB_SIZE, Image.LANCZOS)
                    bg = Image.new("RGB", THUMB_SIZE, (245, 245, 245))
                    offset = (
                        (THUMB_SIZE[0] - img.width) // 2,
                        (THUMB_SIZE[1] - img.height) // 2,
                    )
                    bg.paste(img, offset)
                    images.append(bg)
                except Exception:
                    images.append(_placeholder_tile(label))
            else:
                images.append(_placeholder_tile(label))
            labels.append(label)

    if not images:
        return None

    label_h = 24
    strip_w = THUMB_SIZE[0] * len(images)
    strip_h = THUMB_SIZE[1] + label_h
    strip   = Image.new("RGB", (strip_w, strip_h), (255, 255, 255))
    draw    = ImageDraw.Draw(strip)

    for i, (img, lbl) in enumerate(zip(images, labels)):
        x = i * THUMB_SIZE[0]
        strip.paste(img, (x, 0))
        draw.text((x + 4, THUMB_SIZE[1] + 4), lbl, fill=(50, 50, 50))

    buf = io.BytesIO()
    strip.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _placeholder_tile(label: str) -> "Image.Image":
    tile = Image.new("RGB", THUMB_SIZE, (220, 220, 220))
    draw = ImageDraw.Draw(tile)
    draw.text((8, 8), f"[{label}]", fill=(80, 80, 80))
    return tile


# ── Audio helpers ─────────────────────────────────────────────────────────────

def transcribe_audio_file(path: str) -> str:
    """Use SpeechRecognition to transcribe a local WAV/AIFF/FLAC audio file."""
    if not SR_AVAILABLE:
        raise RuntimeError("SpeechRecognition not installed.")
    recogniser = sr.Recognizer()
    recogniser.energy_threshold = 300
    with sr.AudioFile(path) as source:
        audio = recogniser.record(source)
    return recogniser.recognize_google(audio)


def convert_to_wav(input_path: str) -> Optional[str]:
    """
    Convert any audio/video file to a mono 16-kHz WAV using ffmpeg.
    Returns path to the temp WAV file, or None if ffmpeg is unavailable.
    """
    try:
        out = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        out.close()
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-i", input_path,
                "-ar", "16000", "-ac", "1",
                "-f", "wav", out.name,
            ],
            capture_output=True,
            timeout=60,
        )
        if result.returncode == 0:
            return out.name
        logger.warning("ffmpeg conversion failed: %s", result.stderr.decode())
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.warning("ffmpeg not available: %s", exc)
        return None


# ── Text-to-Speech helpers ────────────────────────────────────────────────────

def text_to_speech_b64(text: str) -> tuple[Optional[str], Optional[str]]:
    """
    Convert text to speech audio, returning (base64_data, mime_type).

    Tries gTTS (online, MP3) first; falls back to pyttsx3 (offline, WAV).
    Returns (None, None) if neither library is available.
    """
    # --- gTTS (requires internet) ---
    if GTTS_AVAILABLE:
        try:
            tts = gTTS(text=text, lang='en', slow=False)
            buf = io.BytesIO()
            tts.write_to_fp(buf)
            buf.seek(0)
            return base64.b64encode(buf.read()).decode(), "audio/mpeg"
        except Exception as exc:
            logger.warning("gTTS failed: %s", exc)

    # --- pyttsx3 (offline fallback) ---
    if PYTTSX3_AVAILABLE:
        try:
            engine = pyttsx3.init()
            engine.setProperty('rate', 170)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                tmp_path = tmp.name
            engine.save_to_file(text, tmp_path)
            engine.runAndWait()
            with open(tmp_path, "rb") as f:
                data = f.read()
            os.unlink(tmp_path)
            return base64.b64encode(data).decode(), "audio/wav"
        except Exception as exc:
            logger.warning("pyttsx3 failed: %s", exc)

    return None, None


# ── Django views ──────────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name="dispatch")
class TranslateView(View):
    """
    POST /api/translate/

    Accepts multipart form data:
        mode  : "text" | "mic" | "file" | "video"
        text  : str   (when mode == "text")
        audio : file  (when mode == "mic" or "file"; WAV/AIFF/FLAC/MP3/WebM)
        video : file  (when mode == "video"; any container with an audio track)

    Returns JSON:
        transcript  — the text that was signed
        sequence    — list of { word, type, images }
        strip_b64   — base64 PNG sign strip  (null if Pillow not installed)
        audio_b64   — base64 TTS audio       (null if gTTS/pyttsx3 not installed)
        audio_mime  — MIME type of audio_b64 ("audio/mpeg" | "audio/wav")
    """

    def post(self, request):
        try:
            mode = request.POST.get("mode", "text")
            tmp_path: Optional[str] = None
            wav_path: Optional[str] = None

            # ── 1. Obtain transcript ───────────────────────────────────────
            if mode == "text":
                transcript = request.POST.get("text", "").strip()
                if not transcript:
                    return self._error("No text provided.", 400)

            elif mode in ("mic", "file"):
                audio_file = request.FILES.get("audio")
                if not audio_file:
                    return self._error("No audio file uploaded.", 400)

                suffix = Path(audio_file.name).suffix or ".wav"
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    for chunk in audio_file.chunks():
                        tmp.write(chunk)
                    tmp_path = tmp.name

                # Convert non-WAV formats (WebM from MediaRecorder, MP3, etc.)
                if suffix.lower() not in (".wav", ".aiff", ".aif", ".flac"):
                    wav_path = convert_to_wav(tmp_path)
                    transcribe_from = wav_path or tmp_path
                else:
                    transcribe_from = tmp_path

                try:
                    transcript = transcribe_audio_file(transcribe_from)
                except Exception as exc:
                    logger.error("Transcription error: %s", exc)
                    return self._error(f"Transcription failed: {exc}", 422)

            elif mode == "video":
                video_file = request.FILES.get("video")
                if not video_file:
                    return self._error("No video file uploaded.", 400)

                v_suffix = Path(video_file.name).suffix or ".mp4"
                with tempfile.NamedTemporaryFile(delete=False, suffix=v_suffix) as tmp:
                    for chunk in video_file.chunks():
                        tmp.write(chunk)
                    tmp_path = tmp.name

                # Extract audio track from video using ffmpeg
                wav_path = convert_to_wav(tmp_path)
                if not wav_path:
                    return self._error(
                        "Could not extract audio from video. "
                        "Please ensure ffmpeg is installed (sudo apt install ffmpeg).",
                        422,
                    )

                try:
                    transcript = transcribe_audio_file(wav_path)
                except Exception as exc:
                    logger.error("Video transcription error: %s", exc)
                    return self._error(f"Transcription failed: {exc}", 422)

            else:
                return self._error(f"Unknown mode: {mode!r}", 400)

            # ── 2. Build sign sequence ─────────────────────────────────────
            tokens = normalise(transcript)
            if not tokens:
                return self._error("No recognisable words in transcript.", 422)

            sequence = build_sequence(tokens)

            # ── 3. Generate sign strip image ──────────────────────────────
            strip_b64 = create_strip_b64(sequence)

            # ── 4. Generate TTS audio for the transcript ──────────────────
            audio_b64, audio_mime = text_to_speech_b64(transcript)

            # ── 5. Log to database ─────────────────────────────────────────
            try:
                TranslationLog.objects.create(
                    mode        = mode,
                    transcript  = transcript,
                    token_count = len(sequence),
                    sign_count  = sum(1 for e in sequence if e["type"] == "word"),
                    spell_count = sum(1 for e in sequence if e["type"] == "fingerspell"),
                )
            except Exception as exc:
                logger.warning("Could not write TranslationLog: %s", exc)

            # ── 6. Serialise and respond ───────────────────────────────────
            public_sequence = [
                {"word": e["word"], "type": e["type"], "images": e["images"]}
                for e in sequence
            ]

            return JsonResponse({
                "transcript": transcript,
                "sequence":   public_sequence,
                "strip_b64":  strip_b64,
                "audio_b64":  audio_b64,
                "audio_mime": audio_mime,
            })

        except Exception as exc:
            logger.exception("Unexpected error in TranslateView")
            return self._error(f"Internal server error: {exc}", 500)
        finally:
            # Clean up temp files
            for p in (tmp_path, wav_path):
                if p:
                    try:
                        os.unlink(p)
                    except OSError:
                        pass

    @staticmethod
    def _error(message: str, status: int = 400) -> JsonResponse:
        return JsonResponse({"error": message}, status=status)


@method_decorator(csrf_exempt, name="dispatch")
class TTSView(View):
    """
    POST /api/tts/

    Body (JSON): { "text": "Hello world" }

    Response (JSON):
        { "audio_b64": str, "mime": str }
    or
        { "error": str }  (if TTS libraries unavailable)
    """

    def post(self, request):
        try:
            try:
                body = json.loads(request.body)
            except json.JSONDecodeError:
                return self._error("Invalid JSON body.", 400)

            text = body.get("text", "").strip()
            if not text:
                return self._error("No text provided.", 400)
            if len(text) > 2000:
                return self._error("Text too long (max 2 000 characters).", 400)

            audio_b64, mime = text_to_speech_b64(text)
            if not audio_b64:
                return self._error(
                    "Text-to-speech unavailable. "
                    "Install gTTS (pip install gtts) or pyttsx3 (pip install pyttsx3).",
                    503,
                )

            return JsonResponse({"audio_b64": audio_b64, "mime": mime})

        except Exception as exc:
            logger.exception("Unexpected error in TTSView")
            return self._error(f"Internal server error: {exc}", 500)

    @staticmethod
    def _error(message: str, status: int = 400) -> JsonResponse:
        return JsonResponse({"error": message}, status=status)


class HistoryView(View):
    """
    GET /api/history/?limit=20

    Returns the most recent translation log entries (default 20, max 100).
    """

    def get(self, request):
        try:
            limit = min(int(request.GET.get("limit", 20)), 100)
        except (ValueError, TypeError):
            limit = 20

        logs = TranslationLog.objects.all()[:limit]
        items = [
            {
                "id":          log.id,
                "mode":        log.mode,
                "transcript":  log.transcript,
                "token_count": log.token_count,
                "sign_count":  log.sign_count,
                "spell_count": log.spell_count,
                "created_at":  log.created_at.isoformat(),
            }
            for log in logs
        ]
        return JsonResponse({"items": items})
