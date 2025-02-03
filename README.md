# Siri Splitwise Integration

A serverless application that allows you to create Splitwise expenses using natural language through Siri shortcuts. No more manual entry and calculations in your notes app. The application uses OpenAI's GPT model to parse natural language into structured expense data.

## Features

- Create Splitwise expenses using natural language descriptions via Siri shortcuts
- Support for equal, percentage, and exact amount splits
- Intelligent friend name matching
- AWS Lambda and API Gateway integration
- Comprehensive test suite

## Prerequisites

- Python 3.9+
- AWS SAM CLI
- AWS CLI configured with appropriate credentials
- Splitwise API credentials
- OpenAI API key

## Project Structure

```
sirisplitwise/
├── lambda_handler.py     # Main Lambda function code
├── tests.py             # Test suite
├── requirements.txt     # Python dependencies
├── template.yaml        # SAM template for AWS resources
├── event.json          # Sample event for local testing
└── pytest.ini          # Pytest configuration
```

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/sirisplitwise.git
cd sirisplitwise
```

2. Create a virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration

1. Create a `.env` file with your API credentials:
```
SPLITWISE_API_KEY=your_api_key
OPENAI_API_KEY=your_api_key
SPLITWISE_CONSUMER_KEY=your_consumer_key
SPLITWISE_CONSUMER_SECRET=your_consumer_secret
```

## Testing

The project includes a comprehensive test suite that verifies expense creation functionality.

### Running Tests

1. Single-person expense test:
```bash
python tests.py --test-type single --friend1 "Friend Name"
```

2. Multi-person expense test:
```bash
python tests.py --test-type multi --friend1 "Friend1 Name" --friend2 "Friend2 Name"
```

Test flags:
- `--test-type`: Type of test to run (`single` or `multi`)
- `--friend1`: Name of the first friend to test with
- `--friend2`: Name of the second friend (required for multi-person tests)

## Deployment

The application is deployed using AWS SAM (Serverless Application Model).

### Local Testing

1. Test the Lambda function locally:
```bash
sam local invoke FlaskSplitwiseLambda -e event.json
```

2. Start a local API Gateway:
```bash
sam local start-api
```

### Deployment to AWS

1. First-time deployment with guided setup:
```bash
sam deploy --guided
```

This will prompt for:
- Stack name (e.g., sirisplitwise-stack)
- AWS Region
- Parameter values for API keys
- Confirmation of IAM role creation
- Deployment preferences

2. Subsequent deployments:
```bash
sam deploy
```

### API Gateway Endpoint

After deployment, you'll receive an API Gateway endpoint URL. The endpoint accepts POST requests to `/addtransaction` with a JSON body:

```json
{
  "message": "Dinner with Ben for $50, split equally"
}
```

## Environment Variables

The following environment variables are required:

- `SPLITWISE_API_KEY`: Your Splitwise API key
- `OPENAI_API_KEY`: Your OpenAI API key
- `SPLITWISE_CONSUMER_KEY`: Your Splitwise consumer key
- `SPLITWISE_CONSUMER_SECRET`: Your Splitwise consumer secret

These are configured in the SAM template and passed to the Lambda function.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
