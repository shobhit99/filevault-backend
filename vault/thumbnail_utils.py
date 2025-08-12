from PIL import Image
from moviepy import VideoFileClip
import psutil
from io import BytesIO
import os

def generate_image_thumbnail(file_obj):
    try:
        file_obj.seek(0)
        image = Image.open(file_obj)
        image.thumbnail((128, 128))
        thumb_io = BytesIO()
        image.save(thumb_io, format='JPEG')
        thumb_io.seek(0)
        return thumb_io
    except Exception:
        # Log error
        return None

def generate_video_thumbnail(file_obj):
    import tempfile
    temp_file_path = None
    try:
        # Check available memory to avoid crashing
        if psutil.virtual_memory().available < 1 * 1024 * 1024 * 1024: # 1 GB
            return None

        file_obj.seek(0)
        # Create a secure temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.tmp') as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(file_obj.read())
        
        clip = VideoFileClip(temp_file_path)
        frame = clip.get_frame(1) # Get frame at 1 second
        clip.close()
        
        image = Image.fromarray(frame)
        image.thumbnail((128, 128))
        
        thumb_io = BytesIO()
        image.save(thumb_io, format='JPEG')
        thumb_io.seek(0)
        return thumb_io
    except Exception:
        # Log error
        return None
    finally:
        # Always cleanup temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except OSError:
                pass  # File might already be deleted

def generate_thumbnail(file_obj, filename):
    file_type = filename.split('.')[-1].lower()
    if file_type in ['jpg', 'jpeg', 'png', 'gif']:
        return generate_image_thumbnail(file_obj)
    elif file_type in ['mp4', 'mov', 'avi', 'mkv']:
        return generate_video_thumbnail(file_obj)
    return None
