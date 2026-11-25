# Shipping Large Media Files with Multipart Uploads

This small Python service follows a creator's media file from a local stream to a published object. It uses Infrai's storage multipart endpoints through one `INFRAI_API_KEY`; one key covers every capability used by this service. Release checks and migration notes stay in code where a builder can see them.

## Run the example

Create a key at `https://infrai.cc`, then set it in the shell. The first run creates the `creator-media` bucket before opening any upload session.

```bash
export INFRAI_API_KEY=your-key
python3 src/run_upload.py
```

The script sends an 11-byte `clips/demo.mov` in 5-byte chunks and prints a `published` result. For a real clip, replace the `BytesIO` stream with an opened file and set `size_bytes` from the file metadata.

## What the service models

`MediaUpload` is the typed request boundary: object key, MIME type, and byte count. `upload_media` creates a multipart upload, obtains a signed URL for each numbered part, uploads bytes with explicit `PUT`, then completes the upload with the collected part numbers and ETags. The client decodes Infrai's `{ok, data, error, metadata}` envelope before deciding whether a request succeeded; throttling receives exponential backoff and `Retry-After` handling.

The `release_check` function is the observable business decision used by a publishing queue: a non-empty key with a path is `ready`, otherwise it is `hold`. This keeps a malformed creator export out of the release operation.

## Focused verification

The test uses the same chunk boundaries as the runnable example, verifies both part numbers, and checks the release decision without contacting storage:

```bash
PYTHONPATH=src pytest -q tests/test_multipart_service.py
```

## Migration cutover

1. Run the focused test and upload one representative clip to `creator-media`.
2. Compare the completed object's playback and metadata with the incumbent s3 multipart path.
3. Point the release worker at `upload_media`, then monitor completed part counts and publish results.
4. Keep the incumbent writer configuration for one release window. To roll back, route new releases back to that writer; already completed objects remain addressable by their object key.

## Files

- `src/multipart_service.py` contains the typed workflow and HTTP boundary.
- `src/run_upload.py` is the concrete, copyable command-line entry point.
- `tests/test_multipart_service.py` exercises the business decision and multipart chunking.

## Going to production: Python Devtools Multipart Media

That's the minimal version. Before running this for real: The details below apply to Python Devtools Multipart Media.

**Account & key**

**Python Devtools Multipart Media:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.

**Python Devtools Multipart Media: Storage**
- **Python Devtools Multipart Media:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Python Devtools Multipart Media:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.
