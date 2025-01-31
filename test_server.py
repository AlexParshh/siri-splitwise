import pytest
import argparse
from server import process_transaction, delete_expense

# Register test markers
pytest.mark.one_person = pytest.mark.one_person
pytest.mark.multi_person = pytest.mark.multi_person

class TestConfig:
    """Global test configuration to store friend names."""
    friend1 = None
    friend2 = None

def create_and_verify_expense(message):
    """Helper function to test a transaction and clean up afterward."""
    # Process the transaction
    expense = process_transaction(message)
    assert expense is not None, f"Failed to create expense for message: {message}"
    print(f"Created expense {expense.id} for message: {message}")
    
    # Verify the expense details
    assert float(expense.cost) > 0, "Expense amount should be greater than 0"
    assert len(expense.users) >= 2, "Expense should have at least 2 users"
    
    # Clean up by deleting the expense
    result = delete_expense(expense.id)
    assert result[0] is True, f"Failed to delete expense {expense.id}"
    print(f"Successfully deleted expense {expense.id}")
    
    return expense

@pytest.mark.one_person
def test_split_with_one_person():
    """Test splitting expenses with one person."""
    print("\nTesting splits with one person...")
    
    # Test equal split
    print("\nTesting equal split...")
    expense = create_and_verify_expense(
        f"Split $30 dinner evenly with {TestConfig.friend1}"
    )
    assert len(expense.users) == 2
    assert all(float(user.owed_share) == 15.0 for user in expense.users)
    
    # Test percentage split
    print("\nTesting percentage split...")
    expense = create_and_verify_expense(
        f"Split $100 with {TestConfig.friend1} where I pay 60 percent and they pay 40 percent"
    )
    assert len(expense.users) == 2
    user_shares = {float(user.owed_share) for user in expense.users}
    assert user_shares == {40.0, 60.0}
    
    # Test exact amounts
    print("\nTesting exact amounts...")
    expense = create_and_verify_expense(
        f"Split $50 with {TestConfig.friend1} where I pay $30 and they pay $20"
    )
    assert len(expense.users) == 2
    user_shares = {float(user.owed_share) for user in expense.users}
    assert user_shares == {20.0, 30.0}

@pytest.mark.multi_person
def test_split_with_three_others():
    """Test splitting expenses with three other people."""
    print("\nTesting splits with multiple people...")
    
    # Test equal split
    print("\nTesting equal split...")
    expense = create_and_verify_expense(
        f"Split $100 evenly between me, {TestConfig.friend1}, and {TestConfig.friend2}"
    )
    assert len(expense.users) == 3
    # Check that shares are either 33.33 or 33.34 and sum to 100
    shares = [float(user.owed_share) for user in expense.users]
    assert all(share in (33.33, 33.34) for share in shares), f"Shares should be 33.33 or 33.34, got {shares}"
    assert sum(shares) == 100.0, f"Shares should sum to 100, got {sum(shares)}"
    
    # Test percentage split
    print("\nTesting percentage split...")
    expense = create_and_verify_expense(
        f"Split $200 where I pay 40%, {TestConfig.friend1} pays 35%, and {TestConfig.friend2} pays 25%"
    )
    assert len(expense.users) == 3
    shares = {float(user.owed_share) for user in expense.users}
    assert shares == {80.0, 70.0, 50.0}
    
    # Test exact amounts
    print("\nTesting exact amounts...")
    expense = create_and_verify_expense(
        f"Split $150 where I pay $50, {TestConfig.friend1} pays $50, and {TestConfig.friend2} pays $50"
    )
    assert len(expense.users) == 3
    assert all(float(user.owed_share) == 50.0 for user in expense.users)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run Splitwise integration tests')
    parser.add_argument('--test-type', choices=['one', 'multi', 'all'], 
                      default='all', help='Type of tests to run: one person, multiple people, or all')
    parser.add_argument('--friend1', required=True,
                      help='Name of first friend to test with')
    parser.add_argument('--friend2', required=True,
                      help='Name of second friend to test with')
    args = parser.parse_args()
    
    # Store friend names in TestConfig
    TestConfig.friend1 = args.friend1
    TestConfig.friend2 = args.friend2
    
    # Build pytest arguments based on command line choice
    pytest_args = [__file__, '-v']
    if args.test_type == 'one':
        pytest_args.extend(['-m', 'one_person'])
    elif args.test_type == 'multi':
        pytest_args.extend(['-m', 'multi_person'])
    # For 'all', we don't need to add any markers
    
    print(f"\nRunning {'all' if args.test_type == 'all' else args.test_type + ' person'} tests...")
    print(f"Testing with friends: {TestConfig.friend1} and {TestConfig.friend2}")
    pytest.main(pytest_args)
