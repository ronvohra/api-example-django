from django.conf.urls import include, url
from django.contrib.auth import views as oauth

from drchrono import views


urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'', include('social.apps.django_app.urls', namespace='social')),
    url(r'^login/$', oauth.login, name='login'),
    url(r'^login_page/', views.login_page, name='login_page'),
    url(r'^logout/$', views.logout, name='logout'),
    url(r'^checkin/', views.checkin_patient, name='checkin'),
    url(r'^walkin/', views.register_walkin_patient, name='walkin'),
    url(r'^demographics/', views.update_demographics, name='demographics'),
    url(r'^call_in_patient/', views.call_in_patient, name='call_in_patient'),
    url(r'^appointment_completed/', views.appointment_completed, name='appointment_completed'),
    url(r'^poll_for_updates/', views.poll_for_updates, name='poll_for_updates')
]
