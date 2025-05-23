# this script needs tesseract, pytesseract, opencv installation as a prerequisite

from PIL import Image
import pytesseract
import cv2

def extract_text_via_cv2():
    image = cv2.imread('case1.png')
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Extract text using Tesseract
    custom_config = r'--oem 3 --psm 1'  # Page segmentation mode for sparse text
    extracted_text = pytesseract.image_to_string(gray_image, config=custom_config)
    print("Extracted text: " + extracted_text)

    lines = extracted_text.split('\t')
    table_data = [line.split() for line in lines if line.strip()]

    # Output the structured data
    for row in table_data:
        print(row)

def extract_text():
    print(pytesseract.image_to_string(Image.open('case1.png')))

def main():
    print(pytesseract.get_tesseract_version()) # to make sure tesseract is installed
    # if installed and prog cannot find tesseract.exr, conside adding the following line to specify the tesseract.exe path from the env being used
    pytesseract.pytesseract.tesseract_cmd = '<path to tesseract.exe>\tesseract.exe'
    extract_text()
    extract_text_via_cv2()

if __name__ == "__main__":
    main()
