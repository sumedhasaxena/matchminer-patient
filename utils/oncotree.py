import sys
import os

sys.path.append(os.path.abspath('../'))

import csv
from collections import defaultdict
import config


def _get_level_columns(fieldnames):
    return sorted(
        (f for f in fieldnames if f.startswith('level_')),
        key=lambda name: int(name.split('_')[1]),
    )


def _parse_level_value(value):
    if not value:
        return ''
    return value.split('(')[0].strip()


def _read_oncotree_rows():
    with open(config.ONCOTREE_TXT_FILE_PATH) as f:
        reader = csv.DictReader(f, delimiter='\t')
        level_columns = _get_level_columns(reader.fieldnames)
        rows = list(reader)
    return rows, level_columns


def _row_path(row, level_columns):
    return [
        _parse_level_value(row[col])
        for col in level_columns
        if _parse_level_value(row[col])
    ]


def _normalize_term(term):
    return term.strip().lower()


def get_all_oncotree_data():
    rows, level_columns = _read_oncotree_rows()

    level_1_list = set()
    mapping_l1_all = defaultdict(set)

    for row in rows:
        level_1 = _parse_level_value(row[level_columns[0]])
        level_1_list.add(level_1)
        mapping_l1_all[level_1].update(
            _parse_level_value(row[col]) for col in level_columns[1:]
        )

    for values in mapping_l1_all.values():
        values.discard('')
    return level_1_list, mapping_l1_all


def get_all_diagnosis_terms():
    level_1_list, mapping_l1_all = get_all_oncotree_data()
    terms = set(level_1_list)
    for values in mapping_l1_all.values():
        terms.update(values)
    return terms


def build_diagnosis_result_from_path(path):
    cleaned = [term for term in path if term]
    if not cleaned:
        return None
    return {
        'path': cleaned,
        'primary_diagnosis': cleaned[-1],
        'level1': cleaned[0],
        'level2': cleaned[1] if len(cleaned) > 1 else None,
        'level3': cleaned[2] if len(cleaned) > 2 else None,
    }


def canonicalize_term(term, candidates):
    if term is None:
        return None
    if term in candidates:
        return term
    term_normalized = _normalize_term(term)
    for candidate in candidates:
        if _normalize_term(candidate) == term_normalized:
            return candidate
    return None


def get_children_of_term(parent_term):
    rows, level_columns = _read_oncotree_rows()
    parent_normalized = _normalize_term(parent_term)
    children = set()

    for row in rows:
        path = _row_path(row, level_columns)
        for index, term in enumerate(path):
            if _normalize_term(term) == parent_normalized and index + 1 < len(path):
                children.add(path[index + 1])

    return sorted(children)


def resolve_diagnosis_hierarchy(diagnosis_value):
    rows, level_columns = _read_oncotree_rows()
    target_normalized = _normalize_term(diagnosis_value)

    best_path = None
    best_depth = -1

    for row in rows:
        path = _row_path(row, level_columns)
        for index, term in enumerate(path):
            if _normalize_term(term) == target_normalized and index > best_depth:
                best_depth = index
                best_path = path[: index + 1]

    return build_diagnosis_result_from_path(best_path) if best_path else None


def get_l1_l2_oncotree_data():
    print(config.ONCOTREE_TXT_FILE_PATH)
    rows, level_columns = _read_oncotree_rows()

    level_1_list = set()
    mapping_l1_l2 = defaultdict(set)

    for row in rows:
        level_1 = _parse_level_value(row[level_columns[0]])
        level_1_list.add(level_1)
        if len(level_columns) > 1:
            level_2 = _parse_level_value(row[level_columns[1]])
            if level_2:
                mapping_l1_l2[level_1].add(level_2)

    for values in mapping_l1_l2.values():
        values.discard('')

    return level_1_list, mapping_l1_l2
