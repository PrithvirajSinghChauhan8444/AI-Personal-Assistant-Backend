from ytmusicapi import YTMusic
import json
import os

# The ytmusicapi requires authentication. 
# Usually, this is done by creating a headers_auth.json file.
# I will check if it exists or if I need to ask the user.

auth_file = "headers_auth.json"

if not os.path.exists(auth_file):
    print(json.dumps({"error": "Authentication file 'headers_auth.json' not found. Please provide authentication headers."}))
else:
    try:
        yt = YTMusic(auth_file)
        playlists = yt.get_library_playlists()
        print(json.dumps(playlists))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
