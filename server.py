import os
import json
from flask import Flask, request, jsonify
from openai import OpenAI
from splitwise import Splitwise
from splitwise.expense import Expense
from splitwise.user import ExpenseUser
from dotenv import load_dotenv

load_dotenv()  # Load environment variables

app = Flask(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Initialize Splitwise client
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
            model="gpt-4o",
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
        
        # For equal splits, make sure payer is included in split_with if not already there
        if parsed_data['split_type'] == 'equal':
            # Get all unique user IDs
            user_ids = {user['user_id'] for user in parsed_data['split_with']}
            
            # Add payer if not in split_with
            if parsed_data['paid_by']['user_id'] not in user_ids:
                parsed_data['split_with'].append(parsed_data['paid_by'])
        
        # Calculate shares based on split type
        if parsed_data['split_type'] == 'equal':
            total_users = len(parsed_data['split_with'])  # Total number of users in the split
            share_per_person = total_amount / total_users
            
            # Add the person who paid
            payer = ExpenseUser()
            payer.setId(parsed_data['paid_by']['user_id'])
            payer.setPaidShare(str(total_amount))
            payer.setOwedShare(str(share_per_person))
            users.append(payer)
            
            # Add all other users
            for user_data in parsed_data['split_with']:
                if user_data['user_id'] != parsed_data['paid_by']['user_id']:
                    user = ExpenseUser()
                    user.setId(user_data['user_id'])
                    user.setPaidShare('0.00')
                    user.setOwedShare(str(share_per_person))
                    users.append(user)
        
        elif parsed_data['split_type'] == 'percentage':
            # Add the person who paid
            payer = ExpenseUser()
            payer.setId(parsed_data['paid_by']['user_id'])
            payer.setPaidShare(str(total_amount))
            payer_split = next((u['split_value'] for u in parsed_data['split_with'] 
                              if u['user_id'] == parsed_data['paid_by']['user_id']), None)
            if payer_split is None:
                payer_split = 100 - sum(u['split_value'] for u in parsed_data['split_with'])
            payer.setOwedShare(str((payer_split / 100.0) * total_amount))
            users.append(payer)
            
            # Add all other users
            for user_data in parsed_data['split_with']:
                if user_data['user_id'] != parsed_data['paid_by']['user_id']:
                    user = ExpenseUser()
                    user.setId(user_data['user_id'])
                    user.setPaidShare('0.00')
                    user.setOwedShare(str((user_data['split_value'] / 100.0) * total_amount))
                    users.append(user)
        
        else:  # exact amounts
            # Add the person who paid
            payer = ExpenseUser()
            payer.setId(parsed_data['paid_by']['user_id'])
            payer.setPaidShare(str(total_amount))
            payer_split = next((u['split_value'] for u in parsed_data['split_with'] 
                              if u['user_id'] == parsed_data['paid_by']['user_id']), None)
            if payer_split is None:
                payer_split = total_amount - sum(u['split_value'] for u in parsed_data['split_with'])
            payer.setOwedShare(str(payer_split))
            users.append(payer)
            
            # Add all other users
            for user_data in parsed_data['split_with']:
                if user_data['user_id'] != parsed_data['paid_by']['user_id']:
                    user = ExpenseUser()
                    user.setId(user_data['user_id'])
                    user.setPaidShare('0.00')
                    user.setOwedShare(str(user_data['split_value']))
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
        print(f"Total users in split: {len(parsed_data['split_with'])}")
        print(f"Share per person: {total_amount / len(parsed_data['split_with'])}")
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
                        print(f"Detailed Error: {error}")
                else:
                    print("No detailed errors available")
            return None
        return created_expense
    except Exception as e:
        print(f"Error creating Splitwise expense: {str(e)}")
        print(f"Error type: {type(e)}")
        return None

@app.route('/addtransaction', methods=['POST'])
def add_transaction():
    print("Raw request data:", request.get_data())
    print("Request headers:", dict(request.headers))
    transaction_data = request.json
    print("Parsed JSON data:", transaction_data)
    transaction_text = transaction_data.get('message')
    print("Extracted message:", transaction_text)
    
    if not transaction_text:
        print("Transaction text is empty or None")
        return jsonify({"status": "error", "message": "No transaction text provided"}), 400
    
    try:
        # Get friends data for context
        friends_data = get_friends_data()
        
        # Parse the transaction text using OpenAI with friends context
        parsed_data = parse_transaction_with_openai(transaction_text, friends_data)
        if not parsed_data:
            return jsonify({"status": "error", "message": "Failed to parse transaction"}), 400
        
        # Create the expense in Splitwise
        expense = create_splitwise_expense(parsed_data)
        if not expense:
            return jsonify({"status": "error", "message": "Failed to create Splitwise expense"}), 400
        
        return jsonify({
            "status": "success",
            "message": "Transaction added to Splitwise",
            "expense_id": expense.id,
            "parsed_data": parsed_data  # Include parsed data for verification
        }), 200
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error processing transaction: {str(e)}"
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
