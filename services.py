import queue


class TaskService():
    service_queue: queue.Queue = queue.Queue()
    __instance = None

    def __new__(cls):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    @classmethod
    def start_service(cls):
        while True:
            task = cls.service_queue.get(block=True)
            job_uuid: str = task[0].uuid
            task[1].result()
            print(f"Processing job: {job_uuid}")
