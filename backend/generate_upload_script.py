"""Upload local files to Railway /data volume"""
import os
import base64

# Get all files from uploads directory
uploads_dir = "uploads"
files_data = {}

for filename in os.listdir(uploads_dir):
    filepath = os.path.join(uploads_dir, filename)
    if os.path.isfile(filepath):
        with open(filepath, 'rb') as f:
            files_data[filename] = base64.b64encode(f.read()).decode()

# Generate Python script to recreate files
script = """
import base64
import os

os.makedirs('/data', exist_ok=True)

files = {
"""

for filename, data in files_data.items():
    script += f'    "{filename}": "{data}",\n'

script += """
}

for filename, data in files.items():
    filepath = os.path.join('/data', filename)
    with open(filepath, 'wb') as f:
        f.write(base64.b64decode(data))
    print(f"Uploaded: {filename}")

print(f"\\nTotal files uploaded: {len(files)}")
"""

with open("upload_to_railway.py", "w") as f:
    f.write(script)

print(f"Generated upload_to_railway.py with {len(files_data)} files")
print("Run: railway run python upload_to_railway.py")
