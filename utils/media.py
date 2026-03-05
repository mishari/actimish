"""
Shared media utilities for upload and processing.
"""
import os


def detect_mime(header_bytes, filename=""):
    """
    Detect MIME type from file header bytes, falling back to extension.
    
    Args:
        header_bytes: First ~2KB of file as bytes
        filename: Optional filename for extension fallback
    
    Returns:
        MIME type string (e.g., "image/jpeg") or None
    """
    # Magic bytes detection
    if header_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if header_bytes[:2] == b"\xff\xd8":
        return "image/jpeg"
    if header_bytes[:4] == b"GIF8":
        return "image/gif"
    if header_bytes[:4] == b"RIFF" and header_bytes[8:12] == b"WEBP":
        return "image/webp"
    if header_bytes[4:8] == b"ftyp":
        return "video/mp4"
    if header_bytes[:4] == b"\x1a\x45\xdf\xa3":
        return "video/webm"

    # Fall back to extension
    if filename:
        ext = os.path.splitext(filename)[1].lower()
        ext_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".mp4": "video/mp4",
            ".webm": "video/webm",
            ".mov": "video/quicktime",
        }
        return ext_map.get(ext)
    
    return None
