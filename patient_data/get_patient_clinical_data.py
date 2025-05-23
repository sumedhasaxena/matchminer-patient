import sys
import os
import json 
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),'..')))

import utils.ai_helper as ai
import utils.oncotree as onct
import argparse
from datetime import datetime
from loguru import logger
from patient_data.patient_clinical_data_config import patient_clinical_schema_keys
import subprocess
import threading

# Set up Loguru to log to a file (e.g., logs/app.log)
logger.add("logs/app.log", rotation="10 MB", retention="10 days", enqueue=True)

clinical_txt_dir = 'clinical_data'
clinical_json_dir = 'clinical_json'

def get_oncotree_diagnosis(text_file, value):
    level_1_diagnosis, mapping_l1_all = onct.get_all_oncotree_data()
    result = ai.get_level1_diagnosis_from_original_conditions(text_file, {value}, level_1_diagnosis)
    level1_diagnosis = result['oncotree_diagnoses'][0]['oncotree_value']
    print(level1_diagnosis)
    if  not level1_diagnosis or level1_diagnosis.lower() == "other":
        logger.debug(f"File: {text_file} | Skipping condition {value} as no oncotree diagnosis was returned")
        return None
                        
    child_oncotree_values = mapping_l1_all[level1_diagnosis]
    result = ai.get_child_level_diagnosis_from_clinical_condition(text_file, child_oncotree_values, value)
    return result.get('oncotree_diagnosis', None)

def calculate_birth_date(age):
    # Calculate the birth date based on the current date and age
    if age and age.isdigit():
        current_year = datetime.now().year
        birth_year = current_year - int(age)
        birth_date = datetime(birth_year, 1, 1)  # Assuming birthdate on Jan 1st
        return birth_date.strftime("%a, %d %b %Y 10:00:00 GMT")
    return None


def parse_clinical_data(text_file):
    clinical_data = {}
    file_path = os.path.join(os.path.dirname(__file__), clinical_txt_dir, text_file)
    with open(file_path, 'r') as file:
        for line in file:
            key, value = (line.strip().split(':', 1) if ':' in line else (None, None))
            if key and value:
                clinical_data[key.strip()] = value.strip().rstrip(',')
    return clinical_data

def convert_to_clinical_data_format(text_file):
    data = {}
    clinical_data = parse_clinical_data(text_file)

    # Populate the output JSON based on the defined keys
    for key_id, official_key in patient_clinical_schema_keys.items():
        #if official_key in clinical_data:
            if key_id == "birth_date_key":
                data[official_key] = calculate_birth_date(clinical_data.get("AGE", ""))
            elif key_id == "sample_id_key":
                data[official_key] = clinical_data[official_key]
            elif key_id == "mrn_key":
                data[official_key] = clinical_data[official_key]
            elif key_id in ["first_name_key", "last_name_key", "physician_email_key", "pathologist_name_key"]:
                data[official_key] = "NA"
            elif key_id == "panel_version_key":
                data[official_key] = 0
            elif key_id == "report_version_key":
                data[official_key] = "0"
            elif key_id == "vital_status_key":
                data[official_key] = "alive"
            elif key_id in ["oncotree_diag_name_key","oncotree_diag_key"]:
                data[official_key] = clinical_data[official_key]
                #to be used if we need AI to get the oncotree diagnosis, from a free text field DIAGNOSIS
                #data[official_key] = get_oncotree_diagnosis(text_file, clinical_data["DIAGNOSIS"])
            elif key_id == "report_date_key":
                date_obj = datetime.strptime(clinical_data[official_key], "%Y-%m-%d")    
                data[official_key] = date_obj.strftime("%a, %d %b %Y 10:00:00 GMT")
            elif key_id == "test_name_key":
                data[official_key] = "oncopanel"
            elif official_key in clinical_data:
                data[official_key] = int(clinical_data[official_key]) if key_id == "tmb_key" else clinical_data[official_key]
    #todo: IDH wildtype and TMB to be moved to genomic data capture logic
    return data

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert plain text patient clinical data to matchminer compliant JSON structure.")
    parser.add_argument("text_file", type=str, help="Name of text file containing clinical data")
    args = parser.parse_args()

    logger.info(f"Starting get_patient_clinical_data.py for file: {args.text_file}")
    response = convert_to_clinical_data_format(args.text_file)
    current_dir = os.path.dirname(__file__)
    output_file = os.path.join(current_dir, clinical_json_dir, f'{os.path.splitext(args.text_file)[0]}.json')
    with open(output_file, "w") as json_file:
        json.dump(response, json_file)
    logger.info(f'JSON written to {output_file}')

