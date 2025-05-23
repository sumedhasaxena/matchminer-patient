from Bio import Entrez
import argparse

def get_gene_info(ref_seq:str):
   Entrez.email = "abc@sample.com"
   handle = Entrez.esummary(db="nucleotide", id=ref_seq)
   record = Entrez.read(handle)
   handle.close()
   return record[0]['Title']

def main(ref_seq: str):
    res = get_gene_info(ref_seq)
    print(f"Gene name for {ref_seq}: {res}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Get gene info from NCBI using reference sequence")
    parser.add_argument("ref_seq", type=str, help="Reference Sequence")
    args = parser.parse_args()
    main(args.ref_seq)

