import pandas as pd
import re

def load_gene_to_ref_seq_mapping():
    df = pd.read_csv('./ref/census_gene_list.csv')
    subset = df[['Gene Symbol', 'Synonyms']]

    gene_to_ref_seq_id_mapping = {}
    for index, row in subset.iterrows():
        synonyms = row['Synonyms']
        if isinstance(synonyms, str):
            synonyms = synonyms.split(',')
        else:
            synonyms = []
        nm_pattern = re.compile(r'NM_\d+\.\d+')
        nm_matches = [s.strip() for s in synonyms if nm_pattern.match(s.strip())]
        if nm_matches:
            ref_seq_id = nm_matches[0]
            gene_to_ref_seq_id_mapping[row['Gene Symbol']] = ref_seq_id
        print(gene_to_ref_seq_id_mapping)
    return gene_to_ref_seq_id_mapping

