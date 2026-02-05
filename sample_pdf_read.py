import os
import pymupdf
from dotenv import load_dotenv

load_dotenv()

PDF_PATH = "data/sample.pdf"
IMAGES_DIR = "data/images"

# Create images directory if it doesn't exist
os.makedirs(IMAGES_DIR, exist_ok=True)

# Extract text and images from the PDF
doc = pymupdf.open(PDF_PATH)
pages_data = []

for page_num, page in enumerate(doc):
    # Extract text from page
    text = page.get_text("text")
    
    # Extract and save images
    image_paths = []
    for img_idx, img in enumerate(page.get_images()):
        xref = img[0]
        base_image = doc.extract_image(xref)
        image_path = f"{IMAGES_DIR}/page{page_num}_img{img_idx}.{base_image['ext']}"
        with open(image_path, "wb") as f:
            f.write(base_image["image"])
        image_paths.append(image_path)
        print(f"Saved: {image_path}")
    
    pages_data.append({
        "page_num": page_num,
        "text": text,
        "images": image_paths
    })

doc.close()

print(f"\nTotal pages: {len(pages_data)}")
for page in pages_data:
    print(f"Page {page['page_num']}: {len(page['images'])} images, {len(page['text'])} chars")