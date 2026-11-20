from io import BytesIO
from multipart_service import InfraiClient, MediaUpload, upload_media


def main() -> None:
    media = MediaUpload("clips/demo.mov", "video/quicktime", 11)
    result = upload_media(InfraiClient(), "creator-media", media, BytesIO(b"hello world"), chunk_size=5)
    print({"status": "published", "object_key": media.object_key, "result": result})


if __name__ == "__main__":
    main()
