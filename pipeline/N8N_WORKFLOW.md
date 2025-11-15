# n8n Workflow for Document Processing Pipeline

This document describes the n8n workflow for orchestrating document processing.

## Overview

The workflow watches `pipeline/inbox/` for new files and processes them through
a series of steps, managing errors and tracking progress via JSON manifests.

## Workflow Nodes

### 1. File Watcher (Trigger)
- **Type**: Local File Trigger
- **Path**: `pipeline/inbox/`
- **Event**: File Created
- **Outputs**: File path, filename

### 2. Move to Processing
- **Type**: Execute Command
- **Command**:
  ```bash
  mv "{{$node["File Watcher"].json["path"]}}" "pipeline/processing/{{$node["File Watcher"].json["name"]}}"
  ```
- **Purpose**: Atomic move to prevent duplicate processing

### 3. Extract Document ID
- **Type**: Code
- **Language**: JavaScript
- **Code**:
  ```javascript
  const filename = $node["Move to Processing"].json["name"];
  const doc_id = filename.replace(/\.txt$/, '');
  return { doc_id, filepath: `pipeline/processing/${filename}` };
  ```

### 4. Step 01: Classify
- **Type**: Execute Command
- **Command**:
  ```bash
  cd "${PROJECT_ROOT}" && \
  uv run python -m unsealed_networks.pipeline.steps.classify \
    "{{$node["Extract Document ID"].json["doc_id"]}}" \
    "{{$node["Extract Document ID"].json["filepath"]}}"
  ```
- **On Error**: Go to "Handle Failure"
- **Note**: Set `PROJECT_ROOT` environment variable in n8n to your installation directory

### 5. Step 02: Extract Entities
- **Type**: Execute Command
- **Command**: Similar to Step 01, calls `unsealed_networks.pipeline.steps.extract_entities`
- **On Error**: Go to "Handle Failure"

### 6. Step 03: Extract URLs
- **Type**: Execute Command
- **Command**: Similar to Step 01, calls `unsealed_networks.pipeline.steps.extract_urls`
- **On Error**: Go to "Handle Failure"

### 7. Step 04: Extract Email Metadata
- **Type**: Execute Command
- **Command**: Similar to Step 01, calls `unsealed_networks.pipeline.steps.extract_email_metadata`
- **On Error**: Go to "Handle Failure"

### 8. Step 99: Assemble Metadata
- **Type**: Execute Command
- **Command**: Similar to Step 01, calls `unsealed_networks.pipeline.steps.assemble_metadata`
- **Purpose**: Final metadata assembly from all step results

### 9. Move to Completed
- **Type**: Execute Command
- **Command**:
  ```bash
  mv "{{$node["Extract Document ID"].json["filepath"]}}" \
     "pipeline/completed/{{$node["File Watcher"].json["name"]}}"
  ```

### 10. Handle Failure
- **Type**: Code
- **Purpose**: Move failed document to dead letters
- **Code**:
  ```javascript
  const doc_id = $node["Extract Document ID"].json["doc_id"];
  const filepath = $node["Extract Document ID"].json["filepath"];
  const error = $node["Step XX"].json["stderr"] || "Unknown error";

  // Move to dead letters
  exec(`mv "${filepath}" "pipeline/dead_letters/${doc_id}.txt"`);

  // Manifest already has error details
  return { doc_id, error };
  ```

## Workflow Diagram

```
[File Watcher] ──> [Move to Processing] ──> [Extract Doc ID]
                                                  │
                                                  ▼
                                          [Step 01: Classify]
                                                  │
                                       ┌──────────┴──────────┐
                                       │                     │
                                    Success               Failure
                                       │                     │
                                       ▼                     ▼
                              [Step 02: Entities]   [Handle Failure]
                                       │                     │
                                       ▼                     ▼
                               [Step 03: URLs]      [Move to Dead Letters]
                                       │
                                       ▼
                             [Step 04: OCR Fixes]
                                       │
                                       ▼
                           [Step 99: Assemble Metadata]
                                       │
                                       ▼
                             [Move to Completed]
```

## Error Handling

Each step node has error handling configured:
1. On failure, execution branches to "Handle Failure"
2. Failed document is moved to `pipeline/dead_letters/`
3. Manifest contains error details and last successful step
4. Workflow continues (doesn't stop entire pipeline)

## Retry Logic

For transient failures (network, temporary resource issues):
1. Configure "Retry On Fail" in each step node
2. Max retries: 3
3. Wait between retries: 30 seconds (exponential backoff)

## Monitoring

### Workflow Execution Dashboard
- Monitor in n8n UI: Execution history shows success/failure
- Filter by status: See only failed executions

### File System Monitoring
```bash
# Watch for new files in inbox
watch -n 5 'ls -lh pipeline/inbox/'

# Monitor processing
ls -lh pipeline/processing/

# Check failures
ls -lh pipeline/dead_letters/
```

### Manifest Inspection
```bash
# View recent manifests
ls -lt pipeline/manifests/ | head -10

# Check specific document
cat pipeline/manifests/HOUSE_OVERSIGHT_123456.json | jq .
```

## Deployment

### 1. Import Workflow to n8n
- Export this workflow as JSON
- Import in n8n UI: Settings > Import from File

### 2. Configure Paths
- Update all file paths to match your installation
- Test with a single document first

### 3. Activate Workflow
- Enable "Active" toggle in n8n
- Workflow will now process files automatically

## Step Invalidation for Reprocessing

When adding a new step (e.g., `step_05_deduplicate.py`):

### 1. Update n8n Workflow
- Add new step node between existing steps
- Connect error handling

### 2. Identify Documents to Reprocess
```bash
# Find manifests missing the new step
python -c "
import json
from pathlib import Path

for manifest_path in Path('pipeline/manifests').glob('*.json'):
    with open(manifest_path) as f:
        manifest = json.load(f)

    has_step = any(s['step_name'] == 'deduplicate' for s in manifest['steps'])
    if not has_step:
        print(manifest['doc_id'])
"
```

### 3. Reprocess Documents
```bash
# For each doc_id from step 2:
# 1. Move document from completed/ to inbox/
# 2. Truncate manifest steps after step_04
# 3. Let n8n workflow reprocess from step_05 onward

# Example script:
for doc_id in $(cat docs_to_reprocess.txt); do
    mv "pipeline/completed/${doc_id}.txt" "pipeline/inbox/"

    python -c "
from unsealed_networks.pipeline.manifest import Manifest
m = Manifest.load(\"$doc_id\")
m.truncate_steps_after('fix_ocr_urls')
m.status = 'processing'
m.save()
    "
done
```

## Testing

Test the workflow with a sample document:

```bash
# Copy test document to inbox
cp source_text/7th_production/TEXT/001/HOUSE_OVERSIGHT_030732.txt \
   pipeline/inbox/

# Watch the workflow execute
tail -f pipeline/manifests/HOUSE_OVERSIGHT_030732.json

# Check result
ls pipeline/completed/HOUSE_OVERSIGHT_030732.txt
cat pipeline/manifests/HOUSE_OVERSIGHT_030732.json | jq .
```
