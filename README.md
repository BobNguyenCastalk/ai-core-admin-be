# AI Core Admin Backend

<div align="center">
  <strong>Configuration Management for AI Core Services</strong>
</div>

<div align="center">
  GraphQL-based admin backend for managing AI Core service configurations.
</div>

## Project Origin

This project is forked from [Saleor](https://github.com/saleor/saleor), a GraphQL-native, API-only platform for scalable composable commerce. The fork was created to build a specialized admin backend for AI Core services.

## Purpose

AI Core Admin Backend is designed to manage configurations for all AI Core services. It provides:

- Centralized configuration management
- User and permission management
- Integration with other AI Core services

## Setup & Installation

1. Clone the repository
2. Install Poetry if not already installed:
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```
3. Install dependencies:
   ```bash
   poetry install
   ```
4. Set up environment variables
5. Run docker to using configuration inside `.devcontainer`
6. Activate the virtual environment and run migrations:
   ```bash
   poetry run python manage.py migrate
   ```
7. Access GraphQL playground at `http://localhost:8000/graphql/`

## GraphQL API

The application uses GraphQL for all API operations. The schema is available at `/graphql/` endpoint.

## License

This project is licensed under the BSD 3-Clause License - see the [LICENSE](LICENSE) file for details.
