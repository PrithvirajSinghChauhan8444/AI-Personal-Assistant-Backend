import os
import re
import shutil

def clean_name(name):
    return re.sub(r'[^a-zA-Z0-9_-]', '-', name.strip().lower())

def migrate():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    skills_dir = os.path.join(base_dir, "Skills")
    if not os.path.exists(skills_dir):
        print("Skills directory not found.")
        return

    # Categories we should skip/ignore as they are already subdirectories
    known_categories = ["general", "information-retrieval", "dev-utils", "productivity", "communication"]

    # We do a two pass migration:
    # 1. Find all SKILL.md files that are directly under Skills/<skill-name>/ (not under a category)
    items = os.listdir(skills_dir)
    for item in items:
        item_path = os.path.join(skills_dir, item)
        if not os.path.isdir(item_path):
            continue
        
        skill_file = os.path.join(item_path, "SKILL.md")
        if os.path.exists(skill_file):
            # Read and parse category
            try:
                with open(skill_file, "r", encoding="utf-8") as f:
                    content = f.read()
                
                meta_match = re.search(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
                category = "general"
                if meta_match:
                    meta_text = meta_match.group(1)
                    cat_match = re.search(r'category:\s*(.*)', meta_text)
                    if cat_match:
                        category = cat_match.group(1).strip()
                
                clean_cat = clean_name(category)
                if not clean_cat:
                    clean_cat = "general"
                
                # Check if this item folder is already inside a category (shouldn't be if it's directly under skills_dir)
                dest_dir = os.path.join(skills_dir, clean_cat, item)
                print(f"Migrating skill '{item}' (category: '{category}') to 'Skills/{clean_cat}/{item}'")
                
                # Make dest folder
                os.makedirs(dest_dir, exist_ok=True)
                
                # Copy/Move all contents of the folder to dest
                for root, dirs, files in os.walk(item_path):
                    # Relative path to destination
                    rel_path = os.path.relpath(root, item_path)
                    target_root = dest_dir if rel_path == "." else os.path.join(dest_dir, rel_path)
                    os.makedirs(target_root, exist_ok=True)
                    for file in files:
                        shutil.move(os.path.join(root, file), os.path.join(target_root, file))
                
                # Remove old folder
                shutil.rmtree(item_path)
                print(f" Successfully migrated: {item}")
            except Exception as e:
                print(f" Error migrating {item}: {e}")

if __name__ == "__main__":
    migrate()
