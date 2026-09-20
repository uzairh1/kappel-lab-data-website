from pathlib import Path

from pipeline.validation.checks import validate_outputs


def run(paths):
    errors, warnings = validate_outputs(
        paths.protein_catalog,
        paths.disease_associations,
        paths.protein_details,
        paths.tissue_expression,
    )
    print(f"Validation: {len(errors)} error(s), {len(warnings)} warning(s)")
    for message in warnings:
        print(f"WARNING: {message}")
    if errors:
        for message in errors:
            print(f"ERROR: {message}")
        raise RuntimeError("Dataset validation failed")
