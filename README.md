# CodeBEgen

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Version](https://img.shields.io/badge/version-0.1.0-green.svg)

## Overview

CodeBEGen is an AI-powered tool that enables developers to rapidly generate backend API functionalities in multiple programming languages with minimal friction. This versatile tool is designed for agile development teams who need to create robust backend services quickly across different technology stacks. CodeBEGen streamlines the process of creating efficient APIs, allowing developers to focus on building great products rather than writing boilerplate code. The project consists of both a backend repository (this one) and a companion frontend repository [FrontEnd Repo](https://github.com/Marlinekhavele/CodeFEGen) that provides an intuitive UI for code generation.

## Features

- **Multi-language Support**: Generate backend code in various languages including Python, JavaScript, Java, Go, and more
- **AI-Powered Code Generation**: Automatically generate fully functional backend endpoints based on simple descriptions or specifications
- **Framework Flexibility**: Support for popular frameworks like FastAPI, Express, Spring Boot, and others
- **Intuitive UI**: User-friendly interface for specifying API requirements and generating code
- **Agile-First Design**: Optimized for rapid iteration and continuous development
- **Seamless Integration**: Easily integrate generated APIs into existing projects
- **Comprehensive Documentation**: Auto-generated API documentation for all endpoints
- **Full-Stack Solution**: Backend repository works with companion frontend repository for a complete development experience [FrontEnd Repo](https://github.com/Marlinekhavele/CodeFEGen)

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

3. **Switch to the main branch** (if not already on `main`):  

   ```sh
   git checkout main
   ```

## Backend Code Generator Project Architecture

```bash
codebegen/
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
│   ├── generators/           # Code generation engines for different languages
│   │   ├── python/           # Python code generators
│   │   │   ├── fastapi/      # FastAPI template generators
│   │   │   ├── flask/        # Flask template generators
│   │   │   ├── django/       # Django template generators
│   │   ├── javascript/       # JavaScript code generators
│   │   │   ├── express/      # Express.js template generators
│   │   │   ├── nest/         # NestJS template generators
│   │   ├── java/             # Java code generators
│   │   │   ├── spring/       # Spring Boot template generators
│   │   ├── go/               # Go code generators
│   │   │   ├── gin/          # Gin template generators
│   │   ├── common/           # Shared utilities across generators
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
-  If you don't have poetry install
   ```sh
    pip install poetry 
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
**Docker Setup and Deployment**:
### Prerequisites for Docker

- Docker installed on your machine
- Docker Compose installed on your machine

### Running with Docker Compose

Configure environment variables:
```sh
 .env.sample .env
```
🔹 Important variables:
```env
APP_PORT=8000  # Port where the app will be accessible
DB_USER=postgres
DB_PASSWORD=password
DB_NAME=code_be_gen
```

### Build and start the containers:
```sh
docker-compose up -d
```
- This builds the application image and starts both the application and PostgreSQL containers in detached mode.
Access the application at http://localhost:8000 (or your configured port)
Stop the containers:
```sh
docker-compose down
```
### Docker Commands Reference
- View application logs:
```sh
docker-compose logs -f backend
```
- Run database migrations in Docker:
```sh
docker-compose exec backend alembic upgrade head
```
- Rebuild after code changes:
```sh
docker-compose build backend
docker-compose up -d
```
- Open a shell in the container:
```sh
docker-compose exec backend bash
```
Troubleshooting Docker Setup
✅ Database Connection Issues:
Check if PostgreSQL container is healthy:
```sh
docker-compose ps
```
✅ Port Conflicts:
Modify `APP_PORT`in your `.env` file if port 8000 is already in use.
✅ Permission Issues:
You may need to use `sudo` before Docker commands or add your user to the Docker group.

## **Database Setup**  

### **Environment Configuration**

The application uses the following database configuration variables in the `.env` file:

```env
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=password
DB_NAME=code_be_gen
DB_TYPE=postgresql
```

Make sure to update these values to match your actual database setup if needed.

---

## Database Schema

The following Entity Relationship Diagram (ERD) shows the core data model for CodBEGen:

```
+---------------------+                 +----------------------+
|       Project       |                 |      Endpoints       |
+---------------------+                 +----------------------+
| ID    UniqueID      |-------          | ID    UniqueID       |
|                     |       .         |                      |
|       name          |       .         |       path           |
|       description   |       .         |       method         |
|       slug          |       .         |       description    |
|       langauge      |       .         |       file_hash      |
|       framework     |         ---->   |      project_id      |
+---------------------+                 +----------------------+
```

This schema represents the relationship between projects and their endpoints. Each project can have multiple endpoints, and each endpoint belongs to a single project (one-to-many relationship).

---

## **Step 1: Create a Database User**

If you need to create a new database user (skip if using existing postgres user):

```sql
CREATE USER postgres WITH PASSWORD 'password';
```

🔹 **Replace:**  

- `postgres` → Your **preferred database username** if different.  
- `password` → A **secure password** if different.  

---

## **Step 2: Create the Database**

```sql
CREATE DATABASE code_be_gen;
```

---

## **Step 3: Grant Permissions**

```sql
GRANT ALL PRIVILEGES ON DATABASE code_be_gen TO postgres;
```

🔹 **Replace:**  

- `postgres` → The **username** you are using.  

---

## **Step 4: Configure Environment Variables**

Create or edit the `.env` file in the project root to include:

```env
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=password
DB_NAME=code_be_gen
DB_TYPE=postgresql
```

The application will use these variables to construct the database connection string.

✅ **Note:** For local development, the default values shown above should work if you've set up PostgreSQL with the default postgres user.

---

## **Step 5: Verify Connection**

After setting up the database, test the connection:

```sh
psql -U postgres -d code_be_gen -h localhost
```

---

## **Step 6: Run database migrations**  

   ```sh
   alembic upgrade head
   ```

   _Do NOT run `alembic revision --autogenerate -m 'initial migration'` initially!_

## **Step 7: If making changes to database models, update migrations**  

```sh
   alembic revision --autogenerate -m 'your migration message'
   alembic upgrade head
   ```

---

## **Adding Tables and Columns**  

1. **After creating new tables or modifying models**:  

- Run Alembic migrations:  

     ```sh
     alembic revision --autogenerate -m "Migration message"
     alembic upgrade head
     ```

---

## **Running Tests with Pytest**  

### **Install Pytest**  

Ensure `pytest` is installed in your virtual environment:  

```sh
poetry add pytest
```

### **Run all tests in the project**  

From the **project root directory**, run:  

```sh
pytest
```

### **Run tests and generate coverage report**  

To check test coverage, install `pytest-cov`:  

```sh
poetry add pytest-cov
```

Then run:  

```sh
pytest --cov=api
```

---

- **Test your endpoints and models** before pushing changes.  
- **Push Alembic migrations** if database models are modified.  
- Ensure your code **follows project standards** and **passes tests** before submitting a pull request.

---

## Pre-Commit Setup (Required for Code Quality)

To maintain consistent code formatting and catch issues before committing, we use pre-commit hooks.

1. Install Pre-commit Hooks
   After cloning the repository and installing dependecies, run:

   ```bash
   pre-commit install
   ```

   This ensures that all pre-commit hooks run before every commit.
2. Manually Run Pre-Commit on All Files
   To check all files before committing:

   ```bash
   pre-commit run --all-files
   ```

3. If a Hook Fails, Fix Issues and Retry
   If pre-commit stops your commit, fix the reported issues and try again.


- **Test your endpoints and models** before pushing changes.  
- **Push Alembic migrations** if database models are modified.  
- Ensure your code **follows project standards** and **passes tests** before submitting a pull request.

---

## Using the UI for Code Generation

Once the application is running, you can access the web interface to generate backend code:

1. **Navigate to the web interface** at `http://localhost:8000` (or your configured port)
2. **Select your target language** from the available options
3. **Choose a framework** appropriate for your selected language
4. **Define your API requirements** through the intuitive form interface
5. **Generate code** with a single click
6. **Download the generated project** as a ZIP file or view individual files

The UI provides a seamless experience for creating backend APIs in your preferred language and framework without writing a single line of code.

## Documentation

For complete documentation, visit [docs.codebegen.io](https://docs.codebegen.io)

## Use Cases

- **Rapid Prototyping**: Quickly build and test API ideas in your preferred language
- **MVP Development**: Generate production-ready APIs for minimum viable products
- **Microservices**: Easily create and manage multiple microservice endpoints with consistent patterns
- **Cross-platform Development**: Generate equivalent APIs across different technology stacks
- **Learning Tool**: Understand best practices for API development in multiple languages
- **Hackathons**: Build functional backends in hours instead of days

## Architecture

CodeBEGen uses a modular architecture with the following components:

- **Core Generator**: AI-powered code generation engine
- **Language-specific Generators**: Specialized modules for each supported programming language
- **Framework Templates**: Templates for popular frameworks in each language
- **Schema Processor**: Converts API specifications into language-specific implementations
- **Web Interface**: User-friendly UI for defining and generating APIs
- **Frontend Repository**: Separate repository for the frontend interface

## Supported Languages and Frameworks

| Language   | Frameworks                          |
|------------|-------------------------------------|
| Python     | FastAPI, Flask, Django              |
| JavaScript | Express.js, NestJS, Koa             |


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

Built with ❤️ by the CodeBEGen Team