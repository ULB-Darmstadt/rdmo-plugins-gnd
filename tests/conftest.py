from pathlib import Path

import django
from django.conf import settings


def pytest_configure():
    if not settings.configured:
        settings.configure(
            USE_I18N=True,
            LANGUAGE_CODE='en',
            LOCALE_PATHS=[str(Path(__file__).resolve().parents[1] / 'rdmo_gnd' / 'locale')],
        )
        django.setup()
