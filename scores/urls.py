from django.conf.urls import url

from . import views


app_name = 'scores'
urlpatterns = [

    url(r'^contest/$', views.ContestList.as_view(), name='contest_list'),
    url(r'^contest/(?P<pk>[0-9]+)/$', views.ContestView.as_view(), name='contest_detail'),
    url(r'^contest/upload/$', views.ContestUpload, name='contest_upload'),
    url(r'^contestant/$', views.ContestantList.as_view(), name='contestant_list'),
    url(r'^contestant/(?P<slug>[\w-]+)/$', views.ContestantView.as_view(), name='contestant_detail'),
    url(r'^song/$', views.SongList.as_view(), name='song_list'),
    url(r'^song/(?P<slug>[\w-]+)/$', views.SongView.as_view(), name='song_detail'),
    url(r'^person/$', views.PersonList.as_view(), name='person_list'),
    url(r'^person/(?P<slug>[\w-]+)/$', views.PersonView.as_view(), name='person_detail'),
    url(r'^person/(?P<slug>[\w-]+)/update/$', views.PersonUpdate.as_view(success_url="/scores/person/{slug}/"), name='person_update'),
    url(r'^import/$', views.Import, name='import'),
    url(r'^import_rtf/$', views.import_rtf_view, name='import_rtf'),
    url(r'^update_aliases/$', views.UpdateAliases, name='update_aliases'),
    url(r'^person_autocomplete/$', views.PersonAutocomplete.as_view(create_field='name'), name='person_autocomplete'),
]