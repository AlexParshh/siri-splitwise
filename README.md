# Siri Splitwise Integration

## Testing

The test suite verifies various Splitwise transaction scenarios including:
- Splitting expenses evenly with one or multiple people
- Splitting by percentages
- Splitting by exact amounts

To run the tests, you'll need to provide the names of two Splitwise friends that you want to test with. The tests will create and then automatically delete test expenses with these friends.

```bash
# Run all tests
python test_server.py --test-type all --friend1 "Friend Name" --friend2 "Other Friend"

# Run only single-person split tests
python test_server.py --test-type one --friend1 "Friend Name" --friend2 "Other Friend"

# Run only multi-person split tests
python test_server.py --test-type multi --friend1 "Friend Name" --friend2 "Other Friend"
```

Note: Make sure these friends are in your Splitwise friends list and their names match exactly as they appear in Splitwise. The tests will create real expenses in Splitwise (and immediately delete them) to verify the functionality.
