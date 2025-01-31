import os
import json
from flask import Flask, request, jsonify
from openai import OpenAI
from splitwise import Splitwise
from splitwise.expense import Expense
from splitwise.user import ExpenseUser
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
splitwise = Splitwise(
    consumer_key=os.getenv('SPLITWISE_CONSUMER_KEY'),
    consumer_secret=os.getenv('SPLITWISE_CONSUMER_SECRET'),
    api_key=os.getenv('SPLITWISE_API_KEY')
)

def get_friends_data():
    """Fetch and format friends data from Splitwise"""
    current_user = splitwise.getCurrentUser()
    friends = splitwise.getFriends()
    
    friends_data = {
        "current_user": {
            "id": current_user.id,
            "name": f"{current_user.first_name} {current_user.last_name}".strip()
        },
        "friends": [
            {
                "id": friend.id,
                "name": f"{friend.first_name} {friend.last_name}".strip(),
                "email": friend.email
            }
            for friend in friends
        ]
    }
    return friends_data

def parse_transaction_with_openai(transaction_text, friends_data):
    # Create a clear context about available friends
    friends_context = "\n".join([
        f"- {friend['name']} (ID: {friend['id']}, Email: {friend['email']})"
        for friend in friends_data['friends']
    ])
    
    # Prompt for OpenAI to convert natural language to structured data
    prompt = f"""Convert the following transaction text to a JSON format suitable for Splitwise.
    The current user is {friends_data['current_user']['name']} (ID: {friends_data['current_user']['id']}).
    
    Available friends:
    {friends_context}
    
    Transaction text: {transaction_text}
    
    Return only valid JSON in this format:
    {{
        "amount": float,
        "description": string,
        "split_type": string,  # One of: "equal", "percentage", "exact"
        "paid_by": {{
            "user_id": string,
            "name": string
        }},
        "split_with": [
            {{
                "user_id": string,
                "name": string,
                "split_value": float  # For percentage: 0-100, for exact: actual amount, for equal: ignored
            }}
        ]
    }}
    
    Do not include any markdown formatting or code block markers. Return only the raw JSON.
    """
    
    try:
        print("Sending request to OpenAI API...")
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that converts natural language transaction descriptions to structured Splitwise data. You have access to the user's friends list and can map names to correct user IDs."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
        )
        print("OpenAI API response received")
        
        try:
            content = response.choices[0].message.content.strip()
            # Remove markdown code block if present
            if content.startswith('```'):
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
            content = content.strip()
            
            parsed_data = json.loads(content)
            print("Successfully parsed OpenAI response:", parsed_data)
            return parsed_data
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON from OpenAI response: {e}")
            print("Raw response content:", response.choices[0].message.content)
            return None
            
    except Exception as e:
        print(f"Error calling OpenAI API: {str(e)}")
        print(f"Error type: {type(e)}")
        return None

def create_splitwise_expense(parsed_data):
    try:
        # Create expense users
        users = []
        total_amount = float(parsed_data['amount'])
        
        # Get list of unique users excluding the payer
        split_users = [
            user for user in parsed_data['split_with'] 
            if user['user_id'] != parsed_data['paid_by']['user_id']
        ]
        
        # Calculate total number of users (including payer)
        total_users = len(split_users) + 1
        
        if parsed_data['split_type'] == 'equal':
            # Round share to 2 decimal places
            share_per_person = round(total_amount / total_users, 2)
            
            # Adjust last share to account for rounding errors
            total_shares = share_per_person * (total_users - 1)
            last_share = round(total_amount - total_shares, 2)
            
            # Add the person who paid
            payer = ExpenseUser()
            payer.setId(parsed_data['paid_by']['user_id'])
            payer.setPaidShare(str(total_amount))
            payer.setOwedShare(str(share_per_person))  # Payer gets the regular share
            users.append(payer)
            
            # Add all other users except the last one
            for user_data in split_users[:-1]:
                user = ExpenseUser()
                user.setId(user_data['user_id'])
                user.setPaidShare('0.00')
                user.setOwedShare(str(share_per_person))
                users.append(user)
            
            # Add the last user with adjusted share if there are other users
            if split_users:
                last_user = ExpenseUser()
                last_user.setId(split_users[-1]['user_id'])
                last_user.setPaidShare('0.00')
                last_user.setOwedShare(str(last_share))
                users.append(last_user)
        
        elif parsed_data['split_type'] == 'percentage':
            # Add the person who paid
            payer = ExpenseUser()
            payer.setId(parsed_data['paid_by']['user_id'])
            payer.setPaidShare(str(total_amount))
            payer_split = next((u['split_value'] for u in parsed_data['split_with'] 
                              if u['user_id'] == parsed_data['paid_by']['user_id']), None)
            if payer_split is None:
                payer_split = 100 - sum(u['split_value'] for u in split_users)
            payer.setOwedShare(str(round((payer_split / 100.0) * total_amount, 2)))
            users.append(payer)
            
            # Add all other users
            for user_data in split_users:
                user = ExpenseUser()
                user.setId(user_data['user_id'])
                user.setPaidShare('0.00')
                user.setOwedShare(str(round((user_data['split_value'] / 100.0) * total_amount, 2)))
                users.append(user)
        
        else:  # exact amounts
            # Add the person who paid
            payer = ExpenseUser()
            payer.setId(parsed_data['paid_by']['user_id'])
            payer.setPaidShare(str(total_amount))
            payer_split = next((u['split_value'] for u in parsed_data['split_with'] 
                              if u['user_id'] == parsed_data['paid_by']['user_id']), None)
            if payer_split is None:
                payer_split = round(total_amount - sum(u['split_value'] for u in split_users), 2)
            payer.setOwedShare(str(payer_split))
            users.append(payer)
            
            # Add all other users
            for user_data in split_users:
                user = ExpenseUser()
                user.setId(user_data['user_id'])
                user.setPaidShare('0.00')
                user.setOwedShare(str(round(user_data['split_value'], 2)))
                users.append(user)

        # Create the expense
        expense = Expense()
        expense.setCost(str(total_amount))
        expense.setDescription(parsed_data['description'])
        expense.setUsers(users)
        
        # Debug information
        print("Creating expense with:")
        print(f"Cost: {str(total_amount)}")
        print(f"Description: {parsed_data['description']}")
        print(f"Split type: {parsed_data['split_type']}")
        print(f"Total users in split: {total_users}")
        print(f"Share per person: {total_amount / total_users}")
        print(f"Number of expense users: {len(users)}")
        for u in users:
            print(f"User {u.getId()}: Paid {u.getPaidShare()}, Owes {u.getOwedShare()}")
        
        created_expense, errors = splitwise.createExpense(expense)
        if errors:
            print("Splitwise API Errors:", str(errors))
            if hasattr(errors, 'getErrors'):
                error_list = errors.getErrors()
                if error_list:
                    for error in error_list:
                        if hasattr(error, 'getMessage'):
                            print(f"Detailed Error: {error.getMessage()}")
                        else:
                            print(f"Detailed Error: {str(error)}")
                else:
                    print("No detailed errors available")
            elif hasattr(errors, 'getMessage'):
                print(f"Error Message: {errors.getMessage()}")
            return None
        return created_expense
    except Exception as e:
        print(f"Error creating Splitwise expense: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print("Traceback:")
        traceback.print_exc()
        return None

def delete_expense(expense_id):
    """Delete a Splitwise expense by ID."""
    try:
        return splitwise.deleteExpense(expense_id)
    except Exception as e:
        print(f"Error deleting expense: {str(e)}")
        return None

def process_transaction(message):
    """Process a transaction message and return the created expense."""
    try:
        # Get current user and friends list from Splitwise
        current_user = splitwise.getCurrentUser()
        friends = splitwise.getFriends()
        
        # Prepare friends data for OpenAI
        friends_data = {
            'current_user': {
                'id': current_user.id,
                'name': f"{current_user.first_name} {current_user.last_name}"
            },
            'friends': [
                {
                    'id': friend.id,
                    'name': f"{friend.first_name} {friend.last_name}",
                    'email': friend.email
                }
                for friend in friends
            ]
        }
        
        # Parse transaction with OpenAI
        parsed_data = parse_transaction_with_openai(message, friends_data)
        if not parsed_data:
            return None
            
        # Create expense in Splitwise
        return create_splitwise_expense(parsed_data)
    except Exception as e:
        print(f"Error processing transaction: {str(e)}")
        return None

@app.route('/addtransaction', methods=['POST'])
def add_transaction():
    try:
        data = request.get_json()
        print("Parsed JSON data:", data)
        
        if not data or 'message' not in data:
            return jsonify({'error': 'No message provided'}), 400
            
        message = data['message']
        print("Extracted message:", message)
        
        expense = process_transaction(message)
        if not expense:
            return jsonify({'error': 'Failed to create expense'}), 400
            
        return jsonify({'success': True, 'expense_id': expense.id}), 200
        
    except Exception as e:
        print(f"Error in add_transaction: {str(e)}")
        return jsonify({'error': str(e)}), 400

@app.route('/deleteransaction', methods=['POST'])
def delete_transaction():
    try:
        data = request.get_json()
        print("Parsed JSON data:", data)
        
        if not data or 'expense_id' not in data:
            return jsonify({'error': 'No expense ID provided'}), 400
            
        expense_id = data['expense_id']
        print("Extracted expense ID:", expense_id)
        
        result = delete_expense(expense_id)
        if not result:
            return jsonify({'error': 'Failed to delete expense'}), 400
            
        return jsonify({'success': True}), 200
        
    except Exception as e:
        print(f"Error in delete_transaction: {str(e)}")
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True)
