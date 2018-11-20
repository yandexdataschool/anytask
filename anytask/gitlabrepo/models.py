import base64

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save, post_delete, m2m_changed, pre_save, post_init
from django.utils import timezone
import unicodedata

import gitlab

from courses.models import Course
from courses.signals import after_save
from issues.models import Issue, File
from tasks.models import Task
from .utils import slugify

gl = gitlab.Gitlab(settings.GITLAB_HOST, private_token=settings.GITLAB_PRIVATE_TOKEN)


class GitlabRepository(models.Model):
    course = models.OneToOneField(Course, related_name='gitlab_repository')
    name = models.CharField(max_length=255, db_index=True, unique=True)

    created_at = models.DateTimeField(auto_now_add=True, default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True, default=timezone.now)

    def __unicode__(self):
        return unicode(self.name)


class GitlabStudentRepository(models.Model):
    repository = models.ForeignKey(GitlabRepository, related_name='instances')


class GitlabFolder(models.Model):
    task = models.OneToOneField(Task, related_name='gitlab_folder')
    name = models.CharField(max_length=255, db_index=True, unique=True)

    created_at = models.DateTimeField(auto_now_add=True, default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True, default=timezone.now)

    def __unicode__(self):
        return unicode(self.name)


class GitlabStudentFolder(models.Model):
    issue = models.OneToOneField(Issue, related_name='gitlab_folder')
    name = models.CharField(max_length=255, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True, default=timezone.now)

    def __unicode__(self):
        return unicode(self.name)


class GitlabFileUpload(models.Model):
    file = models.ForeignKey(File, related_name='gitlab_uploads')

    STATUS_WAITING = 'waiting'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = (
        (STATUS_WAITING, 'Waiting'),
        (STATUS_SUCCESS, 'Success'),
        (STATUS_FAILED,  'Failed'),
    )
    status = models.CharField(choices=STATUS_CHOICES, max_length=20, default=STATUS_WAITING)

    created_at = models.DateTimeField(auto_now_add=True, default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True, default=timezone.now)

    def __unicode__(self):
        return unicode(self.file.filename())


def course_post_save_handler(sender, instance, created, **kwargs):
    print('course post save:', instance.name)

    if not instance.gitlab_integrated:
        return

    repo_name = instance.name_id or slugify(instance.name)

    if not hasattr(instance, 'gitlab_repository'):
        repo = GitlabRepository.objects.create(course=instance, name=repo_name)
    else:
        repo = GitlabRepository.objects.get(course=instance)
        if not repo.name == repo_name:
            repo.name = repo_name
            repo.save()

    # create teacher group
    try:
        teacher_group = gl.groups.get(repo.name)
    except gitlab.GitlabGetError as e:
        if not e.response_code == 404:
            raise e

        teacher_group = gl.groups.create({
            'name': repo.name.capitalize(),
            'path': repo.name,
        })


def course_changed(instance, **kwargs):
    if not instance.gitlab_integrated:
        return

    print('course changed:', instance)

    teacher_group = gl.groups.get(instance.gitlab_repository.name)

    # update teacher group
    if not instance.teachers.exists():
        for member in teacher_group.members.list():
            if not member.access_level == gitlab.OWNER_ACCESS:
                member.delete()
        return

    teachers = {}
    usernames = set()

    for t in instance.teachers.all():
        teachers[t.username] = t
        usernames.add(t.username)

    for member in teacher_group.members.list():
        if member.access_level == gitlab.OWNER_ACCESS:
            continue

        if member.username not in usernames:
            member.delete()
        else:
            usernames.remove(member.username)

    for name in usernames:
        teacher = teachers[name]
        gitlab_user_list = gl.users.list(username=name)

        if not gitlab_user_list:
            gitlab_user = gl.users.create({
                'email': teacher.email,
                'password': 'qwe123qwe',
                'username': name,
                'name': teacher.get_full_name(),
            })
        else:
            gitlab_user = gitlab_user_list[0]

        teacher_group.members.create({
            'user_id': gitlab_user.id,
            'access_level': gitlab.DEVELOPER_ACCESS,
        })


def course_post_delete_handler(sender, instance, **kwargs):
    pass


def task_post_save_handler(instance, **kwargs):
    if not instance.course.gitlab_integrated:
        return

    print('task post save:', instance)

    folder_name = slugify(instance.short_title)

    if not hasattr(instance, 'gitlab_folder'):
        gitlab_folder = GitlabFolder.objects.create(task=instance, name=folder_name)
    else:
        gitlab_folder = GitlabFolder.objects.get(task=instance)

        if not gitlab_folder.name == folder_name:
            gitlab_folder.name = folder_name
            gitlab_folder.save()


def make_project_readme(instance, **kwargs):
    return '# {}\n'.format(instance.name)


def make_issue_readme(instance, **kwargs):
    task = instance.task
    return '# {}\n\n{}\n'.format(task.title, task.task_text)


def issue_post_save_handler(instance, created, **kwargs):
    course = instance.task.course
    if not course.gitlab_integrated:
        return

    print('issue post save:', instance)

    if not created:
        return

    folder_name = instance.task.gitlab_folder.name
    student = instance.student
    repo = course.gitlab_repository

    if not hasattr(instance, 'gitlab_folder'):
        gitlab_folder = GitlabStudentFolder.objects.create(issue=instance, name=folder_name)
    else:
        gitlab_folder = instance.gitlab_folder

    # create student account
    gitlab_user_list = gl.users.list(username=student.username)

    gitlab_user_created = False
    if not gitlab_user_list:
        gitlab_user = gl.users.create({
            'email': student.email,
            'password': 'qwe123qwe',
            'username': student.username,
            'name': student.get_full_name(),
        })
        gitlab_user_created = True
    else:
        gitlab_user = gitlab_user_list[0]

    # create student repository
    try:
        gitlab_project = gl.projects.get('{}/{}'.format(student.username, repo.name))

    except gitlab.GitlabGetError as e:
        if not e.response_code == 404:
            raise e

        gitlab_project = gitlab_user.projects.create({
            'path': repo.name,
            'name': repo.name.capitalize(),
            'description': course.information,
            'visibility': gitlab.VISIBILITY_PRIVATE,
        })

        # create project README
        gitlab_project.files.create({
            'file_path': 'README.md',
            'branch': 'master',
            'content': '# %s' % instance.task.course.name,
            'commit_message': 'add project README',
        })

    # share project to teacher group
    teacher_group = gl.groups.get(repo.name)
    gitlab_project.share(teacher_group.id, gitlab.MASTER_ACCESS)

    # create issue README
    gitlab_project.files.create({
        'file_path': '%s/README.md' % gitlab_folder.name,
        'branch': 'master',
        'content': make_issue_readme(instance),
        'commit_message': 'add README.md',
    })


def issue_file_post_save_handler(instance, created, **kwargs):
    issue = instance.event.issue

    if not issue.task.course.gitlab_integrated or not created:
        return

    print('issue file post:', instance)

    repo = issue.task.course.gitlab_repository
    gitlab_project = gl.projects.get('%s/%s' %(issue.student.username, repo.name))

    file_path = '%s/%s' % (issue.gitlab_folder.name, instance.filename())
    content = base64.b64encode(instance.file.read()).decode()
    try:
        project_file = gitlab_project.files.get(file_path=file_path, ref='master')
        project_file.content = content
        project_file.save(
            branch='master',
            author_email=issue.student.email,
            author_name=issue.student.username,
            commit_message='update file %s' % instance.filename(),
            encoding='base64')

    except gitlab.GitlabGetError as e:
        if not e.response_code == 404:
            raise e

        gitlab_project.files.create({
            'file_path': file_path,
            'branch': 'master',
            'content': content,
            'author_email': issue.student.email,
            'author_name': issue.student.username,
            'commit_message': 'upload %s' % (instance.filename()),
            'encoding': 'base64',
        })


post_save.connect(course_post_save_handler, sender=Course)
post_delete.connect(course_post_delete_handler, sender=Course)

post_save.connect(task_post_save_handler, sender=Task)
post_save.connect(issue_post_save_handler, sender=Issue)
post_save.connect(issue_file_post_save_handler, sender=File)


after_save.connect(course_changed, sender=Course)
