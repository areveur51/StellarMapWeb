# Contributing to StellarMapWeb

Thank you for your interest in contributing to StellarMapWeb! This document provides guidelines for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)

## Code of Conduct

This project follows a standard Code of Conduct. By participating, you are expected to uphold this code:

- Be respectful and inclusive
- Welcome newcomers and help them learn
- Focus on what is best for the community
- Show empathy towards other community members

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally
3. Create a new branch for your feature or bug fix
4. Make your changes
5. Test your changes thoroughly
6. Submit a pull request

## Development Setup

### Prerequisites

- Python 3.10 or higher
- DataStax Astra DB account (for Cassandra database)
- Git

### Installation Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/StellarMapWeb.git
   cd StellarMapWeb
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Generate a Django secret key:**
   ```python
   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   ```
   Add the generated key to your `.env` file as `DJANGO_SECRET_KEY`.

6. **Set up Astra DB:**
   - Create a free Astra DB account at https://astra.datastax.com
   - Create a database and keyspace
   - Download the secure connect bundle
   - Place it in the project root directory
   - Update `.env` with your Astra DB credentials

7. **Run migrations:**
   ```bash
   python manage.py migrate
   ```

8. **Create a superuser:**
   ```bash
   python manage.py createsuperuser
   ```

9. **Run the development server:**
   ```bash
   python manage.py runserver
   ```

## How to Contribute

### Reporting Bugs

If you find a bug, please create an issue on GitHub with:

- A clear, descriptive title
- Steps to reproduce the bug
- Expected behavior
- Actual behavior
- Screenshots (if applicable)
- Your environment details (OS, Python version, etc.)

### Suggesting Features

Feature suggestions are welcome! Please create an issue with:

- A clear description of the feature
- Why this feature would be useful
- Example use cases
- Any implementation ideas (optional)

### Code Contributions

1. **Choose an issue** or create a new one describing what you plan to work on
2. **Comment on the issue** to let others know you're working on it
3. **Fork the repository** and create a feature branch
4. **Write your code** following our coding standards
5. **Test thoroughly** before submitting
6. **Submit a pull request** with a clear description

## Coding Standards

### Python Style Guide

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) style guide
- Use 4 spaces for indentation (no tabs)
- Maximum line length: 100 characters
- Use meaningful variable and function names
- Add docstrings to functions and classes

### Code Quality Tools

We recommend using these tools to maintain code quality:

```bash
# Install code quality tools
pip install black flake8 isort

# Format code with Black
black .

# Sort imports with isort
isort .

# Check code with flake8
flake8 .
```

### Django Best Practices

- Keep views simple and focused
- Use Django's built-in security features
- Never commit sensitive data (API keys, passwords, etc.)
- Use environment variables for configuration
- Write clear commit messages

## Testing

### Running Tests

```bash
# Run all tests
python manage.py test

# Run tests for a specific app
python manage.py test apiApp

# Run tests with coverage
pip install coverage
coverage run --source='.' manage.py test
coverage report
```

### Writing Tests

- Write tests for new features and bug fixes
- Aim for good test coverage
- Test both success and failure cases
- Use descriptive test names

Example test structure:

```python
from django.test import TestCase

class YourModelTestCase(TestCase):
    def setUp(self):
        # Set up test data
        pass
    
    def test_feature_works_correctly(self):
        # Test implementation
        self.assertEqual(expected, actual)
```

## Pull Request Process

1. **Update documentation** if you've added or changed functionality
2. **Ensure all tests pass** before submitting
3. **Update the README.md** if needed
4. **Create a pull request** with:
   - Clear title describing the change
   - Description of what changed and why
   - Reference to related issues (e.g., "Fixes #123")
   - Screenshots for UI changes

5. **Respond to feedback** from maintainers
6. **Keep your branch updated** with the main branch

### Pull Request Checklist

- [ ] Code follows the project's coding standards
- [ ] Tests have been added/updated and all pass
- [ ] Documentation has been updated
- [ ] Commit messages are clear and descriptive
- [ ] No sensitive data (keys, passwords) in commits
- [ ] Branch is up to date with main

## Questions?

If you have questions, please:

- Check existing issues and documentation
- Create a new issue with the "question" label
- Reach out to maintainers

## License

By contributing to StellarMapWeb, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to StellarMapWeb! 🚀
