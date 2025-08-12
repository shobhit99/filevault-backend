# Abnormal File Vault: Plan & API Documentation

This document outlines the plan for building the Abnormal File Vault application and provides a detailed specification for the backend API.

## 1. Development Plan

The development will be structured as follows:

1.  **Project Setup**: Initialize a new Django app `vault` within the `filevaultBackend` project. Install necessary dependencies: `djangorestframework`, `boto3`, `django-cors-headers`, `psycopg2-binary` (for production-readiness with PostgreSQL).
2.  **Database Models**: Define the database schema for users and files. We will use Django's built-in `User` model. For files, we'll create two models to handle file metadata and storage deduplication.
3.  **API Development**:
    *   **Authentication**: Implement user registration, login, and logout endpoints using session-based authentication.
    *   **File Upload**: Create an endpoint to upload files. This will include logic to calculate the file's hash, check for its existence to avoid duplicates, and upload the file to an AWS S3 bucket.
    *   **File Listing & Filtering**: Develop an endpoint to list a user's files with support for filtering by file attributes.
    *   **File Deletion**: Implement an endpoint to delete a file. This will include logic for handling the reference count for deduplicated files.
4.  **API Documentation**: This document will serve as the primary API documentation.
5.  **Testing**: Create a Postman collection for manual testing of the API endpoints.
6.  **Containerization**: Dockerize the Django application for easy deployment and scalability.

## 2. Standard API Response Format

All API responses will follow a consistent format to ensure predictability for the frontend client.

**Success Response:**

```json
{
  "success": true,
  "message": "Descriptive success message.",
  "data": {
    "key": "value"
  }
}
```

**Error Response:**

```json
{
  "success": false,
  "message": "Descriptive error message.",
  "data": null
}
```

## 3. Database Schema

### `auth.User` (Django's built-in User model)

*   `id`
*   `username`
*   `password` (hashed)
*   `email`
*   ...and other default fields.

### `vault.StoredFile`

This model represents a unique file stored in S3.

*   `id` (UUID): Primary key.
*   `file_hash` (CharField, unique): The SHA-256 hash of the file content. Used for deduplication.
*   `s3_key` (CharField): The key of the file in the S3 bucket (we will use the hash as the key).
*   `size` (BigIntegerField): Size of the file in bytes.
*   `ref_count` (PositiveIntegerField): A reference counter to track how many `UserFile` entries point to this stored file.
*   `created_at` (DateTimeField): Timestamp of creation.

### `vault.UserFile`

This model represents a file as seen by a user. It links a user to a stored file.

*   `id` (UUID): Primary key.
*   `user` (ForeignKey to `auth.User`): The owner of the file.
*   `stored_file` (ForeignKey to `vault.StoredFile`): The actual file data.
*   `folder` (ForeignKey to `vault.Folder`): The folder containing the file (can be null for root).
*   `name` (CharField): The name of the file as provided by the user.
*   `created_at` (DateTimeField): Timestamp of creation.
*   `updated_at` (DateTimeField): Timestamp of last update.
*   `is_deleted` (BooleanField): A flag for soft deletion.

## 4. API Endpoints

### Authentication

#### 1. User Registration

*   **Endpoint**: `POST /api/register/`
*   **Description**: Creates a new user account.
*   **Request Body**:
    ```json
    {
      "username": "testuser",
      "password": "strongpassword123",
      "email": "user@example.com"
    }
    ```
*   **Success Response (201 Created)**:
    ```json
    {
      "success": true,
      "message": "User registered successfully.",
      "data": {
        "id": 1,
        "username": "testuser",
        "email": "user@example.com"
      }
    }
    ```
*   **Error Response (400 Bad Request)**: For invalid data or if the user already exists.

#### 2. User Login

*   **Endpoint**: `POST /api/login/`
*   **Description**: Authenticates a user and creates a session.
*   **Request Body**:
    ```json
    {
      "username": "testuser",
      "password": "strongpassword123"
    }
    ```
*   **Success Response (200 OK)**: The session cookie (`sessionid`) will be set in the response headers.
    ```json
    {
      "success": true,
      "message": "Login successful.",
      "data": {
        "id": 1,
        "username": "testuser"
      }
    }
    ```
*   **Error Response (400 Bad Request)**: For invalid credentials.

#### 3. User Logout

*   **Endpoint**: `POST /api/logout/`
*   **Description**: Logs out the current user and clears the session.
*   **Authentication**: Session authentication required.
*   **Success Response (200 OK)**:
    ```json
    {
      "success": true,
      "message": "Logout successful.",
      "data": null
    }
    ```

### File Management

#### 4. Upload File

*   **Endpoint**: `POST /api/files/upload/`
*   **Description**: Uploads a file, performs deduplication, and stores it in S3.
*   **Authentication**: Session authentication required.
*   **Request Type**: `multipart/form-data`
*   **Request Body**:
    *   `file`: The file to be uploaded.
    *   `folder_id` (UUID, optional): The ID of the folder to upload the file into.
*   **Success Response (201 Created)**:
    ```json
    {
      "success": true,
      "message": "File uploaded successfully.",
      "data": {
        "id": "uuid-goes-here",
        "name": "document.pdf",
        "size": 123456,
        "created_at": "YYYY-MM-DDTHH:MM:SSZ"
      }
    }
    ```
*   **Error Response (400 Bad Request)**: If no file is provided.

#### 5. Get Files

*   **Endpoint**: `GET /api/files/`
*   **Description**: Retrieves a list of files and folders for the authenticated user. Supports filtering and browsing folders.
*   **Authentication**: Session authentication required.
*   **Query Parameters (Optional)**:
    *   `folder_id` (UUID): The ID of the folder to browse. If not provided, returns root-level items.
    *   `name`: Filter by file/folder name (contains, case-insensitive).
    *   `ordering`: `name`, `-name`, `created_at`, `-created_at`.
*   **Success Response (200 OK)**:
    ```json
    {
      "success": true,
      "message": "Files retrieved successfully.",
      "data": {
        "files": [
          {
            "id": "uuid-goes-here",
            "name": "document1.pdf",
            "size": 123456,
            "created_at": "YYYY-MM-DDTHH:MM:SSZ",
            "s3_url": "presigned-s3-url-for-download",
            "thumbnail_url": "presigned-s3-url-for-thumbnail"
          }
        ],
        "folders": [
          {
            "id": "folder-uuid-goes-here",
            "name": "My Documents",
            "parent": null,
            "created_at": "YYYY-MM-DDTHH:MM:SSZ"
          }
        ],
        "storage_used": 5000000,
        "storage_limit": 15000000000
      }
    }
    ```

#### 6. Delete File

*   **Endpoint**: `DELETE /api/files/<uuid:file_id>/`
*   **Description**: Deletes a user's file record. If no other user references the file, it is deleted from S3.
*   **Authentication**: Session authentication required.
*   **Success Response (200 OK)**:
    ```json
    {
      "success": true,
      "message": "File deleted successfully.",
      "data": null
    }
    ```
*   **Error Response (404 Not Found)**: If the file does not exist or does not belong to the user.

### Folder Management

#### 7. Create Folder

*   **Endpoint**: `POST /api/folders/`
*   **Description**: Creates a new folder.
*   **Authentication**: Session authentication required.
*   **Request Body**:
    ```json
    {
      "name": "New Folder",
      "parent": "parent-folder-uuid"
    }
    ```
*   **Success Response (201 Created)**:
    ```json
    {
      "success": true,
      "message": "Folder created successfully.",
      "data": {
        "id": "new-folder-uuid",
        "name": "New Folder",
        "parent": "parent-folder-uuid",
        "created_at": "YYYY-MM-DDTHH:MM:SSZ"
      }
    }
    ```
