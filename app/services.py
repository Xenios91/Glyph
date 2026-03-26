import logging
import queue
from typing import Any


class TaskService:
    service_queue: queue.Queue[tuple[Any, Any]] = queue.Queue()
    __instance: Any = None

    def __new__(cls) -> "TaskService":
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    @classmethod
    def start_service(cls) -> None:
        while True:
            task: tuple[Any, Any] = cls.service_queue.get(block=True)
            job_uuid: str = task[0].uuid
            task[1].result()
            logging.info("Processing job: job_uuid=%s", job_uuid)
