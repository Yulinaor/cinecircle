"""What a Taste Match looks like to the web: the number and the data behind its reason line
(plan P4). The web words the reason; nothing about another user is in here except the agreement
percentage on that user's own visible post."""

from pydantic import BaseModel


class Taste(BaseModel):
    fit: int  # 0-100
    genres: list[str]  # up to 2 of the title's genres that fit the viewer, localised
    agreement: int | None  # % the viewer usually agrees with the author; None when not shown
