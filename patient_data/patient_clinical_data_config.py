# Configuration for patient clinical data schema keys
# Maps logical field names to official key names used in data files

patient_clinical_schema_keys = {
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