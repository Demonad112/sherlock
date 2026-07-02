# Setting Up Sherlock in GitHub Codespaces

This guide walks you through running Sherlock in a GitHub Codespace.

## Quick Start (1 minute)

### Option 1: Automatic Setup (Recommended)
1. Open this repo in a Codespace:
   - Click **Code** → **Codespaces** → **Create codespace on master**
   - Wait ~2 minutes for the environment to initialize

2. The devcontainer will automatically:
   - Install Python 3.12
   - Install Sherlock and dependencies (`pip install -e .`)
   - Install development tools (pytest, etc.)

3. Start using Sherlock:
   ```bash
   sherlock --help
   sherlock github user123
   ```

### Option 2: Manual Setup
If you need to set up manually or in a fresh terminal:

```bash
# Install Sherlock from the current directory
pip install -e .

# Verify installation
sherlock --version

# Test basic functionality
sherlock --help
```

## Common Usage Examples

### Search for a single username
```bash
sherlock alice
```

### Search multiple usernames
```bash
sherlock alice bob charlie
```

### Save results to a file
```bash
sherlock --output results.txt alice
sherlock --csv alice
sherlock --xlsx alice
```

### Search only specific sites
```bash
sherlock --site GitHub --site Twitter alice
```

### Use a proxy
```bash
sherlock --proxy socks5://127.0.0.1:1080 alice
```

### Print all results (including not found)
```bash
sherlock --print-all alice
```

### Browse results in browser
```bash
sherlock --browse alice
```

### Enable verbose output
```bash
sherlock --verbose alice
```

### Combine options
```bash
sherlock --csv --output results/ --print-found --verbose alice bob
```

## Running Tests

### Run all tests
```bash
pytest
```

### Run specific test file
```bash
pytest tests/test_probes.py -v
```

### Run with coverage
```bash
pytest --cov=sherlock_project
```

### Run tests in parallel
```bash
pytest -n auto
```

## Development

### File Structure
- `sherlock_project/sherlock.py` - Main search logic
- `sherlock_project/sites.py` - Site manifest management
- `sherlock_project/result.py` - Result tracking
- `sherlock_project/notify.py` - Output handlers
- `sherlock_project/resources/data.json` - Supported sites database

### Making Changes
1. Edit files in the `sherlock_project/` directory
2. Since you installed with `-e` (editable), changes take effect immediately
3. Test your changes: `sherlock --help` or `pytest`

### Adding a New Site
Edit `sherlock_project/resources/data.json` to add site detection rules.

## Troubleshooting

### Command not found: sherlock
Make sure you've installed the package:
```bash
pip install -e .
```

### Import errors in tests
Reinstall the package:
```bash
pip install -e .
pip install -r tests/requirements.txt  # if it exists
```

### Codespace takes too long to load
The devcontainer automatically runs `postCreateCommand`. You can monitor progress in the terminal. Initial setup takes ~2-3 minutes.

## Next Steps

- Explore `docs/README.md` for full usage documentation
- Check out `tests/` to understand the test suite
- Review `pyproject.toml` for all dependencies
- Visit [https://sherlockproject.xyz](https://sherlockproject.xyz) for more info

## Using with Copilot

In your Codespace, you can ask GitHub Copilot:
- "How do I search for a username on a specific site?"
- "How does the site detection logic work?"
- "How do I add a new social network?"
- "What do the different status codes mean?"

Simply use **Ctrl+I** to open Copilot chat and ask questions about the code!
