from typing import List, Optional

from eth_account.account import Account as Eth_account
from farcaster.models import ApiPfp, ApiProfile, ViewerContext
from humps import camelize
from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict, PositiveInt


class BaseModel(PydanticBaseModel):
    model_config = ConfigDict(alias_generator=camelize, populate_by_name=True)


class CastsPostRequestModified(BaseModel):
    text: str
    embeds: Optional[List[str]] = None
    parent: Optional[str] = None


class Next(BaseModel):
    cursor: Optional[str] = None


class ApiUser(BaseModel):
    fid: PositiveInt
    username: Optional[str] = None
    display_name: Optional[str] = None
    registered_at: Optional[PositiveInt] = None
    pfp: Optional[ApiPfp] = None
    profile: ApiProfile
    active_on_fc_network: bool
    follower_count: int
    following_count: int
    referrer_username: Optional[str] = None
    viewer_context: Optional[ViewerContext] = None


class UsersResult(BaseModel):
    users: List[ApiUser]


class FollowersGetResponse(BaseModel):
    result: UsersResult
    next: Optional[Next] = None


class IterableUsersResult(BaseModel):
    users: List[ApiUser]
    cursor: Optional[str] = None


class Account(BaseModel):
    display_name: Optional[str] = None
    username: Optional[str] = None
    address: Optional[str] = None
    bio: Optional[str] = None
    language: Optional[str] = None
    post_max_symbol_limit: Optional[int] = None
    shadow_ban: Optional[bool] = None
    follower_count: Optional[int] = None
    following_count: Optional[int] = None
    ps: str
    proxy: Optional[str] = None
    role: Optional[str] = None

    def __init__(self, **data):
        super().__init__(**data)
        if self.ps and self.address is None:
            Eth_account.enable_unaudited_hdwallet_features()
            self.address = Eth_account.from_mnemonic(self.ps).address

    def to_list_value(self):
        return list(self.model_dump().values())

    def to_list_headers(self):
        return list(self.model_dump().keys())


class ApiStrikeMetadata(BaseModel):
    already_casted_today: bool
    started_at_timestamp: int
    expires_at_timestamp: int
    latest_window_start_timestamp: int
    latest_window_cast_count: int


class ApiStreak(BaseModel):
    key: str
    name: str
    image_url: str
    description: str
    follower_count: int
    norms: Optional[str] = None


class ApiStreakChanel(BaseModel):
    channel: ApiStreak
    streak_count: int
    metadata: ApiStrikeMetadata


class ApiUserFollowingChannels(BaseModel):
    type: str
    key: str
    name: str


class StreakResult(BaseModel):
    streak: Optional[ApiStreakChanel] = None


class UserFollowingChannelsResult(BaseModel):
    channels: List[ApiUserFollowingChannels]


class GetStreakStatusResponse(BaseModel):
    result: Optional[StreakResult] = None
    next: Optional[Next] = None


class GetUserFollowingChannels(BaseModel):
    result: UserFollowingChannelsResult
    next: Optional[Next] = None
