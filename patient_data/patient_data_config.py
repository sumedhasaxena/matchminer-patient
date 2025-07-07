# Configuration for patient clinical data schema keys
# Maps logical field names to official key names used in data files

patient_schema_keys = {
    # mandatory
    "birth_date_key": "BIRTH_DATE",
    "first_name_key": "FIRST_NAME",
    "gender_key": "GENDER",
    "last_name_key": "LAST_NAME",
    "mrn_key": "MRN",
    "oncotree_diag_name_key": "ONCOTREE_PRIMARY_DIAGNOSIS_NAME",
    "oncotree_diag_key": "ONCOTREE_PRIMARY_DIAGNOSIS",
    "panel_version_key": "PANEL_VERSION",
    "pathologist_name_key": "PATHOLOGIST_NAME",
    "physician_email_key": "ORD_PHYSICIAN_EMAIL",
    "report_date_key": "REPORT_DATE",
    "report_version_key": "REPORT_VERSION",
    "sample_id_key": "SAMPLE_ID",
    "test_name_key": "TEST_NAME",
    "vital_status_key": "VITAL_STATUS",
    # optional
    "tmb_key": "TUMOR_MUTATIONAL_BURDEN_PER_MEGABASE",
    "mgmt_promotor_status_key": "MGMT_PROMOTER_STATUS",
    "pdl1_status_key": "PDL1_STATUS",
    "her2_status_key": "HER2_STATUS",
    "pr_status_key": "PR_STATUS",
    "er_status_key": "ER_STATUS",
    "mmr_status_key": "MMR_STATUS",
    "idh_wildtype_key": "IDH_WILDTYPE"
}

# Categorization of fields as clinical vs genomic
# This decides which fields go into patient's clinical json and which go to genomic json
field_categories = {
    "clinical": [
        "birth_date_key", "first_name_key", "gender_key", "last_name_key", "mrn_key",
        "oncotree_diag_name_key", "oncotree_diag_key", "panel_version_key", 
        "pathologist_name_key", "physician_email_key", "report_date_key", 
        "report_version_key", "sample_id_key", "test_name_key", "vital_status_key",
        "mgmt_promotor_status_key", "pdl1_status_key", "her2_status_key", 
        "pr_status_key", "er_status_key", "tmb_key", "mmr_status_key"
    ],
    "genomic": [
        "idh_wildtype_key"
    ]
}

def get_clinical_fields():
    """Get only the clinical fields from patient_schema_keys"""
    return {key: value for key, value in patient_schema_keys.items() 
            if key in field_categories["clinical"]}

def is_clinical_field(field_key):
    """Check if a field key is categorized as clinical"""
    return field_key in field_categories["clinical"]
