import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types

app = FastAPI(
title="MM AI Video Studio",
version="1.1.0",
description="AI-powered Myanmar video storytelling API",
)

app.add_middleware(
CORSMiddleware,
allow_origins=[""],
allow_methods=["GET", "POST", "OPTIONS"],
allow_headers=[""],
)

MAX_FILE_SIZE = 100 * 1024 * 1024
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

@app.get("/")
async def home():
return {
"app": "MM AI Video Studio",
"status": "online",
"message": "Backend is running",
}

@app.get("/health")
async def health():
return {"status": "healthy"}

@app.post("/analyze")
async def analyze_video(video: UploadFile = File(...)):
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise HTTPException(
        status_code=500,
        detail="GEMINI_API_KEY is not configured",
    )

if not video.content_type or not video.content_type.startswith("video/"):
    raise HTTPException(
        status_code=400,
        detail="Please upload a valid video file",
    )

suffix = Path(video.filename or "video.mp4").suffix or ".mp4"
temp_path = None

try:
    total_size = 0

    with tempfile.NamedTemporaryFile(
        suffix=suffix,
        delete=False,
    ) as temp:
        temp_path = temp.name

        while True:
            chunk = await video.read(1024 * 1024)

            if not chunk:
                break

            total_size += len(chunk)

            if total_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail="Video must be 100 MB or smaller",
                )

            temp.write(chunk)

    client = genai.Client(api_key=api_key)

    uploaded_file = client.files.upload(
        file=temp_path,
        config=types.UploadFileConfig(
            mime_type=video.content_type,
        ),
    )

    prompt = """

သင်သည် တရုတ်ဇာတ်လမ်းတိုများကို မြန်မာလို ဇာတ်ကြောင်းပြန်လည်
ပြောပြပေးသော ကျွမ်းကျင်သူတစ်ဦးဖြစ်သည်။

ပေးပို့ထားသော ဗီဒီယိုကို ဆန်းစစ်ပြီး အောက်ပါအချက်များအတိုင်း
သဘာဝကျသော မြန်မာဘာသာစကားဖြင့် ဇာတ်ကြောင်းရေးပေးပါ။

၁။ အဓိကဇာတ်ကောင်များနှင့် ၎င်းတို့၏ အခန်းကဏ္ဍ။
၂။ ဇာတ်ကွက်များနှင့် လှုပ်ရှားမှုများကို အစဉ်လိုက်ဖော်ပြရန်။
၃။ အဓိကပဋိပက္ခများနှင့် စိတ်ခံစားမှုများ။
၄။ အသံဖြင့် ဖတ်ပြရန် သင့်လျော်သော ဇာတ်ကြောင်းတစ်ခု။
၅။ ဗီဒီယိုတွင် မပါဝင်သော အဖြစ်အပျက်များကို မဖန်တီးရန်။

မသေချာသော အချက်အလက်များကို ခန့်မှန်းမရေးပါနှင့်။
မြန်မာဘာသာဖြင့်သာ ဖြေဆိုပါ။
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[uploaded_file, prompt],
    )

    narration = response.text or ""

    if not narration.strip():
        raise HTTPException(
            status_code=502,
            detail="The AI returned an empty narration",
        )

    return {
        "success": True,
        "filename": video.filename,
        "narration": narration,
        "message": "Video analysis completed",
    }

except HTTPException:
    raise

except Exception as exc:
    print(f"Video analysis error: {exc!r}")

    raise HTTPException(
        status_code=500,
        detail=(
            "AI analysis failed. Check the Render logs, "
            "Gemini API key, model availability, and API quota."
        ),
    )

finally:
    await video.close()

    if temp_path and os.path.exists(temp_path):
        os.remove(temp_path)
