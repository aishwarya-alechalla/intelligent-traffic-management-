import easyocr
import os

# Initialize EasyOCR reader
reader = easyocr.Reader(['en'])

# Function to process number plate images
def extract_text_from_images(folder_path):
    extracted_data = {}

    for filename in os.listdir(folder_path):
        if filename.endswith((".jpg", ".jpeg", ".png")):  # Process only image files
            image_path = os.path.join(folder_path, filename)
            result = reader.readtext(image_path, detail=0)  # Extract text

            extracted_data[filename] = result

    return extracted_data
