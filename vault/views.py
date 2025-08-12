from django.contrib.auth import authenticate
from rest_framework import generics, status, renderers
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import UserSerializer, UserFileSerializer, FolderSerializer
from .models import StoredFile, UserFile, Folder
from .s3_utils import s3_client
from .thumbnail_utils import generate_thumbnail
import hashlib

class CustomJSONRenderer(renderers.JSONRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        response_data = {}
        response = renderer_context['response']

        if 'success' in data and 'message' in data:
            response_data = data
        elif response.status_code >= 400:
            response_data['success'] = False
            response_data['message'] = data.get('detail', 'An error occurred.')
            response_data['data'] = data
        else:
            response_data['success'] = True
            response_data['message'] = 'Operation successful.'
            response_data['data'] = data

        return super().render(response_data, accepted_media_type, renderer_context)


class RegisterView(generics.CreateAPIView):
    serializer_class = UserSerializer
    permission_classes = [AllowAny]
    renderer_classes = [CustomJSONRenderer]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            {"success": True, "message": "User registered successfully.", "data": serializer.data},
            status=status.HTTP_201_CREATED,
            headers=headers
        )

class LoginView(APIView):
    permission_classes = [AllowAny]
    renderer_classes = [CustomJSONRenderer]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            access_token = refresh.access_token
            
            return Response({
                "success": True,
                "message": "Login successful.",
                "data": {
                    "user": UserSerializer(user).data,
                    "access": str(access_token),
                    "refresh": str(refresh),
                }
            })
            
        return Response({
            "success": False,
            "message": "Invalid credentials.",
            "data": None
        }, status=status.HTTP_400_BAD_REQUEST)


class TokenVerifyView(APIView):
    renderer_classes = [CustomJSONRenderer]

    def get(self, request):
        if request.user.is_authenticated:
            return Response({
                "success": True,
                "message": "Token is valid.",
                "data": UserSerializer(request.user).data
            })
        return Response({
            "success": False,
            "message": "Token is invalid or expired.",
            "data": None
        }, status=status.HTTP_401_UNAUTHORIZED)


class LogoutView(APIView):
    renderer_classes = [CustomJSONRenderer]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
        except Exception:
            pass  # Token might already be blacklisted or invalid
        
        return Response({
            "success": True,
            "message": "Logout successful.",
            "data": None
        })


class S3StatusView(APIView):
    permission_classes = [AllowAny]
    renderer_classes = [CustomJSONRenderer]

    def get(self, request):
        """Check S3 connection status and configuration"""
        from django.conf import settings
        
        # Check if S3 settings are configured
        s3_config = {
            'AWS_ACCESS_KEY_ID': bool(settings.AWS_ACCESS_KEY_ID),
            'AWS_SECRET_ACCESS_KEY': bool(settings.AWS_SECRET_ACCESS_KEY),
            'AWS_STORAGE_BUCKET_NAME': settings.AWS_STORAGE_BUCKET_NAME,
            'AWS_S3_REGION_NAME': settings.AWS_S3_REGION_NAME,
        }
        
        # Check S3 connection
        connection_status, connection_message = s3_client.check_connection()
        
        return Response({
            "success": True,
            "message": "S3 status check completed",
            "data": {
                "s3_config": s3_config,
                "connection_status": connection_status,
                "connection_message": connection_message,
                "s3_client_initialized": s3_client.client is not None,
            }
        })


class FileUploadView(APIView):
    renderer_classes = [CustomJSONRenderer]

    def post(self, request):
        file_obj = request.FILES.get('file')
        folder_id = request.data.get('folder_id')

        if not file_obj:
            return Response({"success": False, "message": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)

        # Check storage quota
        profile = request.user.profile
        if profile.storage_used + file_obj.size > profile.storage_limit:
            return Response({"success": False, "message": "Storage limit exceeded."}, status=status.HTTP_400_BAD_REQUEST)

        # Calculate file hash
        sha256 = hashlib.sha256()
        for chunk in file_obj.chunks():
            sha256.update(chunk)
        file_hash = sha256.hexdigest()

        # Reset file pointer
        file_obj.seek(0)

        # Generate thumbnail
        thumbnail_obj = generate_thumbnail(file_obj, file_obj.name)
        thumbnail_s3_key = None
        if thumbnail_obj:
            thumbnail_s3_key = f"thumb_{file_hash}.jpg"
        
        # Reset file pointer after thumbnail generation
        file_obj.seek(0)

        # Deduplication check
        stored_file, created = StoredFile.objects.get_or_create(
            file_hash=file_hash,
            defaults={
                'size': file_obj.size,
                's3_key': file_hash,
                'thumbnail_s3_key': thumbnail_s3_key
            }
        )

        print(f"Stored file: {stored_file}")

        if created:
            print(f"Uploading new file to S3 with key: {file_hash}")
            upload_success = s3_client.upload_fileobj(file_obj, file_hash)
            print(f"S3 upload result: {upload_success}")
            
            if not upload_success:
                print(f"Failed to upload file {file_hash} to S3")
                stored_file.delete()
                return Response({"success": False, "message": "Failed to upload file to S3."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            if thumbnail_obj:
                print(f"Uploading thumbnail to S3 with key: {thumbnail_s3_key}")
                thumbnail_upload_success = s3_client.upload_fileobj(thumbnail_obj, thumbnail_s3_key)
                print(f"Thumbnail upload result: {thumbnail_upload_success}")

            stored_file.ref_count = 1
            stored_file.save()
            print(f"File successfully uploaded to S3 and saved to database")
        else:
            print(f"File already exists in database, incrementing ref_count")
            stored_file.ref_count += 1
            stored_file.save()
        
        # Get folder
        folder = None
        if folder_id:
            try:
                folder = Folder.objects.get(id=folder_id, user=request.user)
            except Folder.DoesNotExist:
                return Response({"success": False, "message": "Folder not found."}, status=status.HTTP_404_NOT_FOUND)

        # Create a UserFile instance
        user_file, created = UserFile.objects.get_or_create(
            user=request.user,
            name=file_obj.name,
            folder=folder,
            defaults={'stored_file': stored_file}
        )

        print("user file", user_file)

        if not created:
            # If file with same name exists, update it
            old_stored_file = user_file.stored_file
            old_file_size = old_stored_file.size
            
            # Update to new stored file
            user_file.stored_file = stored_file
            user_file.save()
            
            # Update storage calculation (subtract old, add new if different)
            if old_stored_file != stored_file:
                profile.storage_used = profile.storage_used - old_file_size + file_obj.size
                profile.save()
                
                # Decrement old file reference count
                old_stored_file.ref_count -= 1
                old_stored_file.save()
                
                # Delete old file from S3 if no longer referenced
                if old_stored_file.ref_count == 0:
                    s3_client.delete_object(old_stored_file.s3_key)
                    if old_stored_file.thumbnail_s3_key:
                        s3_client.delete_object(old_stored_file.thumbnail_s3_key)
                    old_stored_file.delete()
        else:
            # Update storage used
            profile.storage_used += file_obj.size
            profile.save()

        serializer = UserFileSerializer(user_file)
        return Response({
            "success": True,
            "message": "File uploaded successfully.",
            "data": serializer.data
        }, status=status.HTTP_201_CREATED)


class FileListView(generics.ListAPIView):
    serializer_class = UserFileSerializer
    renderer_classes = [CustomJSONRenderer]
    pagination_class = None # We are handling pagination manually

    def get_queryset(self):
        # This method is kept for compatibility but the main logic is in `list`
        return UserFile.objects.filter(user=self.request.user, is_deleted=False)

    def list(self, request, *args, **kwargs):
        folder_id = request.query_params.get('folder_id')
        
        # Get root files and folders if no folder_id is provided
        files_queryset = UserFile.objects.filter(user=request.user, is_deleted=False, folder_id=folder_id)
        folders_queryset = Folder.objects.filter(user=request.user, parent_id=folder_id)
        
        # Filtering
        name = request.query_params.get('name')
        if name:
            files_queryset = files_queryset.filter(name__icontains=name)
            folders_queryset = folders_queryset.filter(name__icontains=name)

        # Ordering
        ordering = request.query_params.get('ordering')
        if ordering in ['name', '-name', 'created_at', '-created_at']:
            files_queryset = files_queryset.order_by(ordering)
            folders_queryset = folders_queryset.order_by(ordering)
        elif ordering == 'size':
            # For size ordering, we need to order by the related StoredFile's size
            files_queryset = files_queryset.order_by('stored_file__size')
            # Folders don't have size, so we'll keep them at the top
            folders_queryset = folders_queryset.order_by('name')
        elif ordering == '-size':
            # For descending size ordering
            files_queryset = files_queryset.order_by('-stored_file__size')
            # Folders don't have size, so we'll keep them at the top
            folders_queryset = folders_queryset.order_by('name')
        else:
            # Default ordering by name if no valid ordering is provided
            files_queryset = files_queryset.order_by('name')
            folders_queryset = folders_queryset.order_by('name')
        
        # Combine and serialize
        files_data = self.get_serializer(files_queryset, many=True).data
        folders_data = FolderSerializer(folders_queryset, many=True).data

        # Debug logging removed for production
        
        combined_data = {
            'files': files_data,
            'folders': folders_data,
            'storage_used': request.user.profile.storage_used,
            'storage_limit': request.user.profile.storage_limit
        }
        
        return Response(combined_data)


class FolderCreateView(generics.CreateAPIView):
    serializer_class = FolderSerializer
    renderer_classes = [CustomJSONRenderer]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class FileDeleteView(APIView):
    renderer_classes = [CustomJSONRenderer]

    def delete(self, request, file_id):
        try:
            user_file = UserFile.objects.get(id=file_id, user=request.user, is_deleted=False)
        except UserFile.DoesNotExist:
            return Response({"success": False, "message": "File not found."}, status=status.HTTP_404_NOT_FOUND)

        # Recalculate storage
        file_size = user_file.stored_file.size
        profile = request.user.profile
        profile.storage_used -= file_size
        profile.save()

        # Soft delete the user file
        user_file.is_deleted = True
        user_file.save()

        # Decrement ref count on the stored file
        stored_file = user_file.stored_file
        stored_file.ref_count -= 1
        stored_file.save()

        # If no other user is using this file, delete it from S3
        if stored_file.ref_count == 0:
            if s3_client.delete_object(stored_file.s3_key):
                stored_file.delete()
            else:
                # If S3 deletion fails, we should probably log this
                # and maybe have a cleanup job for orphaned S3 files.
                # For now, we'll restore the ref_count and soft delete status
                stored_file.ref_count += 1
                stored_file.save()
                user_file.is_deleted = False
                user_file.save()
                # Also restore storage used
                profile.storage_used += file_size
                profile.save()
                return Response({"success": False, "message": "Failed to delete file from S3."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


        return Response({"success": True, "message": "File deleted successfully."}, status=status.HTTP_200_OK)


class FileDownloadView(APIView):
    renderer_classes = [CustomJSONRenderer]

    def get(self, request, file_id):
        try:
            user_file = UserFile.objects.get(id=file_id, user=request.user, is_deleted=False)
        except UserFile.DoesNotExist:
            return Response({"success": False, "message": "File not found."}, status=status.HTTP_404_NOT_FOUND)

        stored_file = user_file.stored_file
        print(f"Generating presigned URL for file: {stored_file.s3_key}")
        
        # Generate presigned URL for download
        presigned_url = s3_client.generate_presigned_url(stored_file.s3_key, expiration=3600)
        print(f"Generated presigned URL: {presigned_url}")
        
        if not presigned_url:
            return Response({"success": False, "message": "Failed to generate download URL."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            "success": True,
            "message": "Download URL generated successfully.",
            "data": {
                "download_url": presigned_url,
                "filename": user_file.name,
                "size": stored_file.size
            }
        })
