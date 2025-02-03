import pytest
import argparse
import json
import os
from dotenv import load_dotenv
from splitwise import Splitwise
from lambda_handler import lambda_handler, process_transaction, delete_expense

# Load environment variables
load_dotenv()

# Initialize Splitwise client
splitwise = Splitwise(
    consumer_key=os.getenv('SPLITWISE_CONSUMER_KEY'),
    consumer_secret=os.getenv('SPLITWISE_CONSUMER_SECRET'),
    api_key=os.getenv('SPLITWISE_API_KEY')
)

# Register test markers
pytest.mark.one_person = pytest.mark.one_person
pytest.mark.multi_person = pytest.mark.multi_person

class TestConfig:
    """Global test configuration to store friend names."""
    friend1 = None
    friend2 = None
    expense_ids = []  # Track all created expense IDs in order
    
    @classmethod
    def init_from_env(cls):
        """Initialize friend names from environment variables."""
        cls.friend1 = os.environ.get('TEST_FRIEND1')
        cls.friend2 = os.environ.get('TEST_FRIEND2')
        if not cls.friend1:
            raise ValueError("TEST_FRIEND1 environment variable not set")
        if not cls.friend2:
            raise ValueError("TEST_FRIEND2 environment variable not set for multi-person test")
        # Clear any existing expense IDs
        cls.expense_ids = []

def cleanup_all_expenses():
    """Clean up all tracked expenses."""
    print("\nCleaning up test expenses...")
    # Delete expenses in reverse order (newest first)
    for expense_id in reversed(TestConfig.expense_ids):
        try:
            delete_event = create_mock_delete_event(expense_id)
            delete_response = lambda_handler(delete_event, None)
            if delete_response['statusCode'] == 200:
                print(f"Successfully deleted expense {expense_id}")
            else:
                print(f"Warning: Failed to delete expense {expense_id}. Response: {delete_response}")
        except Exception as e:
            print(f"Error deleting expense {expense_id}: {str(e)}")
    TestConfig.expense_ids.clear()

def create_and_verify_expense(message):
    """Helper function to test a transaction and clean up afterward."""
    try:
        # Create mock event and process with Lambda handler
        event = create_mock_event(message)
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 200, f"Failed to create expense. Response: {response}"
        response_data = json.loads(response['body'])
        expense_id = response_data['expense_id']
        
        # Track the expense ID for cleanup
        TestConfig.expense_ids.append(expense_id)
        print(f"Created expense {expense_id}")
        
        # Get the expense details from Splitwise API
        expense = splitwise.getExpense(expense_id)
        assert expense is not None, "Failed to get expense details"
        
        return expense
    except Exception as e:
        print(f"Error in create_and_verify_expense: {str(e)}")
        raise

@pytest.fixture(autouse=True)
def cleanup_expenses():
    """Fixture to clean up all expenses after each test."""
    yield
    cleanup_all_expenses()

def pytest_configure():
    """Initialize TestConfig when pytest starts."""
    TestConfig.init_from_env()

def create_mock_event(message):
    """Create a mock API Gateway event."""
    return {
        'httpMethod': 'POST',
        'body': json.dumps({'message': message})
    }

def create_mock_delete_event(expense_id):
    """Create a mock API Gateway delete event."""
    return {
        'httpMethod': 'DELETE',
        'body': json.dumps({'expense_id': expense_id})
    }

@pytest.mark.one_person
def test_split_with_one_person():
    """Test splitting expenses with one person."""
    try:
        print("\nTesting splits with one person...")
        print(f"Testing with friend: {TestConfig.friend1}")
        
        # Test equal split with explicit name
        print("\nTesting equal split...")
        message = f"Split $50 evenly between me and {TestConfig.friend1}"
        expense = create_and_verify_expense(message)
        assert len(expense.users) == 2
        shares = [float(user.owed_share) for user in expense.users]
        assert all(share == 25.0 for share in shares), f"Expected all shares to be 25.0, got {shares}"
        
        # Test percentage split with explicit percentages
        print("\nTesting percentage split...")
        message = f"Split $100 where I pay 60% and {TestConfig.friend1} pays 40%"
        expense = create_and_verify_expense(message)
        assert len(expense.users) == 2
        shares = sorted([float(user.owed_share) for user in expense.users])
        assert shares == [40.0, 60.0], f"Expected shares [40.0, 60.0], got {shares}"
        
        # Test exact amounts
        print("\nTesting exact amounts...")
        message = f"Split $75 where I pay $45 and {TestConfig.friend1} pays $30"
        expense = create_and_verify_expense(message)
        assert len(expense.users) == 2
        shares = sorted([float(user.owed_share) for user in expense.users])
        assert shares == [30.0, 45.0], f"Expected shares [30.0, 45.0], got {shares}"
    finally:
        cleanup_all_expenses()

@pytest.mark.multi_person
def test_split_with_three_others():
    """Test splitting expenses with multiple people."""
    try:
        print("\nTesting splits with multiple people...")
        print(f"Testing with friends: {TestConfig.friend1} and {TestConfig.friend2}")
        
        # Test equal split with explicit names
        print("\nTesting equal split...")
        message = f"Split $100 evenly between me, {TestConfig.friend1}, and {TestConfig.friend2}"
        expense = create_and_verify_expense(message)
        assert len(expense.users) == 3
        shares = sorted([float(user.owed_share) for user in expense.users])
        # Splitwise should make it 33.33 + 33.33 + 33.34 = 100.00
        assert shares == [33.33, 33.33, 33.34], f"Expected shares to be [33.33, 33.33, 33.34], got {shares}"
        assert sum(shares) == 100.0, f"Shares should sum to 100, got {sum(shares)}"
        
        # Test percentage split with explicit percentages
        print("\nTesting percentage split...")
        message = f"Split $100 where I pay 50%, {TestConfig.friend1} pays 30%, and {TestConfig.friend2} pays 20%"
        expense = create_and_verify_expense(message)
        assert len(expense.users) == 3
        shares = sorted([float(user.owed_share) for user in expense.users])
        assert shares == [20.0, 30.0, 50.0], f"Expected shares [20.0, 30.0, 50.0], got {shares}"
        
        # Test exact amounts with round numbers
        print("\nTesting exact amounts...")
        message = f"Split $90 where I pay $30, {TestConfig.friend1} pays $30, and {TestConfig.friend2} pays $30"
        expense = create_and_verify_expense(message)
        assert len(expense.users) == 3
        shares = [float(user.owed_share) for user in expense.users]
        assert all(share == 30.0 for share in shares), f"Expected all shares to be 30.0, got {shares}"
    finally:
        cleanup_all_expenses()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run Splitwise integration tests')
    parser.add_argument('--test-type', choices=['one', 'multi', 'all'], 
                      required=True,
                      help='Type of tests to run: one person, multiple people, or all')
    parser.add_argument('--friend1',
                      required=True,
                      help='Name of first friend to test with')
    parser.add_argument('--friend2',
                      help='Name of second friend (required for multi-person tests)')
    
    args = parser.parse_args()
    
    # Validate friend2 is provided for multi-person tests
    if args.test_type in ['multi', 'all'] and not args.friend2:
        parser.error("--friend2 is required when running multi-person tests")
    
    # Initialize TestConfig directly first
    TestConfig.friend1 = args.friend1
    TestConfig.friend2 = args.friend2
    
    # Set environment variables for pytest subprocess
    os.environ['TEST_FRIEND1'] = args.friend1
    os.environ['TEST_FRIEND2'] = args.friend2 if args.friend2 else ''
    
    # Run the specified tests with pytest
    pytest_args = ['-v', __file__]
    if args.test_type == 'one':
        pytest_args.extend(['-k', 'test_split_with_one_person'])
    elif args.test_type == 'multi':
        pytest_args.extend(['-k', 'test_split_with_three_others'])
    
    pytest.main(pytest_args)
