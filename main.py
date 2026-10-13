from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import os
import uuid

app = FastAPI(
    title="MM AI Video Studio",
    description="AI-powered Myanmar video storytelling API",
    version="1.0.0"
)

# Website နဲ့ Backend ချိတ်ဆက်ရန်
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("/tmp/mm_ai_uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB


@app.get("/")
async def home():
    return {
        "app": "MM AI Video Studio",
        "status": "online",
        "message": "Backend အလုပ်လုပ်နေပါပြီ!"
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy"
    }


@app.post("/upload")
async def upload_video(video: UploadFile = File(...)):

    if not video.content_type or not video.content_type.startswith("video/"):
        raise HTTPException(
            status_code=400,
            detail="ဗီဒီယိုဖိုင်ကိုသာ Upload တင်ပေးပါ။"
        )

    file_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / f"{file_id}.video"
    total_size = 0

    try:
        with file_path.open("wb") as output:
            while True:
                chunk = await video.read(1024 * 1024)

                if not chunk:
                    break

                total_size += len(chunk)

                if total_size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail="ဖိုင်အရွယ်အစားသည် 100 MB ထက်ကျော်နေပါသည်။"
                    )

                output.write(chunk)

        return {
            "success": True,
            "file_id": file_id,
            "filename": video.filename,
            "size_mb": round(total_size / (1024 * 1024), 2),
            "message": "ဗီဒီယို Upload အောင်မြင်ပါသည်။"
        }

    except HTTPException:
        file_path.unlink(missing_ok=True)
        raise

    except Exception:
        file_path.unlink(missing_ok=True)

        raise HTTPException(
            status_code=500,
            detail="ဗီဒီယို Upload လုပ်ရာတွင် အမှားဖြစ်ပွားခဲ့ပါသည်။"
        )

    finally:
        await video.close()
