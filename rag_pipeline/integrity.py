
import hashlib
import json
from pathlib import Path

# project directories
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
MANIFEST_FILE = BASE_DIR / "hashes.json"

SUPPORTED_EXTENSIONS = {".pdf", ".txt"}


def calculate_hash(file_path):
    sha256 = hashlib.sha256()

    with open(file_path, "rb") as file:
        while True:
            chunk = file.read(8192)

            if not chunk:
                break

            sha256.update(chunk)

    return sha256.hexdigest()


def get_documents():
    """Find supported course documents in the data folder."""

    DATA_DIR.mkdir(exist_ok=True)

    return sorted(
        path for path in DATA_DIR.rglob("*")
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_EXTENSIONS
        and not path.is_symlink()
    )


def create_manifest(): # create a trusted baseline for approved documents 
    
    documents = get_documents()

    if not documents:
        raise ValueError("No PDF or TXT documents found in data/")

    hashes = {}

    for document in documents:
        relative_path = document.relative_to(DATA_DIR).as_posix()
        hashes[relative_path] = calculate_hash(document)

    # does not silently replace an existing trusted baseline.
    with open(MANIFEST_FILE, "x", encoding="utf-8") as file:
        json.dump(hashes, file, indent=4)

    print(f"Created trusted manifest for {len(hashes)} documents.")

    return hashes


def verify_documents(): # verify every document against the trusted baseline, reporting any discrepancies

    if not MANIFEST_FILE.exists():
        raise FileNotFoundError(
            "No trusted manifest found. Approve documents first."
        )

    with open(MANIFEST_FILE, "r", encoding="utf-8") as file:
        trusted_hashes = json.load(file)

    documents = get_documents()
    current_paths = {
        path.relative_to(DATA_DIR).as_posix(): path
        for path in documents
    }

    all_valid = True

    for filename, document in current_paths.items():
        if filename not in trusted_hashes:
            print(f"[UNAPPROVED] {filename}")
            all_valid = False
            continue

        current_hash = calculate_hash(document)

        if current_hash == trusted_hashes[filename]:
            print(f"[VERIFIED] {filename}")
        else:
            print(f"[MODIFIED] {filename}")
            all_valid = False

    for filename in trusted_hashes:
        if filename not in current_paths:
            print(f"[MISSING] {filename}")
            all_valid = False

    return all_valid


if __name__ == "__main__":
    if verify_documents():
        print("All documents passed integrity verification.")
    else:
        print("Integrity verification failed.")
        raise SystemExit(1)
