import os
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()

class Config:
    """Application configuration constants"""
    # General Config
    SECRET_KEY = os.environ.get('SECRET_KEY', 'a-secure-default-secret-key-for-dev')
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    HOST = os.environ.get('HOST', '0.0.0.0')
    PORT = int(os.environ.get('PORT', 8890))

    # GPU Usage
    # Set to 'true' or 'false' in your .env file
    USE_GPU = os.environ.get('USE_GPU', 'True').lower() in ('true', '1', 't')
    
    # Directory paths
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    IMAGE_FOLDER = os.path.join(BASE_DIR, 'patient_data', 'incoming', 'images')
    TEXT_FOLDER = os.path.join(BASE_DIR, 'patient_data', 'incoming','clinical_data')
    CLINICAL_JSON = os.path.join(BASE_DIR, 'patient_data','incoming', 'clinical_json')
    GENOMIC_JSON = os.path.join(BASE_DIR, 'patient_data','incoming', 'genomic_json')
    EXTRACTED_TEXT = os.path.join(BASE_DIR, 'patient_data','incoming', 'extracted_text')
    LOGS_DIR = os.path.join(BASE_DIR, 'logs')
    
    # Script paths
    CLINICAL_SCRIPT = os.path.join(BASE_DIR, 'patient_data', 'get_patient_clinical_data.py')
    GENOMIC_SCRIPT = os.path.join(BASE_DIR, 'patient_data', 'get_patient_genomic_data.py')
    
    # Log files
    CLINICAL_LOG = os.path.join(LOGS_DIR, 'get_patient_clinical_data.log')
    GENOMIC_LOG = os.path.join(LOGS_DIR, 'get_patient_genomic_data.log')
    APP_LOG = os.path.join(LOGS_DIR, 'app.log')
    
    # Sequence file
    SEQUENCE_FILE = os.path.join(TEXT_FOLDER, '.sequence_counter.json')

GPU_SERVER_HOSTNAME = "http://gpu02.sbms.hku.hk"
#Local_ai
#AI_PORT = 49152
#CHAT_ENDPOINT = "chat/completions"

#vllm
#AI_PORT = 8000
#CHAT_ENDPOINT = "v1/chat/completions"

#SGLang
AI_PORT = 30000
CHAT_ENDPOINT = "v1/chat/completions"

#AI_MODEL = "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"
#AI_MODEL = "deepseek-ai/DeepSeek-R1-Distill-Llama-8B"
LLM_AI_MODEL = "neuralmagic/DeepSeek-R1-Distill-Qwen-32B-quantized.w4a16"

ONCOTREE_TXT_FILE_PATH = "ref/oncotree_file.txt"
GENE_LIST_FILE_PATH = "ref/genes.txt"