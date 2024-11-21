import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.websocket import router as websocket_router
from api.routes import router as api_router
from config.settings import Settings
from utils.redis_manager import RedisManager
from contextlib import asynccontextmanager

settings = Settings()
connection_manager = RedisManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    connection_manager.start()
    yield
    # Shutdown
    connection_manager.stop()

app = FastAPI(name=settings.APP_NAME, debug=settings.DEBUG, lifespan=lifespan)


# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(websocket_router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)