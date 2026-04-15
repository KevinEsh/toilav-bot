import os

import uvicorn
from config import configure_logging
from fastapi import FastAPI
from routes import router

configure_logging()

app = FastAPI(title="Yalti Chatbot")
app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8001,
        reload=True,
        app_dir=os.path.dirname(os.path.abspath(__file__)),
    )
