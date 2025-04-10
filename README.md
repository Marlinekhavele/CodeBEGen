# CodegenBE

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Version](https://img.shields.io/badge/version-0.1.0-green.svg)

## Overview

CodegenBE is an AI-powered tool that enables developers to rapidly generate backend API functionalities with minimal friction. Built on Python and FastAPI, this tool is designed for agile development teams who need to create robust backend services quickly. CodegenBE streamlines the process of creating efficient APIs, allowing developers to focus on building great products rather than writing boilerplate code. The project consists of both a backend repository (this one) and a companion frontend repository for a complete solution.

## Features

- **AI-Powered API Generation**: Automatically generate fully functional FastAPI backend endpoints based on simple descriptions or specifications
- **Agile-First Design**: Optimized for rapid iteration and continuous development
- **Seamless Integration**: Easily integrate generated APIs into existing projects
- **Comprehensive Documentation**: Auto-generated OpenAPI documentation for all endpoints
- **Frontend Integration**: Compatible with the companion frontend repository for a complete full-stack solution

## Getting Started

### Prerequisites

- Python 3.8 or higher
- poetry
- Docker (optional, for containerized deployment)

## **Cloning the Repository**  

1. **Clone the repository** :  

   ```sh
   https://github.com/Marlinekhavele/CodeBEGen.git
   ```

2. **Navigate into the project directory**:  

   ```sh
   cd codebegen
   ```

3. **Switch to the development branch** (if not already on `dev`):  

   ```sh
   git checkout dev
   ```

## Backend IM Project Architecture

```bash
codegenbe/
│
├── alembic/                  # Database migrations
│   ├── versions/             # Migration scripts
│   ├── env.py                # Alembic environment settings
│   ├── script.py.mako        # Template for migrations
│   └── README                # Documentation
│
├── app/
│   ├── __init__.py
│   ├── api/                  # API routes and dependencies
│   │   ├── v1/               # API version 1
│   │   │   ├── models/       # SQLAlchemy models
│   │   │   │   ├── __init__.py
│   │   │   ├── routes/       # API routes
│   │   │   │   ├── __init__.py
│   │   │   ├── schemas/      # Pydantic schemas
│   │   │   │   ├── __init__.py
│   │   │   ├── services/     # Business logic
│   │   │   │   ├── __init__.py
│   │   │   ├── utils/        # Utility functions
│   │   │   │   ├── __init__.py
│   │   ├── __init__.py
│
├── tests/                    # Unit and integration tests
│   ├── __init__.py
│
├── .env.sample               # Sample environment variables
├── .gitignore                # Git ignore file
├── alembic.ini               # Alembic configuration
├── config.py                 # Configuration settings
├── conftest.py               # Pytest configuration
├── LICENSE                   # Project license
├── main.py                   # FastAPI main application entry point
├── poetry.lock               # Poetry lockfile
├── pyproject.toml            # Python dependencies
└── README.md                 # Project documentation
```

## **Setup Instructions**  

1. **Create a virtual environment**:  

   ```sh
   python3 -m venv .venv
   ```

2. **Activate the virtual environment**:  

- On macOS/Linux:  

     ```sh
     source .venv/bin/activate
     ```

- On Windows (PowerShell):  

     ```sh
     .venv\Scripts\Activate
     ```

3. **Install project dependencies**:  

   ```sh
   poetry install
   ```

4. **Create a `.env` file** from `.env.sample`:  

   ```sh
   cp .env.sample .env
   ```

5. **To Run Project Locally**:

```sh
poetry run python main.py
```


## Documentation

For complete documentation, visit [docs.codegenbe.io](https://docs.codegenbe.io)


## Use Cases

- **Rapid Prototyping**: Quickly build and test API ideas
- **MVP Development**: Generate production-ready APIs for minimum viable products
- **Microservices**: Easily create and manage multiple microservice endpoints
- **Hackathons**: Build functional backends in hours instead of days

## Architecture

CodegenBE uses a modular architecture with the following components:

- **Core Generator**: AI-powered code generation engine
- **FastAPI Backend**: Generated APIs use FastAPI for high performance and easy documentation
- **Frontend Repository**: Separate repository for the frontend interface



## Contributing

We welcome contributions from the community! Please read our [Contributing Guidelines](CONTRIBUTING.md) before submitting a pull request.


## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.



## Microsoft Open Source Code of Conduct

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).

For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Related Microsoft Projects

- [VS Code](https://github.com/microsoft/vscode)
- [Playwright](https://github.com/microsoft/playwright)
- [DeepSpeed](https://github.com/microsoft/DeepSpeed)
- [Semantic Kernel](https://github.com/microsoft/semantic-kernel)

## Acknowledgments

- Special thanks to all our contributors and community members
- Inspired by similar tools in the AI-assisted development space
- Built with open source technologies

---

Built with ❤️ by the CodegenBE Team