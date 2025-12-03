# ⚠ Don't use relative imports
from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import MEDIA_EXTENSIONS


class CoomerBaseIE(InfoExtractor):
    """Base class with shared methods for Coomer extractors."""

    _API_BASE = "https://coomer.st/api/v1"
    _VALID_URL = False

    def _is_supported_media(self, extension):
        """Check if extension is a supported video/audio format."""
        ext = extension.lstrip(".").lower()
        return ext in (*MEDIA_EXTENSIONS.video, *MEDIA_EXTENSIONS.audio)

    def _fetch_user_info(self, platform, user):
        return self._download_json(
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
        attachment = post["attachments"][attachment_index]
        thumbnails = []
        if post["previews"] and len(post["previews"]) > 0:
            for preview in post["previews"]:
                thumbnails.append(
                    {
                        "id": f"preview-{preview['name']}",
                        "url": f"{preview['server']}/data{preview['path']}",
                    }
                )
        return {
            "id": f"{userinfo['service']}-{userinfo['name']}-{post['post']['id']}-{attachment_index}",
            "title": post["post"]["title"] or f"Post {post['post']['id']}",
            "display_id": f"{attachment['name']}",
            "description": post["post"]["content"],
            "url": f"{attachment['server']}/data{attachment['path']}",
            "ext": attachment["extension"].lstrip("."),
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

        data = self._download_json(
            f"{self._API_BASE}/{platform}/user/{user}/post/{post_id}",
            post_id,
            headers={"Accept": "text/css"},
        )
        userinfo = self._fetch_user_info(platform, user)

        raw_attachments = data.get("attachments", [])
        # Filter to only supported media formats
        attachments = [
            (i, att)
            for i, att in enumerate(raw_attachments)
            if self._is_supported_media(att.get("extension", ""))
        ]

        if not attachments:
            self.raise_no_formats("No supported media attachments found for this post")

        if len(attachments) == 1:
            orig_idx, _ = attachments[0]
            return self._build_entry(data, userinfo, orig_idx)

        # Multiple attachments - return as playlist
        self.to_screen(f"Post has {len(attachments)} supported attachments")
        entries = [
            self._build_entry(data, userinfo, orig_idx) for orig_idx, _ in attachments
        ]

        return {
            "_type": "playlist",
            "id": f"{userinfo['service']}-{userinfo['name']}-{post_id}",
            "title": data["post"]["title"] or f"Post {post_id}",
            "description": data["post"]["content"],
            "uploader": userinfo["name"],
            "uploader_id": userinfo["id"],
            "channel": userinfo["name"],
            "age_limit": 18,
            "entries": entries,
        }


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
            data = self._download_json(
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
