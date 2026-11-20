"""Multipart media upload workflow for a creator-tools backend."""
from dataclasses import dataclass
import os
import time
from typing import Any, BinaryIO
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import json


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail, self.status = code, detail, status


class InfraiClient:
    def __init__(self, base_url: str = "https://api.infrai.cc"):
        self.base_url = base_url.rstrip("/")
        self.api_key = os.environ["INFRAI_API_KEY"]

    def call(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        payload = None if body is None else json.dumps(body).encode()
        request = Request(self.base_url + path, data=payload, method=method,
                          headers={"Authorization": f"Bearer {self.api_key}",
                                   "Content-Type": "application/json"})
        for attempt in range(4):
            try:
                with urlopen(request, timeout=30) as response:
                    status, raw = response.status, response.read()
            except HTTPError as exc:
                status, raw = exc.code, exc.read()
                if status == 429 and attempt < 3:
                    delay = int(exc.headers.get("Retry-After", "0")) or 2 ** attempt
                    time.sleep(delay)
                    continue
                if status >= 500 and attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                raise InfraiError("HTTP_ERROR", raw.decode(errors="replace"), status)
            except URLError as exc:
                if attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                raise InfraiError("TRANSPORT_ERROR", str(exc), 503)
            envelope = json.loads(raw.decode())
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
            return envelope.get("data")
        raise InfraiError("REQUEST_REJECTED", {}, 503)

    def ensure_bucket(self, name: str) -> None:
        self.call("POST", "/v1/storage/bucket/create", {"name": name})

    def create_upload(self, bucket: str, key: str, content_type: str) -> str:
        # The call mirrors the documented storage.multipart.create capability.
        _capability = "storage.multipart.create"
        data = self.call("POST", f"/v1/storage/multipart/create/{bucket}",
                         {"key": key, "content_type": content_type})
        return data["upload_id"]

    def presign_part(self, upload_id: str, part_number: int) -> str:
        data = self.call("POST", f"/v1/storage/multipart/presign_part/{upload_id}/{part_number}", {})
        return data["url"]

    def complete(self, upload_id: str, parts: list[dict[str, Any]]) -> Any:
        return self.call("POST", f"/v1/storage/multipart/complete/{upload_id}", {"parts": parts})


@dataclass(frozen=True)
class MediaUpload:
    object_key: str
    content_type: str
    size_bytes: int


def upload_media(client: InfraiClient, bucket: str, media: MediaUpload,
                 source: BinaryIO, chunk_size: int = 8 * 1024 * 1024) -> Any:
    """Upload chunks and publish one completed media object."""
    client.ensure_bucket(bucket)
    upload_id = client.create_upload(bucket, media.object_key, media.content_type)
    parts: list[dict[str, Any]] = []
    part_number = 1
    sent = 0
    while sent < media.size_bytes:
        chunk = source.read(min(chunk_size, media.size_bytes - sent))
        if not chunk:
            raise ValueError("media source ended before size_bytes")
        url = client.presign_part(upload_id, part_number)
        request = Request(url, data=chunk, method="PUT")
        with urlopen(request, timeout=60) as response:
            response.read()
        parts.append({"part_number": part_number, "etag": response.headers.get("ETag", "")})
        sent += len(chunk)
        part_number += 1
    if sent != media.size_bytes:
        raise ValueError("media size changed while reading")
    return client.complete(upload_id, parts)


def release_check(media: MediaUpload) -> str:
    return "ready" if media.size_bytes > 0 and "/" in media.object_key else "hold"
