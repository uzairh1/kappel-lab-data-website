from pathlib import Path

from pipeline.validation.checks import validate_outputs


def run(paths):
    errors, warnings = validate_outputs(
        paths.data_json, paths.diseases_json, paths.protein_details, paths.tissues
    )
    print(f"Validation: {len(errors)} error(s), {len(warnings)} warning(s)")
    for message in warnings:
        print(f"WARNING: {message}")
    if errors:
        for message in errors:
            print(f"ERROR: {message}")
        raise RuntimeError("Dataset validation failed")
