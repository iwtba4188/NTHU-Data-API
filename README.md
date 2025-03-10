# NTHU-Data-API
<p align="center">
    <em>NTHU-Data-API is a project designed for NTHU developers.</em>
    <br>
    <em>It provides an easy way to fetch data from the NTHU website.</em>
</p>
<p align="center">
<a href="https://github.com/psf/black" target="_blank">
    <img src="https://img.shields.io/badge/code%20style-black-000000.svg" alt="Code style: black">
</a>
<a href="https://coverage-badge.samuelcolvin.workers.dev/redirect/NTHU-SA/NTHU-Data-API" target="_blank">
    <img src="https://coverage-badge.samuelcolvin.workers.dev/NTHU-SA/NTHU-Data-API.svg" alt="Test Coverage">
</a>
<a href="github.com/NTHU-SA/NTHU-Data-API/actions/workflows/tests.yml" target="_blank">
    <img src="https://github.com/NTHU-SA/NTHU-Data-API/actions/workflows/tests.yml/badge.svg" alt="Test Action Status">
</a>
<br>
<a href="https://sonarcloud.io/summary/new_code?id=NTHU-SA_NTHU-Data-API" target="_blank">
    <img src="https://sonarcloud.io/api/project_badges/measure?project=NTHU-SA_NTHU-Data-API&metric=sqale_rating" alt="
Maintainability Rating">
</a>
<a href="https://sonarcloud.io/summary/new_code?id=NTHU-SA_NTHU-Data-API" target="_blank">
    <img src="https://sonarcloud.io/api/project_badges/measure?project=NTHU-SA_NTHU-Data-API&metric=ncloc" alt="Lines of Code">
</a>
<a href="https://sonarcloud.io/summary/new_code?id=NTHU-SA_NTHU-Data-API" target="_blank">
    <img src="https://sonarcloud.io/api/project_badges/measure?project=NTHU-SA_NTHU-Data-API&metric=sqale_index" alt="Technical Debt">
</a>
</p>

## Getting Started
### Prerequisites
Ensure you have Python 3 installed on your machine. You can verify this by running `python3 --version` in your terminal. If you don't have Python 3 installed, you can download it [here](https://www.python.org/downloads/).

### Installation
1. Clone the repository:
```sh
git clone https://github.com/NTHU-SA/NTHU-Data-API.git
```
2. Navigate to the project directory:
```sh
cd NTHU-Data-API
```
3. Install the required dependencies:
```sh
pip3 install -r requirements.txt
```

### Configuration
Copy the environment template file and fill in your details:
```sh
cp .env.template .env
```

### Running the Application
```sh
python3 main.py
```

## Contributing
We follow certain guidelines for contributing. Here are the types of commits we accept:

- feat: Add or modify features.
- fix: Bug fixes.
- docs: Documentation changes.
- style: Changes that do not affect the meaning of the code (white-space, formatting, missing semi colons, etc).
- refactor: Code changes that neither fixes a bug nor adds a feature.
- update: Data changes that neither fixes a bug nor adds a feature.
- perf: Code changes that improve performance.
- test: Adding missing tests.
- chore: Changes to the build process or auxiliary tools and libraries.
- revert: Reverts a previous commit.

### pre-commit
1. Before committing, use `pre-commit` to ensure the format.
```sh
pip3 install -r requirements-dev.txt
```
2. Install `pre-commit`.
```sh
pre-commit install
```

### Running Tests
To run tests locally before committing changes, follow these steps:
1. Install the required dependencies:
```sh
pip3 install -r requirements-tests.txt
```
2. Run tests:
Navigate to the project's root directory and execute:
```sh
python3 -m pytest -n auto tests -W ignore::DeprecationWarning
```
3. Generate a coverage report (optional):
If you need a test coverage report, run:
```sh
python3 -m pytest -n auto tests -W ignore::DeprecationWarning --cov=src --cov=tests --cov-report=xml --cov-report=html:coverage --cov-fail-under=85
```
## Credit
This project is maintained by NTHUSA 32nd.

## License
This project is licensed under the [MIT License](https://choosealicense.com/licenses/mit/).

## Acknowledgements
Thanks to SonarCloud for providing code quality metrics:

[![SonarCloud](https://sonarcloud.io/images/project_badges/sonarcloud-white.svg)](https://sonarcloud.io/summary/new_code?id=NTHU-SA_NTHU-Data-API)