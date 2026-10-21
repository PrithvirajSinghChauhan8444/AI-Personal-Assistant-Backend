import unittest
from unittest.mock import MagicMock, patch
from modules.workers.misc_worker.worker import MiscWorker
from modules.workers.misc_worker.integrations.misc_client import (
    get_user_playlists,
    create_user_playlist,
    add_tracks_to_playlist,
    search_ytmusic,
    run_script,
)
from modules.workers.misc_worker.tools.misc_tools import (
    ytmusic_list_playlists,
    ytmusic_create_new_playlist,
    ytmusic_add_songs_to_playlist,
    ytmusic_search_songs,
    execute_utility_script,
)

class TestMiscWorker(unittest.TestCase):
    def setUp(self):
        self.mock_llm = MagicMock()
        self.worker = MiscWorker(llm_client=self.mock_llm)
        self.worker._agent = MagicMock()

    def test_execute_misc_success(self):
        msg_mock = MagicMock()
        msg_mock.content = "Playlist created and tracks queued successfully."
        self.worker._agent.invoke.return_value = {"messages": [msg_mock]}

        res = self.worker.execute_task("task_misc_1", "Manage music playlist", {})
        self.assertEqual(res["status"], "completed")
        self.assertIn("Playlist created", res["summary"])

    def test_execute_misc_failure(self):
        self.worker._agent.invoke.side_effect = Exception("Custom script execution timed out")
        res = self.worker.execute_task("task_misc_1", "Manage music playlist", {})
        self.assertEqual(res["status"], "failed")
        self.assertIn("timed out", res["error_message"])

    @patch("modules.workers.misc_worker.integrations.misc_client._get_ytmusic_client")
    def test_get_user_playlists(self, mock_client_factory):
        mock_yt = MagicMock()
        mock_yt.get_library_playlists.return_value = [{"title": "Favorites", "playlistId": "PL123"}]
        mock_client_factory.return_value = mock_yt

        res = get_user_playlists()
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["title"], "Favorites")

    @patch("modules.workers.misc_worker.integrations.misc_client._get_ytmusic_client")
    def test_create_user_playlist(self, mock_client_factory):
        mock_yt = MagicMock()
        mock_yt.create_playlist.return_value = "PL_NEW_123"
        mock_client_factory.return_value = mock_yt

        res = create_user_playlist("Chill Vibes", "Relaxing tracks")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["playlist_id"], "PL_NEW_123")

    @patch("modules.workers.misc_worker.integrations.misc_client.subprocess.run")
    def test_run_script_not_found(self, mock_run):
        res = run_script("non_existent_script.py")
        self.assertIn("error", res)

    @patch("modules.workers.misc_worker.integrations.misc_client.os.path.exists", return_value=True)
    @patch("modules.workers.misc_worker.integrations.misc_client.subprocess.run")
    def test_run_script_success(self, mock_run, mock_exists):
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = "All checks passed\n"
        mock_res.stderr = ""
        mock_run.return_value = mock_res

        res = run_script("test_script.py")
        self.assertEqual(res["status"], "success")
        self.assertIn("All checks passed", res["stdout"])

if __name__ == "__main__":
    unittest.main()
