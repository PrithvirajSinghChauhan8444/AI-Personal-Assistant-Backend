import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "models", "embedding")
os.makedirs(MODELS_DIR, exist_ok=True)

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    print("❌ Error: sentence-transformers is not installed in the current environment.")
    sys.exit(1)

def download_model(model_name: str, folder_name: str):
    target_path = os.path.join(MODELS_DIR, folder_name)
    if os.path.exists(target_path) and os.listdir(target_path):
        print(f"✅ Model '{model_name}' is already downloaded in '{target_path}'.")
        return
    
    print(f"📥 Downloading model '{model_name}' and saving to '{target_path}'...")
    try:
        model = SentenceTransformer(model_name)
        model.save(target_path)
        print(f"🎉 Successfully saved model '{model_name}' locally.")
    except Exception as e:
        print(f"❌ Failed to download model '{model_name}': {e}")
        sys.exit(1)

if __name__ == "__main__":
    download_model("BAAI/bge-small-en-v1.5", "bge-small-en-v1.5")
    download_model("sentence-transformers/all-MiniLM-L6-v2", "all-MiniLM-L6-v2")
    print("✨ Model downloading complete!")
