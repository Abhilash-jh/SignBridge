# SignBridge — Text · Audio · Video → ASL

A Django web application that converts text, microphone audio, uploaded audio files,
and video files into American Sign Language (ASL) sign sequences, with Text-to-Speech
playback and a downloadable sign-strip image.

---

## Features

| Feature | Description |
|---|---|
| **Text → ASL** | Type any sentence; words are matched to ASL signs or fingerspelled |
| **Mic → ASL** | Record live audio in-browser; transcribed via Google Speech-to-Text |
| **Audio file → ASL** | Upload WAV / AIFF / FLAC / MP3 / WebM; auto-converted & transcribed |
| **Video file → ASL** | Upload any video; ffmpeg extracts the audio track, then transcribes |
| **Text-to-Speech** | Transcript is spoken aloud via gTTS (online) or pyttsx3 (offline) |
| **Sign Strip** | All signs composed into a downloadable PNG strip (requires Pillow) |
| **History** | Every translation is logged to SQLite; viewable in the History panel |

---

## Quick Start

```bash
# 1. Clone / unzip the project
cd signbridge

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. (Linux) Install system libraries
sudo apt-get install -y ffmpeg portaudio19-dev

# 5. Apply database migrations
python manage.py migrate

# 6. Create a superuser (optional, for /admin)
python manage.py createsuperuser

# 7. Run the development server
python manage.py runserver
```

Open **http://127.0.0.1:8000/** in your browser.

---

## Project Structure

```
signbridge/                     ← Django project root
├── manage.py
├── requirements.txt
├── db.sqlite3                  ← created on first migrate
├── media/                      ← uploaded files + ASL image cache
├── static/                     ← project-level static files
├── static_root/                ← collectstatic output (production)
│
├── signbridge/                 ← Django project package
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py                 ← root URL config
│   ├── wsgi.py
│   └── asgi.py
│
└── asl_app/                    ← SignBridge application
    ├── __init__.py
    ├── apps.py
    ├── models.py               ← TranslationLog
    ├── views.py                ← TranslateView · TTSView · HistoryView
    ├── urls.py                 ← /api/translate/  /api/tts/  /api/history/
    ├── admin.py
    ├── migrations/
    │   ├── __init__.py
    │   └── 0001_initial.py
    └── templates/
        └── asl_app/
            └── index.html      ← single-page frontend
```

---

## API Reference

### `POST /api/translate/`

Accepts `multipart/form-data`:

| Field | Type | When required |
|---|---|---|
| `mode` | `"text"` \| `"mic"` \| `"file"` \| `"video"` | Always |
| `text` | string | `mode == "text"` |
| `audio` | file (WAV/AIFF/FLAC/MP3/WebM) | `mode == "mic"` or `"file"` |
| `video` | file (MP4/MOV/AVI/MKV/WebM) | `mode == "video"` |

Response JSON:

```json
{
  "transcript": "hello friend",
  "sequence": [
    { "word": "hello",  "type": "word",        "images": ["https://…/hello.jpg"] },
    { "word": "friend", "type": "word",        "images": ["https://…/friend.jpg"] }
  ],
  "strip_b64":  "<base64 PNG>",
  "audio_b64":  "<base64 MP3>",
  "audio_mime": "audio/mpeg"
}
```

### `POST /api/tts/`

Body JSON: `{ "text": "Hello world" }`

Response: `{ "audio_b64": "…", "mime": "audio/mpeg" }`

### `GET /api/history/?limit=20`

Response: `{ "items": [ { id, mode, transcript, token_count, sign_count, spell_count, created_at }, … ] }`

---

## Optional Dependencies

| Package | Purpose | Install |
|---|---|---|
| `gTTS` | Online TTS (MP3 via Google) | `pip install gtts` |
| `pyttsx3` | Offline TTS (WAV, no internet) | `pip install pyttsx3` |
| `Pillow` | Sign strip PNG generation | `pip install Pillow` |
| `ffmpeg` | Audio extraction from video / format conversion | OS package manager |
| `pyaudio` | Live mic support via SpeechRecognition | `pip install pyaudio` + portaudio |

All are optional — the app degrades gracefully when not installed.

---

## Production Deployment Checklist

1. Set `DEBUG = False` and update `ALLOWED_HOSTS` in `settings.py`
2. Generate a strong `SECRET_KEY`
3. Run `python manage.py collectstatic`
4. Use a production database (PostgreSQL recommended)
5. Serve with **gunicorn** behind **nginx**
6. Configure `MEDIA_ROOT` on persistent storage

```bash
pip install gunicorn
gunicorn signbridge.wsgi:application --bind 0.0.0.0:8000 --workers 4
```
