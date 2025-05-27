# pre-requisites
# this script needs an environment with following packages installed:
# #python 3.10
# #PyTorch
# #surya-ocr

from PIL import Image
from surya.recognition import RecognitionPredictor
from surya.detection import DetectionPredictor
from typing import List
from surya.recognition.schema import TextLine
import argparse
import os

extracted_text_dir = 'extracted_text'
image_to_be_extracted_dir = 'images'

def sort_lines(lines:List[TextLine] | List[dict], tolerance=10.0):
    '''
    rearranges the positioning of extracted text, so that workds in same line are grouped together
    '''
    vertical_groups = []
    for line in lines:
        min_y = line.bbox[1] if isinstance(line, TextLine) else line["bbox"][1]
        found_group = False

        #check for existing groups within y tolerance
        for group in vertical_groups:
            if abs(min_y - group[0]) <= tolerance:
                group.append(line)
                found_group = True
                break

        #if group not found,create a new one
        if not found_group:
            vertical_groups.append([min_y,line])   

    sorted_text = []
    for group in sorted(vertical_groups):
        print(group)
        group_lines = sorted(group[1:], key=lambda x:x.bbox[0])
        for line in group_lines:
            sorted_text.append(line.text)
        sorted_text.append("\n")

    return ' '.join(sorted_text).strip()

def main(image_files: list[str], mmid: str):    
    combined_extracted_text = ""
    output_file_name = mmid
    for image_file in image_files:
        current_dir =  os.path.dirname(__file__)
        image_path = os.path.abspath(os.path.join(current_dir,image_to_be_extracted_dir,image_file))
        print(f'Looking for file in {image_path}')
        image = Image.open(image_path)
        langs = ["en"]
        recognition_predictor = RecognitionPredictor()
        detection_predictor = DetectionPredictor()

        predictions = recognition_predictor([image], [langs], detection_predictor)
        text_lines = predictions[0].text_lines
        sorted_text = sort_lines(text_lines)        

        #combine text from all images
        combined_extracted_text+=sorted_text+"\n"

    save_extracted_text(combined_extracted_text, output_file_name)

def save_extracted_text(extracted_text:str, output_file_name:str):
    current_dir =  os.path.dirname(__file__)
    op_file = f'{output_file_name}.txt'
    op_file_path = os.path.join(current_dir, extracted_text_dir,op_file)
    with open(op_file_path, 'w') as op_text_file:
        op_text_file.write(extracted_text)
    print(f"Extracted text saved at {op_file_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract text from image file(s) using surya-ocr.")
    parser.add_argument("args", nargs='+', help="Name of image file(s) followed by MMID. " \
    "The last argement will be considered as MatchMinerId and will be used to name the output file containing extracted text")
    args = parser.parse_args()

    image_files = args.args[:-1]
    mmid = args.args[-1]

    main(image_files, mmid)