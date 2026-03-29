# Contributing to KisanMind

Thanks for your interest in contributing! This is a hackathon project, so we keep things simple.

## Setup

```bash
# Clone and enter the repo
git clone https://github.com/divyamohan1993/kisanmind.git
cd kisanmind

# Backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd frontend
npm install

# Environment
cp .env.example .env
# Fill in your API keys (Gemini, Earth Engine, Twilio, etc.)
```

## Code Style

- **Python**: Follow PEP 8. Use type hints where practical.
- **TypeScript**: Follow the existing ESLint config in `frontend/`.
- Keep functions small and well-named. Comments for non-obvious logic.

## Making Changes

1. Fork the repo and create a feature branch (`git checkout -b feature/my-change`).
2. Make your changes and test locally.
3. Open a Pull Request against `main` with a clear description of what and why.

## Reporting Issues

Open a GitHub Issue with steps to reproduce. Include browser/OS info for frontend bugs.

## Questions?

Open an issue or reach out to the maintainers. We're happy to help.
