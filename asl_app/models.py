"""
models.py — Database models for SignBridge.

TranslationLog: persists every translation request for analytics and history.
"""

from django.db import models
from django.utils import timezone


class TranslationLog(models.Model):
    """Records each translation request for history and analytics."""

    MODE_CHOICES = [
        ('text', 'Text Input'),
        ('mic',  'Microphone'),
        ('file', 'Audio File'),
    ]

    mode        = models.CharField(max_length=10, choices=MODE_CHOICES, default='text')
    transcript  = models.TextField(help_text='The transcribed or typed text.')
    token_count = models.PositiveIntegerField(default=0, help_text='Number of tokens/words in the sequence.')
    sign_count  = models.PositiveIntegerField(default=0, help_text='Words resolved to a whole-word sign.')
    spell_count = models.PositiveIntegerField(default=0, help_text='Words resolved by fingerspelling.')
    created_at  = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Translation Log'
        verbose_name_plural = 'Translation Logs'

    def __str__(self):
        return f"[{self.mode}] {self.transcript[:60]}… ({self.created_at:%Y-%m-%d %H:%M})"
