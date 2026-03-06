#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib.sh"

ensure_prereqs
load_outputs

command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 1; }

CSV_PATH="${1:-${ROOT_DIR}/Comics.csv}"
FORCE_SEED="${FORCE_SEED:-false}"

if [[ ! -f "${CSV_PATH}" ]]; then
  echo "CSV file not found: ${CSV_PATH}" >&2
  exit 1
fi

if ! aws dynamodb describe-table --region "${AWS_REGION}" --table-name "${DDB_TABLE_NAME}" >/dev/null 2>&1; then
  echo "DynamoDB table '${DDB_TABLE_NAME}' does not exist. Run scripts/aws/01-bootstrap.sh first." >&2
  exit 1
fi

EXISTING_COUNT="$(aws dynamodb scan --region "${AWS_REGION}" --table-name "${DDB_TABLE_NAME}" --select COUNT --limit 1 --query 'Count' --output text)"
if [[ "${EXISTING_COUNT}" != "0" && "${FORCE_SEED}" != "true" ]]; then
  echo "Table '${DDB_TABLE_NAME}' is not empty (count sample=${EXISTING_COUNT})." >&2
  echo "Refusing to seed to avoid overwriting IDs. Set FORCE_SEED=true to continue." >&2
  exit 1
fi

TMP_DIR="$(mktemp -d)"
cleanup() { rm -rf "${TMP_DIR}"; }
trap cleanup EXIT

python3 - "${CSV_PATH}" "${TMP_DIR}" "${DDB_TABLE_NAME}" << 'PY'
import csv
import json
import os
import sys

csv_path = sys.argv[1]
out_dir = sys.argv[2]
table = sys.argv[3]

required = ["Title", "Volume", "Writer", "Artist"]
rows = []

with open(csv_path, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    missing = [c for c in required if c not in (reader.fieldnames or [])]
    if missing:
        raise SystemExit(f"CSV missing required columns: {', '.join(missing)}")

    for idx, row in enumerate(reader, start=1):
        rows.append({
            "PutRequest": {
                "Item": {
                    "id": {"N": str(idx)},
                    "title": {"S": (row.get("Title") or "").strip()},
                    "volume": {"S": str(row.get("Volume") or "").strip()},
                    "writer": {"S": (row.get("Writer") or "").strip()},
                    "artist": {"S": (row.get("Artist") or "").strip()},
                }
            }
        })

chunk_size = 25
for i in range(0, len(rows), chunk_size):
    chunk = rows[i:i + chunk_size]
    payload = {table: chunk}
    with open(os.path.join(out_dir, f"batch_{i//chunk_size:05d}.json"), "w", encoding="utf-8") as out:
        json.dump(payload, out)

print(len(rows))
PY

TOTAL_ROWS="$(python3 - "${CSV_PATH}" << 'PY'
import csv
import sys
with open(sys.argv[1], newline="", encoding="utf-8") as f:
    print(sum(1 for _ in csv.DictReader(f)))
PY
)"

retry_batch() {
  local batch_file="$1"
  local attempt=0
  local current_file="${batch_file}"

  while true; do
    local response
    response="$(aws dynamodb batch-write-item --region "${AWS_REGION}" --request-items "file://${current_file}")"
    local unprocessed_count
    unprocessed_count="$(echo "${response}" | jq '[.UnprocessedItems[]? | length] | add // 0')"

    if [[ "${unprocessed_count}" == "0" ]]; then
      break
    fi

    attempt=$((attempt + 1))
    if [[ ${attempt} -gt 8 ]]; then
      echo "Failed to process batch after retries: ${batch_file}" >&2
      return 1
    fi

    local retry_file
    retry_file="${TMP_DIR}/retry_$(basename "${batch_file}")_${attempt}.json"
    echo "${response}" | jq '.UnprocessedItems' > "${retry_file}"
    current_file="${retry_file}"
    sleep $((attempt * 2))
  done
}

batch_files=("${TMP_DIR}"/batch_*.json)
if [[ ! -e "${batch_files[0]}" ]]; then
  echo "No rows found in CSV; nothing to seed."
  exit 0
fi

for file in "${batch_files[@]}"; do
  retry_batch "${file}"
done

echo "Seed complete. Imported ${TOTAL_ROWS} rows from ${CSV_PATH} into table ${DDB_TABLE_NAME}."
