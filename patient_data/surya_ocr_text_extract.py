# pre-requisites
# this script needs an environment with following packages installed:
# #python 3.10
# #PyTorch
# #surya-ocr

# Configuration: Set to False if running on non-GPU machine
USE_GPU = True

# Always import typing for type hints
from typing import List, TYPE_CHECKING
from loguru import logger

# Conditional imports based on GPU configuration
if USE_GPU:
    try:
        from PIL import Image
        from surya.recognition import RecognitionPredictor
        from surya.detection import DetectionPredictor
        from surya.recognition.schema import TextLine
        import torch
        
        # Check if CUDA is available
        if not torch.cuda.is_available():
            logger.warning("CUDA not available, falling back to mock response")
            USE_GPU = False
    except ImportError as e:
        logger.warning(f"GPU packages not available: {e}, falling back to mock response")
        USE_GPU = False

import argparse
import os
import time
import re

extracted_text_dir = 'extracted_text'
image_to_be_extracted_dir = 'images'

# Set up Loguru to log to a file (e.g., logs/app.log)
logger.add("logs/surya_ocr_text_extract.log", rotation="10 MB", retention="10 days", enqueue=True)

def sort_lines(lines, tolerance=10.0):
    '''
    rearranges the positioning of extracted text, so that words in same line are grouped together
    '''
    if not USE_GPU:
        # Return empty string when not in GPU mode
        return ""
        
    vertical_groups = []
    for line in lines:
        min_y = line.bbox[1] if hasattr(line, 'bbox') else line["bbox"][1]
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
        # Sort text boxes on the same line by their horizontal position
        group_lines = sorted(group[1:], key=lambda x: x.bbox[0])
        
        # Join the text from all boxes on this line with a space
        full_line = ' '.join(line.text for line in group_lines)
        
        # Append the now correctly-spaced line to the list
        sorted_text.append(full_line)
        
        # Add a newline character to separate this line from the next
        sorted_text.append("\n")

    # Join all the complete lines together
    return ''.join(sorted_text).strip()

def extract_text_with_surya(image_path: str) -> str:
    """
    Extract text from image using Surya OCR
    """
    image = Image.open(image_path)
    recognition_predictor = RecognitionPredictor()
    detection_predictor = DetectionPredictor()

    predictions = recognition_predictor([image], det_predictor=detection_predictor)
    text_lines = predictions[0].text_lines
    sorted_text = sort_lines(text_lines)
    
    return sorted_text

def get_mock_response() -> str:
    """
    Return mock OCR response for non-GPU environments
    """
    return """
<b>ARFRP1</b> R177H NM_003224.3: c.530G>A(p.R177H), 530G>A, chr20:62331871 38.07% 
 <i>CREBBP</i> N435fs*4 NM_004380.2: c.1304dup(p.N435Kfs*4), 1304_1305insA, chr16:3842007 44.14% 
 <strong>FLCN</strong> H429fs*39 NM_144997.5: c.1285del(p.H429Tfs*39), 1285delC, chr17:17119708-17119709 41.29% 
 <b>MRE11</b> 
 Q582* NM_005590.3: c.1744C>T(p.Q582*), 1744C>T, chr11:94180424 48.54% 
 (MRE11A) 
 <i>MSH2</i> Y408fs*9 NM_000251.1: c.1222dup(p.Y408Lfs*9), 1222_1223insT, chr2:47657025 43.98% 
 S271fs*2 NM_000251.1: c.811_814del(p.S271Rfs*2), 811_814delTCTG, chr2:47641422-47641 48.39% 
 426 
 <strong>PDGFRA</strong> exon 20 (A916T) NM_006206.4: c.2746G>A(p.A916T), 2746G>A, chr4:55155037 37.67% 
 <b>QKI</b> K134fs*14 NM_006775.2: c.401del(p.K134Rfs*14), 401delA, chr6:163899919-163899920 46.44% 
 <i>ROST</i> fusion GOPC(NM_020399)-ROS1(NM_002944) fusion (G8; R35) 
 <strong>SETD2</strong> splice site 4715+1G>A NM_014159.6: c.4715+1G>A(p.?), 4715+1G>A, chr3:47155365 43.64% 
 <b>SUFU</b> R146* NM_016169.3: c.436C>T(p.R146*), 436C>T, chr10:104309845 43.46% 
 <i>TP53</i> R337C NM_000546.4: c.1009C>T(p.R337C), 1009C>T, chr17:7574018 46.45% 
 L93fs*30 NM_000546.4: c.277del(p.L93Cfs*30), 277deIC, chr17:7579409-7579410 45.74%
"""

def clean_html_tags(text: str) -> str:
    """
    Remove HTML tags from text while preserving the content and line breaks.
    """
    # Remove HTML tags using regex
    no_html = re.sub(r'<[^>]+>', '', text)
    
    # Process each line to remove extra horizontal whitespace and preserve newlines
    lines = no_html.split('\n')
    cleaned_lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in lines]
    
    # Join the cleaned lines back together, preserving the structure
    return '\n'.join(cleaned_lines).strip()

def decode_html_entities(text: str) -> str:
    """
    Decode common HTML entities
    """
    import html
    return html.unescape(text)

def process_extracted_text(text: str, clean_html: bool = True, decode_entities: bool = True) -> str:
    """
    Process extracted text to clean HTML tags and decode entities
    """
    if clean_html:
        text = clean_html_tags(text)
    if decode_entities:
        text = decode_html_entities(text)
    return text

def main(image_files: list[str], mmid: str):    
    combined_extracted_text = ""
    output_file_name = mmid
    
    if not USE_GPU:
        logger.info("Running in non-GPU mode - using mock response")
        mock_text = get_mock_response()
        combined_extracted_text = process_extracted_text(mock_text)
        logger.info("Mock OCR response generated and processed")
    else:
        logger.info("Running in GPU mode - using Surya OCR")
        for image_file in image_files:
            current_dir = os.path.dirname(__file__)
            image_path = os.path.abspath(os.path.join(current_dir, image_to_be_extracted_dir, image_file))
            logger.info(f'Processing image file: {image_path}')
            
            if os.path.exists(image_path):
                try:
                    extracted_text = extract_text_with_surya(image_path)
                    processed_text = process_extracted_text(extracted_text)
                    combined_extracted_text += processed_text + "\n"
                    logger.info(f"Successfully extracted text from {image_file}")
                except Exception as e:
                    logger.error(f"Error extracting text from {image_file}: {e}")
                    raise Exception(f"OCR processing failed for {image_file}: {str(e)}")
            else:
                logger.warning(f"Image file not found: {image_path}")
                raise FileNotFoundError(f"Image file not found: {image_path}")

    save_extracted_text(combined_extracted_text, output_file_name)

def save_extracted_text(extracted_text:str, output_file_name:str):
    current_dir =  os.path.dirname(__file__)
    op_file = f'{output_file_name}.txt'
    op_file_path = os.path.join(current_dir, extracted_text_dir,op_file)
    with open(op_file_path, 'w') as op_text_file:
        op_text_file.write(extracted_text)
    logger.info(f"Extracted text saved at {op_file_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract text from image file(s) using surya-ocr.")
    parser.add_argument("args", nargs='+', help="Name of image file(s) followed by MMID. " \
    "The last argument will be considered as MatchMinerId and will be used to name the output file containing extracted text")
    args = parser.parse_args()

    image_files = args.args[:-1]
    mmid = args.args[-1]

    main(image_files, mmid)