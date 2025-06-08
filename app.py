from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import os
from werkzeug.utils import secure_filename
from datetime import datetime
import json
from utils.oncotree import get_l1_l2_l3_oncotree_data
from utils.diagnosis_rules import DIAGNOSIS_DROPDOWN_RULES
from urllib.parse import unquote
from patient_data.patient_clinical_data_config import patient_clinical_schema_keys
from patient_data.get_patient_clinical_data import get_oncotree_diagnosis, get_additional_info
import subprocess
from loguru import logger
import threading


app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Needed for flash messages

# folders that contain uploaded data
IMAGE_FOLDER = r'./patient_data/images'
TEXT_FOLDER = r'./patient_data/clinical_data'

#folders that contain processed data
CLINICAL_JSON = r'./patient_data/clinical_json'
GENOMIC_JSON = r'./patient_data/genomic_json'
EXTRACTED_TEXT = r'./patient_data/extracted_text'

SEQUENCE_FILE = os.path.join(TEXT_FOLDER, '.sequence_counter.json')

os.makedirs(IMAGE_FOLDER, exist_ok=True)
os.makedirs(TEXT_FOLDER, exist_ok=True)
os.makedirs(CLINICAL_JSON, exist_ok=True)
os.makedirs(GENOMIC_JSON, exist_ok=True)
os.makedirs(EXTRACTED_TEXT, exist_ok=True)

# Load OncoTree data at startup
level1_list, level1_to_level2, level2_to_level3 = get_l1_l2_l3_oncotree_data()
# Convert sets to sorted lists for consistent ordering
level1_list = sorted(list(level1_list))
level1_to_level2 = {k: sorted(list(v)) for k, v in level1_to_level2.items()}
level2_to_level3 = {k: sorted(list(v)) for k, v in level2_to_level3.items()}



# Set up Loguru to log to a file (e.g., logs/app.log)
logger.add("logs/app.log", rotation="10 MB", retention="10 days", enqueue=True)

def load_sequence_counter():
    """Load the sequence counter from file"""
    if os.path.exists(SEQUENCE_FILE):
        try:
            with open(SEQUENCE_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def save_sequence_counter(counter):
    """Save the sequence counter to file"""
    with open(SEQUENCE_FILE, 'w') as f:
        json.dump(counter, f)

def generate_unique_id():
    """Generate a unique ID in format YYMMDD-XXXX"""
    today = datetime.now()
    date_prefix = today.strftime('%y%m%d')
    
    # Load current sequence counter
    counter = load_sequence_counter()
    
    # Clean up old dates (keep only today's counter)
    counter = {k: v for k, v in counter.items() if k == date_prefix}
    
    # Get or initialize sequence for today
    if date_prefix in counter:
        next_seq = counter[date_prefix] + 1
    else:
        next_seq = 1
    
    # Update and save the counter
    counter[date_prefix] = next_seq
    save_sequence_counter(counter)
    
    # Format with leading zeros
    return f"{date_prefix}-{next_seq:04d}"

@app.route('/debug/oncotree')
def debug_oncotree():
    """Debug endpoint to check OncoTree data"""
    return jsonify({
        'level1_list': level1_list,
        'mapping_l1_l2': level1_to_level2,
        'mapping_l2_l3': level2_to_level3
    })

@app.route('/get_level2/<path:level1>')
def get_level2(level1):
    """API endpoint to get level2 values for a given level1"""
    # Decode the URL-encoded level1 value
    level1 = unquote(level1)
    print(f"Received request for level1: {level1}")  # Debug print
    return jsonify(level1_to_level2.get(level1, []))

@app.route('/get_level3/<path:level2>')
def get_level3(level2):
    """API endpoint to get level3 values for a given level2"""
    # Decode the URL-encoded level2 value
    level2 = unquote(level2)
    print(f"Received request for level2: {level2}")  # Debug print
    return jsonify(level2_to_level3.get(level2, []))

@app.route('/get_additional_diagnosis_dropdowns/<path:diagnosis>')
def get_additional_diagnosis_dropdowns(diagnosis):
    """API endpoint to get dropdown options for a specific diagnosis"""
    diagnosis = unquote(diagnosis)
    print(f"Received request for diagnosis: {diagnosis}")  # Debug print
    
    # Get level1 and level2 from the diagnosis string
    parts = diagnosis.split(' > ')
    level1 = parts[0] if len(parts) > 0 else ''
    level2 = parts[1] if len(parts) > 1 else ''
    
    # Collect dropdowns from both level1 and level2 rules
    dropdowns = []
    
    # Check level1 rules
    if level1 in DIAGNOSIS_DROPDOWN_RULES:
        dropdowns.extend(DIAGNOSIS_DROPDOWN_RULES[level1]['dropdowns'])
    
    # Check level2 rules
    if level2 in DIAGNOSIS_DROPDOWN_RULES:
        dropdowns.extend(DIAGNOSIS_DROPDOWN_RULES[level2]['dropdowns'])
    
    return jsonify(dropdowns)

def get_diagnosis_result(unique_id, diagnosis_free_text=None, diagnosis_level1=None, diagnosis_level2=None, diagnosis_level3=None):
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
            # If free text diagnosis was entered, use get_oncotree_diagnosis
            diagnosis_result = get_oncotree_diagnosis(unique_id, diagnosis_free_text)
            logger.info(f"Diagnosis lookup completed for {unique_id}: {diagnosis_result}")
            
            if diagnosis_result is None:
                return None, f"Error: Could not find a matching diagnosis for '{diagnosis_free_text}'"
            
            return diagnosis_result, None
            
        else:
            # If no free text diagnosis, use dropdown selections
            if not diagnosis_level1:
                return None, "Error: Level 1 diagnosis is required"
                
            # Create diagnosis_result in same format as get_oncotree_diagnosis
            diagnosis_result = {
                'level1': diagnosis_level1,
                'level2': diagnosis_level2 if diagnosis_level2 else None,
                'level3': diagnosis_level3 if diagnosis_level3 else None
            }
            return diagnosis_result, None
            
    except Exception as e:
        logger.error(f"Error in diagnosis processing for {unique_id}: {str(e)}")
        return None, f"Error processing diagnosis: {str(e)}"

def process_uploaded_images(unique_id, image_files):
    """
    Process uploaded images: save files and run OCR extraction.
    
    Args:
        unique_id (str): The unique patient ID
        image_files: List of uploaded image files from request.files
    
    Returns:
        tuple: (image_filenames, extracted_text)
            - image_filenames: list of saved image filenames
            - extracted_text: extracted text from OCR or None if error
    """
    image_filenames = []
    image_paths = []
    
    # Save uploaded files
    for index, image_file in enumerate(image_files, 1):
        if image_file and image_file.filename:
            ext = os.path.splitext(secure_filename(image_file.filename))[1]
            image_filename = f"{unique_id}-{index:02d}{ext}"
            image_path = os.path.abspath(os.path.join(IMAGE_FOLDER, image_filename))
            image_file.save(image_path)
            image_filenames.append(image_filename)
            image_paths.append(image_path)

    # Run OCR text extraction for all files at once
    extracted_text = None
    if image_paths:
        try:
            logger.info("Begin simulation of OCR extraction...")
            # Run surya_ocr_text_extract.py with all image paths
            result = subprocess.run(
                ['python', 'patient_data/surya_ocr_text_extract.py'] + image_paths + [unique_id],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"Successfully ran OCR extraction for {len(image_paths)} files")
            
            # Read the extracted text file created by the script
            extracted_text_file = os.path.join(EXTRACTED_TEXT, f"{unique_id}.txt")
            if os.path.exists(extracted_text_file):
                with open(extracted_text_file, 'r', encoding='utf-8') as f:
                    extracted_text = f.read()
                logger.info(f"Loaded extracted text from {extracted_text_file}")
            else:
                logger.warning(f"Extracted text file not found: {extracted_text_file}")
                
        except subprocess.CalledProcessError as e:
            logger.error(f"Error running OCR extraction: {str(e)}")
            logger.error(f"Error output: {e.stderr}")
        except Exception as e:
            logger.error(f"Unexpected error during OCR extraction: {str(e)}")

    return image_filenames, extracted_text

@app.route('/back_to_index')
def back_to_index():
    # Redirect to index, which will pre-populate from session
    return redirect(url_for('index', from_review=1))

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            # Generate unique ID first
            unique_id = generate_unique_id() 
            logger.info(f"Generated unique ID for new submission: {unique_id}")
            
            # Get form data
            form_data = request.form.to_dict()
            gender = form_data.get('gender', '')
            age = form_data.get('age', '')
            diagnosis_free_text = form_data.get('diagnosis_free_text', '')
            report_date = form_data.get('report_date', '')
            description = form_data.get('description', '')

            # Use OCR to extract text from images
            image_files = request.files.getlist('genomic_images')
            try:
                image_filenames, extracted_text = process_uploaded_images(unique_id, image_files)
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
                
                try:
                    # Get oncotree diagnosis match using AI
                    diagnosis_result, error = get_diagnosis_result(
                        unique_id=unique_id,
                        diagnosis_free_text=diagnosis_free_text
                    )

                    # Check for AI service errors
                    if isinstance(diagnosis_result, dict) and 'error' in diagnosis_result:
                        logger.error(f"AI service error for {unique_id}: {diagnosis_result['message']}")
                        flash(diagnosis_result['message'])
                        return redirect(url_for('index'))

                    # Extract additional clinical/genomic info from AI   
                    try:
                        additional_info_dict = get_additional_info(unique_id, description)
                        logger.info(f"Retrieved additional info for {unique_id}")
                    except Exception as e:
                        logger.exception(f"Error getting additional info for {unique_id}: {str(e)}")
                        raise
                    
                    # Check for AI service errors in additional info
                    if isinstance(additional_info_dict, dict) and 'error' in additional_info_dict:
                        logger.error(f"AI service error in additional info for {unique_id}: {additional_info_dict['message']}")
                        flash(additional_info_dict['message'])
                        return redirect(url_for('index'))

                    # Extract and store individual values from additional info
                    for key, schema_key in patient_clinical_schema_keys.items():
                        if schema_key in additional_info_dict:
                            session[schema_key] = additional_info_dict[schema_key]
                            logger.info(f"Stored {schema_key} in session for {unique_id}: {additional_info_dict[schema_key]}")
                
                except Exception as e:
                    logger.exception(f"Error processing diagnosis for {unique_id}: {str(e)}")
                    raise
            
            else: # When diagnosis was selected using dropdowns
                try:
                    diagnosis_result, error = get_diagnosis_result(
                        unique_id=unique_id,
                        diagnosis_level1=form_data.get('diagnosis_level1', ''),
                        diagnosis_level2=form_data.get('diagnosis_level2', ''),
                        diagnosis_level3=form_data.get('diagnosis_level3', '')
                    )
                    logger.info(f"Processed dropdown diagnosis for {unique_id}")

                    # Handle dynamic diagnosis dropdowns only when using dropdown selection
                    if diagnosis_result and not error:
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

            if error:
                logger.error(f"Validation error for {unique_id}: {error}")
                flash(error)
                return redirect(url_for('index'))

            # Store all form data in session for review page
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

            # Log all session values after processing
            logger.info('Session values after form submission:')
            for key, value in session.items():
                logger.info(f'{key}: {value}')

            return redirect(url_for('review'))

        except Exception as e:
            logger.exception(f"Error in index POST for ID {form_data.get('unique_id', 'unknown')}: {str(e)}")
            logger.error(f"Exception type: {type(e).__name__}")
            logger.error(f"Exception args: {e.args}")
            flash(f"An error occurred while processing your request: {str(e)}")
            return redirect(url_for('index'))

    # If this is a direct GET (not from review/back), clear the session
    # You can use a query param or referrer check if you want to preserve session for "back" navigation
    if request.method == 'GET' and not request.args.get('from_review'):
        session.clear()

    # For GET, pre-populate from session if available
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
        # ... any other context ...
    )

# def run_script_in_background(script_path, args, log_file, start_msg, finish_msg):
#     def runner():
#         logger.info(start_msg)
#         process = subprocess.Popen(
#             ['python', script_path] + args,
#             stdout=open(log_file, 'a'),
#             stderr=subprocess.STDOUT
#         )
#         process.wait()
#         logger.info(finish_msg)
#     threading.Thread(target=runner, daemon=True).start()


# def run_chained_scripts(first_script, first_args, first_log, first_start_msg, first_finish_msg,
#                         second_script, second_args, second_log, second_start_msg, second_finish_msg):
#     def runner():
#         logger.info(first_start_msg)
#         process = subprocess.Popen(
#             ['python', first_script] + first_args,
#             stdout=open(first_log, 'a'),
#             stderr=subprocess.STDOUT
#         )
#         process.wait()
#         logger.info(first_finish_msg)
#         if process.returncode == 0:
#             logger.info(second_start_msg)
#             process2 = subprocess.Popen(
#                 ['python', second_script] + second_args,
#                 stdout=open(second_log, 'a'),
#                 stderr=subprocess.STDOUT
#             )
#             process2.wait()
#             logger.info(second_finish_msg)
#         else:
#             logger.error(f"{first_script} failed with return code {process.returncode}. {second_script} will not be run.")
#     threading.Thread(target=runner, daemon=True).start()

@app.route('/review', methods=['GET'])
def review():
    form_data = session.get('form_data')
    free_text_diagnosis = session.get('free_text_diagnosis')
    diagnosis_result = session.get('diagnosis_result')
    diagnosis_error = session.get('diagnosis_error')

    dynamic_dropdowns = []
    # Reverse the mapping for value->key
    value_to_key = {v: k for k, v in patient_clinical_schema_keys.items()}

    for session_key in session.keys():
        if session_key in value_to_key:
            dropdown_key = value_to_key[session_key]
            # Search all diagnoses and their dropdowns for a match
            for diagnosis, rule in DIAGNOSIS_DROPDOWN_RULES.items():
                for dropdown in rule['dropdowns']:
                    if dropdown['name'] == dropdown_key:
                        dynamic_dropdowns.append({
                            'name': session_key,
                            'label': dropdown['label'],
                            'options': dropdown['values'],
                            'selected': session[session_key]
                        })

    # Prepare level2 and level3 lists for dropdowns
    selected_level1 = diagnosis_result.get('level1') if diagnosis_result else None
    selected_level2 = diagnosis_result.get('level2') if diagnosis_result else None
    level2_list = level1_to_level2.get(selected_level1, []) if selected_level1 else []
    level3_list = level2_to_level3.get(selected_level2, []) if selected_level2 else []
   
    # Store dynamic_dropdowns in session for use in confirmation and text file
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
    try:
        # Get the selected diagnosis levels
        diagnosis_level1 = request.form.get('diagnosis_level1')
        diagnosis_level2 = request.form.get('diagnosis_level2')
        diagnosis_level3 = request.form.get('diagnosis_level3')
        
        # Get the stored form data
        form_data = session.get('form_data')
        if not form_data:
            logger.error("No form data found in session during submit_review")
            return redirect(url_for('index'))
        
        # Update form data with selected diagnosis
        form_data['diagnosis_level1'] = diagnosis_level1
        form_data['diagnosis_level2'] = diagnosis_level2
        form_data['diagnosis_level3'] = diagnosis_level3
        
        # Get the unique ID
        unique_id = form_data.get('unique_id')
        logger.info(f"Processing review submission for ID: {unique_id}")
        
        # Get the updated OCR-extracted text from the form, in case user manually updated the text
        updated_extracted_text = request.form.get('extracted_text', '')
        
        # Update session with the new extracted text
        session['extracted_text'] = updated_extracted_text
        
        # Save the updated extracted text to the EXTRACTED_TEXT folder
        extracted_text_file = os.path.join(EXTRACTED_TEXT, f"{unique_id}.txt")
        try:
            with open(extracted_text_file, 'w', encoding='utf-8') as f:
                f.write(updated_extracted_text)
            logger.info(f"Successfully updated extracted text file for {unique_id}")
        except IOError as e:
            logger.error(f"Failed to write extracted text file for {unique_id}: {str(e)}")
            raise
        
        # Determine the lowest level diagnosis
        diagnosis_value = diagnosis_level3 or diagnosis_level2
        
        # Retrieve dynamic_dropdowns from session (as built for the review page)
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

        # Save data to a text file named after unique_id in TEXT_FOLDER
        data_file = f"{unique_id}.txt"
        data_file_path = os.path.abspath(os.path.join(TEXT_FOLDER, data_file))
        try:
            with open(data_file_path, 'w', encoding='utf-8') as f:
                f.write(f"{patient_clinical_schema_keys['sample_id_key']}: {unique_id}\n")
                f.write(f"{patient_clinical_schema_keys['mrn_key']}: {unique_id}\n")
                f.write(f"{patient_clinical_schema_keys['gender_key']}: {form_data.get('gender', '')}\n")
                f.write(f"{patient_clinical_schema_keys['age_key'] if 'age_key' in patient_clinical_schema_keys else 'AGE'}: {form_data.get('age', '')}\n")
                f.write(f"{patient_clinical_schema_keys['oncotree_diag_key'] if 'oncotree_diag_key' in patient_clinical_schema_keys else 'DIAGNOSIS'}: {diagnosis_value}\n")
                f.write(f"{patient_clinical_schema_keys['oncotree_diag_name_key'] if 'oncotree_diag_name_key' in patient_clinical_schema_keys else 'DIAGNOSIS_NAME'}: {diagnosis_value}\n")
                f.write(f"{patient_clinical_schema_keys['report_date_key']}: {form_data.get('report_date', '')}\n")
                # Write dynamic dropdowns as key-value pairs
                for dd in dynamic_dropdowns:
                    f.write(f"{dd['name']}: {dd['selected']}\n")
                f.write("---\n")
            logger.info(f"Successfully wrote clinical data file for {unique_id}")
        except IOError as e:
            logger.error(f"Failed to write clinical data file for {unique_id}: {str(e)}")
            raise
        
        # Clear session data
        session.pop('form_data', None)
        session.pop('free_text_diagnosis', None)
        session.pop('diagnosis_result', None)
        session.pop('diagnosis_error', None)
        logger.info(f"Cleared session data for {unique_id}")
        
        # Redirect to confirmation page with banner and read-only fields
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
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Exception args: {e.args}")
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8890, debug=True) 