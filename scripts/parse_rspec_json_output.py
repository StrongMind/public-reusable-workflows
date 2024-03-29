import json
import sys

def main(rspec_output_file):
    with open(rspec_output_file, 'r') as file:
        data = json.load(file)

    specific_pending_messages = [
        "Temporarily skipped with xit",
        "Not yet implemented",
        "Add a hash of attributes"
    ]

    skipped_tests = [
        example for example in data['examples']
        if example['status'] == 'pending' and
           any(msg in example.get('pending_message', '') for msg in specific_pending_messages)
    ]

    if skipped_tests:
        print("Build failed because the following tests were skipped for no good reason:")
        for test in skipped_tests:
            print(f"{test['full_description']} - Reason: {test['pending_message']}")
        sys.exit(1) 
    else:
        print("No skipped tests found without a good reason.")
        sys.exit(0) 

if __name__ == "__main__":
    main(sys.argv[1])
