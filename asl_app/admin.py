from django.contrib import admin
from .models import TranslationLog


@admin.register(TranslationLog)
class TranslationLogAdmin(admin.ModelAdmin):
    list_display  = ('id', 'mode', 'short_transcript', 'token_count', 'sign_count', 'spell_count', 'created_at')
    list_filter   = ('mode', 'created_at')
    search_fields = ('transcript',)
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)

    def short_transcript(self, obj):
        return obj.transcript[:80] + ('…' if len(obj.transcript) > 80 else '')
    short_transcript.short_description = 'Transcript'
