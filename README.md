# Veoci Solution Mapper

Map and visualize Veoci solution structure - forms, workflows, task types, and their relationships.

## Quick Start (Solutions Engineers)

### 1. Download

Download the latest release for your platform:

**[Download Latest Release](https://github.com/Veoci-Labs/veoci-solution-mapper/releases/latest)**

| Platform | File |
|----------|------|
| Mac | `veoci-map-macos.tar.gz` |
| Windows | `veoci-map-windows-x64.zip` |
| Linux | `veoci-map-linux-x64.tar.gz` |

### 2. Extract

**Mac/Linux:**
```bash
tar -xzf veoci-map-macos.tar.gz
chmod +x veoci-map
```

**Windows:**
Right-click the zip file and select "Extract All"

### 3. Run

```bash
./veoci-map
```

The wizard will guide you:
1. **Enter your PAT** - Get it from https://veoci.com/v/me/settings/advanced
2. **Enter container ID** - The room/container you want to map
3. **View results** - Dashboard opens automatically in your browser

Your PAT is saved locally for future runs.

### Output

The tool generates:
- **Interactive Dashboard** (`solution.html`) - Visual graph + data tables
- **JSON Export** (`solution.json`) - Raw data for further processing
- **Markdown Summary** (`solution.md`) - AI-enhanced descriptions
- **Mermaid Diagram** (`solution.mmd`) - For embedding in docs

## Scripting Mode

For automation, bypass the wizard with flags:

```bash
./veoci-map --pat YOUR_PAT --container CONTAINER_ID
```

## Troubleshooting

### Mac: "Cannot be opened" or "unidentified developer"

Run this command to remove the quarantine flag:
```bash
xattr -d com.apple.quarantine veoci-map
```

Then run `./veoci-map` normally. You only need to do this once.

### Windows: SmartScreen warning

Click "More info" then "Run anyway". You only need to do this once.

---

## Development

For contributors and developers who want to build from source.

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Installation

```bash
git clone https://github.com/Veoci-Labs/veoci-solution-mapper.git
cd veoci-solution-mapper

# Install with uv
uv pip install -e ".[dev]"

# Or with pip
pip install -e ".[dev]"
```

### Configuration

Set environment variables or use a `.env` file:

```bash
export VEOCI_TOKEN=your-pat-here
export GEMINI_API_KEY=your-gemini-key  # Optional, for AI features
```

### Usage

```bash
# Run wizard
veoci-map

# Or with flags
veoci-map --pat TOKEN --container CONTAINER_ID

# Show help
veoci-map --help
```

### Building Executables

```bash
# Install PyInstaller
pip install pyinstaller

# Build (injects GEMINI_API_KEY if set)
./build.sh
```

Output: `dist/veoci-map`

### Linting

```bash
ruff check .
ruff format .
```
