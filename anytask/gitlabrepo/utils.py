import re
import unicodedata
from transliterate import translit

from django.utils.safestring import mark_safe


def slugify(value, allow_unicode=False, allow_translit=True):
    """
    Convert to ASCII if 'allow_unicode' is False. Convert spaces to hyphens.
    Remove characters that aren't alphanumerics, underscores, or hyphens.
    Convert to lowercase. Also strip leading and trailing whitespace.
    """
    # value = str(value)
    if allow_translit:
        value = translit(value, 'ru', reversed=True)

    if allow_unicode:
        value = unicodedata.normalize('NFKC', value)
    else:
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value).strip().lower()
    return mark_safe(re.sub(r'[-\s]+', '-', value))