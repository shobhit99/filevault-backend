from django.contrib.auth.models import User
from rest_framework import serializers
from .models import UserFile, StoredFile, Folder, UserProfile
from .s3_utils import s3_client

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ('storage_limit', 'storage_used')

class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password', 'profile')
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user

class StoredFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoredFile
        fields = ('size',)

class UserFileSerializer(serializers.ModelSerializer):
    size = serializers.IntegerField(source='stored_file.size', read_only=True)
    s3_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = UserFile
        fields = ('id', 'name', 'size', 'created_at', 's3_url', 'thumbnail_url', 'folder')

    def get_s3_url(self, obj):
        try:
            url = s3_client.generate_presigned_url(obj.stored_file.s3_key)
            print(f"Generated S3 URL for {obj.stored_file.s3_key}: {url}")
            return url
        except Exception as e:
            print(f"Failed to generate S3 URL for {obj.stored_file.s3_key}: {e}")
            return None
    
    def get_thumbnail_url(self, obj):
        if obj.stored_file.thumbnail_s3_key:
            try:
                url = s3_client.generate_presigned_url(obj.stored_file.thumbnail_s3_key)
                print(f"Generated thumbnail URL for {obj.stored_file.thumbnail_s3_key}: {url}")
                return url
            except Exception as e:
                print(f"Failed to generate thumbnail URL for {obj.stored_file.thumbnail_s3_key}: {e}")
                return None
        return None

class FolderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Folder
        fields = ('id', 'name', 'parent', 'created_at')
        extra_kwargs = {
            'user': {'read_only': True},
        }
