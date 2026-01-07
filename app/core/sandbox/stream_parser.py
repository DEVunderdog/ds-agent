import struct
import io
from typing import Tuple


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
            header_from_data = self.buffer[:self.header]
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
