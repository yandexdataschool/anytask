from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


if not hasattr(settings, 'GITLAB_HOST'):
    raise ImproperlyConfigured('GITLAB_HOST setting is required.')

if not hasattr(settings, 'GITLAB_PRIVATE_TOKEN'):
    raise ImproperlyConfigured('GITLAB_PRIVATE_TOKEN setting is required.')
