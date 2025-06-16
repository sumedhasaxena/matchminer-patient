"""
MatchMiner Patient Data Processing Application

This Flask application handles patient data capture, review, and processing
for the MatchMiner system. It processes clinical and genomic data and converts
them to MatchMiner-compliant JSON formats.
"""

# Standard library imports
import time
import os
import json
import threading
import subprocess
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any

# Third-party imports
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.utils import secure_filename
from urllib.parse import unquote
from loguru import logger

# Local imports
from utils.oncotree import get_l1_l2_l3_oncotree_data
from utils.diagnosis_rules import DIAGNOSIS_DROPDOWN_RULES
from patient_data.patient_clinical_data_config import patient_clinical_schema_keys
from patient_data.get_patient_clinical_data import get_oncotree_diagnosis, get_additional_info

# Configuration
class Config:
    """Application configuration constants"""
    SECRET_KEY = 'your_secret_key'
    HOST = '0.0.0.0'
    PORT = 8890
    DEBUG = True
    
    # Directory paths
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    IMAGE_FOLDER = os.path.join(BASE_DIR, 'patient_data', 'images')
    TEXT_FOLDER = os.path.join(BASE_DIR, 'patient_data', 'clinical_data')
    CLINICAL_JSON = os.path.join(BASE_DIR, 'patient_data', 'clinical_json')
    GENOMIC_JSON = os.path.join(BASE_DIR, 'patient_data', 'genomic_json')
    EXTRACTED_TEXT = os.path.join(BASE_DIR, 'patient_data', 'extracted_text')
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

# Initialize Flask app
app = Flask(__name__)
app.secret_key = Config.SECRET_KEY

# Create necessary directories
for directory in [Config.IMAGE_FOLDER, Config.TEXT_FOLDER, Config.CLINICAL_JSON, 
                  Config.GENOMIC_JSON, Config.EXTRACTED_TEXT, Config.LOGS_DIR]:
    os.makedirs(directory, exist_ok=True)

# Set up logging
logger.add(Config.APP_LOG, rotation="10 MB", retention="10 days", enqueue=True)

# Load OncoTree data at startup
level1_list, level1_to_level2, level2_to_level3 = get_l1_l2_l3_oncotree_data()
level1_list = sorted(list(level1_list))
level1_to_level2 = {k: sorted(list(v)) for k, v in level1_to_level2.items()}
level2_to_level3 = {k: sorted(list(v)) for k, v in level2_to_level3.items()}

class SequenceManager:
    """Manages unique ID generation and sequence counting"""
    
    @staticmethod
    def load_sequence_counter() -> Dict[str, int]:
        """Load the sequence counter from file"""
        if os.path.exists(Config.SEQUENCE_FILE):
            try:
                    with open(Config.SEQUENCE_FILE, 'r') as f:
                        return json.load(f)
            except json.JSONDecodeError:
                    logger.warning("Invalid sequence counter file, starting fresh")
                    return {}
        return {}

    @staticmethod
    def save_sequence_counter(counter: Dict[str, int]) -> None:
        """Save the sequence counter to file"""
        with open(Config.SEQUENCE_FILE, 'w') as f:
            json.dump(counter, f)

    @staticmethod
    def generate_unique_id() -> str:
        """Generate a unique ID in format YYMMDD-XXXX"""
        today = datetime.now()
        date_prefix = today.strftime('%y%m%d')
        
        counter = SequenceManager.load_sequence_counter()
        counter = {k: v for k, v in counter.items() if k == date_prefix}
        
        next_seq = counter.get(date_prefix, 0) + 1
        counter[date_prefix] = next_seq
        SequenceManager.save_sequence_counter(counter)
        
        return f"{date_prefix}-{next_seq:04d}"

class BackgroundProcessor:
    """Handles background script execution"""
    
    @staticmethod
    def run_script_in_background(script_path: str, args: List[str], log_file: str, 
                                start_msg: str, finish_msg: str) -> None:
        """Run a script in the background with logging"""
        def runner():
            logger.info(start_msg)
            try:
                with open(log_file, 'a') as log_handle:
                    process = subprocess.Popen(
                        ['python', script_path] + args,
                        stdout=log_handle,
                        stderr=subprocess.STDOUT
                    )
                    process.wait()
                logger.info(finish_msg)
            except Exception as e:
                logger.error(f"Background script failed: {str(e)}")
        
        threading.Thread(target=runner, daemon=True).start()

    @staticmethod
    def start_data_processing(unique_id: str, data_file: str) -> None:
        """Start both clinical and genomic data processing in background"""
        processing_configs = [
            {
                'script_path': Config.CLINICAL_SCRIPT,
                'args': [data_file],
                'log_file': Config.CLINICAL_LOG,
                'start_msg': f"Starting clinical data conversion for {unique_id}",
                'finish_msg': f"Completed clinical data conversion for {unique_id}",
                'type': 'clinical'
            },
            {
                'script_path': Config.GENOMIC_SCRIPT,
                'args': [data_file],
                'log_file': Config.GENOMIC_LOG,
                'start_msg': f"Starting genomic data conversion for {unique_id}",
                'finish_msg': f"Completed genomic data conversion for {unique_id}",
                'type': 'genomic'
            }
        ]
        
        for config in processing_configs:
            try:
                BackgroundProcessor.run_script_in_background(
                    script_path=config['script_path'],
                    args=config['args'],
                    log_file=config['log_file'],
                    start_msg=config['start_msg'],
                    finish_msg=config['finish_msg']
                )
                logger.info(f"Started background {config['type']} data processing for {unique_id}")
            except Exception as e:
                logger.error(f"Failed to start {config['type']} data processing for {unique_id}: {str(e)}")

class DataProcessor:
    """Handles data processing and file operations"""
    
    @staticmethod
    def save_extracted_text(unique_id: str, text_content: str) -> None:
        """Save extracted text to file"""
        file_path = os.path.join(Config.EXTRACTED_TEXT, f"{unique_id}.txt")
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(text_content)
            logger.info(f"Successfully saved extracted text for {unique_id}")
        except IOError as e:
            logger.error(f"Failed to save extracted text for {unique_id}: {str(e)}")
            raise

    @staticmethod
    def save_clinical_data(unique_id: str, form_data: Dict[str, Any], 
                          diagnosis_value: str, dynamic_dropdowns: List[Dict[str, Any]]) -> str:
        """Save clinical data to text file and return the filename"""
        data_file = f"{unique_id}.txt"
        file_path = os.path.join(Config.TEXT_FOLDER, data_file)
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                # Write basic patient information
                f.write(f"{patient_clinical_schema_keys['sample_id_key']}: {unique_id}\n")
                f.write(f"{patient_clinical_schema_keys['mrn_key']}: {unique_id}\n")
                f.write(f"{patient_clinical_schema_keys['gender_key']}: {form_data.get('gender', '')}\n")
                f.write(f"{patient_clinical_schema_keys.get('age_key', 'AGE')}: {form_data.get('age', '')}\n")
                f.write(f"{patient_clinical_schema_keys.get('oncotree_diag_key', 'DIAGNOSIS')}: {diagnosis_value}\n")
                f.write(f"{patient_clinical_schema_keys.get('oncotree_diag_name_key', 'DIAGNOSIS_NAME')}: {diagnosis_value}\n")
                f.write(f"{patient_clinical_schema_keys['report_date_key']}: {form_data.get('report_date', '')}\n")
                
                # Write TMB if present
                tmb = session.get(patient_clinical_schema_keys['tmb_key'])
                if tmb is not None:
                    f.write(f"TUMOR_MUTATIONAL_BURDEN_PER_MEGABASE: {tmb}\n")
                
                # Write dynamic dropdowns
                for dd in dynamic_dropdowns:
                    f.write(f"{dd['name']}: {dd['selected']}\n")
                f.write("---\n")
            
            logger.info(f"Successfully saved clinical data for {unique_id}")
            return data_file
        except IOError as e:
            logger.error(f"Failed to save clinical data for {unique_id}: {str(e)}")
            raise

    @staticmethod
    def process_uploaded_images(unique_id: str, image_files) -> Tuple[List[str], Optional[str]]:
        """Process uploaded images: save files and run OCR extraction"""
        image_filenames = []
        image_paths = []
        
        # Save uploaded files
        for index, image_file in enumerate(image_files, 1):
            if image_file and image_file.filename:
                ext = os.path.splitext(secure_filename(image_file.filename))[1]
                image_filename = f"{unique_id}-{index:02d}{ext}"
                image_path = os.path.join(Config.IMAGE_FOLDER, image_filename)
                image_file.save(image_path)
                image_filenames.append(image_filename)
                image_paths.append(image_path)

        # Run OCR text extraction
        if image_paths:
            try:
                # Run OCR extraction using the existing surya_ocr_text_extract.py script
                result = subprocess.run(
                    ['python', 'patient_data/surya_ocr_text_extract.py'] + image_paths + [unique_id],
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                # Log stderr if there's any output
                if result.stderr:
                    logger.warning(f"OCR script stderr for {unique_id}: {result.stderr}")
                
                # Read extracted text from the file created by the OCR script
                extracted_text_file = os.path.join(Config.EXTRACTED_TEXT, f"{unique_id}.txt")
                if os.path.exists(extracted_text_file):
                    with open(extracted_text_file, 'r', encoding='utf-8') as f:
                        extracted_text = f.read()
                    logger.info(f"OCR extraction completed for {unique_id}")
                    return image_filenames, extracted_text
                else:
                    logger.warning(f"Extracted text file not found for {unique_id}")
                    return image_filenames, None
            except subprocess.CalledProcessError as e:
                logger.error(f"OCR processing failed for {unique_id}: {e.stderr}")
                return image_filenames, None
            except Exception as e:
                logger.error(f"OCR processing failed for {unique_id}: {str(e)}")
                return image_filenames, None
            
        return image_filenames, None

    @staticmethod
    def delete_uploaded_images(image_paths: List[str], unique_id: str) -> None:
        """Delete uploaded images after OCR extraction is completed"""
        deleted_count = 0
        for image_path in image_paths:
            try:
                if os.path.exists(image_path):
                    os.remove(image_path)
                    deleted_count += 1
                    logger.debug(f"Deleted image: {image_path}")
            except OSError as e:
                logger.error(f"Failed to delete image {image_path} for {unique_id}: {str(e)}")
        
        if deleted_count > 0:
            logger.info(f"Deleted {deleted_count} uploaded images for {unique_id}")
        else:
            logger.warning(f"No images were deleted for {unique_id}")

class DiagnosisProcessor:
    """Handles diagnosis processing and validation"""
    
    @staticmethod
    def get_diagnosis_result(unique_id: str, diagnosis_free_text: Optional[str] = None,
                           diagnosis_level1: Optional[str] = None,
                           diagnosis_level2: Optional[str] = None,
                           diagnosis_level3: Optional[str] = None) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Get diagnosis result either from free text lookup or dropdown selections.
        
        Args:
            unique_id (str): The unique patient ID
            diagnosis_free_text (str, optional): Free text diagnosis input
            diagnosis_level1 (str, optional): Level 1 diagnosis from dropdown
            diagnosis_level2 (str, optional): Level 2 diagnosis from dropdown
            diagnosis_level3 (str, optional): Level 3 diagnosis from dropdown
        
        Returns:
            tuple: (diagnosis_result, error_message)
                - diagnosis_result: dict with level1, level2, level3 keys or None
                - error_message: str error message if any, None otherwise
        """
        try:
            if diagnosis_free_text:
                try:
                    diagnosis_result = get_oncotree_diagnosis(unique_id, diagnosis_free_text)
                    logger.info(f"Diagnosis lookup completed for {unique_id}: {diagnosis_result}")
                    
                    if diagnosis_result is None:
                        return None, f"Error: Could not find a matching diagnosis for '{diagnosis_free_text}'"
                    
                    return diagnosis_result, None
                except KeyError as ke:
                    logger.error(f"AI response missing required key for {unique_id}: {str(ke)}")
                    return None, f"Error: AI diagnosis lookup failed - missing required data. Please try again or use manual diagnosis selection."
                except Exception as ai_error:
                    # Check if it's a connection error from the AI service
                    error_str = str(ai_error)
                    if "connection_error" in error_str or "Connection error" in error_str:
                        logger.error(f"AI service connection error for {unique_id}: {error_str}")
                        return None, f"Error: Unable to connect to AI diagnosis service. Please try again later or use manual diagnosis selection."
                    else:
                        logger.error(f"AI diagnosis lookup failed for {unique_id}: {error_str}")
                        return None, f"Error: AI diagnosis lookup failed. Please try again or use manual diagnosis selection."
            else:
                if not diagnosis_level1:
                    return None, "Error: Level 1 diagnosis is required"
                
                if not diagnosis_level2:
                    return None, "Error: Level 2 diagnosis is required"
                
                diagnosis_result = {
                    'level1': diagnosis_level1,
                    'level2': diagnosis_level2,
                    'level3': diagnosis_level3
                }
                return diagnosis_result, None
                
        except Exception as e:
            logger.error(f"Error in diagnosis processing for {unique_id}: {str(e)}")
            return None, f"Error processing diagnosis: {str(e)}"

    @staticmethod
    def build_dynamic_dropdowns() -> List[Dict[str, Any]]:
        """Build dynamic dropdowns from session data"""
        dynamic_dropdowns = []
        value_to_key = {v: k for k, v in patient_clinical_schema_keys.items()}

        for session_key in session.keys():
            if session_key in value_to_key:
                dropdown_key = value_to_key[session_key]
                for diagnosis, rule in DIAGNOSIS_DROPDOWN_RULES.items():
                    for dropdown in rule['dropdowns']:
                        if dropdown['name'] == dropdown_key:
                            logger.info(f"Found dropdown match: {session_key} -> {dropdown_key}")
                            dynamic_dropdowns.append({
                                'name': session_key,
                                'label': dropdown['label'],
                                'options': dropdown['values'],
                                'selected': session[session_key]
                            })
        return dynamic_dropdowns

# Route handlers
@app.route('/debug/oncotree')
def debug_oncotree():
    """Debug endpoint to check OncoTree data"""
    return jsonify({
        'level1_list': level1_list,
        'mapping_l1_l2': level1_to_level2,
        'mapping_l2_l3': level2_to_level3
    })

@app.route('/get_level2/<path:level1>')
def get_level2(level1: str):
    """API endpoint to get level2 values for a given level1"""
    level1 = unquote(level1)
    logger.debug(f"Received request for level1: {level1}")
    return jsonify(level1_to_level2.get(level1, []))

@app.route('/get_level3/<path:level2>')
def get_level3(level2: str):
    """API endpoint to get level3 values for a given level2"""
    level2 = unquote(level2)
    logger.debug(f"Received request for level2: {level2}")
    return jsonify(level2_to_level3.get(level2, []))

@app.route('/diagnosis_autocomplete')
def diagnosis_autocomplete():
    """API endpoint to get auto-complete suggestions for diagnosis field"""
    query = request.args.get('q', '').lower().strip()
    if not query:
        return jsonify([])
    
    suggestions = []
    
    # Search in level2 using level1_to_level2 to get ALL level2 items
    for level1, level2_list in level1_to_level2.items():
        for level2 in level2_list:
            if query in level2.lower():
                suggestions.append({
                    'parent': level1,
                    'type': 'level2',
                    'value': f"{level2}"
                })
    
    # Search in level3 using level2_to_level3
    for level2, level3_list in level2_to_level3.items():
        for level3 in level3_list:
            if query in level3.lower():
                suggestions.append({
                    'parent': level2,
                    'type': 'level3',
                    'value': f"{level3}"
                })
    
    # Remove duplicates and limit results
    unique_suggestions = []
    seen_values = set()
    for suggestion in suggestions[:10]:  # Limit to 10 suggestions
        if suggestion['value'] not in seen_values:
            unique_suggestions.append(suggestion)
            seen_values.add(suggestion['value'])
    
    return jsonify(unique_suggestions)

@app.route('/get_additional_diagnosis_dropdowns/<path:diagnosis>')
def get_additional_diagnosis_dropdowns(diagnosis: str):
    """API endpoint to get dropdown options for a specific diagnosis"""
    diagnosis = unquote(diagnosis)
    logger.debug(f"Received request for diagnosis: {diagnosis}")
    
    parts = diagnosis.split(' > ')
    level1 = parts[0] if len(parts) > 0 else ''
    level2 = parts[1] if len(parts) > 1 else ''
    
    dropdowns = []
    
    if level1 in DIAGNOSIS_DROPDOWN_RULES:
        dropdowns.extend(DIAGNOSIS_DROPDOWN_RULES[level1]['dropdowns'])
    
    if level2 in DIAGNOSIS_DROPDOWN_RULES:
        dropdowns.extend(DIAGNOSIS_DROPDOWN_RULES[level2]['dropdowns'])
    
    return jsonify(dropdowns)

@app.route('/back_to_index')
def back_to_index():
    """Redirect back to index page"""
    return redirect(url_for('index'))

@app.route('/clear_session', methods=['POST'])
def clear_session():
    """Clear session data and return fresh index page"""
    session.clear()
    return jsonify({'status': 'success'})

@app.route('/', methods=['GET', 'POST'])
def index():
    """Main form submission and display endpoint"""
    if request.method == 'POST':
        try:
            # Generate unique ID
            unique_id = SequenceManager.generate_unique_id()
            logger.info(f"Generated unique ID for new submission: {unique_id}")
            
            # Get form data
            form_data = request.form.to_dict()
            gender = form_data.get('gender', '')
            age = form_data.get('age', '')
            diagnosis_free_text = form_data.get('diagnosis_free_text', '')
            # Use current date for report_date instead of form input
            report_date = datetime.now().strftime('%Y-%m-%d')
            description = form_data.get('description', '')

            # Process uploaded images
            image_files = request.files.getlist('genomic_images')
            try:
                image_filenames, extracted_text = DataProcessor.process_uploaded_images(unique_id, image_files)
                logger.info(f"Processed {len(image_filenames)} images for {unique_id}")
            except Exception as e:
                logger.exception(f"Error processing images for {unique_id}: {str(e)}")
                raise
            
            # Store extracted text in session if available
            if extracted_text:
                session['extracted_text'] = extracted_text
                logger.info(f"Stored extracted text in session for {unique_id}")

            # Get diagnosis result
            if diagnosis_free_text:
                session['free_text_diagnosis'] = diagnosis_free_text
                logger.info(f"Processing free text diagnosis for {unique_id}: {diagnosis_free_text}")

                diagnosis_result, diagnosis_error = DiagnosisProcessor.get_diagnosis_result(
                    unique_id, diagnosis_free_text)
            
                if diagnosis_error:
                    session['diagnosis_error'] = diagnosis_error
                    flash(diagnosis_error)
                    return redirect(url_for('index'))
                
                # Extract additional clinical/genomic info from AI   
                additional_info_dict = get_additional_info(unique_id, description)
                logger.info(f"Retrieved additional info for {unique_id}")

                 # Check for connection errors in the AI response
                if isinstance(additional_info_dict, dict) and 'error' in additional_info_dict:
                    logger.error(f"MMID: {unique_id} | AI service error in additional info: {additional_info_dict.get('message', 'Unknown error')}")
                    flash(additional_info_dict['message'])
                    return redirect(url_for('index'))
                
                # Extract and store individual values from additional info
                for key, schema_key in patient_clinical_schema_keys.items():
                    if schema_key in additional_info_dict:
                        session[schema_key] = additional_info_dict[schema_key]
                        logger.info(f"Stored {schema_key} in session for {unique_id}: {additional_info_dict[schema_key]}")           
            
            else:# When diagnosis was selected using dropdowns
                try:
                    diagnosis_result, diagnosis_error = DiagnosisProcessor.get_diagnosis_result(
                        unique_id=unique_id,
                        diagnosis_level1=form_data.get('diagnosis_level1', ''),
                        diagnosis_level2=form_data.get('diagnosis_level2', ''),
                        diagnosis_level3=form_data.get('diagnosis_level3', '')
                    )
                    logger.info(f"Processed dropdown diagnosis for {unique_id}")

                    if diagnosis_error:
                        session['diagnosis_error'] = diagnosis_error
                        flash(diagnosis_error)
                        return redirect(url_for('index'))

                    # Handle dynamic diagnosis dropdowns only when using dropdown selection
                    if diagnosis_result:
                        # Get the appropriate diagnosis level for dropdown rules
                        diagnosis_for_rules = diagnosis_result.get('level2') or diagnosis_result.get('level1')
                        
                        if diagnosis_for_rules in DIAGNOSIS_DROPDOWN_RULES:
                            # Get the dropdowns defined for this diagnosis
                            dropdowns = DIAGNOSIS_DROPDOWN_RULES[diagnosis_for_rules]['dropdowns']
                            
                            # For each dropdown, check if it has a value in form_data
                            for dropdown in dropdowns:
                                # Find the schema key for this dropdown
                                schema_key = None
                                for key, value in patient_clinical_schema_keys.items():
                                    if value == dropdown:
                                        schema_key = value
                                        break
                                
                                if schema_key and dropdown in form_data:
                                    # Store the dropdown value in session using the schema key
                                    session[schema_key] = form_data[dropdown]
                                    logger.info(f"Stored dynamic dropdown {schema_key} in session for {unique_id}: {form_data[dropdown]}")
                
                except Exception as e:
                    logger.exception(f"Error processing dropdown diagnosis for {unique_id}: {str(e)}")
                    raise

            # Store form data in session
            session['form_data'] = {
                'unique_id': unique_id,
                'gender': gender,
                'age': age,
                'report_date': report_date,
                'description': description,
                'genomic_images': image_filenames
            }
            session['diagnosis_result'] = diagnosis_result
            logger.info(f"Stored form data and diagnosis result in session for {unique_id}")

            logger.info('Session values after form submission:')
            for key, value in session.items():
                logger.info(f'{key}: {value}')

            return redirect(url_for('review'))

        except Exception as e:
            logger.exception(f"Error in index POST for ID {form_data.get('unique_id', 'unknown')}: {str(e)}")
            flash(f"An error occurred while processing your request: {str(e)}")
            return redirect(url_for('index'))

    # Handle GET request
    if request.method == 'GET' and not request.args.get('from_review'):
        # Don't clear session if there are diagnosis errors to preserve flash messages
        diagnosis_error = session.get('diagnosis_error')
        if not diagnosis_error:
            session.clear()

    # Pre-populate from session
    form_data = session.get('form_data', {})
    diagnosis_result = session.get('diagnosis_result', {})
    free_text_diagnosis = session.get('free_text_diagnosis', '')
    extracted_text = session.get('extracted_text', '')

    return render_template(
        'index.html',
        form_data=form_data,
        diagnosis_result=diagnosis_result,
        free_text_diagnosis=free_text_diagnosis,
        extracted_text=extracted_text,
        level1_list=level1_list,
    )

@app.route('/review', methods=['GET'])
def review():
    """Review page endpoint"""
    form_data = session.get('form_data')
    free_text_diagnosis = session.get('free_text_diagnosis')
    diagnosis_result = session.get('diagnosis_result')
    diagnosis_error = session.get('diagnosis_error')

    if not form_data:
        logger.error("No form data found in session during review")
        return redirect(url_for('index'))

    # Build dynamic dropdowns
    dynamic_dropdowns = DiagnosisProcessor.build_dynamic_dropdowns()
    
    # Prepare level2 and level3 lists
    selected_level1 = diagnosis_result.get('level1') if diagnosis_result else None
    selected_level2 = diagnosis_result.get('level2') if diagnosis_result else None
    level2_list = level1_to_level2.get(selected_level1, []) if selected_level1 else []
    level3_list = level2_to_level3.get(selected_level2, []) if selected_level2 else []
   
    # Store dynamic_dropdowns in session
    session['dynamic_dropdowns'] = dynamic_dropdowns

    return render_template(
        'review.html',
        form_data=form_data,
        free_text_diagnosis=free_text_diagnosis,
        level1_list=level1_list,
        diagnosis_result=diagnosis_result,
        diagnosis_error=diagnosis_error,
        dynamic_dropdowns=dynamic_dropdowns,
        level2_list=level2_list,
        level3_list=level3_list
    )

@app.route('/submit_review', methods=['POST'])
def submit_review():
    """Submit review and start background processing"""
    try:
        # Get form data
        diagnosis_level1 = request.form.get('diagnosis_level1')
        diagnosis_level2 = request.form.get('diagnosis_level2')
        diagnosis_level3 = request.form.get('diagnosis_level3')
        
        form_data = session.get('form_data')
        if not form_data:
            logger.error("No form data found in session during submit_review")
            return redirect(url_for('index'))
        
        # Update form data with selected diagnosis
        form_data.update({
            'diagnosis_level1': diagnosis_level1,
            'diagnosis_level2': diagnosis_level2,
            'diagnosis_level3': diagnosis_level3
        })
        
        unique_id = form_data.get('unique_id')
        logger.info(f"Processing review submission for ID: {unique_id}")
        
        # Update extracted text
        updated_extracted_text = request.form.get('extracted_text', '')
        session['extracted_text'] = updated_extracted_text
        
        # Save extracted text
        DataProcessor.save_extracted_text(unique_id, updated_extracted_text)
        
        # Determine diagnosis value
        diagnosis_value = diagnosis_level3 or diagnosis_level2
        
        # Process dynamic dropdowns
        session_dynamic_dropdowns = session.get('dynamic_dropdowns', [])
        if not session_dynamic_dropdowns:
            logger.warning(f"No dynamic dropdowns found in session for {unique_id}")
        
        dynamic_dropdowns = []
        for dd in session_dynamic_dropdowns:
            key = dd['name']
            selected_value = request.form.get(key, '')
            dynamic_dropdowns.append({
                'name': key,
                'label': dd['label'],
                'options': dd['options'],
                'selected': selected_value
            })

        # Save clinical data
        data_file = DataProcessor.save_clinical_data(
            unique_id, form_data, diagnosis_value, dynamic_dropdowns
        )
        
        # Start background processing
        BackgroundProcessor.start_data_processing(unique_id, data_file)
        
        # Delete uploaded images after successful submission and background processing start
        image_filenames = form_data.get('genomic_images', [])
        if image_filenames:
            image_paths = [os.path.join(Config.IMAGE_FOLDER, filename) for filename in image_filenames]
            DataProcessor.delete_uploaded_images(image_paths, unique_id)
        
        # Clear session data
        session_keys_to_clear = ['form_data', 'free_text_diagnosis', 'diagnosis_result', 'diagnosis_error']
        for key in session_keys_to_clear:
            session.pop(key, None)
        logger.info(f"Cleared session data for {unique_id}")
        
        # Return confirmation page
        flash_msg = f"MatchMiner ID: {unique_id}\nPatient data recorded successfully. Please save the MatchMiner ID for future reference"
        return render_template(
            'confirmation.html',
            form_data=form_data,
            free_text_diagnosis=session.get('free_text_diagnosis'),
            level1_list=level1_list,
            diagnosis_result={
                'level1': diagnosis_level1,
                'level2': diagnosis_level2,
                'level3': diagnosis_level3
            },
            dynamic_dropdowns=dynamic_dropdowns,
            level2_list=level1_to_level2.get(diagnosis_level1, []),
            level3_list=level2_to_level3.get(diagnosis_level2, []),
            success_message=flash_msg
        )
        
    except Exception as e:
        logger.exception(f"Error in submit_review for ID {form_data.get('unique_id', 'unknown')}: {str(e)}")
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG) 