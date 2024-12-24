import json
import logging
import os
import random
import time
import uuid
from typing import Any, Dict, List, Optional

import requests
from eth_account.account import Account
from eth_account.signers.local import LocalAccount
from farcaster import Warpcast
from farcaster.models import (
    AuthParams,
    CastContent,
    CastReactionsPutResponse,
    CastsGetResponse,
    CastsPostResponse,
    IterableCastsResult,
    Parent,
    ReactionsPutResult,
    StatusContent,
    StatusResponse,
)
from loguru import logger
from pydantic import BaseModel, PositiveInt
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from models import (
    ApiUser,
    FollowersGetResponse,
    GetStreakStatusResponse,
    GetUserFollowingChannels,
    IterableUsersResult,
)

API_V1_URL = "https://client.warpcast.com/v1/"


class WarpModified(Warpcast):
    def __init__(
        self,
        mnemonic: str | None = None,
        private_key: str | None = None,
        access_token: str | None = None,
        expires_at: int | None = None,
        rotation_duration: int = 10,
        proxy: str | None = None,
        **data,
    ):
        self.config = ConfigurationParams(**data)
        self.wallet = get_wallet(mnemonic, private_key)
        self.access_token = access_token
        self.expires_at = expires_at
        self.rotation_duration = rotation_duration

        self.fc_device_id = str(uuid.uuid4())
        self.fc_amplitude_device_id = str(uuid.uuid4())
        self.device_model = None
        self.build_version = None
        self.app_version = None
        self.lang = None
        self.lang_short = None

        self.session = requests.Session()
        self.upload_client = requests.Session()
        if proxy:
            proxies = {
                "http": f"http://{proxy}",
                "https": f"http://{proxy}",
            }
            self.session.proxies = proxies
            self.upload_client.proxies = proxies
        self.session.headers.update(
            {
                "Host": "client.warpcast.com",
                "fc-device-model": "iPhone 14 Pro Max",
                "User-Agent": "mobile-client/400 CFNetwork/1496.0.7 Darwin/23.5.0",
                "fc-native-build-version": "400",
                "fc-device-id": self.fc_device_id,
                "fc-native-application-version": "1.0.74",
                "fc-device-os": "iOS",
                "fc-amplitude-device-id": self.fc_amplitude_device_id,
                "Connection": "keep-alive",
                "fc-address": self.wallet.address,
                "Accept-Language": "ru",
                "Accept": "*/*",
                "Content-Type": "application/json; charset=utf-8",
            }
        )
        self._create_new_random_headers()
        self.session.mount(
            self.config.base_path,
            HTTPAdapter(
                max_retries=Retry(
                    total=2, backoff_factor=1, status_forcelist=[520, 413, 429, 503]
                )
            ),
        )
        if self.access_token:
            self.session.headers.update(
                {"Authorization": f"Bearer {self.access_token}"}
            )
            if not self.expires_at:
                self.expires_at = 33228645430000

        elif not self.wallet:
            raise Exception("No wallet or access token provided")
        else:
            self.create_new_auth_token(expires_in=self.rotation_duration)

        self.me = self.get_me()
        self.session_time = int(time.time() * 1000)
        self.idempotency_key = str(uuid.uuid4())
        self.idfv = str(uuid.uuid4()).upper()
        # self.my_ip = self.get_my_ip()
        self.event_data_file = "data/db/events.json"
        self.event_id = 0
        self.get_event_id()

        self.session.headers.update(
            {
                "fc-amplitude-session-id": str(self.session_time),
            }
        )

    def _create_new_random_headers(self):
        self.device_model = random.choice(
            [
                "iPhone 14 Pro Max",
                "iPhone 14 Pro",
                "iPhone 15 Pro Max",
                "iPhone 15 Pro",
            ]
        )
        self.build_version = random.randint(400, 413)
        self.app_version = random.randint(75, 79)
        self.lang, self.lang_short = random.choice(
            ["Russian:ru", "English:en", "Spanish:es", "French:fr", "German:de"]
        ).split(":")

        self.session.headers.update(
            {
                "fc-device-model": self.device_model,
                "User-Agent": f"mobile-client/{self.build_version} CFNetwork/1496.0.7 Darwin/23.5.0",
                "fc-native-build-version": str(self.build_version),
                "fc-native-application-version": f"1.0.{self.app_version}",
                "Accept-Language": self.lang_short,
            }
        )

    def get_event_id(self):
        if (
            not os.path.exists(self.event_data_file)
            or os.path.getsize(self.event_data_file) == 0
            or os.path.getsize(self.event_data_file) == 1
        ):
            with open(self.event_data_file, "w") as f:
                json.dump({}, f)

        with open(self.event_data_file, "r") as f:
            data = json.load(f)

        account_id = str(self.me.fid)
        if account_id in data:
            self.event_id = data[account_id]["event_id"]
        else:
            data[account_id] = {"event_id": 0}
            self.event_id = 0
            with open(self.event_data_file, "w") as f:
                json.dump(data, f)

    def increment_event_id(self):
        self.event_id += 1
        account_id = str(self.me.fid)

        with open(self.event_data_file, "r") as f:
            data = json.load(f)

        data[account_id]["event_id"] = self.event_id

        with open(self.event_data_file, "w") as f:
            json.dump(data, f)

    def get_my_ip(self):
        while True:
            try:
                response = requests.get("http://eth0.me")
                response.raise_for_status()
                return response.text.strip()
            except requests.RequestException as e:
                logger.error(f"Ошибка запроса ip: {e}. Повторная попытка...")
                time.sleep(1)

    def create_new_auth_token(self, expires_in: PositiveInt = 10) -> str:
        now = int(time.time())
        self.session_time = now * 1000
        auth_params = AuthParams(
            timestamp=now * 1000,
            expires_at=(now + (expires_in * 60)) * 1000,
        )
        # logging.debug(f"Creating new auth token with params: {auth_params}")
        response = self.put_auth(auth_params)
        self.access_token = response.token.secret
        self.expires_at = auth_params.expires_at
        self.rotation_duration = expires_in

        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.access_token}",
                "fc-amplitude-session-id": str(self.session_time),
            }
        )

        return self.access_token

    def _patch(
        self,
        path: str,
        params: Dict[Any, Any] = {},
        json: Dict[Any, Any] = {},
        headers: Dict[Any, Any] = {},
    ) -> Dict[Any, Any]:
        self._check_auth_header()
        logging.debug(f"PATCH {path} {params} {json} {headers}")
        response: Dict[Any, Any] = self.session.patch(
            self.config.base_path + path, params=params, json=json, headers=headers
        ).json()
        if "errors" in response:
            raise Exception(response["errors"])  # pragma: no cover
        return response

    def get_followers(
        self,
        fid: int,
        cursor: Optional[str] = None,
        limit: PositiveInt = 25,
    ) -> IterableUsersResult:
        users: List[ApiUser] = []
        while True:
            response = self._get(
                "followers",
                params={"fid": fid, "cursor": cursor, "limit": min(limit, 100)},
            )
            response_model = FollowersGetResponse(**response)
            if response_model.result.users:
                users.extend(response_model.result.users)
            if not response_model.next or len(users) >= limit:
                break
            cursor = response_model.next.cursor
        return IterableUsersResult(
            users=users[:limit], cursor=getattr(response_model.next, "cursor", None)
        )

    def generate_custom_id(self, custom_id):
        suffix = uuid.uuid4().hex[:16]
        zeros_uuid = "0" * 16 + uuid.uuid4().hex[:8]
        return f"{zeros_uuid}-{suffix}-{str(custom_id)}"

    def evry_requests_update_headers(self, custom_id: int = 0):
        self.session.headers.update(
            {
                "x-datadog-parent-id": str(random.randint(10**18, 10**19 - 1)),
                "x-datadog-sampling-priority": "0",
                "b3": self.generate_custom_id(custom_id=custom_id),
                "x-datadog-trace-id": str(
                    random.randint(10**18, 10**19 - 1),
                ),
            }
        )

    def tupical(self, event: list):
        self.evry_requests_update_headers()
        body = {
            "api_key": "7dd7b12861158f5e89ab5508bd9ce4c0",
            "events": [
                {
                    "user_id": str(self.me.fid),
                    "device_id": self.fc_device_id,
                    "session_id": int(self.session_time),
                    "time": int(time.time() * 1000),
                    "app_version": self.app_version,
                    "platform": "iOS",
                    "os_name": "ios",
                    "os_version": "17.5.1",
                    "device_manufacturer": "Apple",
                    "device_model": self.device_model,
                    "language": self.lang,
                    "country": self.lang_short.upper(),
                    "carrier": "--",
                    "ip": "$remote",  # self.my_ip
                    "idfv": self.idfv,
                    "insert_id": str(uuid.uuid4()),
                    "event_type": "click create cast modal cast",
                    "event_properties": {
                        "isReply": False,
                        "hasEmbeds": True,
                        "location": "Drawer/CreateCast",
                        "warpcastPlatform": "mobile",
                    },
                    "event_id": 180,
                    "library": "amplitude-react-native-ts/1.4.4",
                },
            ],
            "options": {
                "min_id_length": 1,
            },
        }
        body["events"][0].update(event)

        response = self._post("/amp/api2/2/httpapi", json=body)
        return response

    def send_device(self):
        self.evry_requests_update_headers(custom_id=1)
        body = {
            "deviceId": self.fc_device_id,
            "deviceModel": self.device_model,
            "deviceName": "iPhone",
            "deviceOs": "iOS",
            "notificationsSystemEnabled": True,
        }
        response = self._put("devices", json=body)
        return response

    def update_contact_device_state(self):
        self.evry_requests_update_headers()
        body = {
            "deviceId": self.fc_device_id,
            "enabled": False,
            "localStorageSize": 0,
        }
        response = self._post("update-contacts-device-state", json=body)
        return response

    def casts_wiewed(self, cast_hashes: list):
        body = {
            "castHashes": cast_hashes,
        }
        response = self._put("casts-viewed", json=body)
        return response

    def set_bio_and_display_name(self, bio: str, display_name: str):
        body = {
            "displayName": display_name,
            "bio": bio,
        }
        response = self._patch(
            "me",
            json=body,
        )
        return StatusResponse(**response).result

    def post_cast(
        self,
        text: str,
        embeds: Optional[List[str]] = None,
        parent: Optional[Parent] = None,
        cast_distribution: Optional[str] = "default",
        channel_key: Optional[str] = None,
    ) -> CastContent:
        body = {
            "text": text,
            "embeds": [],
            "castDistribution": cast_distribution,
        }
        if channel_key:
            body.update({"channelKey": channel_key})

        if embeds:
            body.update({"embeds": embeds})

        if parent:
            body.update(
                {
                    "parent": {"hash": parent},
                }
            )

        tupical = {
            "event_type": "click create cast modal cast",
            "event_properties": {
                "isReply": False,
                "hasEmbeds": False,
                "location": "Drawer/CreateCast",
                "warpcastPlatform": "mobile",
            },
            "event_id": self.event_id,
        }
        if channel_key:
            tupical["event_properties"]["channelKey"] = channel_key
        self.increment_event_id()
        self.tupical(event=tupical)
        time.sleep(random.randint(1, 3))

        response = self._post(
            "casts",
            json=body,
        )
        tupical = {
            "event_type": "cast message",
            "event_properties": {
                "is reply": False,
                "is channel": False,
                "channel name": "",
                "is long cast": False,
                "is narrowcast": False,
                "location": "Drawer/CreateCast/PreviewCast",
                "warpcastPlatform": "mobile",
            },
            "event_id": self.event_id,
        }
        if channel_key:
            tupical["event_properties"].update(
                {
                    "is channel": True,
                    "channel name": channel_key,
                }
            )
        self.increment_event_id()
        self.tupical(event=tupical)

        return CastsPostResponse(**response).result

    def repost_cast(self, cast_hash: str, user_fid: int = 0) -> ReactionsPutResult:
        body = {
            "castHash": cast_hash,
        }
        tupical = {
            "event_type": "show recast or quote cast prompt",
            "event_properties": {"warpcastPlatform": "mobile"},
            "event_id": self.event_id,
        }
        self.increment_event_id()
        self.tupical(event=tupical)
        time.sleep(random.randint(1, 3))

        response = self._put(
            "recasts",
            json=body,
        )

        tupical = {
            "event_type": "react to cast",
            "event_properties": {
                "on": "user-profile",
                "castHash": cast_hash,
                "type": "recast",
                "is remove": False,
                "has asset embed": False,
                "cast fid": user_fid,
                "warpcastPlatform": "mobile",
            },
            "event_id": self.event_id,
        }
        self.increment_event_id()
        self.tupical(event=tupical)
        return response

    def _cast_attachments(self, username: str, cast_hash: str):
        prepare_hash = cast_hash[:10]
        body = {
            "text": "",
            "embeds": [
                f"https://warpcast.com/{username}/{prepare_hash}",
            ],
        }
        response = self._put(
            "cast-attachments",
            json=body,
        )
        return response

    def repost_cast_uqote(
        self, username: str, cast_hash: str, text: str = "", user_fid: int = 0
    ):
        self._cast_attachments(username=username, cast_hash=cast_hash)
        prepare_hash = cast_hash[:10]
        embeds = [
            f"https://warpcast.com/{username}/{prepare_hash}",
        ]

        tupical = {
            "event_type": "show recast or quote cast prompt",
            "event_properties": {"warpcastPlatform": "mobile"},
            "event_id": self.event_id,
        }
        self.increment_event_id()
        self.tupical(event=tupical)
        tupical = {
            "event_type": "react to cast",
            "event_properties": {
                "on": "user-profile",
                "castHash": cast_hash,
                "type": "quote",
                "is remove": False,
                "has asset embed": False,
                "cast fid": user_fid,
                "warpcastPlatform": "mobile",
            },
            "event_id": self.event_id,
        }
        self.increment_event_id()
        self.tupical(event=tupical)

        tupical = {
            "event_type": "click create cast modal cast",
            "event_properties": {
                "isReply": False,
                "hasEmbeds": True,
                "location": "Drawer/CreateCast",
                "warpcastPlatform": "mobile",
            },
            "event_id": self.event_id,
        }
        self.increment_event_id()
        self.tupical(event=tupical)

        self.post_cast(text=text, embeds=embeds, cast_distribution="default")

    def delete_cast(self, cast_hash: str) -> StatusContent:
        body = {"castHash": cast_hash}
        response = self._delete(
            "casts",
            json=body,
        )
        return StatusResponse(**response).result

    def like_cast(self, cast_hash: str, cast_fid: int = 0) -> ReactionsPutResult:
        body = {"castHash": cast_hash}
        response = self._put(
            "cast-likes",
            json=body,
        )
        if cast_fid:
            tupical = {
                "event_type": "react to cast",
                "event_properties": {
                    "on": "user-profile",
                    "type": "like",
                    "is remove": False,
                    "has asset embed": False,
                    "cast fid": cast_fid,
                    "author has active badge": False,
                    "warpcastPlatform": "mobile",
                },
                "event_id": self.event_id,
            }
            self.increment_event_id()
            self.tupical(event=tupical)
        return CastReactionsPutResponse(**response).result

    def follow_user(self, fid: PositiveInt) -> StatusContent:
        body = {"targetFid": fid}
        response = self._put(
            "follows",
            json=body,
        )
        tupical = {
            "event_type": "follow user",
            "event_properties": {
                "on": "user-profile",
                "is remove": False,
                "warpcastPlatform": "mobile",
            },
            "event_id": self.event_id,
        }
        self.increment_event_id()
        self.tupical(event=tupical)
        return StatusResponse(**response).result

    def get_thread_casts(self, thread_hash: str):
        response = self._get(
            "thread-casts",
            params={
                "castHash": thread_hash,
                "limit": "15",
            },
        )
        return CastsGetResponse(**response).result

    def get_casts(
        self,
        fid: int,
        limit: PositiveInt = 15,
    ) -> IterableCastsResult:
        response = self._get(
            "profile-casts",
            params={"fid": fid, "limit": min(limit, 100)},
        )
        return CastsGetResponse(**response).result

    def get_user_following_channels(self):
        response = self._get(
            "user-following-channels",
            params={"fid": self.me.fid, "limit": 50},
        )
        return GetUserFollowingChannels(**response).result.channels

    def get_streak_status(self):
        response = self._get(
            "channel-streaks",
            params={
                "fid": self.me.fid,
            },
        )
        return GetStreakStatusResponse(**response).result.streak

    def start_stike(self, channel_key: str):
        body = {"channelKey": channel_key}
        response = self._post("channel-streaks", json=body)
        return response

    def get_img_upload_url(self) -> str:
        self._check_auth_header()
        response = self.session.post(
            url=f"{API_V1_URL}generate-image-upload-url", json={}
        )
        return response.json()["result"]["url"]

    def upload_img(self, file_path: str):
        upload_url = self.get_img_upload_url()
        with open(file_path, "rb") as f:
            files = {"file": f}
            response = self.upload_client.post(url=upload_url, files=files)
        return next(
            (url for url in response.json()["result"]["variants"] if "original" in url),
            None,
        )


def get_wallet(
    mnemonic: Optional[str] = None, private_key: Optional[str] = None
) -> Optional[LocalAccount]:
    Account.enable_unaudited_hdwallet_features()

    if mnemonic:
        account: LocalAccount = Account.from_mnemonic(mnemonic)
        return account  # pragma: no cover
    elif private_key:
        account = Account.from_key(private_key)
        return account  # pragma: no cover
    return None


class ConfigurationParams(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    base_path: str = "https://client.warpcast.com/v2/"
    base_options: Optional[Dict[Any, Any]] = None
