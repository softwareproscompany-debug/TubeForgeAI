"""YouTube Data API integration: OAuth helpers, resumable uploads, metadata,
analytics, the publication upload state machine, and content integrity checks."""

import os
from difflib import SequenceMatcher
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.utils import timezone

from core.utils import UpstreamError

YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]
_OAUTH_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
_OAUTH_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
_YT_API = "https://www.googleapis.com/youtube/v3"
_YT_UPLOAD_API = "https://www.googleapis.com/upload/youtube/v3"
_YT_ANALYTICS_API = "https://youtubeanalytics.googleapis.com/v2"


class YouTubeError(UpstreamError):
    default_code = "YOUTUBE_ERROR"
    default_detail = "A YouTube API request failed."


# ---------------------------------------------------------------------------
# OAuth helpers
# ---------------------------------------------------------------------------
def build_authorization_url(state):
    params = {
        "client_id": settings.YOUTUBE_CLIENT_ID,
        "redirect_uri": settings.YOUTUBE_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(YOUTUBE_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{_OAUTH_AUTH_URL}?{urlencode(params)}"


def _token_request(data):
    try:
        response = requests.post(_OAUTH_TOKEN_URL, data=data, timeout=30)
    except requests.RequestException as exc:
        raise YouTubeError(f"Token endpoint unreachable: {type(exc).__name__}") from exc
    if response.status_code != 200:
        raise YouTubeError(f"Token request failed with HTTP {response.status_code}.")
    return response.json()


def exchange_code(code):
    return _token_request(
        {
            "client_id": settings.YOUTUBE_CLIENT_ID,
            "client_secret": settings.YOUTUBE_CLIENT_SECRET,
            "redirect_uri": settings.YOUTUBE_REDIRECT_URI,
            "grant_type": "authorization_code",
            "code": code,
        }
    )


def refresh_access_token(refresh_token):
    return _token_request(
        {
            "client_id": settings.YOUTUBE_CLIENT_ID,
            "client_secret": settings.YOUTUBE_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
    )


def revoke(token):
    try:
        requests.post(_OAUTH_REVOKE_URL, data={"token": token}, timeout=15)
    except requests.RequestException as exc:
        raise YouTubeError(f"Revoke unreachable: {type(exc).__name__}") from exc


def tokeninfo(access_token):
    try:
        response = requests.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"access_token": access_token},
            timeout=15,
        )
    except requests.RequestException as exc:
        raise YouTubeError(f"tokeninfo unreachable: {type(exc).__name__}") from exc
    if response.status_code != 200:
        raise YouTubeError("Access token is not valid.")
    return response.json()


def get_channel_info(access_token):
    client = YouTubeClient(access_token)
    data = client._api("GET", "/channels", params={"part": "snippet", "mine": "true"})
    items = data.get("items", [])
    if not items:
        raise YouTubeError("No YouTube channel found for this account.")
    return {"id": items[0]["id"], "title": items[0]["snippet"].get("title", "")}


# ---------------------------------------------------------------------------
# YouTube API client
# ---------------------------------------------------------------------------
class RetryableUploadError(YouTubeError):
    default_code = "UPLOAD_RETRYABLE"


class YouTubeClient:
    def __init__(self, access_token):
        self.access_token = access_token

    def _headers(self, extra=None):
        headers = {"Authorization": f"Bearer {self.access_token}"}
        if extra:
            headers.update(extra)
        return headers

    def _api(self, method, path, params=None, json_body=None, timeout=30):
        try:
            response = requests.request(
                method,
                _YT_API + path,
                headers=self._headers(),
                params=params,
                json=json_body,
                timeout=timeout,
            )
        except requests.RequestException as exc:
            raise YouTubeError(
                f"YouTube API unreachable: {type(exc).__name__}"
            ) from exc
        if response.status_code == 401:
            raise YouTubeError(
                "YouTube authorization required (token expired/revoked)."
            )
        if response.status_code == 403 and "quota" in response.text.lower():
            raise YouTubeError("YouTube API quota exceeded.")
        if response.status_code >= 400:
            raise YouTubeError(f"YouTube API HTTP {response.status_code}.")
        return response.json()

    # -- resumable upload: initiate -> upload chunks -> reconcile ----------------
    def initiate_resumable_upload(
        self, metadata, file_size_bytes, mime_type="video/mp4"
    ):
        try:
            response = requests.post(
                f"{_YT_UPLOAD_API}/videos",
                params={"uploadType": "resumable", "part": "snippet,status"},
                headers=self._headers(
                    {
                        "Content-Type": "application/json; charset=UTF-8",
                        "X-Upload-Content-Length": str(file_size_bytes),
                        "X-Upload-Content-Type": mime_type,
                    }
                ),
                json=metadata,
                timeout=30,
            )
        except requests.RequestException as exc:
            raise RetryableUploadError(
                f"Upload initiation unreachable: {type(exc).__name__}"
            ) from exc
        if response.status_code not in (200, 201):
            raise RetryableUploadError(
                f"Upload initiation HTTP {response.status_code}."
            )
        session_uri = response.headers.get("Location")
        if not session_uri:
            raise YouTubeError("Upload initiation did not return a session URI.")
        return session_uri

    def _query_upload_offset(self, session_uri, file_size_bytes):
        response = requests.put(
            session_uri,
            headers=self._headers(
                {"Content-Length": "0", "Content-Range": f"bytes */{file_size_bytes}"}
            ),
            timeout=30,
        )
        if response.status_code == 308:
            uploaded_range = response.headers.get("Range", "")
            if uploaded_range.startswith("bytes=0-"):
                return int(uploaded_range.split("-")[1]) + 1
            return 0
        if response.status_code in (200, 201):
            return file_size_bytes
        raise RetryableUploadError(f"Upload reconcile HTTP {response.status_code}.")

    def upload_chunks(
        self, session_uri, file_path, file_size_bytes, chunk_size=8 * 1024 * 1024
    ):
        offset = 0
        with open(file_path, "rb") as handle:
            while offset < file_size_bytes:
                handle.seek(offset)
                chunk = handle.read(chunk_size)
                end = offset + len(chunk) - 1
                try:
                    response = requests.put(
                        session_uri,
                        headers=self._headers(
                            {
                                "Content-Length": str(len(chunk)),
                                "Content-Range": f"bytes {offset}-{end}/{file_size_bytes}",
                            }
                        ),
                        data=chunk,
                        timeout=300,
                    )
                except requests.RequestException:
                    offset = self._query_upload_offset(session_uri, file_size_bytes)
                    continue
                if response.status_code == 308:
                    offset = end + 1
                    continue
                if response.status_code in (200, 201):
                    return response.json()
                if response.status_code >= 500 or response.status_code == 429:
                    # Reconcile with the server before retrying the chunk.
                    offset = self._query_upload_offset(session_uri, file_size_bytes)
                    continue
                raise YouTubeError(f"Upload chunk HTTP {response.status_code}.")
        # Final reconcile in case the last chunk response was lost.
        status_response = requests.put(
            session_uri,
            headers=self._headers(
                {"Content-Length": "0", "Content-Range": f"bytes */{file_size_bytes}"}
            ),
            timeout=30,
        )
        if status_response.status_code in (200, 201):
            return status_response.json()
        raise RetryableUploadError(
            "Upload finished without a video resource; retry reconcile."
        )

    def upload_video(
        self, file_path, title, description="", tags=(), privacy_status="private"
    ):
        file_size = os.path.getsize(file_path)
        metadata = {
            "snippet": {"title": title, "description": description, "tags": list(tags)},
            "status": {"privacyStatus": privacy_status},
        }
        session_uri = self.initiate_resumable_upload(metadata, file_size)
        resource = self.upload_chunks(session_uri, file_path, file_size)
        return resource.get("id")

    def upload_thumbnail(self, video_id, image_path):
        with open(image_path, "rb") as handle:
            content = handle.read()
        try:
            response = requests.post(
                f"{_YT_UPLOAD_API}/thumbnails/set",
                params={"videoId": video_id},
                headers=self._headers({"Content-Type": "image/jpeg"}),
                data=content,
                timeout=60,
            )
        except requests.RequestException as exc:
            raise YouTubeError(
                f"Thumbnail upload unreachable: {type(exc).__name__}"
            ) from exc
        if response.status_code >= 400:
            raise YouTubeError(f"Thumbnail upload HTTP {response.status_code}.")
        return response.json()

    def update_metadata(self, video_id, title=None, description=None, tags=None):
        body = {"id": video_id, "snippet": {}}
        if title is not None:
            body["snippet"]["title"] = title
        if description is not None:
            body["snippet"]["description"] = description
        if tags is not None:
            body["snippet"]["tags"] = list(tags)
        return self._api("PUT", "/videos", params={"part": "snippet"}, json_body=body)

    def analytics_report(
        self, channel_id, metrics, start_date, end_date, video_id=None
    ):
        params = {
            "ids": f"channel=={channel_id}",
            "startDate": start_date,
            "endDate": end_date,
            "metrics": metrics,
        }
        if video_id:
            params["filters"] = f"video=={video_id}"
        try:
            response = requests.get(
                f"{_YT_ANALYTICS_API}/reports",
                headers=self._headers(),
                params=params,
                timeout=30,
            )
        except requests.RequestException as exc:
            raise YouTubeError(f"Analytics unreachable: {type(exc).__name__}") from exc
        if response.status_code >= 400:
            raise YouTubeError(f"Analytics HTTP {response.status_code}.")
        return response.json()


# ---------------------------------------------------------------------------
# Upload state machine
# ---------------------------------------------------------------------------
UPLOAD_STATES = [
    "DRAFT",
    "VALIDATING",
    "APPROVED",
    "UPLOAD_PENDING",
    "UPLOADING",
    "PROCESSING",
    "SCHEDULED",
    "PUBLISHED",
    "RETRYABLE_FAILURE",
    "PERMANENT_FAILURE",
    "AUTHORIZATION_REQUIRED",
    "QUOTA_BLOCKED",
    "CANCELED",
]

_UPLOAD_LEGAL = {
    "DRAFT": {"VALIDATING", "CANCELED"},
    "VALIDATING": {"APPROVED", "DRAFT", "CANCELED", "PERMANENT_FAILURE"},
    "APPROVED": {"UPLOAD_PENDING", "SCHEDULED", "CANCELED"},
    "UPLOAD_PENDING": {
        "UPLOADING",
        "CANCELED",
        "AUTHORIZATION_REQUIRED",
        "QUOTA_BLOCKED",
    },
    "UPLOADING": {
        "PROCESSING",
        "RETRYABLE_FAILURE",
        "CANCELED",
        "AUTHORIZATION_REQUIRED",
        "QUOTA_BLOCKED",
    },
    "PROCESSING": {"SCHEDULED", "PUBLISHED", "RETRYABLE_FAILURE", "PERMANENT_FAILURE"},
    "SCHEDULED": {"PUBLISHED", "CANCELED"},
    "RETRYABLE_FAILURE": {"UPLOAD_PENDING", "CANCELED"},
    "AUTHORIZATION_REQUIRED": {"UPLOAD_PENDING", "CANCELED"},
    "QUOTA_BLOCKED": {"UPLOAD_PENDING", "CANCELED"},
    "PERMANENT_FAILURE": set(),
    "PUBLISHED": set(),
    "CANCELED": set(),
}


class InvalidUploadTransition(Exception):
    def __init__(self, from_state, to_state):
        super().__init__(f"Invalid upload transition: {from_state} -> {to_state}")
        self.from_state = from_state
        self.to_state = to_state


class UploadStateMachine:
    STATES = UPLOAD_STATES
    LEGAL = _UPLOAD_LEGAL
    TERMINAL = frozenset({"PUBLISHED", "PERMANENT_FAILURE", "CANCELED"})

    @classmethod
    def validate_transition(cls, from_state, to_state):
        if to_state not in cls.LEGAL.get(from_state, ()):
            raise InvalidUploadTransition(from_state, to_state)
        return True

    @classmethod
    def transition(cls, job, to_state):
        cls.validate_transition(job.status, to_state)
        job.status = to_state
        if to_state == "PUBLISHED":
            job.published_at = timezone.now()
        job.save()
        return job


# ---------------------------------------------------------------------------
# Content integrity checks
# ---------------------------------------------------------------------------
class ContentIntegrityChecker:
    """Pre-publish checks. Issues are {severity, code, message}; severity
    'blocking' issues prevent the publication from being APPROVED."""

    @staticmethod
    def run(project, publication):
        issues = []
        add = issues.append

        # 1. Unsupported factual claims vs fact-check status.
        for script in project.script_versions.all():
            if script.fact_check_status == "FLAGGED":
                add(
                    {
                        "severity": "blocking",
                        "code": "unsupported_factual_claims",
                        "message": f"Script v{script.version_number} is FLAGGED by fact-check; "
                        "resolve before publishing.",
                    }
                )

        # 2. Missing citations on approved scripts.
        for script in project.script_versions.filter(approval_status="APPROVED"):
            text = (script.rendered_text or "").lower()
            if "http" not in text and "[cite" not in text and "source:" not in text:
                add(
                    {
                        "severity": "warning",
                        "code": "missing_citations",
                        "message": f"Approved script v{script.version_number} has no citations.",
                    }
                )

        # 3. License metadata gaps.
        for asset in project.assets.filter(source_type__in=["STOCK", "GENERATED"]):
            if not asset.license_metadata:
                add(
                    {
                        "severity": "warning",
                        "code": "license_metadata_gap",
                        "message": f"Asset {asset.id} ({asset.asset_type}) has no license metadata.",
                    }
                )

        # 4. Near-duplicate detection (sha256 + title similarity).
        siblings = project.channel.publications.exclude(
            pk=publication.pk
        ).select_related("asset")
        for other in siblings:
            if (
                other.title
                and publication.title
                and SequenceMatcher(
                    None, other.title.lower(), publication.title.lower()
                ).ratio()
                > 0.92
            ):
                add(
                    {
                        "severity": "blocking",
                        "code": "near_duplicate",
                        "message": f"Title is near-duplicate of publication {other.id}.",
                    }
                )
                break
        if publication.asset and publication.asset.sha256:
            dup = siblings.filter(asset__sha256=publication.asset.sha256).first()
            if dup:
                add(
                    {
                        "severity": "blocking",
                        "code": "near_duplicate",
                        "message": f"Asset sha256 duplicates publication {dup.id}.",
                    }
                )

        # 5. Misleading title / thumbnail heuristics.
        title = publication.title or ""
        if len(title) > 10 and title == title.upper():
            add(
                {
                    "severity": "warning",
                    "code": "misleading_title",
                    "message": "Title is all caps, which reads as clickbait.",
                }
            )
        if any(token in title for token in ("!!!", "100% FREE", "YOU WON'T BELIEVE")):
            add(
                {
                    "severity": "warning",
                    "code": "misleading_title",
                    "message": "Title contains sensationalist clickbait markers.",
                }
            )
        if not project.assets.filter(asset_type="THUMBNAIL", status="READY").exists():
            add(
                {
                    "severity": "warning",
                    "code": "missing_thumbnail",
                    "message": "No READY thumbnail asset is attached to this project.",
                }
            )

        # 6. Synthetic-content disclosure requirement.
        if project.assets.filter(source_type="GENERATED").exists():
            description = (publication.description or "").lower()
            if "ai-generated" not in description and "synthetic" not in description:
                add(
                    {
                        "severity": "blocking",
                        "code": "synthetic_disclosure_required",
                        "message": "AI-generated content requires a disclosure in the description "
                        "(mention 'AI-generated' or 'synthetic').",
                    }
                )

        # 7. Channel prohibited categories.
        prohibited = set(
            (publication.channel.publishing_policy or {}).get(
                "prohibited_categories", []
            )
        )
        haystack = set(publication.tags or []) | set(title.lower().split())
        hit = prohibited & haystack
        if hit:
            add(
                {
                    "severity": "blocking",
                    "code": "prohibited_category",
                    "message": f"Publication touches prohibited categories: {sorted(hit)}.",
                }
            )

        return issues
