from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='TranslationLog',
            fields=[
                ('id',          models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mode',        models.CharField(choices=[('text', 'Text Input'), ('mic', 'Microphone'), ('file', 'Audio File')], default='text', max_length=10)),
                ('transcript',  models.TextField(help_text='The transcribed or typed text.')),
                ('token_count', models.PositiveIntegerField(default=0, help_text='Number of tokens/words in the sequence.')),
                ('sign_count',  models.PositiveIntegerField(default=0, help_text='Words resolved to a whole-word sign.')),
                ('spell_count', models.PositiveIntegerField(default=0, help_text='Words resolved by fingerspelling.')),
                ('created_at',  models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
            ],
            options={'ordering': ['-created_at'], 'verbose_name': 'Translation Log', 'verbose_name_plural': 'Translation Logs'},
        ),
    ]
