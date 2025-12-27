# Veoci Solution Mapper

CLI tool to map Veoci solution structure and dependencies.

## Status

🚧 **Under Development** - This project is in early development.

## Installation

Install with uv:

```bash
uv pip install -e .
```

Or with development dependencies:

```bash
uv pip install -e ".[dev]"
```

## Configuration

Create a `.env` file by copying the example:

```bash
cp .env.example .env
```

Then fill in your Veoci credentials:

```
VEOCI_TOKEN=your-personal-access-token-here
VEOCI_BASE_URL=https://stage.veoci.com  # or your custom Veoci instance URL
```

The application will automatically load environment variables from `.env` on startup.

## Usage

```bash
# Show help
veoci-map --help

# Map a room (placeholder - not yet implemented)
veoci-map --room-id <room-id> --token <your-token>

# Use environment variable for token
export VEOCI_TOKEN=<your-token>
veoci-map --room-id <room-id>

# Specify output directory
veoci-map --room-id <room-id> --output ./output

# Interactive mode
veoci-map --room-id <room-id> --interactive
```

## Development

Run linter:

```bash
ruff check .
ruff format .
```

Run tests:

```bash
pytest
```
