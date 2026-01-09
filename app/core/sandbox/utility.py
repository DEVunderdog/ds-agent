import os
import struct
import io
import tarfile
import time
from typing import Tuple, Dict, Union, List


class StreamParser:
    def __init__(self, header: int):
        self.header = header
        self.buffer = bytearray()
        self._stdout = io.BytesIO()
        self._stderr = io.BytesIO()

    def feed(self, data: bytes):
        self.buffer.extend(data)
        self._process_buffer()

    def _process_buffer(self):
        while True:
            if len(self.buffer) < self.header:
                return

            # Docker Header: [StreamType (1b)][Padding (3b)][Length (4b)]
            header_from_data = self.buffer[: self.header]
            stream_type, length = struct.unpack(">BxxxL", header_from_data)

            total_frame_size = self.header + length

            if len(self.buffer) < total_frame_size:
                return

            payload_start = self.header
            payload_end = total_frame_size
            payload = self.buffer[payload_start:payload_end]

            if stream_type == 1:
                self._stdout.write(payload)
            elif stream_type == 2:
                self._stderr.write(payload)

            del self.buffer[:total_frame_size]

    def get_output(self) -> Tuple[bytes, bytes]:
        return self._stdout.getvalue(), self._stderr.getvalue()


def create_archive(files: List[Dict[str, Union[str, bytes]]]) -> bytes:
    tar_stream = io.BytesIO()
    with tarfile.open(fileobj=tar_stream, mode="w") as tar:
        for f in files:
            name = f["name"]
            content = f["content"]

            if isinstance(content, str):
                content = content.encode("utf-8")

            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            info.mtime = int(time.time())
            tar.addfile(info, io.BytesIO(content))

    tar_stream.seek(0)
    return tar_stream.getvalue()


def extract_file_from_archive(tar_bytes: bytes, filename: str) -> bytes:
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r") as tar:
        try:
            member = tar.getmember(filename)
            if not member.isfile():
                raise FileNotFoundError(f"{filename} is not a regular file")

            f = tar.extractfile(member)
            return f.read() if f else b""
        except KeyError:
            raise FileNotFoundError(f"file {filename} not found in archive")


def create_archive_from_path(file_paths: List[Tuple[str, str]]) -> bytes:
    tar_stream = io.BytesIO()
    with tarfile.open(fileobj=tar_stream, mode="w") as tar:
        for local_path, remote_name in file_paths:
            if not os.path.exists(local_path):
                raise FileNotFoundError(f"local file not found: {local_path}")

            with open(local_path, "rb") as f:
                data = f.read()

            info = tarfile.TarInfo(name=remote_name)
            info.size = len(data)
            info.mtime = int(time.time())

            tar.addfile(info, io.BytesIO(data))

    tar_stream.seek(0)
    return tar_stream.getvalue()
