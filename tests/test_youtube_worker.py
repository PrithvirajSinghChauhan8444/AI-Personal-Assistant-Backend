import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Set paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from src.CoreFunctions.StateGraph.worker_framework import WorkerRegistry
from src.CoreFunctions.StateGraph.Workers.YoutubeWorker.youtube_worker import YoutubeWorker
from src.CoreFunctions.Integrations.Google.youtube_ops import (
    get_video_state,
    set_video_state,
    check_new_videos,
    search_youtube_videos,
    get_video_transcript
)

class TestYoutubeWorkerAndOps(unittest.TestCase):
    
    def setUp(self):
        # Clean state/memory mock
        self.memory_store = {}
        
    @patch('src.CoreFunctions.Integrations.Google.youtube_ops.fetch_memory')
    def test_get_video_state(self, mock_fetch):
        # Test state retrieval when video state is set
        mock_fetch.return_value = "read"
        state = get_video_state("dQw4w9WgXcQ")
        self.assertEqual(state, "read")
        mock_fetch.assert_called_with(category="past", key="yt_state_dQw4w9WgXcQ")
        
        # Test state retrieval when video is unseen (None)
        mock_fetch.return_value = None
        state = get_video_state("xyz12345678")
        self.assertIsNone(state)

    @patch('src.CoreFunctions.Integrations.Google.youtube_ops.store_memory')
    @patch('src.CoreFunctions.Integrations.Google.youtube_ops.MemoryManager')
    def test_set_video_state_and_limit(self, mock_um_class, mock_store):
        mock_um = MagicMock()
        mock_um.enabled = True
        mock_um.list_keys.return_value = ["past:yt_state_v1"] * 505  # Trigger cleanup
        mock_um.retrieve_memory.return_value = {"value": "read", "timestamp": "2026-07-14T05:30:00"}
        mock_um_class.return_value = mock_um
        
        # Test set status
        set_video_state("dQw4w9WgXcQ", "read")
        mock_store.assert_called_with(category="past", key="yt_state_dQw4w9WgXcQ", value="read")
        
        # Verify cleanup attempt was made (since count > 500)
        mock_um.list_keys.assert_called_with("past:yt_state_*")

    @patch('src.CoreFunctions.Integrations.Google.youtube_ops.get_youtube_service')
    @patch('src.CoreFunctions.Integrations.Google.youtube_ops.get_video_state')
    def test_check_new_videos(self, mock_get_state, mock_get_service):
        # Mock youtube api client
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        
        # Mock channel list response
        mock_service.channels().list().execute.return_value = {
            "items": [{
                "snippet": {"title": "TechChannel"},
                "contentDetails": {
                    "relatedPlaylists": {"uploads": "uploads_playlist_123"}
                }
            }]
        }
        
        # Mock playlist items response (latest uploads)
        mock_service.playlistItems().list().execute.return_value = {
            "items": [
                {
                    "snippet": {
                        "title": "New Python Video",
                        "publishedAt": "2026-07-14T05:30:00Z",
                        "resourceId": {"videoId": "video_py_1"}
                    }
                },
                {
                    "snippet": {
                        "title": "Old Python Video",
                        "publishedAt": "2026-07-14T05:30:00Z",
                        "resourceId": {"videoId": "video_py_2"}
                    }
                }
            ]
        }
        
        # Mock database state: video_py_1 is unseen (None), video_py_2 is read ("read")
        def mock_state_side_effect(vid):
            if vid == "video_py_2":
                return "read"
            return None
        mock_get_state.side_effect = mock_state_side_effect
        
        # Call check new videos
        new_vids = check_new_videos(["channel_abc"], limit_per_channel=2)
        
        # Should only return video_py_1 because video_py_2 has already been read
        self.assertEqual(len(new_vids), 1)
        self.assertEqual(new_vids[0]["video_id"], "video_py_1")
        self.assertEqual(new_vids[0]["title"], "New Python Video")

    @patch('src.CoreFunctions.Integrations.Google.youtube_ops.get_youtube_service')
    def test_search_youtube_videos(self, mock_get_service):
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        
        mock_service.search().list().execute.return_value = {
            "items": [{
                "id": {"videoId": "search_vid_1"},
                "snippet": {
                    "title": "Search Result Title",
                    "description": "Result Desc",
                    "publishedAt": "2026-07-14T01:00:00Z",
                    "channelId": "chan_xyz",
                    "channelTitle": "My Fav Channel"
                }
            }]
        }
        
        results = search_youtube_videos("LangGraph", max_results=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["video_id"], "search_vid_1")
        self.assertEqual(results[0]["title"], "Search Result Title")

    @patch('src.CoreFunctions.Integrations.Google.youtube_ops.get_youtube_service')
    def test_get_video_details(self, mock_get_service):
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        
        mock_service.videos().list().execute.return_value = {
            "items": [{
                "id": "dQw4w9WgXcQ",
                "snippet": {
                    "title": "Mock Video Title",
                    "description": "Mock Video Desc",
                    "channelTitle": "Mock Channel",
                    "tags": ["test"],
                    "publishedAt": "2026-07-14T02:00:00Z"
                }
            }]
        }
        
        from src.CoreFunctions.Integrations.Google.youtube_ops import get_video_details
        details = get_video_details("dQw4w9WgXcQ")
        self.assertIsNotNone(details)
        self.assertEqual(details["video_id"], "dQw4w9WgXcQ")
        self.assertEqual(details["title"], "Mock Video Title")
        self.assertEqual(details["description"], "Mock Video Desc")


    @patch('src.CoreFunctions.Integrations.Google.youtube_ops.YouTubeTranscriptApi')
    def test_get_video_transcript(self, mock_api_class):
        # Mock instance and fetch method
        mock_api_instance = MagicMock()
        mock_api_class.return_value = mock_api_instance
        
        mock_api_instance.fetch.return_value = [
            {"text": "Hello world", "start": 0.0, "duration": 2.0},
            {"text": "Welcome to the tutorial", "start": 5.5, "duration": 3.0}
        ]
        
        transcript = get_video_transcript("dQw4w9WgXcQ")
        self.assertIn("[00:00] Hello world", transcript)
        self.assertIn("[00:05] Welcome to the tutorial", transcript)

    def test_worker_registration(self):
        # Verify the YoutubeWorker is loaded and registered in the WorkerRegistry
        # Make sure that force scanning includes it
        from src.CoreFunctions.StateGraph.worker_framework import scan_and_register_workers
        scan_and_register_workers()
        
        all_workers = WorkerRegistry.get_all_workers()
        self.assertIn("YoutubeWorker", all_workers)
        worker = WorkerRegistry.get_worker("YoutubeWorker")
        self.assertEqual(worker.name, "YoutubeWorker")
        self.assertIn("youtube", worker.categories)
        self.assertTrue(len(worker.tools) > 0)


if __name__ == "__main__":
    unittest.main()
