try:
    from django.conf.urls import *
except ImportError:  # django < 1.4
    from django.conf.urls.defaults import *

# place app url patterns here
urlpatterns = patterns(
    'gitlabrepo.views',
    url(r'^hooks/(?P<student_repo_id>\d+)$', 'project_hook_view'),
)
