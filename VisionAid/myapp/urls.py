from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('capture_frame/', views.capture_frame_view, name='capture_frame'),
]
