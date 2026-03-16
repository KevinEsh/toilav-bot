import uvicorn
from config import configure_logging
from fastapi import FastAPI
from routes import router

configure_logging()

app = FastAPI(title="Yalti Chatbot")
app.include_router(router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
