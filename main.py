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

Use a model available to your Gemini API key.

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

You are a professional Chinese drama recap narrator.

Analyze the uploaded video and write an engaging Burmese narration
based only on events and details supported by the video.

Include:

1. Main characters and their apparent roles.
2. Important scenes and actions in chronological order.
3. Main conflicts and emotional moments.
4. A coherent Burmese narration suitable for voice-over.
5. Do not invent events or character relationships.

If any detail is unclear, say so rather than guessing.
Return the narration in natural Burmese.
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
