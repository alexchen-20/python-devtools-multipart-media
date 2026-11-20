import io
from multipart_service import MediaUpload, release_check, upload_media


class FakeClient:
    def __init__(self):
        self.parts = []
    def ensure_bucket(self, name): self.bucket = name
    def create_upload(self, bucket, key, content_type): return "upload-1"
    def presign_part(self, upload_id, number): self.parts.append(number); return "data:text/plain,unused"
    def complete(self, upload_id, parts): return {"upload_id": upload_id, "parts": parts}


def test_release_check_and_chunk_decision(monkeypatch):
    media = MediaUpload("exports/take.mov", "video/quicktime", 6)
    assert release_check(media) == "ready"
    client = FakeClient()
    monkeypatch.setattr("multipart_service.urlopen", lambda request, timeout: FakeResponse())
    result = upload_media(client, "media", media, io.BytesIO(b"abcdef"), chunk_size=4)
    assert client.parts == [1, 2]
    assert result["parts"][1]["part_number"] == 2


class FakeResponse:
    headers = {"ETag": "etag-demo"}
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self): return b""
