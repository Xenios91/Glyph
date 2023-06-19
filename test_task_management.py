import unittest
from request_handler import DataHandler, TrainingRequest
from services import TaskService

from task_management import TaskManager


class task_management_test(unittest.TestCase):

    def test_get_uuid(self):
        task_manager: TaskManager = TaskManager()
        uuid: str = task_manager.get_uuid()
        self.assertTrue(len(uuid) == 36)
        self.assertTrue(isinstance(uuid, str))

    def test_get_status(self):
        task_manager: TaskManager = TaskManager()
        training_request: TrainingRequest = TrainingRequest("1234", "test_model", {
                                                            "binaryName": "testBin", "functionsMap": {"functions": [{"tokenList": ["testToken"]}]}})
        TaskService().service_queue.put(training_request)
        status: str = task_manager.get_status("1234")
        self.assertEqual("starting", status)


if __name__ == '__main__':
    unittest.main()
