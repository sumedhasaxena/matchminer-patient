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
    "SAMPLE_ID": "ReportId",
    "MRN": "ReportId",
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

def supplement_mandatory_clinical_fields(patient_data: Dict[str, Any]) -> Dict[str, Any]:
    patient_data["FIRST_NAME"] = "NA"
    patient_data["LAST_NAME"] = "NA"
    patient_data["ORD_PHYSICIAN_EMAIL"] = "NA"
    patient_data["PANEL_VERSION"] = 0
    patient_data["REPORT_VERSION"] = "0"
    patient_data["VITAL_STATUS"] = "alive"
    patient_data["TEST_NAME"] = "oncopanel"
    return patient_data

def extract_variants_from_xml(root: etree.Element, gene_vus_mapping:dict ) -> list:
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
        
        is_vus = gene_vus_mapping.get(gene)
        if is_vus == "true":
            entry["TIER"] = 4

        variants.append(entry)

    return variants

def extract_cnvs_from_xml(root: etree.Element, gene_vus_mapping:dict) -> list:
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
        
        is_vus = gene_vus_mapping.get(gene)
        if is_vus == "true":
            entry["TIER"] = 4

        cnvs.append(entry)

    return cnvs

def extract_rearrangements_from_xml(root: etree.Element, gene_vus_mapping:dict) -> list:
    svs = []

    for sv in root.xpath('//variant:rearrangement ', namespaces=NAMESPACES):
        gene = sv.get('targeted-gene')        
        
        entry = {
            "WILDTYPE": False,
            "TRUE_HUGO_SYMBOL": gene,
            "VARIANT_CATEGORY": "SV",
        }
        svs.append(entry)

        is_vus = gene_vus_mapping.get(gene)
        if is_vus == "true":
            entry["TIER"] = 4

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
        if copy_number >= 4 : # use 4 as cut off
            return "High level amplification"
        elif copy_number > 2 and copy_number < 4: 
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
            "ReportId": root.xpath('//PMI/ReportId/text()'),
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
                    value = values[0].strip()
                    if mm_key == "BIRTH_DATE" and value:
                        try:
                            birth_date = datetime.strptime(value, "%Y-%m-%d")
                            patient_data[mm_key] = birth_date.strftime("%a, %d %b %Y 10:00:00 GMT")
                        except ValueError:
                            try:
                                if len(value) == 4 and value.isdigit():
                                    birth_date = datetime(int(value), 1, 1)
                                    patient_data[mm_key] = birth_date.strftime("%a, %d %b %Y 10:00:00 GMT")
                                else:
                                    raise
                            except ValueError:
                                patient_data[mm_key] = value
                    else:
                        patient_data[mm_key] = value   
        
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

        variant_prop_nodes = root.xpath('//rr:ResultsPayload//FinalReport//VariantProperties/VariantProperty', namespaces=NAMESPACES)
        gene_vus_mapping = {}
        if variant_prop_nodes:  
            for vp in variant_prop_nodes:
                gene_name = vp.get('geneName')
                is_vus = vp.get('isVUS')
                gene_vus_mapping[gene_name] = is_vus

        # Extract variants for genomic data
        variants = extract_variants_from_xml(root, gene_vus_mapping)
        cnv = extract_cnvs_from_xml(root, gene_vus_mapping)
        variants.extend(cnv)
        svs = extract_rearrangements_from_xml(root, gene_vus_mapping)
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

def process_xml_file(xml_file_path: str):
    """Process a single XML file and write clinical/genomic JSON outputs."""
    logger.info(f'Reading XML file: {xml_file_path}')

    if not os.path.exists(xml_file_path):
        logger.error(f'XML file not found: {xml_file_path}')
        return

    base_dir = os.path.dirname(__file__)

    try:
        with open(xml_file_path, 'rb') as file:
            xml_content = file.read()

        logger.info(f'Successfully read XML content from {xml_file_path}')

        default_id = os.path.splitext(os.path.basename(xml_file_path))[0]

        # Parse XML and extract data
        extracted_data = parse_foundation_med_xml(xml_content, default_id)

        clinical_data = extracted_data.get("clinical_data", {})
        genomic_data = extracted_data.get("genomic_data", [])

        sample_id = clinical_data.get("SAMPLE_ID")
        if not sample_id:
            raise ValueError("Unable to determine sample ID for output filenames.")

        clinical_dir = os.path.join(base_dir, "incoming","clinical_json")
        genomic_dir = os.path.join(base_dir,"incoming", "genomic_json")
        os.makedirs(clinical_dir, exist_ok=True)
        os.makedirs(genomic_dir, exist_ok=True)

        clinical_path = os.path.join(clinical_dir, f"{sample_id}.json")
        genomic_path = os.path.join(genomic_dir, f"{sample_id}.json")

        with open(clinical_path, "w", encoding="utf-8") as clinical_file:
            json.dump(clinical_data, clinical_file, indent=2, ensure_ascii=False)
        with open(genomic_path, "w", encoding="utf-8") as genomic_file:
            json.dump(genomic_data, genomic_file, indent=2, ensure_ascii=False)

        logger.info(f"Clinical data saved to {clinical_path}")
        logger.info(f"Genomic data saved to {genomic_path}")

    except Exception as e:
        logger.error(f'Error processing XML file {xml_file_path}: {str(e)}')
        raise


def main(xml_file: Optional[str] = None, xml_dir: Optional[str] = None):
    """Main entry point to process one XML file or all XML files in a directory."""
    base_dir = os.path.dirname(__file__)

    if xml_dir:
        xml_dir_path = xml_dir if os.path.isabs(xml_dir) else os.path.join(base_dir, xml_dir)
        if not os.path.isdir(xml_dir_path):
            logger.error(f"XML directory not found: {xml_dir_path}")
            return

        xml_files = sorted(
            os.path.join(xml_dir_path, fname)
            for fname in os.listdir(xml_dir_path)
            if fname.lower().endswith(".xml")
        )

        if not xml_files:
            logger.warning(f"No XML files found in directory: {xml_dir_path}")
            return

        for path in xml_files:
            try:
                process_xml_file(path)
            except Exception:
                logger.error(f"Failed to process XML file: {path}", exc_info=True)
        return

    if not xml_file:
        logger.error("No XML file provided. Specify a file or use --xml-dir.")
        return

    xml_file_path = xml_file if os.path.isabs(xml_file) else os.path.join(base_dir, xml_file)
    process_xml_file(xml_file_path)

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
    parser.add_argument("--xml-file", type=str, help="Path to XML file containing Foundation Medicine data")
    parser.add_argument("--xml-dir", type=str, help="Directory containing multiple XML files to process")
    args = parser.parse_args()

    main(args.xml_file, args.xml_dir)

