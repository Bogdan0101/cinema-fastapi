from fastapi import FastAPI
from src.routes.movies import router as movie_router

app = FastAPI(
    title="Cinema FastAPI",
)

app.include_router(movie_router, prefix="/cinema", tags=["movies"])


@app.get("/")
async def root():
    return {"message": "Hello World"}
