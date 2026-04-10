from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import investigations, results
from app.core.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="NexusScope OSINT API Engine"
)

# Set all CORS enabled origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(investigations.router, prefix="/api/v1/investigations", tags=["Investigations"])
app.include_router(results.router, prefix="/api/v1/results", tags=["Results"])

@app.get("/")
async def root():
    return {"message": "NexusScope OSINT API is online"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}
