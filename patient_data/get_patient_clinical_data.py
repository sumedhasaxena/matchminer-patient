import sys
import os
import json 
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),'..')))

import utils.ai_helper as ai
import utils.oncotree as onct
import argparse
from datetime import datetime
from loguru import logger
from patient_data.patient_data_config import patient_schema_keys, get_clinical_fields, is_clinical_field
# Set up Loguru to log to its own file (as this can also be run as a standalone script)
logger.add("logs/get_patient_clinical_data.log", rotation="10 MB", retention="10 days", enqueue=True)

clinical_txt_dir = 'incoming/clinical_data'
clinical_json_dir = 'incoming/clinical_json'

def get_oncotree_diagnosis(mmid, value):
    """
    Oncotree diagnosis mapping:
    1. If value is an exact OncoTree term at any level, resolve full hierarchy
    2. Otherwise use AI to find level1, then the closest descendant term
    """
    level_1_list, mapping_l1_all = onct.get_all_oncotree_data()

    exact_match = onct.resolve_diagnosis_hierarchy(value)
    if exact_match:
        logger.info(
            f"MMID: {mmid} | Found exact match: {exact_match['primary_diagnosis']} "
            f"(path={exact_match['path']})"
        )
        return exact_match

    logger.info(f"MMID: {mmid} | No exact match found, using AI for: {value}")

    result = ai.get_level1_diagnosis_from_free_text(mmid, {value}, level_1_list)

    if isinstance(result, dict) and 'error' in result:
        logger.error(f"MMID: {mmid} | AI service error: {result.get('message', 'Unknown error')}")
        raise Exception(f"AI service error: {result.get('message', 'Unknown error')}")

    level1_diagnosis = onct.canonicalize_term(result.get('oncotree_diagnosis'), level_1_list)

    if not level1_diagnosis:
        logger.debug(f"MMID: {mmid} | No level1 diagnosis found for: {value}")
        return None

    child_oncotree_values = mapping_l1_all.get(level1_diagnosis, set())
    if not child_oncotree_values:
        logger.info(f"MMID: {mmid} | No child values for level1={level1_diagnosis}")
        return onct.build_diagnosis_result_from_path([level1_diagnosis])

    result = ai.get_child_level_diagnosis_from_clinical_condition(
        mmid, child_oncotree_values, value
    )

    if isinstance(result, dict) and 'error' in result:
        logger.error(
            f"MMID: {mmid} | AI service error in child diagnosis: "
            f"{result.get('message', 'Unknown error')}"
        )
        raise Exception(f"AI service error: {result.get('message', 'Unknown error')}")

    child_diagnosis = result.get('oncotree_diagnosis', None)

    if not child_diagnosis:
        logger.info(f"MMID: {mmid} | No child diagnosis found, returning level1 only")
        return onct.build_diagnosis_result_from_path([level1_diagnosis])

    resolved = onct.resolve_diagnosis_hierarchy(child_diagnosis)
    if resolved:
        logger.info(
            f"MMID: {mmid} | AI found diagnosis: {resolved['primary_diagnosis']} "
            f"(path={resolved['path']})"
        )
        return resolved

    logger.error(
        f"MMID: {mmid} | Could not resolve hierarchy for child diagnosis: {child_diagnosis}"
    )
    return onct.build_diagnosis_result_from_path([level1_diagnosis])

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
    
    # Get only clinical fields from the schema
    clinical_schema_keys = get_clinical_fields()

    # Populate the output JSON based on the clinical keys only
    for key_id, official_key in clinical_schema_keys.items():
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
            elif key_id == "report_date_key":
                date_obj = datetime.strptime(clinical_data[official_key], "%Y-%m-%d")    
                data[official_key] = date_obj.strftime("%a, %d %b %Y 10:00:00 GMT")
            elif key_id == "test_name_key":
                data[official_key] = "oncopanel"
            elif official_key in clinical_data:
                data[official_key] = float(clinical_data[official_key]) if key_id == "tmb_key" else clinical_data[official_key]
    #todo: IDH wildtype and TMB to be moved to genomic data capture logic
    return data

def get_additional_info(mmid, additional_info):
    additional_info_dict = ai.get_additional_info(mmid, additional_info)
    return additional_info_dict

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
