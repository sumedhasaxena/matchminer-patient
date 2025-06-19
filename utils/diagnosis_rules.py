"""Configuration for diagnosis-specific dropdown rules"""

DIAGNOSIS_DROPDOWN_RULES = {
    '_' : {
        'texts':[
            {
                'label': 'Tumor Mutational Burden',
                'name': 'tmb_key'
            }
        ]
    },
    'Diffuse Glioma': {
        'dropdowns': [
            {
                'label': 'IDH wildtype',
                'name': 'idh_wildtype_key',
                'values': ['True', 'False']
            },
            {
                'label': 'MGMT Promoter Status',
                'name': 'mgmt_promotor_status_key',
                'values': ['Methylated', 'Unmethylated']
            }
        ]
    },
    'Colorectal Adenocarcinoma': {
        'dropdowns': [
            {
                'label': 'MMR Status',
                'name': 'mmr_status_key',
                'values': [
                    'Proficient (MMR-P / MSS)',
                    'Deficient (MMR-D / MSI-H)'
                ]
            }
        ]
    },
    
    'Breast': {
        'dropdowns': [
            {
                'label': 'HER2 Status',
                'name': 'her2_status_key',
                'values': ['Positive', 'Negative', 'Unknown']
            },
            {
                'label': 'ER Status',
                'name': 'er_status_key',
                'values': ['Positive', 'Negative', 'Unknown']
            },
            {
                'label': 'PR Status',
                'name': 'pr_status_key',
                'values': ['Positive', 'Negative', 'Unknown']
            }
        ]
    },
    'Non-Small Cell Lung Cancer': {
        'dropdowns': [
            {
                'label': 'PDL1 Status',
                'name': 'pdl1_status_key',
                'values': ['High','Low']
            }
        ]
    }
}