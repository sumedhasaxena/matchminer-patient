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
    "model":config.LLM_AI_MODEL,
    "messages":[
        {"role": "system", "content": "You are a biomedical researcher."},
        {
          "role":"user", "content": prompt
        }
    ],
    "temperature": 0.5, #lower value of temperature results in more deterministric responses
    "max_tokens": 8192,
    "response_format": {
    "type": "json_object"
    },
    "stream":False
    }
    req_body_json = json.dumps(req_body)
    logger.debug(f"AI request | ID:{id} | {req_body_json}")
    endpoint_url = f'{urllib.parse.urljoin(f"{config.GPU_SERVER_HOSTNAME}:{config.AI_PORT}", config.CHAT_ENDPOINT)}'
    print(endpoint_url)

    response = requests.post(endpoint_url, data=req_body_json, headers={"Content-Type":"application/json"})
    response.raise_for_status()

    print(response.status_code)
    ai_response = response.json()
    logger.debug(f"AI response | ID:{id} | {ai_response}")
    return ai_response

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
2. VARIANT_CATEGORY: Type of variant. Needs to be one of the following values: ['MUTATION', 'CNV', 'SV', 'SIGNATURE']. SV stands for 'Structural variation and variants of type 'fusion' from the report should be marked with 'SV'
3. TRUE_VARIANT_CLASSIFICATION: If the 'VARIANT_CATEGORY' = 'MUTATION', the value should be one of the following values: ['In_Frame_Del', 'In_Frame_Ins', 'Missense_Mutation', 'Nonsense_Mutation', 'Nonstop_Mutation', 'Frame_Shift_Del','Frame_Shift_Ins','Initiator_Codon', 'Intron', 'RNA', 'Silent', 'Splice_Acceptor', 'Splice_Donor', 'Splice_Region','Splice_Site', 'Splice_Lost', 'Translation_Start_Site', "3'UTR", "5'Flank", "5'UTR"]. Otherwise, exclude this field.
4. TRUE_PROTEIN_CHANGE: Protein change if described in the report. Example: "p.R146*"
5. CNV_CALL: If the 'VARIANT_CATEGORY' = 'CNV', the value for this field should be one of the following values: ["High level amplification", "Homozygous deletion", "Gain", "Heterozygous deletion"].Otherwise, exclude this field.

Example:
FLCN H429fs*39 NM_144997.5: c.128Sdel(p.H429Tfs*39), 1285delC

Output:
{{
        "WILDTYPE": false,
        "TRUE_HUGO_SYMBOL": "FLCN",
        "VARIANT_CATEGORY": "MUTATION",         
        "TRUE_VARIANT_CLASSIFICATION": "Frame_Shift_Del",
        "TRUE_PROTEIN_CHANGE": "p.H429Tfs*39"
}}
"""
    
    return prompt


def safe_get(dict_data, keys):
    for key in keys:
        dict_data = dict_data.get(key, {})
    return dict_data