from flask import Flask, render_template, request, redirect, url_for, flash
import os
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Needed for flash messages

IMAGE_FOLDER = r'../nct2ctml/patient_data/images'
TEXT_FOLDER = r'../nct2ctml/patient_data/clinical_data'

os.makedirs(IMAGE_FOLDER, exist_ok=True)
os.makedirs(TEXT_FOLDER, exist_ok=True)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        gender = request.form.get('gender', '')
        sample_id = request.form.get('sample_id', '')
        age = request.form.get('age', '')
        diagnosis = request.form.get('diagnosis', '')
        report_date = request.form.get('report_date', '')
        tumor_mutational_burden = request.form.get('tumor_mutational_burden', '')
        pdl1_status = request.form.get('pdl1_status', '')
        her2_status = request.form.get('her2_status', '')
        pr_status = request.form.get('pr_status', '')
        er_status = request.form.get('er_status', '')
        mgmt_promoter_status = request.form.get('mgmt_promoter_status', '')
        description = request.form.get('description', '')

        # Handle multiple image uploads
        image_files = request.files.getlist('genomic_images')
        image_filenames = []
        image_paths = []
        
        # Process each uploaded image
        for image_file in image_files:
            if image_file and image_file.filename and sample_id:
                ext = os.path.splitext(secure_filename(image_file.filename))[1]
                # Add timestamp to make filename unique
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                image_filename = f"{sample_id}_{timestamp}{ext}"
                image_path = os.path.abspath(os.path.join(IMAGE_FOLDER, image_filename))
                image_file.save(image_path)
                image_filenames.append(image_filename)
                image_paths.append(image_path)

        # Save data to a text file named after sample_id, overwrite each time
        if sample_id:
            # Save main data file
            data_file = f"{sample_id}.txt"
            data_file_path = os.path.abspath(os.path.join(TEXT_FOLDER, data_file))
            with open(data_file_path, 'w', encoding='utf-8') as f:
                f.write(f"GENDER : {gender}\n")
                f.write(f"SAMPLE_ID : {sample_id}\n")
                f.write(f"AGE: {age}\n")
                f.write(f"DIAGNOSIS : {diagnosis}\n")
                f.write(f"REPORT_DATE: {report_date}\n")
                f.write(f"TUMOR_MUTATIONAL_BURDEN_PER_MEGABASE: {tumor_mutational_burden}\n")
                f.write(f"PDL1_STATUS: {pdl1_status}\n")
                f.write(f"HER2_STATUS: {her2_status}\n")
                f.write(f"PR_STATUS: {pr_status}\n")
                f.write(f"ER_STATUS: {er_status}\n")
                f.write(f"MGMT_PROMOTER_STATUS: {mgmt_promoter_status}\n")
                f.write("---\n")

            # Save description to a separate file
            if description:
                desc_file = f"{sample_id}_description.txt"
                desc_file_path = os.path.abspath(os.path.join(TEXT_FOLDER, desc_file))
                with open(desc_file_path, 'w', encoding='utf-8') as f:
                    f.write(description)

            if image_filenames:
                flash(f'Data saved! Text file: {data_file_path} | Description file: {desc_file_path} | Images: {", ".join(image_paths)}')
            else:
                flash(f'Data saved! Text file: {data_file_path} | Description file: {desc_file_path}')
        else:
            flash('Sample ID is required to save data.')
        return redirect(url_for('index'))
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True) 