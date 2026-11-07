"""Response and request bodies for /me and /users."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from cinecircle_api.catalog.parse import Locale

FollowState = Literal["self", "none", "requested", "following"]

DisplayName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
Bio = Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]


class UserCard(BaseModel):
    """The only fields any signed-in user may see about anyone (rule R1.2)."""

    username: str
    display_name: str
    avatar_url: str | None
    follow_state: FollowState


class UserDetails(BaseModel):
    bio: str | None
    post_count: int  # shared posts
    # Accepted follow rows; only the owner sees them (the lists are owner-only too, plan P10).
    followers_count: int | None = None
    following_count: int | None = None


class UserProfile(UserCard):
    details: UserDetails | None  # null unless the viewer is the owner or an approved follower


class SearchUsersResponse(BaseModel):
    results: list[UserCard]


class MyProfile(BaseModel):
    username: str
    display_name: str
    avatar_url: str | None
    bio: str | None
    locale: Locale


class MeResponse(BaseModel):
    id: UUID
    email: str | None
    profile: MyProfile | None


class CreateProfile(BaseModel):
    username: str  # normalised and checked in the route, for its own error codes
    display_name: DisplayName
    locale: Locale = "he"


class UpdateProfile(BaseModel):
    """Every field optional; there is deliberately no username (a username never changes)."""

    model_config = ConfigDict(extra="forbid")

    display_name: DisplayName | None = None
    bio: Bio | None = None  # "" or null clears it
    locale: Locale | None = None

    @field_validator("display_name", "locale", mode="before")
    @classmethod
    def _not_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("must not be null")
        return value
