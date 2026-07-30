from fastapi import FastAPI

from app.api.datasets import router as datasets_router
from app.api.planning import router as planning_router

app = FastAPI(title="7x API")
app.include_router(datasets_router)
app.include_router(planning_router)


@app.get("/health")
def health():
    return {"status": "ok"}
