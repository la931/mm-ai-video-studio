import os
import time
import tempfile
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types

app = FastAPI(title="MM AI Video Studio")

app.add_middleware(
CORSMiddleware,
allow_origins=[""],
allow_methods=["GET", "POST"],
allow_headers=[""],
)

MAX_FILE_SIZE = 100 * 1024 * 1024

@app.get("/")
async def home():
return {
"app": "MM AI Video Studio",
"status": "online",
"message": "Backend is running"
}

@app.get("/health")
async def health():
return {"status": "healthy"}

@app.post("/analyze")
async def analyze_video(video: UploadFile = File(...)):

api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    raise HTTPException(
        status_code=500,
        detail="GEMINI_API_KEY is not configured"
    )

if not video.content_type or not video.content_type.startswith("video/"):
    raise HTTPException(
        status_code=400,
        detail="Please upload a video file"
    )

suffix = Path(video.filename or "video.mp4").suffix or ".mp4"
temp_path = None
uploaded_file = None

try:
    total_size = 0

    with tempfile.NamedTemporaryFile(
        suffix=suffix,
        delete=False
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
                    detail="Video must be 100 MB or smaller"
                )

            temp.write(chunk)

    client = genai.Client(api_key=api_key)

    uploaded_file = client.files.upload(
        file=temp_path,
        config=types.UploadFileConfig(
            mime_type=video.content_type
        )
    )

    # Wait until Gemini finishes processing the uploaded video.
    deadline = time.time() + 240

    while uploaded_file.state and uploaded_file.state.name == "PROCESSING":
        if time.time() > deadline:
            raise HTTPException(
                status_code=504,
                detail="Video processing timed out. Please try a shorter video."
            )

        time.sleep(3)
        uploaded_file = client.files.get(name=uploaded_file.name)

    if not uploaded_file.state or uploaded_file.state.name != "ACTIVE":
        raise HTTPException(
            status_code=422,
            detail="Gemini could not process this video"
        )

    prompt = """

You are a professional Chinese drama recap narrator.

Analyze the uploaded video and explain its actual story in Burmese.

Write in natural, engaging Burmese suitable for voice narration.

Include:

1. The main characters and their apparent roles.
2. The important scenes and actions in chronological order.
3. The main conflict and emotional moments.
4. A coherent Burmese narration based on what is actually shown.
5. Do not invent events that are not supported by the video.

If some details are unclear, say so instead of guessing.
Return the narration in Burmese.
"""

    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=[uploaded_file, prompt]
    )

    narration = response.text or ""

    if not narration.strip():
        raise HTTPException(
            status_code=502,
            detail="AI did not return a narration"
        )

    return {
        "success": True,
        "filename": video.filename,
        "narration": narration,
        "message": "AI video analysis completed"
    }

except HTTPException:
    raise

except Exception as exc:
    print("Video analysis error:", repr(exc))

    raise HTTPException(
        status_code=500,
        detail="AI analysis failed. Check the Render logs and Gemini API configuration."
    )

finally:
    await video.close()

    if temp_path and os.path.exists(temp_path):
        os.remove(temp_path)
