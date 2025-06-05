from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import shutil
import os
from core.pipeline import process_card

app = FastAPI()
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
templates = Jinja2Templates(directory="frontend/templates")

UPLOAD_DIR = "frontend/static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "result": None, "filename": None})

@app.post("/upload", response_class=HTMLResponse)
async def upload(request: Request, file: UploadFile = File(...)):
    file_location = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Обработка карточки
    result = process_card(file_location)
    return templates.TemplateResponse("index.html", {"request": request, "result": result, "filename": file.filename})