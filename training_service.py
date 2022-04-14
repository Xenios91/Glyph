from asyncio import Future
from typing import Dict
import time


class TrainingService():
    queue: Dict[str, Future] = {}

    @classmethod
    def start_service(cls):
        while True:
            for uuid, request in cls.queue.items():
                request.result()
                print(f"Processing job: {uuid}")
            time.sleep(15)
