import mimetypes

from django.contrib.auth import get_user_model

from ..models import MessageAttachment

User = get_user_model()


def detect_attachment_type(attachment_type):
    if attachment_type:
        if attachment_type == "image":
            return MessageAttachment.ATTACHMENT_IMAGE
        if attachment_type == "video":
            return MessageAttachment.ATTACHMENT_VIDEO
        if attachment_type == "audio":
            return MessageAttachment.ATTACHMENT_AUDIO
    return MessageAttachment.ATTACHMENT_FILE
