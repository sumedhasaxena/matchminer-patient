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