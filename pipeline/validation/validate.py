from pipeline.validation.checks import validate_outputs, validate_source


def run(paths, source_df=None):
    errors = []
    warnings = []
    if source_df is not None:
        source_errors, source_warnings = validate_source(source_df)
        errors.extend(source_errors)
        warnings.extend(source_warnings)
    output_errors, output_warnings = validate_outputs(
        paths.data_json,
        paths.diseases_json,
        paths.protein_details,
        paths.tissues,
    )
    errors.extend(output_errors)
    warnings.extend(output_warnings)
    if errors:
        print("Validation FAILED")
        for msg in errors:
            print(f"  ERROR: {msg}")
        return 1
    print(f"  0 validation errors; {len(warnings)} warnings")
    for msg in warnings:
        print(f"  WARNING: {msg}")
    return 0
