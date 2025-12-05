# ⚠ Don't use relative imports
from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.networking.exceptions import HTTPError
from yt_dlp.utils import ExtractorError, MEDIA_EXTENSIONS
from random import shuffle

coomer_media_hosts = [
    "https://n1.coomer.st",
    "https://n2.coomer.st",
    "https://n3.coomer.st",
    "https://n4.coomer.st",
]


class CoomerBaseIE(InfoExtractor):
    """Base class with shared methods for Coomer extractors."""

    _API_BASE = "https://coomer.st/api/v1"
    _VALID_URL = False

    def _is_supported_media(self, extension):
        """Check if extension is a supported video/audio format."""
        ext = extension.lstrip(".").lower()
        return ext in (*MEDIA_EXTENSIONS.video, *MEDIA_EXTENSIONS.audio)

    def _download_json_with_retry(self, url, video_id, **kwargs):
        """Download JSON with retry logic for rate limiting."""
        last_error = None
        for retry in self.RetryManager():
            try:
                return self._download_json(url, video_id, **kwargs)
            except ExtractorError as e:
                if not isinstance(e.cause, HTTPError) or e.cause.status not in (
                    403,
                    429,
                    502,
                    503,
                ):
                    raise
                if e.cause.status in (403, 429):
                    self.report_warning(
                        "Rate limit hit. Use --extractor-retries and --retry-sleep "
                        "to configure retry behavior.",
                        only_once=True,
                    )
                last_error = e
                retry.error = e.cause
        raise last_error  # type: ignore[misc]

    def _fetch_user_info(self, platform, user):
        return self._download_json_with_retry(
            f"{self._API_BASE}/{platform}/user/{user}/profile",
            user,
            headers={"Accept": "text/css"},
        )

    def _build_channel_url(self, platform, user):
        if platform == "fansly":
            return f"https://fansly.com/{user}/posts"
        elif platform == "onlyfans":
            return f"https://onlyfans.com/{user}"
        return None

    def _build_post_url(self, platform, user, post_id):
        return f"https://coomer.st/{platform}/user/{user}/post/{post_id}"

    def _build_user_url(self, platform, user):
        return f"https://coomer.st/{platform}/user/{user}"

    def _parse_date(self, date_str):
        from datetime import datetime

        try:
            dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
            return int(dt.timestamp())
        except ValueError:
            return None


class CoomerPostIE(CoomerBaseIE):
    """Extractor for individual Coomer posts."""

    IE_NAME = "coomer:post"
    _VALID_URL = r"https?://(?:www\.)?coomer\.(?:su|st)/(?P<platform>fansly|onlyfans|candfans)/user/(?P<user>[^/]+)/post/(?P<id>[^/]+)"

    _TESTS = [
        {
            "url": "https://coomer.st/onlyfans/user/bigtittygothegg/post/1999540943",
            "info_dict": {
                "id": "onlyfans-bigtittygothegg-1999540943-0",
                "ext": str,
                "title": str,
                "uploader": "bigtittygothegg",
                "age_limit": 18,
            },
        }
    ]

    def _build_entry(self, post, userinfo, attachment_index=0):
        attachment = post["post"]["attachments"][attachment_index]
        ext = attachment["path"].split(".")[-1].lower()
        formats = []
        thumbnails = []
        shuffle(coomer_media_hosts)
        if ext in MEDIA_EXTENSIONS.video:
            # Find unique thumbnails in previews whose path is not in post.attachments
            attachment_paths = {att["path"] for att in post["post"]["attachments"]}
            for preview in post["previews"]:
                if preview["path"] not in attachment_paths:
                    thumbnails.append(
                        {
                            "url": f"https://img.coomer.st/thumbnail/data{preview['path']}",
                        }
                    )
            if len(thumbnails) > 1:
                # I have yet to figure out how they are associated so it only works if they are unique for now
                thumbnails = []
            for att in post["attachments"]:
                if attachment["path"] == att["path"]:
                    for host in coomer_media_hosts:
                        formats.append(
                            {
                                "url": f"{host}/data{att['path']}",
                            }
                        )
                    break
        elif ext in MEDIA_EXTENSIONS.audio:
            for server in coomer_media_hosts:
                formats.append(
                    {
                        "url": f"{server}/data{attachment['path']}",
                    }
                )
        else:
            for preview in post["previews"]:
                if preview["path"] == attachment["path"]:
                    thumbnails.append(
                        {
                            "url": f"https://img.coomer.st/thumbnail/data{preview['path']}",
                        }
                    )
                    break
            for server in coomer_media_hosts:
                formats.append(
                    {
                        "url": f"{server}/data{attachment['path']}?f={attachment['name']}",
                    }
                )

        return {
            "id": f"{userinfo['service']}-{userinfo['name']}-{post['post']['id']}-{attachment_index}",
            "title": post["post"]["title"] or f"Post {post['post']['id']}",
            "display_id": f"{attachment['name']}",
            "description": post["post"]["content"],
            "formats": formats,
            "thumbnails": thumbnails,
            "uploader": userinfo["name"],
            "uploader_id": userinfo["id"],
            "uploader_url": self._build_user_url(userinfo["service"], userinfo["id"]),
            "channel": userinfo["name"],
            "channel_id": userinfo["id"],
            "channel_url": self._build_channel_url(userinfo["service"], userinfo["id"]),
            "age_limit": 18,
            "timestamp": self._parse_date(post["post"]["published"]),
            "tags": post["post"].get("tags", []),
            "location": userinfo["service"],
            "series": userinfo["name"],
            "season": post["post"]["title"],
            "season_id": post["post"]["id"],
            "episode_number": attachment_index + 1,
        }

    def _real_extract(self, url):
        mobj = self._match_valid_url(url)
        platform = mobj.group("platform")
        user = mobj.group("user")
        post_id = mobj.group("id")

        data = self._download_json_with_retry(
            f"{self._API_BASE}/{platform}/user/{user}/post/{post_id}",
            post_id,
            headers={"Accept": "text/css"},
        )
        userinfo = self._fetch_user_info(platform, user)

        if len(data["post"]["attachments"]) == 0 and len(data["attachments"]) > 0:
            # Filter out unsupported media attachments
            for att in data["attachments"]:
                data["post"]["attachments"].append(
                    {
                        "name": att["name"],
                        "path": att["path"],
                    }
                )

        if len(data["post"]["attachments"]) == 0:
            self.raise_no_formats("No supported media attachments found for this post")
        elif len(data["post"]["attachments"]) == 1:
            return self._build_entry(data, userinfo, 0)
        else:
            # Multiple attachments - return as playlist
            self.to_screen(
                f"Post has {len(data['post']['attachments'])} supported attachments"
            )
            entries = []
            for idx in range(len(data["post"]["attachments"])):
                entries.append(self._build_entry(data, userinfo, idx))

            return self.playlist_result(
                entries=entries,
                description=data["post"]["content"],
                playlist_id=f"{userinfo['service']}-{userinfo['name']}-{post_id}",
                playlist_title=data["post"]["title"] or f"Post {post_id}",
                uploader=userinfo["name"],
                uploader_id=userinfo["id"],
                channel=userinfo["name"],
                channel_id=userinfo["id"],
            )


class CoomerUserIE(CoomerBaseIE):
    """Extractor for Coomer user profiles (all posts)."""

    IE_NAME = "coomer:user"
    _VALID_URL = r"https?://(?:www\.)?coomer\.(?:su|st)/(?P<platform>fansly|onlyfans|candfans)/user/(?P<id>[^/]+)/?(?:\?.*)?$"

    _TESTS = [
        {
            "url": "https://coomer.st/onlyfans/user/bigtittygothegg",
            "info_dict": {
                "id": "onlyfans-bigtittygothegg-posts",
                "title": str,
            },
            "playlist_mincount": 1,
        }
    ]

    def _entries(self, platform, user):
        offset = 0
        page_size = 50

        while True:
            data = self._download_json_with_retry(
                f"{self._API_BASE}/{platform}/user/{user}/posts",
                user,
                query={"o": offset} if offset else None,
                headers={"Accept": "text/css"},
                note=f"Downloading posts page {offset // page_size + 1}",
            )

            if not data:
                break

            for post in data:
                post_url = self._build_post_url(platform, user, post["id"])
                yield self.url_result(
                    post_url, CoomerPostIE, post["id"], post.get("title")
                )

            if len(data) < page_size:
                break

            offset += page_size

    def _real_extract(self, url):
        mobj = self._match_valid_url(url)
        platform = mobj.group("platform")
        user = mobj.group("id")

        userinfo = self._fetch_user_info(platform, user)

        return self.playlist_result(
            self._entries(platform, user),
            playlist_id=f"{userinfo['service']}-{userinfo['name']}-posts",
            playlist_title=f"{userinfo['name']}'s posts on {userinfo['service']}",
            uploader=userinfo["name"],
            uploader_id=userinfo["id"],
            uploader_url=self._build_user_url(userinfo["service"], userinfo["id"]),
            channel=userinfo["name"],
            channel_id=userinfo["id"],
            channel_url=self._build_channel_url(userinfo["service"], userinfo["id"]),
        )
