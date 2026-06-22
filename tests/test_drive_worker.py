import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Set paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Prevent duplicate module objects being loaded under different namespaces
import src.CoreFunctions.unified_memory
sys.modules['CoreFunctions.unified_memory'] = src.CoreFunctions.unified_memory

import src.CoreFunctions.memory
sys.modules['CoreFunctions.memory'] = src.CoreFunctions.memory

import src.CoreFunctions.StateGraph.registry
sys.modules['CoreFunctions.StateGraph.registry'] = src.CoreFunctions.StateGraph.registry

from src.CoreFunctions.StateGraph.registry import WorkerRegistry
from src.CoreFunctions.StateGraph.Workers.GoogleDriveWorker.drive_worker import GoogleDriveWorker
from src.CoreFunctions.Integrations.GoogleDrive.drive_ops import (
    list_drive_files, download_drive_file, upload_drive_file,
    create_drive_folder, delete_drive_file, get_drive_about
)

class TestGoogleDriveWorker(unittest.TestCase):
    def setUp(self):
        # Setup mocks for API dependencies to avoid actual network/auth requests
        self.mock_creds_patch = patch('src.CoreFunctions.Integrations.GoogleDrive.drive_ops.get_valid_credentials')
        self.mock_build_patch = patch('src.CoreFunctions.Integrations.GoogleDrive.drive_ops.build')
        
        self.mock_get_creds = self.mock_creds_patch.start()
        self.mock_build = self.mock_build_patch.start()
        
        # Setup MagicMocks for Drive service
        self.mock_service = MagicMock()
        self.mock_files = MagicMock()
        
        self.mock_service.files.return_value = self.mock_files
        self.mock_build.return_value = self.mock_service
        self.mock_get_creds.return_value = MagicMock() # Mock credentials object

    def tearDown(self):
        self.mock_creds_patch.stop()
        self.mock_build_patch.stop()

    def test_worker_registration(self):
        # Verify that GoogleDriveWorker is registered in WorkerRegistry._registry
        from src.CoreFunctions.StateGraph.registry import scan_and_register_workers
        scan_and_register_workers()
        
        self.assertIn("GoogleDriveWorker", WorkerRegistry._registry)
        worker = WorkerRegistry.get_worker("GoogleDriveWorker")
        self.assertEqual(worker.name, "GoogleDriveWorker")
        self.assertIn("cloud-storage", worker.categories)
        self.assertEqual(len(worker.tools), 7) # 6 Drive tools + 1 human_intervention

    def test_list_drive_files(self):
        # Set up mock files list return value
        mock_list = MagicMock()
        mock_list.execute.return_value = {
            'files': [
                {'id': '123', 'name': 'file1.txt', 'mimeType': 'text/plain'},
                {'id': '456', 'name': 'folder1', 'mimeType': 'application/vnd.google-apps.folder'}
            ]
        }
        self.mock_files.list.return_value = mock_list
        
        res = list_drive_files(query="name contains 'test'", limit=5)
        
        self.mock_files.list.assert_called_once_with(
            q="name contains 'test'",
            pageSize=5,
            fields="nextPageToken, files(id, name, mimeType, size, modifiedTime, parents)"
        )
        self.assertEqual(res["count"], 2)
        self.assertEqual(res["files"][0]["name"], "file1.txt")

    def test_create_drive_folder(self):
        mock_create = MagicMock()
        mock_create.execute.return_value = {'id': 'folder_99', 'name': 'NewFolder'}
        self.mock_files.create.return_value = mock_create
        
        res = create_drive_folder(name="NewFolder", parent_id="parent_abc")
        
        self.mock_files.create.assert_called_once_with(
            body={
                'name': 'NewFolder',
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': ['parent_abc']
            },
            fields='id, name'
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["folder"]["id"], "folder_99")

    def test_delete_drive_file(self):
        mock_update = MagicMock()
        mock_update.execute.return_value = {'id': 'file_123', 'trashed': True}
        self.mock_files.update.return_value = mock_update
        
        res = delete_drive_file(file_id="file_123")
        
        self.mock_files.update.assert_called_once_with(
            fileId="file_123",
            body={'trashed': True}
        )
        self.assertIn("Successfully moved file/folder", res)

    @patch('src.CoreFunctions.Integrations.GoogleDrive.drive_ops.MediaFileUpload')
    def test_upload_drive_file(self, mock_media_class):
        mock_create = MagicMock()
        mock_create.execute.return_value = {'id': 'uploaded_77', 'name': 'notes.txt', 'mimeType': 'text/plain'}
        self.mock_files.create.return_value = mock_create
        
        # Mock os.path.exists to return True
        with patch('os.path.exists', return_value=True):
            res = upload_drive_file(local_path="/tmp/notes.txt", name="notes.txt", parent_id="parent_xyz")
            
        self.mock_files.create.assert_called_once_with(
            body={
                'name': 'notes.txt',
                'parents': ['parent_xyz']
            },
            media_body=mock_media_class.return_value,
            fields='id, name, mimeType'
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["file"]["id"], "uploaded_77")

    @patch('src.CoreFunctions.Integrations.GoogleDrive.drive_ops.MediaIoBaseDownload')
    @patch('os.makedirs')
    @patch('src.CoreFunctions.Integrations.GoogleDrive.drive_ops.open', create=True)
    def test_download_drive_file_binary(self, mock_open, mock_makedirs, mock_download_class):
        # 1. Mock file metadata call
        mock_get_meta = MagicMock()
        mock_get_meta.execute.return_value = {'name': 'photo.jpg', 'mimeType': 'image/jpeg'}
        self.mock_files.get.return_value = mock_get_meta
        
        # 2. Mock downloader return
        mock_downloader = MagicMock()
        mock_downloader.next_chunk.return_value = (None, True)
        mock_download_class.return_value = mock_downloader
        
        res = download_drive_file(file_id="photo_123", local_path="/downloads/photo.jpg")
        
        self.mock_files.get.assert_called_once_with(fileId="photo_123", fields='name, mimeType')
        self.mock_files.get_media.assert_called_once_with(fileId="photo_123")
        self.assertIn("Successfully downloaded file 'photo.jpg'", res)

    @patch('src.CoreFunctions.Integrations.GoogleDrive.drive_ops.MediaIoBaseDownload')
    @patch('os.makedirs')
    @patch('src.CoreFunctions.Integrations.GoogleDrive.drive_ops.open', create=True)
    def test_download_drive_file_google_doc_export(self, mock_open, mock_makedirs, mock_download_class):
        # 1. Mock workspace file metadata
        mock_get_meta = MagicMock()
        mock_get_meta.execute.return_value = {'name': 'Weekly Report', 'mimeType': 'application/vnd.google-apps.document'}
        self.mock_files.get.return_value = mock_get_meta
        
        # 2. Mock downloader
        mock_downloader = MagicMock()
        mock_downloader.next_chunk.return_value = (None, True)
        mock_download_class.return_value = mock_downloader
        
        # Call download drive file (the extension .docx should be automatically appended)
        res = download_drive_file(file_id="doc_456", local_path="/downloads/Weekly Report")
        
        self.mock_files.export_media.assert_called_once_with(
            fileId="doc_456",
            mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        self.assertIn("Successfully downloaded file 'Weekly Report' to '/downloads/Weekly Report.docx'", res)

    def test_get_drive_about(self):
        mock_about = MagicMock()
        mock_about.get.return_value.execute.return_value = {
            'storageQuota': {
                'limit': '15000000000',
                'usage': '5000000000',
                'usageInDrive': '3000000000',
                'usageInDriveTrash': '200000000'
            },
            'user': {
                'displayName': 'John Doe',
                'emailAddress': 'john.doe@gmail.com'
            }
        }
        self.mock_service.about.return_value = mock_about
        
        res = get_drive_about(account="personal")
        
        self.mock_service.about.return_value.get.assert_called_once_with(fields="storageQuota, user")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["user"]["display_name"], "John Doe")
        self.assertEqual(res["storage_formatted"]["limit"], "13.97 GB")
        self.assertEqual(res["storage_formatted"]["usage_total"], "4.66 GB")
        self.assertEqual(res["storage_formatted"]["free_space"], "9.31 GB")

if __name__ == "__main__":
    unittest.main()
