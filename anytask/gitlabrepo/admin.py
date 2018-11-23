from django.contrib import admin

from gitlabrepo.models import GitlabRepository, GitlabStudentRepository, GitlabFolder, GitlabStudentFolder, \
    GitlabFileUpload

admin.site.register(GitlabRepository)
admin.site.register(GitlabStudentRepository)
admin.site.register(GitlabFolder)
admin.site.register(GitlabStudentFolder)
admin.site.register(GitlabFileUpload)
