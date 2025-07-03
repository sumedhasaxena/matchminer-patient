# Matchminer Patient Application

This web application provides a user-friendly interface for Clinical Data Analysts to enter, review, and submit patient data into the Matchminer system. It leverages Optical Character Recognition (OCR) and AI-powered services to streamline data extraction from unstructured sources like clinical notes and PDF reports, while ensuring data integrity through a robust review and confirmation process.

---

## 1. Development Environment Setup

To get started with development, you'll need to set up an isolated Python environment. This prevents dependency conflicts with other projects. You can use either Python's built-in `venv` module or `conda`.

**Prerequisites:**
*   Git
*   Python 3.9+
*   Anaconda or Miniconda (if using `conda`)

**Steps:**

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/sumedhasaxena/matchminer-patient.git
    cd matchminer-patient
    ```

2.  **Create and activate the environment:**

    Choose one of the following options:

    **Option A: Using `venv` (standard Python)**

    a. **Create the virtual environment:**
    *   On **macOS and Linux**:
        ```bash
        python3 -m venv venv
        ```
    *   On **Windows**:
        ```bash
        python -m venv venv
        ```

    b. **Activate the virtual environment:**
    *   On **macOS and Linux**:
        ```bash
        source venv/bin/activate
        ```
    *   On **Windows**:
        ```bash
        .\venv\Scripts\activate
        ```
    ---
    **Option B: Using `conda`**

    a. **Create the Conda environment:**
    ```bash
    conda create --name matchminer-env python=3.9
    ```
    *(You can replace `matchminer-env` with your preferred environment name.)*

    b. **Activate the Conda environment:**
    ```bash
    conda activate matchminer-env
    ```

Your terminal prompt should now be prefixed with `(venv)` or `(matchminer-env)`, indicating that the environment is active.

---

## 2. Installing Dependencies

All the required Python packages are listed in the `requirements.txt` file.

With your environment activated, run the following command to install them:

```bash
pip install -r requirements.txt
```

---

## 3. Running the Application

Once the setup is complete and the dependencies are installed, you can run the Flask web application locally.

Execute the following command in your terminal:

```bash
python app.py
```

The application will start, and you can access it by navigating to the following URL in your web browser:

**http://127.0.0.1:8890**

---

## 4. General Application Flow

The application is designed around a simple, user-centric workflow:

1.  **Data Entry:** The user starts on the main page where they can upload patient report images (for OCR), enter a diagnosis (using free-text search or dropdowns), and add any unstructured clinical notes. Diagnosis-specific fields will appear dynamically.
2.  **Review Stage:** After submitting the initial data, the user is taken to a review page. Here, all entered, extracted, and AI-inferred data is displayed for verification. The user can edit any field to make corrections.
3.  **Confirmation:** Upon confirming the data, the application saves the final record, generates a unique MatchMiner ID, and displays a read-only confirmation page.
4.  **Background Processing:** The final data is processed in the background, generating the necessary JSON files for the Matchminer system while allowing the user to proceed with the next patient without waiting.

---

## 5. Deployment (Production on Linux)

To deploy this application to a production Linux server, we recommend using a combination of **Gunicorn**, **Nginx**, and **Systemd**.

### **A. On Your Server:**

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/sumedhasaxena/matchminer-patient.git
    cd matchminer-patient
    ```
2.  **Set Up Environment:** Create and activate a Python virtual environment as described in the setup section.
3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Create Environment File:** Copy the example file and set your production values.
    ```bash
    cp .env.example .env
    nano .env  # Edit the file to set your SECRET_KEY, etc.
    ```
5.  **Configure `gunicorn_start.sh`:**
    *   Edit the `gunicorn_start.sh` script.
    *   Set `FLASKDIR` to the absolute path of your project (e.g., `/home/user/matchminer-patient`).
    *   Set `USER` and `GROUP` to the Linux user you want the app to run as.
    *   Make the script executable: `chmod +x gunicorn_start.sh`.

### **B. Configure Systemd Service:**

1.  **Copy the Service File:**
    ```bash
    sudo cp matchminer-patient.service /etc/systemd/system/matchminer-patient.service
    ```
2.  **Edit the Service File:**
    ```bash
    sudo nano /etc/systemd/system/matchminer-patient.service
    ```
    *   Update the `User`, `Group`, `WorkingDirectory`, and `ExecStart` paths to match your server setup.
3.  **Reload and Enable the Service:**
    ```bash
    sudo systemctl daemon-reload
    sudo systemctl start matchminer-patient.service
    sudo systemctl enable matchminer-patient.service # To start on boot
    ```
4.  **Check Status:**
    ```bash
    sudo systemctl status matchminer-patient.service
    ```

### **C. Configure Nginx:**

1.  **Copy the Nginx Config:**
    ```bash
    sudo cp nginx.conf /etc/nginx/sites-available/matchminer-patient
    ```
2.  **Edit the Config:**
    ```bash
    sudo nano /etc/nginx/sites-available/matchminer-patient
    ```
    *   Change `your_server_domain_or_ip` to your server's actual domain or IP address.
    *   Update all instances of `/path/to/your/matchminer-patient` to your absolute project path.
3.  **Enable the Site:**
    ```bash
    sudo ln -s /etc/nginx/sites-available/matchminer-patient /etc/nginx/sites-enabled
    ```
4.  **Test and Restart Nginx:**
    ```bash
    sudo nginx -t
    sudo systemctl restart nginx
    ```

Your application should now be live and served by Nginx. Remember to also configure your firewall (`ufw`) to allow traffic on port 80 (HTTP) and 443 (HTTPS if you add SSL).