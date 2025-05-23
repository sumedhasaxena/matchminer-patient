from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import os
from werkzeug.utils import secure_filename
from datetime import datetime
import json
from utils.oncotree import get_l1_l2_l3_oncotree_data
from utils.diagnosis_rules import DIAGNOSIS_DROPDOWN_RULES
from urllib.parse import unquote
from patient_data.patient_clinical_data_config import patient_clinical_schema_keys
import subprocess
from loguru import logger
import threading

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Needed for flash messages

IMAGE_FOLDER = r'./patient_data/images'
TEXT_FOLDER = r'./patient_data/clinical_data'
SEQUENCE_FILE = os.path.join(TEXT_FOLDER, '.sequence_counter.json')

os.makedirs(IMAGE_FOLDER, exist_ok=True)
os.makedirs(TEXT_FOLDER, exist_ok=True)

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

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Generate unique ID first
        unique_id = generate_unique_id()
        
        gender = request.form.get('gender', '')
        age = request.form.get('age', '')
        diagnosis_level1 = request.form.get('diagnosis_level1', '')
        diagnosis_level2 = request.form.get('diagnosis_level2', '')
        diagnosis_level3 = request.form.get('diagnosis_level3', '')
        
        # Format diagnosis based on available levels
        if diagnosis_level1 and diagnosis_level2:
            if diagnosis_level3:
                diagnosis = f"{diagnosis_level3}"
            else:
                diagnosis = f"{diagnosis_level2}"
        else:
            diagnosis = ""
            
        report_date = request.form.get('report_date', '')
        tumor_mutational_burden = request.form.get('tumor_mutational_burden', '')
        
        # Get all possible diagnosis-specific fields
        all_diagnosis_fields = set()
        for rule in DIAGNOSIS_DROPDOWN_RULES.values():
            for dropdown in rule['dropdowns']:
                all_diagnosis_fields.add(dropdown['name'])
        
        # Get values for all diagnosis-specific fields
        diagnosis_fields = {}
        for field in all_diagnosis_fields:
            value = request.form.get(field, '')
            if value:  # Only include non-empty values
                # Use mapping if available, otherwise use the field as is
                field_name = patient_clinical_schema_keys.get(field, field)
                #field_name = field_name.upper().replace('_', ' ')
                diagnosis_fields[field_name] = value

        description = request.form.get('description', '')

        # Handle multiple image uploads
        image_files = request.files.getlist('genomic_images')
        image_filenames = []
        image_paths = []
        
        # Process each uploaded image
        for index, image_file in enumerate(image_files, 1):
            if image_file and image_file.filename:
                ext = os.path.splitext(secure_filename(image_file.filename))[1]
                # Add sequential number to filename
                image_filename = f"{unique_id}-{index:02d}{ext}"
                image_path = os.path.abspath(os.path.join(IMAGE_FOLDER, image_filename))
                image_file.save(image_path)
                image_filenames.append(image_filename)
                image_paths.append(image_path)

        # Save data to a text file named after unique_id
        data_file = f"{unique_id}.txt"
        data_file_path = os.path.abspath(os.path.join(TEXT_FOLDER, data_file))
        with open(data_file_path, 'w', encoding='utf-8') as f:
            f.write(f"{patient_clinical_schema_keys['sample_id_key']}: {unique_id}\n")
            f.write(f"{patient_clinical_schema_keys['mrn_key']}: {unique_id}\n")
            f.write(f"{patient_clinical_schema_keys['gender_key']}: {gender}\n")
            f.write(f"{patient_clinical_schema_keys['age_key'] if 'age_key' in patient_clinical_schema_keys else 'AGE'}: {age}\n")
            f.write(f"{patient_clinical_schema_keys['oncotree_diag_key'] if 'oncotree_diag_key' in patient_clinical_schema_keys else 'DIAGNOSIS'}: {diagnosis}\n")
            f.write(f"{patient_clinical_schema_keys['oncotree_diag_name_key'] if 'oncotree_diag_name_key' in patient_clinical_schema_keys else 'DIAGNOSIS_NAME'}: {diagnosis}\n")
            f.write(f"{patient_clinical_schema_keys['report_date_key']}: {report_date}\n")
            f.write(f"{patient_clinical_schema_keys['tmb_key']}: {tumor_mutational_burden}\n")
            
            # Write all diagnosis-specific fields
            for field_name, value in sorted(diagnosis_fields.items()):
                f.write(f"{field_name}: {value}\n")
            
            f.write("---\n")

        # Save description to a separate file
        if description:
            desc_file = f"{unique_id}_description.txt"
            desc_file_path = os.path.abspath(os.path.join(TEXT_FOLDER, desc_file))
            with open(desc_file_path, 'w', encoding='utf-8') as f:
                f.write(description)

        # Format the message with Patient ID and reference note
        flash(f"Patient ID: {unique_id}\nPlease save the patient ID for future reference")

        # Start the clinical data script in the background
        logger.info(f"Starting get_patient_clinical_data.py for file: {data_file}")
        process = subprocess.Popen(
            ['python', 'patient_data/get_patient_clinical_data.py', data_file],
            stdout=open('logs/get_patient_clinical_data.log', 'a'),
            stderr=subprocess.STDOUT
        )
        def log_on_finish(proc, data_file):
            proc.wait()
            logger.info(f"get_patient_clinical_data.py finished for file: {data_file}")
        threading.Thread(target=log_on_finish, args=(process, data_file), daemon=True).start()

        return redirect(url_for('index'))
    return render_template('index.html', level1_list=level1_list)

if __name__ == '__main__':
    app.run(debug=True) 