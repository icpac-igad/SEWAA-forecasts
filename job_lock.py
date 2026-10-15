"""Single-run lock for one forecast channel (dataset + accumulation).

Cloud Scheduler starts a Cloud Run Job execution every 30 minutes whether or not the
previous one has finished, and Cloud Run doesn't prevent overlapping executions. A run
longer than the schedule interval (e.g. catching up several IMERG 6h init times) would
otherwise overlap the next one: both executions would run the same expensive inference
and race on the same output files and available_dates.json.

With CGAN_LOCK_BUCKET set (cloudbuild.yaml sets it to the forecast data bucket), the lock
is an object `locks/<channel>.lock` in that bucket:

  - acquire: create the object with `ifGenerationMatch=0`. GCS guarantees only one
    creator succeeds; everyone else gets HTTP 412 and skips this run.
  - heartbeat: the holder updates the object's metadata every HEARTBEAT_SECONDS, which
    bumps its `updated` time.
  - stale: a lock whose `updated` time is older than STALE_SECONDS belongs to a run that
    died without releasing it (OOM kill, task timeout). It is deleted with generation +
    metageneration preconditions (so a lock that just heartbeated is never stolen) and
    acquisition is retried once.
  - release: delete the object, on normal exit and on SIGTERM.

Uses only the standard library and the metadata server for credentials, so it adds no
dependency. Without CGAN_LOCK_BUCKET (docker-compose, local runs) it falls back to an
flock on a local file, which stops overlapping runs on the same machine.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import signal
import socket
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

HEARTBEAT_SECONDS = int(os.environ.get("CGAN_LOCK_HEARTBEAT_SECONDS", "60"))
STALE_SECONDS = int(os.environ.get("CGAN_LOCK_STALE_SECONDS", "600"))

_METADATA_TOKEN_URL = (
    "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"
)
_GCS_API = "https://storage.googleapis.com/storage/v1"
_GCS_UPLOAD_API = "https://storage.googleapis.com/upload/storage/v1"


class LockHeld(Exception):
    """Another live run holds the lock."""


def _holder_id() -> str:
    # CLOUD_RUN_EXECUTION identifies the job execution; fall back to host + pid.
    return os.environ.get("CLOUD_RUN_EXECUTION") or f"{socket.gethostname()}:{os.getpid()}"


# ── GCS backend ──────────────────────────────────────────────────────────────


class _GcsLock:
    def __init__(self, bucket: str, name: str):
        self.bucket = bucket
        self.name = name
        self.generation: str | None = None
        self._token: str | None = None
        self._token_expiry = 0.0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # -- HTTP helpers --

    def _access_token(self) -> str:
        if self._token is None or time.time() > self._token_expiry - 60:
            req = urllib.request.Request(_METADATA_TOKEN_URL, headers={"Metadata-Flavor": "Google"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.load(resp)
            self._token = data["access_token"]
            self._token_expiry = time.time() + int(data.get("expires_in", 300))
        return self._token

    def _request(self, method: str, url: str, body: bytes | None = None, content_type: str | None = None):
        headers = {"Authorization": f"Bearer {self._access_token()}"}
        if content_type:
            headers["Content-Type"] = content_type
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}

    def _object_url(self, **params) -> str:
        url = f"{_GCS_API}/b/{self.bucket}/o/{urllib.parse.quote(self.name, safe='')}"
        return f"{url}?{urllib.parse.urlencode(params)}" if params else url

    # -- lock protocol --

    def _try_create(self) -> bool:
        params = urllib.parse.urlencode({"uploadType": "media", "name": self.name, "ifGenerationMatch": "0"})
        body = json.dumps({"holder": _holder_id(), "acquired": datetime.now(timezone.utc).isoformat()}).encode()
        try:
            obj = self._request("POST", f"{_GCS_UPLOAD_API}/b/{self.bucket}/o?{params}", body, "application/json")
        except urllib.error.HTTPError as err:
            if err.code == 412:  # object already exists
                return False
            raise
        self.generation = obj["generation"]
        return True

    def _remove_if_stale(self) -> bool:
        """Delete the existing lock if its holder stopped heartbeating. True if removed."""
        try:
            obj = self._request("GET", self._object_url())
        except urllib.error.HTTPError as err:
            if err.code == 404:  # released meanwhile
                return True
            raise
        updated = datetime.fromisoformat(obj["updated"].replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - updated).total_seconds()
        if age < STALE_SECONDS:
            holder = (obj.get("metadata") or {}).get("holder", "unknown")
            raise LockHeld(f"{self.name} held by {holder} (last heartbeat {int(age)}s ago)")
        print(f"[lock] {self.name} is stale (last heartbeat {int(age)}s ago); removing it")
        try:
            self._request(
                "DELETE",
                self._object_url(ifGenerationMatch=obj["generation"], ifMetagenerationMatch=obj["metageneration"]),
            )
        except urllib.error.HTTPError as err:
            if err.code in (404, 412):  # someone else removed or refreshed it first
                return err.code == 404
            raise
        return True

    def _heartbeat(self) -> None:
        while not self._stop.wait(HEARTBEAT_SECONDS):
            try:
                body = json.dumps({"metadata": {"holder": _holder_id(), "heartbeat": str(int(time.time()))}}).encode()
                self._request("PATCH", self._object_url(ifGenerationMatch=self.generation), body, "application/json")
            except Exception as err:  # keep running; a missed beat only risks a stale-steal later
                print(f"[lock] heartbeat for {self.name} failed: {err}", file=sys.stderr)

    def acquire(self) -> None:
        if not self._try_create():
            if not (self._remove_if_stale() and self._try_create()):
                raise LockHeld(f"{self.name} was taken by another run")
        print(f"[lock] acquired gs://{self.bucket}/{self.name}")
        self._thread = threading.Thread(target=self._heartbeat, daemon=True)
        self._thread.start()

    def release(self) -> None:
        self._stop.set()
        if self.generation is None:
            return
        try:
            self._request("DELETE", self._object_url(ifGenerationMatch=self.generation))
            print(f"[lock] released gs://{self.bucket}/{self.name}")
        except urllib.error.HTTPError as err:
            if err.code not in (404, 412):
                print(f"[lock] failed to release {self.name}: {err}", file=sys.stderr)
        self.generation = None


# ── local backend ────────────────────────────────────────────────────────────


class _FileLock:
    def __init__(self, name: str):
        self.path = os.path.join(tempfile.gettempdir(), name.replace("/", "_"))
        self._fh = None

    def acquire(self) -> None:
        self._fh = open(self.path, "w")
        try:
            fcntl.flock(self._fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self._fh.close()
            self._fh = None
            raise LockHeld(f"{self.path} is locked by another local run") from None

    def release(self) -> None:
        if self._fh:
            fcntl.flock(self._fh, fcntl.LOCK_UN)
            self._fh.close()
            self._fh = None


# ── public API ───────────────────────────────────────────────────────────────


@contextlib.contextmanager
def channel_lock(channel: str):
    """Hold the lock for `channel` (e.g. "imerg-6h") for the duration of the block.

    Raises LockHeld if another live run holds it.
    """
    name = f"locks/{channel}.lock"
    bucket = os.environ.get("CGAN_LOCK_BUCKET")
    lock = _GcsLock(bucket, name) if bucket else _FileLock(f"cgan-{channel}.lock")
    lock.acquire()

    # Cloud Run sends SIGTERM before killing a task (timeout, cancellation): release the
    # lock so the next scheduled run doesn't have to wait for it to go stale.
    previous = signal.getsignal(signal.SIGTERM)

    def _on_sigterm(signum, frame):
        lock.release()
        signal.signal(signal.SIGTERM, previous if callable(previous) else signal.SIG_DFL)
        os.kill(os.getpid(), signal.SIGTERM)

    signal.signal(signal.SIGTERM, _on_sigterm)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous)
        lock.release()
