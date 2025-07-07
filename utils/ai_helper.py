import json
import config
import requests
import urllib.parse
from loguru import logger

def get_patient_genomic_criteria(id:str, genomic_data: str) -> dict:    
    prompt = get_ai_prompt_for_patient_genomic_criteria(genomic_data)        
    ai_response = send_ai_request(id, prompt)
    patient_genomic_criteria = parse_ai_response(ai_response)
    return patient_genomic_criteria

def parse_ai_response(ai_response):
    oncotree_diagnoses_dict = {}

    # Check for connection errors first
    if isinstance(ai_response, dict) and 'error' in ai_response:
        logger.error(f"AI service error in response: {ai_response.get('message', 'Unknown error')}")
        raise Exception(f"AI service error: {ai_response.get('message', 'Unknown error')}")

    try:
        if type(ai_response) is dict and 'choices' in ai_response.keys() and type(ai_response['choices']) is list:
            answer = ai_response['choices'][0]
            ai_response_content = safe_get(answer,['message','content'])
            if ai_response_content:
                prefix_pos = ai_response_content.find('```json') #look for ```json in response string 
                if prefix_pos > -1:
                    begin_content = ai_response_content.find('```json')+len('```json')
                    end_content = ai_response_content.find('```', begin_content)
                    oncotree_diagnoses_response_string = ai_response_content[begin_content:end_content].strip()
                else:
                    prefix_pos = ai_response_content.find('</think>')# elseget everything after </think>
                    if prefix_pos > -1:
                        begin_content = ai_response_content.find('</think>')+len('</think>')
                        oncotree_diagnoses_response_string = ai_response_content[begin_content:].strip()
                    else:
                        oncotree_diagnoses_response_string = ai_response_content
                
                oncotree_diagnoses_dict = json.loads(oncotree_diagnoses_response_string)
    except json.JSONDecodeError as ex:
        logger.error(f"Unexpected response format: {ex=}, {type(ex)=}")
    return oncotree_diagnoses_dict

def send_ai_request(id, prompt):
    req_body = {
        "model": config.LLM_AI_MODEL,
        "messages": [
            {"role": "system", "content": "You are a biomedical researcher."},
            {
                "role": "user", "content": prompt
            }
        ],
        "temperature": 0.5,
        "max_tokens": 8192,
        "response_format": {
            "type": "json_object"
        },
        "stream": False
    }
    req_body_json = json.dumps(req_body)
    logger.debug(f"AI request | ID:{id} | {req_body_json}")
    endpoint_url = f'{urllib.parse.urljoin(f"{config.GPU_SERVER_HOSTNAME}:{config.AI_PORT}", config.CHAT_ENDPOINT)}'
    print(endpoint_url)

    try:
        response = requests.post(endpoint_url, data=req_body_json, headers={"Content-Type": "application/json"})
        response.raise_for_status()
        print(response.status_code)
        ai_response = response.json()
        logger.debug(f"AI response | ID:{id} | {ai_response}")
        return ai_response
    except requests.exceptions.ConnectionError:
        logger.error(f"Connection error while making AI request | ID:{id}")
        return {"error": "connection_error", "message": "Unable to connect to AI service. Please try again later."}
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error while making AI request | ID:{id} | Error: {str(e)}")
        return {"error": "request_error", "message": f"Error communicating with AI service: {str(e)}"}

def get_ai_prompt_for_patient_genomic_criteria(genomic_data):
    prompt = f"""Task: Convert the following text about genomic report of a patient sample into JSON format as described below:
    Text: {genomic_data}
    Output JSON Format:
    [
   {{
      "WILDTYPE":false,
      "TRUE_HUGO_SYMBOL":"CDK4",
      "VARIANT_CATEGORY":"CNV",
      "CNV_CALL":"High level amplification"
   }},
   {{
      "WILDTYPE":false,
      "TRUE_HUGO_SYMBOL":"ARFRP1",
      "VARIANT_CATEGORY":"MUTATION",
      "TRUE_VARIANT_CLASSIFICATION":"Missense_Mutation",
      "TRUE_PROTEIN_CHANGE":"p.R177H"
   }},
   {{
      "WILDTYPE":false,
      "TRUE_HUGO_SYMBOL":"CREBBP",
      "VARIANT_CATEGORY":"MUTATION",
      "TRUE_VARIANT_CLASSIFICATION":"Frame_Shift_Ins",
      "TRUE_PROTEIN_CHANGE":"p.N435Kfs*4"
   }}
]
Instructions:
Each JSON object may contain following fields:
1. TRUE_HUGO_SYMBOL: The gene symbol that's metioned in the beginning of each line. If it does not look like a gene symbol, try to find the closest match from the gene(s) defined at the end of the line.
2. VARIANT_CATEGORY: Type of variant. Needs to be one of the following values: ['MUTATION', 'CNV', 'SV', 'SIGNATURE']. SV stands for 'Structural variation' and variants of type 'fusion' from the report should be marked with 'SV'
3. TRUE_VARIANT_CLASSIFICATION: If the 'VARIANT_CATEGORY' = 'MUTATION', the value should be one of the following values: ['In_Frame_Del', 'In_Frame_Ins', 'Missense_Mutation', 'Nonsense_Mutation', 'Nonstop_Mutation', 'Frame_Shift_Del','Frame_Shift_Ins','Initiator_Codon', 'Intron', 'RNA', 'Silent', 'Splice_Acceptor', 'Splice_Donor', 'Splice_Region','Splice_Site', 'Splice_Lost', 'Translation_Start_Site', "3'UTR", "5'Flank", "5'UTR"]. Otherwise, exclude this field.
4. TRUE_PROTEIN_CHANGE: Protein change if described in the report. Example: "p.R146*". If the variant is a fusion, don't add this field.
5. CNV_CALL: If the 'VARIANT_CATEGORY' = 'CNV', the value for this field should be one of the following values: ["High level amplification", "Homozygous deletion", "Gain", "Heterozygous deletion"].Otherwise, exclude this field.
6. If the instructions mention IDH wildtype, add a section with 'TRUE_HUGO_SYMBOL' as IDH, and 'WILDTYPE' as true/false.

Example:
FLCN H429fs*39 NM_144997.5: c.128Sdel(p.H429Tfs*39), 1285delC
ROS1 fusion GOPC(NM_020399)-ROS1(NM_002944) fusion (G8; R35)
TERT promoter -124C>T NM_198253.2: c.-124C>T, -124C>T
IDH_WILDTYPE: True
Output:
[[{{
    "WILDTYPE": false,
    "TRUE_HUGO_SYMBOL": "FLCN",
    "VARIANT_CATEGORY": "MUTATION",         
    "TRUE_VARIANT_CLASSIFICATION": "Frame_Shift_Del",
    "TRUE_PROTEIN_CHANGE": "p.H429Tfs*39"
}},
{{
    "WILDTYPE": false,
    "TRUE_HUGO_SYMBOL": "ROS1",
    "VARIANT_CATEGORY": "MUTATION"
}},
{{
    "WILDTYPE": false,
    "TRUE_HUGO_SYMBOL": "TERT",
    "VARIANT_CATEGORY": "MUTATION"
    "TRUE_VARIANT_CLASSIFICATION": "5'Flank",
}},
{{
    "WILDTYPE": true,
    "TRUE_HUGO_SYMBOL": "IDH",
}}]]
"""
    
    return prompt

def get_ai_prompt_level1_for_free_text_diagnosis(diagnosis, level1_oncotree_list):
    prompt = f"""Task: Map the diagnosis to the closest type listed in 'Oncotree values' below.
    Diagnosis: {diagnosis}
    Oncotree values:{level1_oncotree_list}
    The output should be in the json format :
    {{
    "oncotree_diagnosis": ""
    }}"""
    
    return prompt

def get_level1_diagnosis_from_free_text(mmid:str, diagnosis: str, level1_oncotree: set) -> dict:    
    
    level1_oncotree_list = list(level1_oncotree)    
    prompt = get_ai_prompt_level1_for_free_text_diagnosis(diagnosis, level1_oncotree_list)
        
    ai_response = send_ai_request(mmid, prompt)
    oncotree_diagnosis_dict = parse_ai_response(ai_response)
    return oncotree_diagnosis_dict

def get_child_level_diagnosis_from_clinical_condition(mmid:str, child_nodes_oncotree:set, condition: str) -> dict:

    child_nodes_oncotree_list = list(child_nodes_oncotree)

    prompt = get_ai_prompt_clinical_oncotree_diagnosis(condition, child_nodes_oncotree_list)

    ai_response = send_ai_request(mmid, prompt)
    oncotree_diagnosis_dict = parse_ai_response(ai_response)   
    return oncotree_diagnosis_dict

def get_ai_prompt_clinical_oncotree_diagnosis(condition, child_nodes_oncotree_list):

    # cancer_condition: {condition} E.g. -> Colorectal Cancer
    # Oncotree values: {child_nodes_oncotree} # E.g. -> {'Signet Ring Cell Adenocarcinoma of the Colon and Rectum', 'Colon Adenocarcinoma In Situ', 'Small Bowel Well-Differentiated Neuroendocrine Tumor', 'Gastrointestinal Neuroendocrine Tumors', 'Well-Differentiated Neuroendocrine Tumor of the Rectum', 'Small Bowel Cancer', 'Anal Squamous Cell Carcinoma', 'Anorectal Mucosal Melanoma', 'Low-grade Appendiceal Mucinous Neoplasm', 'Medullary Carcinoma of the Colon', 'Goblet Cell Adenocarcinoma of the Appendix', 'Mucinous Adenocarcinoma of the Appendix', 'Appendiceal Adenocarcinoma', 'Small Intestinal Carcinoma', 'Well-Differentiated Neuroendocrine Tumor of the Appendix', 'Signet Ring Cell Type of the Appendix', 'Colorectal Adenocarcinoma', 'High-Grade Neuroendocrine Carcinoma of the Colon and Rectum', 'Colonic Type Adenocarcinoma of the Appendix', 'Anal Gland Adenocarcinoma', 'Rectal Adenocarcinoma', 'Mucinous Adenocarcinoma of the Colon and Rectum', 'Duodenal Adenocarcinoma', 'Colon Adenocarcinoma', 'Tubular Adenoma of the Colon'}

    prompt = f"""
    Task: Map the cancer condition to the closest diagnosis from the list of 'Oncotree values' below.
    Cancer_condition: {condition}
    Oncotree values: {child_nodes_oncotree_list}
    The output should be in the json format :
    {{
    "cancer_condition": "",
    "oncotree_diagnosis": ""
    }}
    """
    return prompt

def get_additional_info(mmid:str, additional_info: str)-> dict:
    prompt = get_additional_info_prompt(additional_info)
    ai_response = send_ai_request(mmid, prompt)
    additional_info_dict = parse_ai_response(ai_response)   
    return additional_info_dict

def get_additional_info_prompt(additional_info):
    prompt = f"""Task: Analyze the provided description and identify the status of specific conditions. Only include conditions mentioned in the description and omit any absent fields.
    Add HER2/ER/PR status as negative if description mentions TNBC (Triple Negative Breast Cancer).
    If MSI status is mentioned as MSS/MS-stable, add 'MMR_STATUS' as 'Proficient (MMR-P / MSS)'

Conditions and Expected Output:
HER2: HER2_STATUS - Positive/Negative/Unknown
ER: ER_STATUS - Positive/Negative/Unknown
PR: PR_STATUS - Positive/Negative/Unknown
PDL1: PDL1_STATUS - High/Low/Unknown
MGMT Promoter Status: MGMT_PROMOTER_STATUS - Methylated/Unmethylated
MMR Status: MMR_STATUS - Proficient (MMR-P / MSS) / Deficient (MMR-D / MSI-H)
IDH Wildtype: IDH_WILDTYPE - True/False
TMB: TUMOR_MUTATIONAL_BURDEN_PER_MEGABASE - Any float value

    Description: {additional_info}

    Example Description:
    IDH wildtype
    MGMT promoter unmethylated
    TMB: 2.83 muts/mb
    MS-stable 

    Example Output:
    {{
    "IDH_WILDTYPE": "True",
    "TUMOR_MUTATIONAL_BURDEN_PER_MEGABASE": 2.83,
    "MGMT_PROMOTER_STATUS": "Unmethylated",
    "MMR_STATUS": "Proficient (MMR-P / MSS)"
    }}
    """         
    return prompt

def safe_get(dict_data, keys):
    for key in keys:
        dict_data = dict_data.get(key, {})
    return dict_data