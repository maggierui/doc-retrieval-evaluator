import json
import csv
import argparse
import os

def convert_json_to_csv(input_file, output_file):
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found.")
        return

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            print("Error: JSON data must be a list of objects.")
            return

        if not data:
            print("Warning: JSON list is empty. No CSV generated.")
            return

        # Determine headers from the keys of the first dictionary
        # Explicitly ordering them as preferred, with others following
        preferred_order = ["query", "score", "reason", "retrieved_context_preview", "full_retrieved_context", "retrieved_chunks"]
        all_keys = list(data[0].keys())
        
        # Create headers list maintaining preferred order for known keys, then appending any others
        headers = [k for k in preferred_order if k in all_keys] + [k for k in all_keys if k not in preferred_order]

        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)

            for entry in data:
                row = []
                for header in headers:
                    val = entry.get(header, "")
                    # Check if value is complex (list or dict), if so, stringify it
                    if isinstance(val, (list, dict)):
                        val = json.dumps(val, ensure_ascii=False)
                    row.append(val)
                writer.writerow(row)
        
        print(f"Successfully converted '{input_file}' to '{output_file}'.")

    except json.JSONDecodeError:
        print(f"Error: Failed to decode JSON from '{input_file}'.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert evaluation results JSON to CSV.")
    parser.add_argument("--input", "-i", type=str, default="evaluation_results_formatted.json", help="Path to input JSON file.")
    parser.add_argument("--output", "-o", type=str, default="evaluation_results.csv", help="Path to output CSV file.")
    
    args = parser.parse_args()
    convert_json_to_csv(args.input, args.output)
