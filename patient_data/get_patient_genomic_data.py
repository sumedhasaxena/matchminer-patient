import sys
import os
import json 
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),'..')))

import utils.ai_helper as ai
import get_gene_from_seq_id as gg
import re
import argparse
from loguru import logger
from utils.census import load_gene_to_ref_seq_mapping

extracted_text_dir = 'extracted_text'
genomic_json_dir = 'genomic_json'
clinical_txt_dir = 'clinical_data'

# Set up Loguru to log to a file
logger.add("logs/get_patient_genomic_data.log", rotation="10 MB", retention="10 days", enqueue=True)

# Load gene to ref_seq_idmapping from CSV
gene_to_ref_seq_id_mapping = load_gene_to_ref_seq_mapping()

def get_and_append_gene_from_census(text:str):
    lines = text.strip().split('\n')
    modified_lines = []

    for line in lines:# For every line in genomic report (extracted via OCR)
        matches = re.findall(r'NM_\d+(?:\.\d+)?', line) #get the ref_seq id via regex, might be multiple in case of fusion
        genes = []
        for patient_ref_seq_id in matches:
            mapped_genes = [key for key, val in gene_to_ref_seq_id_mapping.items() if val.split('.')[0] == patient_ref_seq_id.split('.')[0]] #lookup the gene name <-> ref_seq_id mapping downloaded from census excluding the version number
            if mapped_genes:
                genes.append(mapped_genes[0]) #should have a unique ref_seq_id -> gene match, so get the 1st lookedup entry
        if genes:
            modified_lines.append(line + " Possible Gene(s): " + ", ".join(genes)) #append the gene names looked up from census to every line of extracted text.
        else:
            modified_lines.append(line)            
    return "\n".join(modified_lines)

def get_and_append_gene_from_ncbi(text:str):
    lines = text.strip().split('\n')
    modified_lines = []

    for line in lines:
        matches = re.findall(r'NM_\d+(?:\.\d+)?', line)
        genes = []
        for ref_seq_id in matches:
            try:
                gene_title = gg.get_gene_info(ref_seq_id)
                gene_name_matches = re.findall(r'\(([^)]+)\)', gene_title)
                for gene_names in gene_name_matches:
                    genes.append(gene_names) 
            except Exception as e:
                logger.error(f"Error fetching gene name for {ref_seq_id}: {e}")
        if genes:
            modified_lines.append(line + " Possible Gene(s): " + ", ".join(genes))
                    
    return modified_lines

        
def get_patent_genomic_data(genomic_text:str, file_name:str):
   try:
       response = ai.get_patient_genomic_criteria(file_name, genomic_text)
       return response
   except Exception as e:
       logger.error(f"Error in genomic data processing for {file_name}: {str(e)}")
       # Return empty list as fallback for connection errors
       return []

def main(text_file: str):
    combined_content = ""
    current_dir = os.path.dirname(__file__)

    # read OCR extracted content
    OCR_TXT_FILE_PATH = os.path.join(current_dir, extracted_text_dir, text_file)
    logger.info(f'Looking for file in {OCR_TXT_FILE_PATH}')
    with open(OCR_TXT_FILE_PATH, 'r') as file:
        ocr_content = file.read()        
        modified_lines = get_and_append_gene_from_census(ocr_content)
        combined_content += modified_lines
        combined_content += "\n"

    # read clinical data
    CLINICAL_TXT_FILE_PATH = os.path.join(current_dir, clinical_txt_dir, text_file)
    logger.info(f'Looking for file in {CLINICAL_TXT_FILE_PATH}')
    with open(CLINICAL_TXT_FILE_PATH, 'r') as file:
        clinical_content = file.read()
        combined_content += clinical_content
    
    logger.info(f"Combined content for {text_file}: {combined_content}")
        
    response = get_patent_genomic_data(combined_content, text_file)
    output_file = os.path.join(current_dir, genomic_json_dir, f'{os.path.splitext(text_file)[0]}.json')
    with open(output_file, "w") as json_file: 
        json.dump(response, json_file)
    logger.info(f'JSON written to {output_file}')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert plain text genomic data to matchminer compliant JSON structure.")
    parser.add_argument("text_file", type=str, help="Name of text file containing genomic criteria")
    args = parser.parse_args()

    main(args.text_file)

