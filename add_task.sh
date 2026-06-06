#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

parent_id=""
infile="tasks.json"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --file)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --file" >&2
        exit 1
      fi
      infile="$2"
      shift 2
      ;;
    --parent-id)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --parent-id" >&2
        exit 1
      fi
      parent_id="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      echo "Usage: $0 [--file PATH] [--parent-id ID]" >&2
      exit 1
      ;;
  esac
done

if ! command -v wl-paste >/dev/null 2>&1; then
  echo "wl-paste is required but not found" >&2
  exit 1
fi

input_text="$(wl-paste)"
if [[ -z "${input_text//[[:space:]]/}" ]]; then
  echo "Clipboard is empty" >&2
  exit 1
fi

if [[ -n "$parent_id" ]]; then
  python3 "$SCRIPT_DIR/text_to_json.py" --infile "$infile" --parent-id "$parent_id" "$input_text"
else
  python3 "$SCRIPT_DIR/text_to_json.py" --infile "$infile" "$input_text"
fi

outfile="${infile%.json}.md"
python3 "$SCRIPT_DIR/json_to_markdown.py" -i "$infile" -o "$outfile"
