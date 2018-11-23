from django.conf.urls import patterns, include, url
from django.conf import settings
from django.views.generic.base import TemplateView

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns(
    '',
    url(r'^admin/', include(admin.site.urls)),
    url(r'^course/', include('courses.urls')),
    url(r'^issue/', include('issues.urls')),
    url(r'^school/', include('schools.urls')),
    url(r'^task/', include('tasks.urls')),
    url(r'^user/', include('users.urls')),
    url(r'^users/(?P<username>.*)/', 'users.views.users_redirect'),
    url(r'^setlanguage/', 'users.views.set_user_language'),
    url(r'^invites/', include('invites.urls')),
    url(r'^anyrb/', include('anyrb.urls')),
    url(r'^accounts/logout/$', 'django.contrib.auth.views.logout', {'next_page': '/'}),
    url(r'^accounts/profile/(?P<username>.*)/(?P<year>\d+)', 'users.views.profile'),
    url(r'^accounts/profile/(?P<username>.*)', 'users.views.profile'),
    url(r'^accounts/profile', 'users.views.profile'),
    url(r'^accounts/', include('registration.backends.default_with_names.urls')),
    url(r'^static/(?P<path>.*)$', 'django.views.static.serve', {'document_root': settings.STATIC_ROOT}),
    url(r'^media/(?P<path>.*)$', 'django.views.static.serve', {'document_root': settings.MEDIA_ROOT}),
    url(r'^about$', TemplateView.as_view(template_name='about.html')),
    url(r'^$', 'index.views.index'),
    url(r'^search/', include('search.urls')),
    url(r'^staff', include('staff.urls')),
    url(r'^blog/', include('blog.urls')),
    url(r'^mail/', include('mail.urls')),
    url(r'^admission/', include('admission.urls')),
    url(r'^shad2017/register', 'admission.views.register'),
    url(r'^shad2017/activate/(?P<activation_key>\w+)/', 'admission.views.activate'),
    url(r'^shad2017/decline/(?P<activation_key>\w+)/', 'admission.views.decline'),
    url(r'^lesson/', include('lessons.urls')),
    url(r'^api/', include('api.urls')),
    url(r'^jupyter/', include('jupyter.urls')),
    url(r'^gitlab/', include('gitlabrepo.urls')),
)
