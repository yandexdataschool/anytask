# -*- coding: utf-8 -*-

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

    class Meta:
        verbose_name_plural = 'gitlab repositories'


class GitlabStudentRepository(models.Model):
    repository = models.ForeignKey(GitlabRepository, related_name='instances')
    student = models.ForeignKey(User, related_name='gitlab_repositories')

    created_at = models.DateTimeField(auto_now_add=True, default=timezone.now)

    class Meta:
        verbose_name_plural = 'gitlab student repositories'


class GitlabFolder(models.Model):
    repository = models.ForeignKey(GitlabRepository, related_name='folders')
    task = models.OneToOneField(Task, related_name='gitlab_folder')
    name = models.CharField(max_length=255, db_index=True, unique=True)

    created_at = models.DateTimeField(auto_now_add=True, default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True, default=timezone.now)

    def __unicode__(self):
        return unicode(self.name)


class GitlabStudentFolder(models.Model):
    repository = models.ForeignKey(GitlabStudentRepository, related_name='folders')
    folder = models.ForeignKey(GitlabFolder, related_name='instances')
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

    repo = instance.course.gitlab_repository
    folder_name = slugify(instance.short_title or instance.title)

    if not hasattr(instance, 'gitlab_folder'):

        try:
            GitlabFolder.objects.create(
                repository=repo,
                task=instance,
                name=folder_name,
            )
        except gitlab.GitlabCreateError:
            pass

    else:
        gitlab_folder = GitlabFolder.objects.get(task=instance)

        if not gitlab_folder.name == folder_name:
            gitlab_folder.name = folder_name
            gitlab_folder.save()


def make_project_readme(instance, **kwargs):
    return '\n'.join([
        u'# {}'.format(instance.name),
        '\n{}/course/{}'.format(settings.GITLAB_ANYTASK_REDIRECT_URL, instance.id),
        u'\n\n{}'.format(instance.information),
    ])


def make_issue_readme(instance, **kwargs):
    task = instance.task
    return u'\n'.join([
        u'# {}'.format(task.title),
        '\n{}/issue/{}'.format(settings.GITLAB_ANYTASK_REDIRECT_URL, instance.id),
        u'\n{}'.format(task.task_text),
    ])


def issue_post_save_handler(instance, created, **kwargs):
    course = instance.task.course
    if not course.gitlab_integrated:
        return

    if not created:
        return

    folder_name = instance.task.gitlab_folder.name
    student = instance.student
    repo = course.gitlab_repository

    if not hasattr(instance, 'gitlab_folder'):
        gitlab_folder = GitlabStudentFolder.objects.create(
            repository=repo,
            folder=instance.task.gitlab_folder,
            issue=instance,
            name=folder_name,
        )
    else:
        gitlab_folder = instance.gitlab_folder

    # create student account
    gitlab_user_list = gl.users.list(username=student.username)

    if not gitlab_user_list:
        gitlab_user = gl.users.create({
            'email': student.email,
            'password': 'qwe123qwe',
            'username': student.username,
            'name': student.get_full_name(),
        })
    else:
        gitlab_user = gitlab_user_list[0]

    # create student repository
    try:
        gitlab_project = gl.projects.get('{}/{}'.format(student.username, repo.name))

    except gitlab.GitlabGetError as e:
        if not e.response_code == 404:
            raise e

        user_project = gitlab_user.projects.create({
            'path': repo.name,
            'name': repo.name.capitalize(),
            'description': course.information,
            'visibility': 'private',
        })

        gitlab_project = gl.projects.get(user_project.id)

        # create project README
        gitlab_project.files.create({
            'file_path': 'README.md',
            'branch': 'master',
            'content': make_project_readme(instance.task.course),
            'commit_message': 'add project README',
        })

        # create student repo
        student_repo = GitlabStudentRepository.objects.create(
            repository=repo,
            student=student,
        )

        # add project hook
        gitlab_project.hooks.create({
            'url': '{}/gitlab/hooks/{}'.format(settings.GITLAB_ANYTASK_REDIRECT_URL, student_repo.id),
            'push_events': 1,
            'merge_requests_events': 1,
            'note_events': 1,
            'enable_ssl_verification': 0,
        })

    # share project to teacher group
    teacher_group = gl.groups.get(repo.name)
    try:
        gitlab_project.share(teacher_group.id, gitlab.MASTER_ACCESS)
    except gitlab.GitlabCreateError as e:
        if not e.response_code == 409:
            raise e

    # create issue README
    gitlab_project.files.create({
        'file_path': '%s/README.md' % gitlab_folder.name,
        'branch': 'master',
        'content': make_issue_readme(instance),
        'commit_message': "add new task: {}".format(gitlab_folder.name),
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
