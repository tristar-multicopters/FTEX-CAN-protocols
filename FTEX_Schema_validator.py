import json
import sys
import argparse
from collections import Counter
from jsonschema import validate
from jsonschema.exceptions import ValidationError

# Allowed integer types for parameters using Valid_Flags
INT_TYPES = {"uint8_t", "uint16_t", "uint32_t", "int8_t", "int16_t", "int32_t"}

# Maximum values for each integer type
TYPE_MAX_VALUES = {
    "uint8_t": 0xFF,
    "uint16_t": 0xFFFF,
    "uint32_t": 0xFFFFFFFF,
    "int8_t": 0x7F,
    "int16_t": 0x7FFF,
    "int32_t": 0x7FFFFFFF,
}

# Custom exception for duplicate keys
class DuplicateKeyError(Exception):
    pass

# Custom JSON loader to detect duplicate keys
def json_load_with_duplicates_check(file_path):
    def raise_on_duplicates(ordered_pairs):
        # Check for duplicate keys
        keys = [key for key, _ in ordered_pairs]
        duplicates = [item for item, count in Counter(keys).items() if count > 1]
        if duplicates:
            raise DuplicateKeyError(f"Duplicate keys found: {', '.join(duplicates)}")
        return dict(ordered_pairs)

    with open(file_path, 'r') as file:
        return json.load(file, object_pairs_hook=raise_on_duplicates)

# Function to validate JSON data against the schema
def validate_json(data, schema):
    try:
        validate(instance=data, schema=schema)
        print("Schema validation passed.")
    except ValidationError as err:
        print("Schema validation failed.")
        print(f"Validation error message:\n{err.message}")
        print(f"Error occurred at: {' -> '.join(map(str, err.absolute_path))}")
        return False
    return True

# Function to check uniqueness of CO_ID keys
def validate_unique_co_ids(data):
    print("Running CO_ID validation...")
    co_ids = []

    # Recursive function to find all CO_IDs
    def find_co_ids(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key.startswith("CO_ID_"):
                    co_ids.append(key)
                find_co_ids(value)
        elif isinstance(obj, list):
            for item in obj:
                find_co_ids(item)

    find_co_ids(data)

    # Check for duplicates
    duplicates = [item for item, count in Counter(co_ids).items() if count > 1]
    if duplicates:
        print(f"Duplicate CO_IDs found: {', '.join(duplicates)}")
        return False

    print("All CO_IDs are unique.")
    return True

# Function to check uniqueness of CANOpen_Index values
def validate_unique_canopen_indexes(data):
    print("Running CANOpen_Index uniqueness validation...")
    canopen_indexes = []

    # Recursive function to find all CANOpen_Index values
    def find_canopen_indexes(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == "CANOpen_Index":
                    canopen_indexes.append(value)
                find_canopen_indexes(value)
        elif isinstance(obj, list):
            for item in obj:
                find_canopen_indexes(item)

    find_canopen_indexes(data)

    # Check for duplicates
    duplicates = [item for item, count in Counter(canopen_indexes).items() if count > 1]
    if duplicates:
        print(f"Duplicate CANOpen_Index values found: {', '.join(duplicates)}")
        return False

    print("All CANOpen_Index values are unique.")
    return True

def check_unique_subindexes(data):
    print("Running Subindex uniqueness validation...")
    for key, value in data.items():
        if key == "protocol":
            continue

        for co_id, co_id_data in value.items():
            if co_id == "Notes":
                continue
            if "Parameters" in co_id_data:
                subindexes = set()
                for param_name, param_data in co_id_data["Parameters"].items():
                    subindex = param_data.get("Subindex")
                    if subindex in subindexes:
                        print(f"Duplicate Subindex error in {co_id} -> {param_name}: Duplicate Subindex {subindex}")
                        return False
                    subindexes.add(subindex)

    print("All Subindexes are unique within each Parameters object.")
    return True

def check_parameter_names(data):
    print("Running Parameter name uniqueness validation...")
    for key, value in data.items():
        if key == "protocol":
            continue
        for co_id, co_id_data in value.items():
            if co_id == "Notes":
                continue
            if "Parameters" in co_id_data:
                parameter_names = set()
                for param_name in co_id_data["Parameters"].keys():
                    if not param_name.startswith("CO_PARAM"):
                        print(f"Parameter {param_name} expected to start with CO_PARAM")
                        return False
                    if param_name in parameter_names:
                        print(f"Duplicate Parameter name error in {co_id}: Duplicate Parameter {param_name}")
                        return False
                    parameter_names.add(param_name)
                    
    print("All Parameter names are unique within each Parameters object.")
    return True

def is_power_of_two(value: int) -> bool:
    if value == 0:
        return True  # allow 0 to represent "no flags set"
    return (value & (value - 1)) == 0

def validate_valid_flags(data):
    print("Running Valid_Flags validation...")

    def walk(obj, path_prefix=None):
        if path_prefix is None:
            path_prefix = []
        errors = []
        if isinstance(obj, dict):
            for key, value in obj.items():
                # Skip the protocol metadata
                if key == "protocol":
                    continue
                if key.startswith("CO_ID_") and isinstance(value, dict):
                    params = value.get("Parameters")
                    if isinstance(params, dict):
                        for param_name, param_data in params.items():
                            if not isinstance(param_data, dict):
                                continue
                            if "Valid_Flags" in param_data:
                                type_name = param_data.get("Type")
                                if type_name not in INT_TYPES:
                                    errors.append(f"{key} -> {param_name}: Valid_Flags requires integer Type, found '{type_name}'")
                                flags = param_data.get("Valid_Flags")
                                if not isinstance(flags, list) or len(flags) == 0:
                                    errors.append(f"{key} -> {param_name}: Valid_Flags must be a non-empty array")
                                    continue
                                seen_values = set()
                                max_value = TYPE_MAX_VALUES.get(type_name, None)
                                for idx, flag in enumerate(flags):
                                    location = f"{key} -> {param_name} -> Valid_Flags[{idx}]"
                                    if not isinstance(flag, dict):
                                        errors.append(f"{location}: each item must be an object")
                                        continue
                                    if "value" not in flag:
                                        errors.append(f"{location}: missing 'value'")
                                        continue
                                    value_field = flag["value"]
                                    if not isinstance(value_field, int):
                                        errors.append(f"{location}: 'value' must be an integer")
                                        continue
                                    if value_field < 0:
                                        errors.append(f"{location}: 'value' must be >= 0")
                                        continue
                                    if max_value is not None and value_field > max_value:
                                        errors.append(f"{location}: 'value' {value_field} exceeds max for {type_name} ({max_value})")
                                        continue
                                    if value_field in seen_values:
                                        errors.append(f"{location}: duplicate flag value {value_field}")
                                        continue
                                    seen_values.add(value_field)
                                    if not is_power_of_two(value_field):
                                        errors.append(f"{location}: 'value' must be 0 or a single-bit power of two")
                # Recurse and accumulate errors
                errors.extend(walk(value, path_prefix + [key]))
        elif isinstance(obj, list):
            for item in obj:
                errors.extend(walk(item, path_prefix))
        return errors

    errors = walk(data)
    if errors:
        print("Valid_Flags validation errors:")
        for e in errors:
            print(f"- {e}")
        return False
    print("All Valid_Flags entries are valid bitmasks and types are correct.")
    return True

def validate_active_sub_code_consistency(data):
    print("Running CO_PARAM_ACTIVE_SUB_CODE consistency validation...")
    
    # Collect all CO_PARAM_ACTIVE_SUB_CODE parameters
    active_sub_code_params = {}
    
    def collect_active_sub_code_params(obj, path_prefix=None):
        if path_prefix is None:
            path_prefix = []
        if isinstance(obj, dict):
            for key, value in obj.items():
                # Skip the protocol metadata
                if key == "protocol":
                    continue
                if key.startswith("CO_ID_") and isinstance(value, dict):
                    params = value.get("Parameters")
                    if isinstance(params, dict):
                        for param_name, param_data in params.items():
                            if param_name.startswith("CO_PARAM_ACTIVE_SUB_CODE") and isinstance(param_data, dict):
                                active_sub_code_params[param_name] = {
                                    'co_id': key,
                                    'type': param_data.get("Type"),
                                    'valid_options': param_data.get("Valid_Options", [])
                                }
                # Recurse
                collect_active_sub_code_params(value, path_prefix + [key])
        elif isinstance(obj, list):
            for item in obj:
                collect_active_sub_code_params(item, path_prefix)
    
    collect_active_sub_code_params(data)
    
    if not active_sub_code_params:
        print("No CO_PARAM_ACTIVE_SUB_CODE parameters found.")
        return True
    
    # Check if all parameters have the same type
    types = set(param['type'] for param in active_sub_code_params.values())
    if len(types) > 1:
        print("CO_PARAM_ACTIVE_SUB_CODE validation errors:")
        for param_name, param_data in active_sub_code_params.items():
            print(f"- {param_data['co_id']} -> {param_name}: Type '{param_data['type']}' differs from expected")
        return False
    
    expected_type = list(types)[0]
    print(f"All CO_PARAM_ACTIVE_SUB_CODE parameters have consistent type: {expected_type}")
    
    # Check if all parameters have the same Valid_Options
    valid_options_sets = []
    for param_name, param_data in active_sub_code_params.items():
        valid_options = param_data['valid_options']
        if not isinstance(valid_options, list):
            print(f"CO_PARAM_ACTIVE_SUB_CODE validation errors:")
            print(f"- {param_data['co_id']} -> {param_name}: Valid_Options must be a list")
            return False
        
        # Convert to a comparable format (list of tuples of value and description)
        options_set = set()
        for option in valid_options:
            if not isinstance(option, dict) or 'value' not in option or 'description' not in option:
                print(f"CO_PARAM_ACTIVE_SUB_CODE validation errors:")
                print(f"- {param_data['co_id']} -> {param_name}: Invalid Valid_Options format")
                return False
            options_set.add((option['value'], option['description']))
        
        valid_options_sets.append((param_name, param_data['co_id'], options_set))
    
    # Compare all Valid_Options sets
    reference_set = valid_options_sets[0][2]
    errors = []
    
    for param_name, co_id, options_set in valid_options_sets[1:]:
        if options_set != reference_set:
            errors.append(f"{co_id} -> {param_name}: Valid_Options differ from reference")
    
    if errors:
        print("CO_PARAM_ACTIVE_SUB_CODE validation errors:")
        for error in errors:
            print(f"- {error}")
        return False
    
    print(f"All {len(active_sub_code_params)} CO_PARAM_ACTIVE_SUB_CODE parameters have consistent Valid_Options.")
    return True

# class argument:
#     schema_file = ""
#     data_file = ""

def main():
    # Set up command-line argument parsing
    parser = argparse.ArgumentParser(description='Validate JSON data against a JSON Schema.')
    parser.add_argument('schema_file', help='Path to the JSON Schema file')
    parser.add_argument('data_file', help='Path to the JSON data file')
    args = parser.parse_args()

    # Load the JSON Schema
    try:
        with open(args.schema_file, 'r') as schema_file:
            schema = json.load(schema_file)
    except FileNotFoundError:
        print(f"Schema file not found: {args.schema_file}")
        sys.exit(1)
    except json.JSONDecodeError as err:
        print(f"Error parsing the schema file: {err}")
        sys.exit(1)

    # Load the JSON Data with duplicate key check
    try:
        data = json_load_with_duplicates_check(args.data_file)
    except DuplicateKeyError as err:
        print(f"Duplicate key error: {err}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"Data file not found: {args.data_file}")
        sys.exit(1)
    except json.JSONDecodeError as err:
        print(f"Error parsing the data file: {err}")
        sys.exit(1)

    # Validate the data
    schema_validation_passed = validate_json(data, schema)
    co_id_validation_passed = validate_unique_co_ids(data)
    canopen_index_validation_passed = validate_unique_canopen_indexes(data)
    unique_subindexes_passed = check_unique_subindexes(data)
    param_names_passed = check_parameter_names(data)
    valid_flags_passed = validate_valid_flags(data)
    active_sub_code_consistency_passed = validate_active_sub_code_consistency(data)

    # Exit with appropriate code
    if schema_validation_passed and co_id_validation_passed and canopen_index_validation_passed and unique_subindexes_passed and param_names_passed and valid_flags_passed and active_sub_code_consistency_passed:
        print("JSON data is valid.")
        sys.exit(0)  # Success
    else:
        print("JSON data validation failed.")
        sys.exit(1)  # Failure

if __name__ == '__main__':
    main()
