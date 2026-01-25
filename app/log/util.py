import json
from typing import List
from pathlib import Path
from typing import Optional
from app.constants.globals import DEV_LOG_PATH, PROD_LOG_PATH
from app.config import settings
from app.models.api import LogEntry


def get_log_path() -> str:
    if settings.is_development:
        return DEV_LOG_PATH
    else:
        return PROD_LOG_PATH


def get_log_level() -> str:
    if settings.is_development:
        return "DEBUG"
    else:
        return "INFO"


def get_filtered_logs(
    file_path: Path,
    limit: int = 100,
    level: Optional[str] = None,
    logger_name: Optional[str] = None,
    thread_id: Optional[str] = None,
    search_text: Optional[str] = None,
) -> List[LogEntry]:

    if not file_path.exists():
        return []

    results = []

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        for line in reversed(lines):
            if not line.strip():
                if not line.strip():
                    continue

                try:
                    log_data = json.loads(line)

                    if level and log_data.get("level", "").upper() != level.upper():
                        continue

                    if (
                        logger_name
                        and logger_name.lower()
                        not in log_data.get("logger", "").lower()
                    ):
                        continue

                    if thread_id:
                        log_thread = log_data.get("thread_id")
                        if log_thread != thread_id:
                            continue

                    if (
                        search_text
                        and search_text.lower()
                        not in log_data.get("message", "").lower()
                    ):
                        continue

                    results.append(LogEntry(**log_data))

                    if len(results) >= limit:
                        break

                except json.JSONDecodeError:
                    continue
    except Exception as e:
        return [
            LogEntry(
                timestamp="NOW",
                level="ERROR",
                logger="system",
                message=f"Error reading logs: {str(e)}",
                module="log_reader",
                line_no=0,
            )
        ]

    return results
