import sys
import os
import json
import argparse
from datetime import datetime
from loguru import logger
from typing import Dict, Any, Optional
from lxml import etree

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import utils.ai_helper as ai
import utils.oncotree as onct
from patient_data.patient_data_config import patient_schema_keys, get_clinical_fields, is_clinical_field


logger.add("logs/get_patient_foundation_med_data.log", rotation="10 MB", retention="10 days", enqueue=True)

# Mapping from matchminer keys to XML tags
mm_patient_to_xml_tag_map = {
    "BIRTH_DATE": "DOB",
    "FIRST_NAME": "FirstName", 
    "GENDER": "Gender",
    "LAST_NAME": "LastName",
    "ONCOTREE_PRIMARY_DIAGNOSIS_NAME": "SubmittedDiagnosis",
    "PATHOLOGIST_NAME": "Pathologist",
    "REPORT_DATE": "ReceivedDate"
}

mm_patient_biomarkers_to_xml_tag_map = {
    "TUMOR_MUTATIONAL_BURDEN_PER_MEGABASE": "tumor-mutation-burden",
    "MMR_STATUS": "microsatellite-instability"
}   

# XML namespaces
NAMESPACES = {
    'rr': 'http://integration.foundationmedicine.com/reporting',
    'variant': 'http://foundationmedicine.com/compbio/variant-report-external'
}

def generate_unique_id() -> str:
    return f"fm-{datetime.now().strftime('%Y%m%d%H%M%S')}"

def supplement_mandatory_clinical_fields(patient_data: Dict[str, Any]) -> Dict[str, Any]:    
    unique_id = generate_unique_id()
    patient_data["SAMPLE_ID"] = unique_id
    patient_data["MRN"] = unique_id
    patient_data["FIRST_NAME"] = "NA"
    patient_data["LAST_NAME"] = "NA"
    patient_data["ORD_PHYSICIAN_EMAIL"] = "NA"
    patient_data["PANEL_VERSION"] = 0
    patient_data["REPORT_VERSION"] = "0"
    patient_data["VITAL_STATUS"] = "alive"
    patient_data["TEST_NAME"] = "oncopanel"
    return patient_data

def extract_variants_from_xml(root: etree.Element) -> list:
    variants = []

    for variant in root.xpath('//variant:short-variant', namespaces=NAMESPACES):
        gene = variant.get('gene')
        if not gene:
            continue

        functional_effect = variant.get('functional-effect')
        cds_effect = variant.get('cds-effect')
        variant_classification = map_variant_category(functional_effect, cds_effect)

        entry = {
            "WILDTYPE": False,
            "TRUE_HUGO_SYMBOL": gene,
            "VARIANT_CATEGORY": "MUTATION"
        }

        if variant_classification and variant_classification != 'Other':
            entry["TRUE_VARIANT_CLASSIFICATION"] = variant_classification

        variants.append(entry)

    return variants

def extract_cnvs_from_xml(root: etree.Element) -> list:
    cnvs = []

    for cnv in root.xpath('//variant:copy-number-alteration', namespaces=NAMESPACES):
        gene = cnv.get('gene')        
        cnv_type = cnv.get('type')
        copy_number_str = cnv.get('copy-number')

        try:
            copy_number = int(copy_number_str) if copy_number_str else None
        except ValueError:
            copy_number = None

        cnv_call = map_cnv_call(cnv_type, copy_number) if cnv_type and copy_number is not None else None

        entry = {
            "WILDTYPE": False,
            "TRUE_HUGO_SYMBOL": gene,
            "VARIANT_CATEGORY": "CNV",
        }

        if cnv_call:
            entry["CNV_CALL"] = cnv_call

        cnvs.append(entry)

    return cnvs

def extract_rearrangements_from_xml(root: etree.Element) -> list:
    svs = []

    for sv in root.xpath('//variant:rearrangement ', namespaces=NAMESPACES):
        gene = sv.get('targeted-gene')        
        
        entry = {
            "WILDTYPE": False,
            "TRUE_HUGO_SYMBOL": gene,
            "VARIANT_CATEGORY": "SV",
        }
        svs.append(entry)

    return svs

def map_variant_category(functional_effect: str, cds_effect:str) -> str:
    map = {'missense':'Missense_Mutation',
           'nonsense':'Nonsense_Mutation'}
    
    effect = 'Other'

    if functional_effect in map.keys():
        effect = map[functional_effect.lower()]
    elif functional_effect == 'frameshift':
        if 'del' in cds_effect.lower():
            effect = 'Frame_Shift_Del'
        elif 'ins' in cds_effect.lower():
            effect = 'Frame_Shift_Ins'
    elif functional_effect == 'nonframeshift':
        
        if 'del' in cds_effect.lower():
            effect = 'In_Frame_Del'
        elif 'ins' in cds_effect.lower():
            effect = 'In_Frame_Ins'       
    
    return effect 

def map_cnv_call(cnv_type: str, copy_number:str) -> Optional[str]:
    # matchminer cnv calls
    # "High level amplification"
    # "Homozygous deletion"
    # 'Gain'
    # 'Heterozygous deletion'
    
    if cnv_type == "amplification":
        if copy_number >= 7 :
            return "High level amplification"
        elif copy_number > 2 and copy_number < 7:
            return "Gain"
    elif cnv_type == "partial amplification":
        return "Gain"
    elif cnv_type == "loss":
        if copy_number == 0:
            return "Homozygous deletion"
        elif copy_number == 1:
            return "Heterozygous deletion"    
    
    return None

def parse_foundation_med_xml(xml_content: bytes, id: str) -> Dict[str, Any]:
    
    try:
        root = etree.fromstring(xml_content)
        patient_data = {}
        
        pmi_data = {
            "DOB": root.xpath('//PMI/DOB/text()'),
            "Gender": root.xpath('//PMI/Gender/text()'),
            "SubmittedDiagnosis": root.xpath('//PMI/SubmittedDiagnosis/text()'),
            "Pathologist": root.xpath('//PMI/Pathologist/text()'),
            "CopiedPhysician1": root.xpath('//PMI/CopiedPhysician1/text()'),
            "ReceivedDate": root.xpath('//PMI/ReceivedDate/text()')
        }           
        
        # Map patient data
        for mm_key, xml_tag in mm_patient_to_xml_tag_map.items():
        
            if mm_key == "ONCOTREE_PRIMARY_DIAGNOSIS_NAME":
                free_text_diagnosis = pmi_data.get("SubmittedDiagnosis", [])[0].strip()
                oncotree_diagnosis = get_oncotree_diagnosis(id, free_text_diagnosis)
                patient_data[mm_key] = oncotree_diagnosis
                patient_data["ONCOTREE_PRIMARY_DIAGNOSIS"] = oncotree_diagnosis

            elif mm_key == "REPORT_DATE":
                values = pmi_data.get(xml_tag, [])
                if values and values[0]:
                    try:
                        date_obj = datetime.strptime(values[0].strip(), "%Y-%m-%d")
                        patient_data[mm_key] = date_obj.strftime("%a, %d %b %Y 10:00:00 GMT")
                    except ValueError:
                        patient_data[mm_key] = values[0].strip()

            else:
                values = pmi_data.get(xml_tag, [])
                if values and values[0]:
                    # Special handling for birth date - convert year to full date
                    if mm_key == "BIRTH_DATE":
                        try:
                            year = int(values[0].strip())
                            birth_date = datetime(year, 1, 1)
                            patient_data[mm_key] = birth_date.strftime("%a, %d %b %Y 10:00:00 GMT")
                        except ValueError:
                            patient_data[mm_key] = values[0].strip()
                    else:
                        patient_data[mm_key] = values[0].strip()   
        
        # Map biomarker data
        biomarkers_nodes = root.xpath('//variant:variant-report/variant:biomarkers', namespaces=NAMESPACES)
        biomarkers_element = biomarkers_nodes[0] if biomarkers_nodes else None

        tmb_score = biomarkers_element.xpath('.//variant:tumor-mutation-burden/@score', namespaces=NAMESPACES)
        patient_data["TUMOR_MUTATIONAL_BURDEN_PER_MEGABASE"] = float(tmb_score[0]) if tmb_score else None

        msi_status = biomarkers_element.xpath('.//variant:microsatellite-instability/@status', namespaces=NAMESPACES)
        msi_status = msi_status[0] if msi_status else None

        if msi_status:
            if msi_status == "MSI-H":
                patient_data["MMR_STATUS"] = "Deficient (MMR-D / MSI-H)"
            elif msi_status == "MSI-L" or msi_status == "MSS":
                patient_data["MMR_STATUS"] = "Proficient (MMR-P / MSS)"
            else:
                patient_data["MMR_STATUS"] = None
        
        patient_data = supplement_mandatory_clinical_fields(patient_data)

        # Extract variants for genomic data
        variants = extract_variants_from_xml(root)
        cnv = extract_cnvs_from_xml(root)
        variants.extend(cnv)
        svs = extract_rearrangements_from_xml(root)
        variants.extend(svs)

        return {
            "clinical_data": patient_data,
            "genomic_data": variants
        }
    
    except etree.ParseError as e:
        logger.error(f"XML parsing error for {id}: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error parsing XML for {id}: {str(e)}")
        raise

def main(xml_file: str, output_prefix: str = None):
    """Main function to process Foundation Medicine XML file."""
    current_dir = os.path.dirname(__file__)    
    
    xml_file_path = os.path.join(current_dir, xml_file)
    logger.info(f'Reading XML file: {xml_file_path}')
    
    if not os.path.exists(xml_file_path):
        logger.error(f'XML file not found: {xml_file_path}')
        return
    
    try:
        with open(xml_file_path, 'rb') as file:
            xml_content = file.read()
        
        logger.info(f'Successfully read XML content from {xml_file_path}')
        
        # Parse XML and extract data
        extracted_data = parse_foundation_med_xml(xml_content, output_prefix)
        
        # Pretty print the result        
        print(json.dumps(extracted_data, indent=2, ensure_ascii=False))
        
    except Exception as e:
        logger.error(f'Error processing XML file {xml_file}: {str(e)}')
        raise

def get_oncotree_diagnosis(id, value):
    """
    Oncotree diagnosis mapping:
    1. If value is exact level2/level3 match
    2. If not exact match, use AI to find level1, then level2/level3
    """
    level_1_diagnosis, level_2_diagnosis, level_3_diagnosis, mapping_l1_all, level1_to_level2, level2_to_level3 = onct.get_all_oncotree_data()
    
    # Step 1: Check if value is an exact level2 or level3 match
    value_normalized = value.strip().lower()
    level_3_diagnosis_lower = {x.strip().lower() for x in level_3_diagnosis}
    level_2_diagnosis_lower = {x.strip().lower() for x in level_2_diagnosis}
    if value_normalized in level_3_diagnosis_lower:
        # Find the original value with correct casing from the set
        for item in level_3_diagnosis:
            if item.strip().lower() == value_normalized:
                return item
    elif value_normalized in level_2_diagnosis_lower:
        # Find the original value with correct casing from the set
        for item in level_2_diagnosis:
            if item.strip().lower() == value_normalized:
                return item
    
    # Step 2: Not an exact match, use AI to child level diagnosis
    logger.info(f"ID: {id} | No exact match found, using AI for: {value}")
    
    # Get level1 using AI
    result = ai.get_level1_diagnosis_from_free_text(id, {value}, level_1_diagnosis)
    
    if isinstance(result, dict) and 'error' in result:
        logger.error(f"ID: {id} | AI service error: {result.get('message', 'Unknown error')}")
        raise Exception(f"AI service error: {result.get('message', 'Unknown error')}")
    
    level1_diagnosis = result.get('oncotree_diagnosis')
    
    if not level1_diagnosis:
        logger.debug(f"ID: {id} | No level1 diagnosis found for: {value}")
        return None
    
    child_oncotree_values = mapping_l1_all[level1_diagnosis]
    result = ai.get_child_level_diagnosis_from_clinical_condition(id, child_oncotree_values, value)
    
    if isinstance(result, dict) and 'error' in result:
        logger.error(f"ID: {id} | AI service error in child diagnosis: {result.get('message', 'Unknown error')}")
        raise Exception(f"AI service error: {result.get('message', 'Unknown error')}")
    
    child_diagnosis = result.get('oncotree_diagnosis', None)
    
    if not child_diagnosis:
        logger.info(f"ID: {id} | No child diagnosis found, returning level1 only")
        return level1_diagnosis
    else:
        return child_diagnosis

    return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract patient data from Foundation Medicine XML format.")
    parser.add_argument("xml_file", type=str, help="Name of XML file containing Foundation Medicine data")
    parser.add_argument("--output-prefix", type=str, help="Output prefix for JSON files (defaults to XML filename without extension)")
    args = parser.parse_args()
    
    main(args.xml_file, args.output_prefix)
