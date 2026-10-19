import unittest
from unittest.mock import MagicMock
from modules.synthesizer.finalizer import OutputSynthesizer
from modules.synthesizer.reflection import ReflectionEngine

class TestSynthesizer(unittest.TestCase):
    def setUp(self):
        self.mock_llm = MagicMock()
        self.mock_resp = MagicMock()
        self.mock_resp.content = "Here is your synthesized answer."
        self.mock_llm.invoke.return_value = self.mock_resp

        self.synthesizer = OutputSynthesizer(llm_client=self.mock_llm)
        self.reflection = ReflectionEngine(llm_client=self.mock_llm)

    def test_synthesize_output(self):
        completed_tasks = {
            "task_1": {"worker": "SystemWorker", "description": "Check CPU", "summary": "CPU at 15%"}
        }
        res = self.synthesizer.synthesize("Check system health", completed_tasks)
        self.assertIn("synthesized answer", res)

    def test_reflection_extract_facts(self):
        self.mock_resp.content = "- User prefers dark mode\n- User lives in Seattle"
        facts = self.reflection.extract_facts("Set theme to dark", "Done!")
        self.assertEqual(len(facts), 2)
        self.assertEqual(facts[0], "User prefers dark mode")

if __name__ == "__main__":
    unittest.main()
