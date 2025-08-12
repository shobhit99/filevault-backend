from django.contrib import admin
from .models import StoredFile, UserFile

@admin.register(StoredFile)
class StoredFileAdmin(admin.ModelAdmin):
    list_display = ('file_hash', 's3_key', 'size', 'ref_count', 'created_at')
    search_fields = ('file_hash', 's3_key')

@admin.register(UserFile)
class UserFileAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'stored_file', 'created_at', 'updated_at', 'is_deleted')
    list_filter = ('user', 'is_deleted')
    search_fields = ('name', 'user__username')
