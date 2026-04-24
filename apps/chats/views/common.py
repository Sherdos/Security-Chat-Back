import mimetypes

from django.contrib.auth import get_user_model

from ..models import MessageAttachment

User = get_user_model()


def detect_attachment_type(uploaded_file):
    mime_type, _ = mimetypes.guess_type(uploaded_file.name)
    if mime_type:
        if mime_type.startswith("image/"):
            return MessageAttachment.ATTACHMENT_IMAGE
        if mime_type.startswith("video/"):
            return MessageAttachment.ATTACHMENT_VIDEO
        if mime_type.startswith("audio/"):
            return MessageAttachment.ATTACHMENT_AUDIO
    return MessageAttachment.ATTACHMENT_FILE
