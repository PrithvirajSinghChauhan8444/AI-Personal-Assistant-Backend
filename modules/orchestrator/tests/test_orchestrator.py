import unittest
from modules.orchestrator.scheduler import TaskScheduler
from modules.contracts.state_contract import SubTask

class TestTaskScheduler(unittest.TestCase):
    def setUp(self):
        self.scheduler = TaskScheduler(allow_parallel=True, max_parallel=2)

    def test_empty_subtasks_routes_to_finalizer(self):
        targets, updated = self.scheduler.evaluate_queue([], {})
        self.assertEqual(targets, ["OutputFinalizer"])
        self.assertEqual(updated, [])

    def test_single_pending_task_dispatched(self):
        subtasks: list[SubTask] = [{
            "id": "task_1",
            "description": "Read file",
            "assigned_worker": "SystemWorker",
            "status": "pending",
            "depends_on": []
        }]
        targets, updated = self.scheduler.evaluate_queue(subtasks, {})
        self.assertEqual(targets, ["SystemWorker"])
        self.assertEqual(len(updated), 1)
        self.assertEqual(updated[0]["status"], "in_progress")

    def test_dependent_task_waits_for_prerequisite(self):
        subtasks: list[SubTask] = [
            {
                "id": "task_1",
                "description": "Fetch data",
                "assigned_worker": "GmailWorker",
                "status": "in_progress",
                "depends_on": []
            },
            {
                "id": "task_2",
                "description": "Process data",
                "assigned_worker": "SystemWorker",
                "status": "pending",
                "depends_on": ["task_1"]
            }
        ]
        targets, updated = self.scheduler.evaluate_queue(subtasks, {})
        # task_2 cannot run yet because task_1 is not completed; routes to task_1's worker to complete it
        self.assertEqual(targets, ["CommunicationWorker"])
        self.assertEqual(len(updated), 0)

    def test_dependent_task_runs_after_completion(self):
        subtasks: list[SubTask] = [
            {
                "id": "task_1",
                "description": "Fetch data",
                "assigned_worker": "GmailWorker",
                "status": "completed",
                "depends_on": []
            },
            {
                "id": "task_2",
                "description": "Process data",
                "assigned_worker": "SystemWorker",
                "status": "pending",
                "depends_on": ["task_1"]
            }
        ]
        targets, updated = self.scheduler.evaluate_queue(subtasks, {"task_1": {"summary": "Done"}})
        self.assertEqual(targets, ["SystemWorker"])
        self.assertEqual(len(updated), 1)
        self.assertEqual(updated[0]["id"], "task_2")
        self.assertEqual(updated[0]["status"], "in_progress")

    def test_all_completed_routes_to_finalizer(self):
        subtasks: list[SubTask] = [
            {
                "id": "task_1",
                "description": "Task 1",
                "assigned_worker": "SystemWorker",
                "status": "completed",
                "depends_on": []
            }
        ]
        targets, updated = self.scheduler.evaluate_queue(subtasks, {"task_1": {"summary": "Done"}})
        self.assertEqual(targets, ["OutputFinalizer"])

if __name__ == "__main__":
    unittest.main()
