"""Configuration for diagnosis-specific dropdown rules"""

DIAGNOSIS_DROPDOWN_RULES = {
    
    'Diffuse Glioma': {
        'dropdowns': [
            {
                'label': 'IDH wildtype',
                'name': 'idh_wildtype',
                'values': ['True', 'False']
            },
            {
                'label': 'MGMT Promoter Status',
                'name': 'mgmt_promoter_status',
                'values': ['Methylated', 'Unmethylated']
            }
        ]
    },
    'Colorectal Adenocarcinoma': {
        'dropdowns': [
            {
                'label': 'MMR Status',
                'name': 'mmr_status',
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
                'name': 'her2_status',
                'values': ['Positive', 'Negative', 'Unknown']
            },
            {
                'label': 'ER Status',
                'name': 'er_status',
                'values': ['Positive', 'Negative', 'Unknown']
            },
            {
                'label': 'PR Status',
                'name': 'pr_status',
                'values': ['Positive', 'Negative', 'Unknown']
            },
            {
                'label': 'PDL1 Status',
                'name': 'pdl1_status',
                'values': ['High','Low']
            }
        ]
    }
} 