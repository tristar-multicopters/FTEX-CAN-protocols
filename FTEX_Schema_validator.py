import json
import sys
import argparse
from collections import Counter
from jsonschema import validate
from jsonschema.exceptions import ValidationError

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

    # Exit with appropriate code
    if schema_validation_passed and co_id_validation_passed and canopen_index_validation_passed and unique_subindexes_passed and param_names_passed:
        print("JSON data is valid.")
        sys.exit(0)  # Success
    else:
        print("JSON data validation failed.")
        sys.exit(1)  # Failure

if __name__ == '__main__':
    main()
