# Contributing

Thank you for contributing to Backup Organizer.

## Development Setup

1. Clone the repository.
2. Create and activate a virtual environment.
3. Install dependencies:

```bash
pip install -r requirements.txt
```

## Running Locally

Run the Streamlit interface:

```bash
python -m streamlit run src/interface.py
```

Run CLI help:

```bash
python src/indexacao_texto.py --help
```

## Pull Request Guidelines

1. Create a branch from `main`.
2. Keep changes focused and small.
3. Include or update tests when possible.
4. Update docs (`README.md` or `docs/`) when behavior changes.
5. Ensure CI is green before requesting review.

## Commit Message Suggestions

Use clear, action-oriented messages.

Examples:
- `feat: add OCR throughput profile`
- `fix: handle resumo_curto migration`
- `docs: update installation workflow`

## Reporting Issues

Please use the issue templates and include:
- Steps to reproduce
- Expected behavior
- Actual behavior
- Logs or screenshots when applicable

## License

By contributing, you agree that your contributions are licensed under GPL-3.0-or-later.
