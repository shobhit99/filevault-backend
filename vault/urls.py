from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    RegisterView, LoginView, LogoutView, TokenVerifyView, S3StatusView,
    FileUploadView, FileListView, FileDeleteView, FileDownloadView,
    FolderCreateView
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('token/verify/', TokenVerifyView.as_view(), name='token-verify'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('s3/status/', S3StatusView.as_view(), name='s3-status'),
    path('files/upload/', FileUploadView.as_view(), name='file-upload'),
    path('files/', FileListView.as_view(), name='file-list'),
    path('files/<uuid:file_id>/download/', FileDownloadView.as_view(), name='file-download'),
    path('files/<uuid:file_id>/', FileDeleteView.as_view(), name='file-delete'),
    path('folders/', FolderCreateView.as_view(), name='folder-create'),
]
