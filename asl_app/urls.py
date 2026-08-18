"""
urls.py — URL routing for the asl_app (SignBridge API).

Include in your project's root urls.py:

    from django.urls import path, include
    urlpatterns = [
        path('api/', include('asl_app.urls', namespace='asl_app')),
    ]

Registered URLs:
    POST /api/translate/    — text / audio / video → ASL sign sequence + TTS
    POST /api/tts/          — text → speech audio (base64)
    GET  /api/history/      — recent translation log entries
"""

from django.urls import path
from .views import TranslateView, TTSView, HistoryView

app_name = "asl_app"

urlpatterns = [
    # Core translation endpoint (text, mic, file, video → signs)
    path("translate/", TranslateView.as_view(), name="translate"),

    # Standalone text-to-speech endpoint
    path("tts/",       TTSView.as_view(),       name="tts"),

    # Translation history (read-only)
    path("history/",   HistoryView.as_view(),   name="history"),
]
