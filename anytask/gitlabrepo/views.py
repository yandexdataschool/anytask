# Create your views here.
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import HttpResponse, HttpResponseNotFound, HttpResponseBadRequest

import logging
import json
import os

from .models import GitlabStudentRepository

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(['POST'])
def project_hook_view(request, student_repo_id):
    data = json.loads(request.body)
    print('project hook for repo:', student_repo_id, data)

    student_repo = GitlabStudentRepository.objects.get(pk=student_repo_id)

    try:
        object_kind = data['object_kind']

        # handle comment events
        if object_kind == 'note':
            user = data['user']

            try:
                author = User.objects.get(username=user['username'])
            except User.DoesNotExist:
                author = User.objects.get(username='admin')

            # project_path = data['project']['path_with_namespace']
            position_new_path = data['object_attributes']['position']['new_path']
            folder_path = os.path.normpath(position_new_path).split(os.sep)[0]
            folder_matched = list(student_repo.folders.filter(name=os.path.basename(folder_path)))
            student_folder = folder_matched[0] if folder_matched else None

            print('note is sent', 'author:', author, 'project_path:', folder_path, student_folder)

            if student_folder:
                object_url = data['object_attributes']['url']
                msg = u'A new comment: <a href="{}">Details</a>'.format(object_url)
                student_folder.issue.add_comment(msg, author=author)

    except KeyError as e:
        print('Event error:', e)

    return HttpResponse('OK')