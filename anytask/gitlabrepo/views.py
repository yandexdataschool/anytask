# Create your views here.
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import HttpResponse, HttpResponseNotFound, HttpResponseBadRequest

import logging


logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(['POST'])
def project_hook_view(request):
    pass