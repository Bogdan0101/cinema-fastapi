from datetime import datetime
from decimal import Decimal
from typing import Optional, List, TypeVar, Generic
import uuid as uuid_obj
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class PaginateResponseSchema(BaseModel, Generic[T]):
    items: List[T]
    prev_page: Optional[str] = None
    next_page: Optional[str] = None
    total_pages: int
    total_items: int
    model_config = ConfigDict(from_attributes=True)


class NameIdSchema(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)


class EntityDetailSchema(NameIdSchema):
    movies: List[NameIdSchema] = []


class EntityMovieCountSchema(NameIdSchema):
    movies_count: int = 0


class EntityCreateOrUpdateSchema(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class MovieCreateSchema(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    year: int = Field(ge=1895, le=datetime.now().year + 5)
    time: int = Field(gt=0)
    imdb: float = Field(0.0, ge=0, le=10.0)
    votes: int = Field(0, ge=0)
    meta_score: Optional[float] = Field(0.0, ge=0, le=100.0)
    gross: Optional[float] = Field(None, ge=0)
    price: Decimal = Field(Decimal("0.0"), ge=0)
    description: str = Field(min_length=3)
    certification: str = Field(min_length=1)
    genres: List[str]
    stars: List[str]
    directors: List[str]
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class MovieUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    year: Optional[int] = Field(None, ge=1895, le=datetime.now().year + 5)
    time: Optional[int] = Field(None, gt=0)
    imdb: Optional[float] = Field(None, ge=0, le=10.0)
    votes: Optional[int] = Field(None, ge=0)
    meta_score: Optional[float] = Field(None, ge=0, le=100.0)
    gross: Optional[float] = Field(None, ge=0)
    price: Optional[Decimal] = Field(
        None, ge=0, max_digits=10, decimal_places=2, le=99999999.99
    )
    description: Optional[str] = Field(None, min_length=3)

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class MovieSchemaBase(BaseModel):
    id: int
    uuid: uuid_obj.UUID
    name: str
    year: int
    time: int
    imdb: float
    votes: int
    meta_score: float | None = None
    gross: float | None = None
    price: Decimal
    model_config = ConfigDict(from_attributes=True)


class MovieDetailSchema(MovieSchemaBase):
    description: str

    certification: Optional[NameIdSchema] = None
    genres: List[NameIdSchema] = []
    stars: List[NameIdSchema] = []
    directors: List[NameIdSchema] = []

    model_config = ConfigDict(from_attributes=True)
