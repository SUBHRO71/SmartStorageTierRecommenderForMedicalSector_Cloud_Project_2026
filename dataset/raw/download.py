import os
import urllib.request
import hashlib
import argparse
from tqdm import tqdm

DATA_ENTRY_URL = "https://nihcc.app.box.com/v/ChestXray-NIHCC/file/219760887468" # Placeholder, actual URL requires scraping or direct link
# A direct link provided by researchers typically looks like:
DIRECT_CSV_URL = "https://raw.githubusercontent.com/arnoweng/CheXNet/master/ChestX-ray14/Data_Entry_2017.csv" 
# (Note: In a real scenario, downloading directly from NIH Box needs a proper downloader script or API. We'll use a direct source for the metadata CSV if available or mock it for this demonstration).

def download_file(url: str, output_path: str, expected_md5: str = None) -> None:
    """Download a file with progress bar and optional md5 check."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    print(f"Downloading from {url} to {output_path}...")
    
    class DownloadProgressBar(tqdm):
        def update_to(self, b=1, bsize=1, tsize=None):
            if tsize is not None:
                self.total = tsize
            self.update(b * bsize - self.n)

    try:
        with DownloadProgressBar(unit='B', unit_scale=True, miniters=1, desc=output_path.split('/')[-1]) as t:
            urllib.request.urlretrieve(url, filename=output_path, reporthook=t.update_to)
            
        print("Download complete.")
        
        if expected_md5:
            print("Verifying checksum...")
            hasher = hashlib.md5()
            with open(output_path, 'rb') as f:
                buf = f.read()
                hasher.update(buf)
            file_md5 = hasher.hexdigest()
            if file_md5 != expected_md5:
                print(f"Warning: Checksum mismatch! Expected {expected_md5}, got {file_md5}")
            else:
                print("Checksum verified successfully.")
                
    except Exception as e:
        print(f"Error downloading file: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download NIH ChestX-ray14 metadata")
    parser.add_argument("--output_dir", type=str, default=".", help="Output directory")
    args = parser.parse_args()
    
    output_file = os.path.join(args.output_dir, "Data_Entry_2017.csv")
    download_file(DIRECT_CSV_URL, output_file)
