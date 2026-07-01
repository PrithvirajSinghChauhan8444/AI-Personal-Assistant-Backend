from unittest.mock import MagicMock

def create_mock_gmail_service():
    service = MagicMock()
    
    # Setup mocks for messages endpoints
    messages_list_mock = MagicMock()
    messages_get_mock = MagicMock()
    messages_send_mock = MagicMock()
    messages_batchModify_mock = MagicMock()
    messages_trash_mock = MagicMock()
    messages_delete_mock = MagicMock()
    
    # Setup mocks for drafts endpoints
    drafts_create_mock = MagicMock()
    
    # Setup mocks for labels endpoints
    labels_list_mock = MagicMock()
    labels_create_mock = MagicMock()
    labels_delete_mock = MagicMock()
    labels_patch_mock = MagicMock()

    # Connect the nested chaining structure: service.users().*
    users_mock = service.users.return_value
    
    # Messages chain: service.users().messages()
    messages_api = users_mock.messages.return_value
    messages_api.list.return_value = messages_list_mock
    messages_api.get.return_value = messages_get_mock
    messages_api.send.return_value = messages_send_mock
    messages_api.batchModify.return_value = messages_batchModify_mock
    messages_api.trash.return_value = messages_trash_mock
    messages_api.delete.return_value = messages_delete_mock
    
    # Drafts chain: service.users().drafts()
    drafts_api = users_mock.drafts.return_value
    drafts_api.create.return_value = drafts_create_mock
    
    # Labels chain: service.users().labels()
    labels_api = users_mock.labels.return_value
    labels_api.list.return_value = labels_list_mock
    labels_api.create.return_value = labels_create_mock
    labels_api.delete.return_value = labels_delete_mock
    labels_api.patch.return_value = labels_patch_mock
    
    # Attach helper attributes for easy testing
    service._messages_list_mock = messages_list_mock
    service._messages_get_mock = messages_get_mock
    service._messages_send_mock = messages_send_mock
    service._messages_batchModify_mock = messages_batchModify_mock
    service._messages_trash_mock = messages_trash_mock
    service._messages_delete_mock = messages_delete_mock
    service._drafts_create_mock = drafts_create_mock
    service._labels_list_mock = labels_list_mock
    service._labels_create_mock = labels_create_mock
    service._labels_delete_mock = labels_delete_mock
    service._labels_patch_mock = labels_patch_mock
    
    def set_list_response(messages_list, next_page_token=None):
        ret = {"messages": messages_list}
        if next_page_token:
            ret["nextPageToken"] = next_page_token
        messages_list_mock.execute.return_value = ret
        
    def set_get_response(message_data):
        messages_get_mock.execute.return_value = message_data
        
    def set_labels_list_response(labels_list):
        labels_list_mock.execute.return_value = {"labels": labels_list}
        
    def set_labels_create_response(label_data):
        labels_create_mock.execute.return_value = label_data
        
    service.set_list_response = set_list_response
    service.set_get_response = set_get_response
    service.set_labels_list_response = set_labels_list_response
    service.set_labels_create_response = set_labels_create_response
    
    return service
