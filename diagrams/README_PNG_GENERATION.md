# PlantUML PNG Generation Instructions

## Overview

This directory contains PlantUML diagram source files (`.puml`) and their corresponding PNG images (`.png`). The PNG images are referenced in the technical documentation and must be generated from the PlantUML source files.

## Required PNG Generation

### ✅ Existing PNGs (Already Generated)
1. `01_system_overview.png`
2. `02_data_pipeline.png`
3. `03_database_schema.png`
4. `04_frontend_api.png`
5. `05_monitoring_system.png`
6. `06_hybrid_architecture.png`
7. `07_hva_ranking_system.png`
8. `08_query_builder_architecture.png`

### ❌ Missing PNG (Needs Generation)
9. **`09_dual_pipeline_architecture.png`** ← **REQUIRED**

## How to Generate PNG Files

### Option 1: Online PlantUML Server (Easiest)

1. Visit https://www.plantuml.com/plantuml/uml/
2. Copy the contents of `09_dual_pipeline_architecture.puml`
3. Paste into the editor
4. Click "Submit" to render
5. Right-click the diagram → "Save image as..."
6. Save as `09_dual_pipeline_architecture.png` in the `diagrams/` directory

### Option 2: PlantUML CLI (Local)

```bash
# Install PlantUML (requires Java)
# macOS
brew install plantuml

# Ubuntu/Debian
sudo apt-get install plantuml

# Generate PNG from PUML file
cd diagrams/
plantuml 09_dual_pipeline_architecture.puml

# This will create 09_dual_pipeline_architecture.png in the same directory
```

### Option 3: VS Code Extension

1. Install "PlantUML" extension in VS Code
2. Open `09_dual_pipeline_architecture.puml`
3. Press `Alt+D` (or `Option+D` on Mac) to preview
4. Right-click preview → "Export Current Diagram"
5. Select "png" format
6. Save to `diagrams/` directory

### Option 4: Docker (No local installation)

```bash
# Use official PlantUML Docker image
docker run --rm -v $(pwd):/diagrams plantuml/plantuml:latest \
  -tpng /diagrams/09_dual_pipeline_architecture.puml

# PNG will be created in the diagrams/ directory
```

## Verification

After generating the PNG, verify it exists:

```bash
ls -lh diagrams/09_dual_pipeline_architecture.png
```

Expected file size: ~50-200 KB

## Update Documentation

Once the PNG is generated, the documentation will automatically reference it:

**File**: `TECHNICAL_ARCHITECTURE.md`  
**Line**: ~758  
**Reference**: `![Dual-Pipeline Architecture](./diagrams/09_dual_pipeline_architecture.png)`

## Quality Settings (Recommended)

When generating PNGs, use these settings for best results:

- **Format**: PNG
- **Resolution**: 300 DPI (high quality)
- **Background**: Transparent or white
- **Width**: Auto (maintain aspect ratio)
- **Color depth**: 24-bit (true color)

## Maintaining Consistency

When updating diagrams:
1. Edit the `.puml` source file first
2. Regenerate the PNG using one of the methods above
3. Commit both `.puml` and `.png` files together
4. Verify the PNG displays correctly in documentation

## Troubleshooting

**Issue**: PlantUML syntax errors  
**Solution**: Validate syntax at https://www.plantuml.com/plantuml/uml/

**Issue**: PNG not displaying in documentation  
**Solution**: Check file path, ensure PNG exists, verify file permissions

**Issue**: Diagram too large or small  
**Solution**: Adjust `skinparam defaultFontSize` in `.puml` file

## Git Workflow

```bash
# After generating PNG
git add diagrams/09_dual_pipeline_architecture.puml
git add diagrams/09_dual_pipeline_architecture.png
git commit -m "docs: Add dual-pipeline architecture diagram (PlantUML + PNG)"
```

## Next Steps

1. **Generate the missing PNG** using one of the methods above
2. **Verify** the PNG displays correctly in TECHNICAL_ARCHITECTURE.md
3. **Commit** both the `.puml` source and generated `.png` file
4. **Update** GIT_COMMIT_COMMANDS.md if needed

## Related Files

- Source: `diagrams/09_dual_pipeline_architecture.puml`
- Output: `diagrams/09_dual_pipeline_architecture.png` (needs generation)
- Documentation: `TECHNICAL_ARCHITECTURE.md` (Section 9)
