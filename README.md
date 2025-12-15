# PDF Order Extractor API

A FastAPI-based web service for extracting order information from PDF and PNG files. The API integrates with a PostgreSQL database using Prisma ORM and supports user authentication with JWT tokens.

## Features

- **File Upload**: Accept PDF and PNG files for order extraction
- **Order Extraction**: Intelligent parsing of order data from uploaded documents
- **User Authentication**: JWT-based authentication system
- **Database Integration**: PostgreSQL database with Prisma ORM for data persistence
- **Third-Party Integration**: Send extracted orders to external APIs
- **Company Management**: Multi-tenant support with company-based configurations
- **API Documentation**: Automatic OpenAPI/Swagger documentation

## Tech Stack

- **Backend**: FastAPI (Python)
- **Database**: PostgreSQL with Prisma ORM
- **Authentication**: JWT tokens with python-jose
- **File Processing**: PyPDF2 for PDF handling
- **HTTP Client**: httpx for external API calls
- **Environment Management**: python-dotenv

## Prerequisites

- Python 3.8+
- PostgreSQL database
- Prisma 

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd pdf_extractor
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   venv\Scripts\activate  # On Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   Create a `.env` file in the root directory with the following variables:
   ```
   DATABASE_URL="postgresql://username:password@localhost:5432/database_name"
   SECRET_KEY="your-secret-key-here"
   ```

5. Set up the database:
   ```bash
   # Generate Prisma client
   python -m prisma generate

   # Push schema to database
   python -m prisma db push
   ```

## Usage

### Starting the API Server

Run the API server using the provided batch file:
```bash
start_api.bat
```

Or manually:
```bash
python -m uvicorn src.api:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

### API Endpoints

#### Authentication
- `POST /login` - User authentication
  - Body: `{"username": "string", "password": "string"}`
  - Returns: JWT token

#### Order Extraction
- `POST /extract-order` - Upload and extract order from PDF/PNG
  - Headers: `Authorization: Bearer <jwt-token>`
  - Form data: `file` (PDF/PNG), `cus_id` (string)
  - Returns: Extracted order data

#### Customers
- `GET /customers` - Retrieve customer list
  - Headers: `Authorization: Bearer <jwt-token>`
  - Returns: List of customers

#### Maintenance
- `DELETE /cleanup-uploads` - Clean upload directory
  - Headers: `Authorization: Bearer <jwt-token>`

#### Health Check
- `GET /health` - API health status
- `GET /` - API root status

### API Documentation

Once the server is running, visit `http://localhost:8000/docs` for interactive Swagger documentation.

## Configuration

The API supports company-specific configurations defined in `src/config.py`. Each company can have:
- API service URLs for customers and orders
- Custom extraction settings

## Database Schema

The application uses the following main entities:
- **User**: System users with authentication
- **Company**: Multi-tenant companies
- **Order**: Extracted order information
- **Item**: Individual items within orders

## Development

### Running Tests
```bash
# Add test commands here if available
```

### Code Formatting
```bash
# Add linting/formatting commands if configured
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

[Add license information here]

## Support

For support or questions, please [add contact information].