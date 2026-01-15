import tempfile
import magic
import structlog
from pathlib import Path
from fastapi import UploadFile, File, HTTPException, status, APIRouter
from app.constants.globals import MAX_DATASET_FILE_SIZE

logger = structlog.get_logger(__name__)

MAX_FILE_SIZE = MAX_DATASET_FILE_SIZE * 1024 * 1024
CHUNK_SIZE = 1024 * 1024

router = APIRouter(prefix="/uploads", tags=["file uploads"])


@router.post("/dataset")
async def upload_dataset(file: UploadFile = File(...)):

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid file extension. Only .csv files are allowed",
        )

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as temp_file:
            real_file_size = 0

            while content := await file.read(CHUNK_SIZE):
                real_file_size += len(content)

                if real_file_size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=f"file too large. Maximum size is {MAX_FILE_SIZE/1024/1024}MB",
                    )

                temp_file.write(content)

            temp_file.seek(0)

            header_sample = temp_file.read(2048)
            mime_type = magic.from_buffer(header_sample, mime=True)

            temp_file.seek(0)

            valid_mime_types = ["text/csv", "text/plain", "application/csv"]

            if mime_type not in valid_mime_types:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"invalid file type detected: {mime_type}. Please upload a valid CSV",
                )

            # Need to figure out the what to do with the tempath
    except HTTPException:
        # cleanup temp file if it was created
        raise

    except Exception as e:
        # cleanup temporary file
        logger.error(f"error while uploading file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="error while uploading file",
        )
