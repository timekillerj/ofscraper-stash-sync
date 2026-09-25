import hashlib
import json
import logging
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx


class OnlyFansClient:
    RULES_URL = (
        "https://raw.githubusercontent.com/"
        "xagler/dynamic-rules/main/onlyfans.json"
    )

    PROFILE_URL = "https://onlyfans.com/api2/v2/users/{}"

    def __init__(
        self,
        auth_file=Path.home()
        / ".config/ofscraper/main_profile/auth.json",
    ):
        self.auth_file = Path(auth_file)
        self.auth = self._load_auth()
        self.rules = self._load_rules()

        self.headers = {
            "accept": "application/json, text/plain, */*",
            "app-token": self.rules.get(
                "app_token",
                self.auth["app-token"],
            ),
            "user-id": self.auth["auth_id"],
            "x-bc": self.auth["x-bc"],
            "referer": "https://onlyfans.com",
            "user-agent": self.auth["user_agent"],
        }

        self.cookies = {
            "sess": self.auth["sess"],
            "auth_id": self.auth["auth_id"],
        }

        if self.auth.get("auth_uid"):
            self.cookies[
                f"auth_uid_{self.auth['auth_id']}"
            ] = self.auth["auth_uid"]

    def _load_auth(self):
        with open(self.auth_file, "r") as f:
            return json.load(f)

    def _load_rules(self):
        response = httpx.get(
            self.RULES_URL,
            timeout=20.0,
            follow_redirects=True,
        )
        response.raise_for_status()

        return response.json()

    def _create_sign(self, url):
        timestamp = str(round(time.time() * 1000))

        parsed = urlparse(url)
        path = parsed.path

        if parsed.query:
            path += "?" + parsed.query

        msg = "\n".join(
            [
                self.rules["static_param"],
                timestamp,
                path,
                self.headers["user-id"],
            ]
        )

        sha1 = hashlib.sha1(
            msg.encode("utf-8")
        ).hexdigest()

        sha1_bytes = sha1.encode("ascii")

        checksum = (
            sum(
                sha1_bytes[i]
                for i in self.rules[
                    "checksum_indexes"
                ]
            )
            + self.rules["checksum_constant"]
        )

        sign = self.rules["format"].format(
            sha1,
            abs(checksum),
        )

        return {
            "sign": sign,
            "time": timestamp,
        }

    def get_profile(self, username):
        url = self.PROFILE_URL.format(username)

        headers = self.headers | self._create_sign(url)

        try:
            with httpx.Client(
                http2=True,
                headers=headers,
                cookies=self.cookies,
                timeout=20.0,
            ) as client:
                response = client.get(url)

            if response.status_code == 404:
                logging.info(
                    f"OnlyFans profile @{username} "
                    "does not exist"
                )
                return None

            response.raise_for_status()

            return response.json()

        except httpx.HTTPError as e:
            logging.warning(
                f"Unable to retrieve OnlyFans profile "
                f"@{username}: {e}"
            )
            return None

    def get_avatar(self, username):
        profile = self.get_profile(username)

        if not profile:
            return None

        avatar = profile.get("avatar")

        if not avatar:
            logging.info(
                f"OnlyFans profile @{username} "
                "has no avatar"
            )
            return None

        logging.info(
            f"Found OnlyFans avatar for @{username}"
        )

        return avatar