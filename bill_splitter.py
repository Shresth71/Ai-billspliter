import os
import json
import datetime
from collections import defaultdict

class BillSplitter:
    def __init__(self, storage_file="expenses.json"):
        self.storage_file = storage_file
        self.expenses = []
        self.users = set()
        self.load_data()
    
    def load_data(self):
        """Load existing expense data if available"""
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r') as f:
                    data = json.load(f)
                    self.expenses = data.get('expenses', [])
                    self.users = set(data.get('users', []))
            except Exception as e:
                print(f"Error loading data: {e}")
                self.expenses = []
                self.users = set()
    
    def save_data(self):
        """Save expense data to file"""
        data = {
            'expenses': self.expenses,
            'users': list(self.users)
        }
        with open(self.storage_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def add_user(self, username):
        """Add a new user to the system"""
        if username in self.users:
            return f"User '{username}' already exists."
        
        self.users.add(username)
        self.save_data()
        return f"User '{username}' added successfully."
    
    def add_expense(self, paid_by, amount, description, participants=None, date=None):
        """Add a new expense to the system"""
        # Validate user
        if paid_by not in self.users:
            return f"Error: User '{paid_by}' does not exist."
        
        # Set default date to today if not provided
        if date is None:
            date = datetime.datetime.now().strftime("%Y-%m-%d")
            
        # Set default participants to all users if not provided
        if participants is None or len(participants) == 0:
            participants = list(self.users)
        else:
            # Validate all participants
            for participant in participants:
                if participant not in self.users:
                    return f"Error: Participant '{participant}' does not exist."
        
        # Create expense record
        expense = {
            'id': len(self.expenses) + 1,
            'paid_by': paid_by,
            'amount': float(amount),
            'description': description,
            'date': date,
            'participants': participants
        }
        
        self.expenses.append(expense)
        self.save_data()
        return f"Expense '{description}' ({amount}) added successfully."

    def categorize_expense(self, expense_id, category):
        """Categorize an expense"""
        for expense in self.expenses:
            if expense['id'] == expense_id:
                expense['category'] = category
                self.save_data()
                return f"Expense {expense_id} categorized as '{category}'."
        return f"Error: Expense {expense_id} not found."

    def get_expense_summary(self):
        """Get a summary of all expenses"""
        if not self.expenses:
            return "No expenses recorded yet."
        
        total_amount = sum(expense['amount'] for expense in self.expenses)
        categories = defaultdict(float)
        
        for expense in self.expenses:
            category = expense.get('category', 'Uncategorized')
            categories[category] += expense['amount']
        
        summary = f"Total expenses: ₹{total_amount:.2f}\n\n"
        summary += "Breakdown by category:\n"
        for category, amount in categories.items():
            summary += f"- {category}: ₹{amount:.2f} ({(amount/total_amount)*100:.1f}%)\n"
        
        return summary
    
    def calculate_balances(self):
        """Calculate who owes whom how much"""
        # Initialize balances dictionary
        balances = {user: 0 for user in self.users}
        
        # Calculate net balances
        for expense in self.expenses:
            payer = expense['paid_by']
            amount = expense['amount']
            participants = expense['participants']
            
            # Skip if no participants
            if not participants:
                continue
                
            # Calculate share per person
            share = amount / len(participants)
            
            # Add full amount to payer
            balances[payer] += amount
            
            # Subtract each participant's share
            for participant in participants:
                balances[participant] -= share
        
        # Convert balances to settlement transactions
        settlements = self._simplify_settlements(balances)
        
        return settlements
    
    def _simplify_settlements(self, balances):
        """Simplify the settlement transactions"""
        # Separate debtors and creditors
        debtors = [(user, balance) for user, balance in balances.items() if balance < 0]
        creditors = [(user, balance) for user, balance in balances.items() if balance > 0]
        
        # Sort by absolute amount (descending)
        debtors.sort(key=lambda x: x[1])
        creditors.sort(key=lambda x: x[1], reverse=True)
        
        settlements = []
        
        # Match debtors with creditors
        i, j = 0, 0
        while i < len(debtors) and j < len(creditors):
            debtor, debt = debtors[i]
            creditor, credit = creditors[j]
            
            # Determine the transaction amount
            amount = min(abs(debt), credit)
            
            if amount > 0.01:  # Ignore very small amounts
                settlements.append({
                    'from': debtor,
                    'to': creditor,
                    'amount': round(amount, 2)
                })
            
            # Update remaining balances
            debtors[i] = (debtor, debt + amount)
            creditors[j] = (creditor, credit - amount)
            
            # Move to next person if their balance is settled
            if abs(debtors[i][1]) < 0.01:
                i += 1
            if creditors[j][1] < 0.01:
                j += 1
        
        return settlements
    
    def get_user_expenses(self, username):
        """Get all expenses for a specific user"""
        if username not in self.users:
            return f"Error: User '{username}' does not exist."
        
        # Expenses paid by the user
        paid_expenses = [e for e in self.expenses if e['paid_by'] == username]
        
        # Expenses where the user is a participant
        participating_expenses = [e for e in self.expenses if username in e['participants']]
        
        # Calculate total paid and owed
        total_paid = sum(e['amount'] for e in paid_expenses)
        
        total_owed = 0
        for expense in participating_expenses:
            share = expense['amount'] / len(expense['participants'])
            total_owed += share
        
        # Calculate net balance
        net_balance = total_paid - total_owed
        
        return {
            'username': username,
            'total_paid': round(total_paid, 2),
            'total_owed': round(total_owed, 2),
            'net_balance': round(net_balance, 2),
            'paid_expenses': paid_expenses,
            'participating_expenses': participating_expenses
        }

# Sample CLI interface for the bill splitter
def run_cli():
    print("=== AI Automated Bill Splitter ===")
    bs = BillSplitter()
    
    while True:
        print("\nOptions:")
        print("1. Add User")
        print("2. Add Expense")
        print("3. View Expense Summary")
        print("4. Calculate Settlements")
        print("5. View User Expenses")
        print("6. Categorize Expense")
        print("7. Exit")
        
        choice = input("Enter your choice (1-7): ")
        
        if choice == '1':
            username = input("Enter username: ")
            print(bs.add_user(username))
            
        elif choice == '2':
            if not bs.users:
                print("No users added yet. Please add users first.")
                continue
                
            paid_by = input("Paid by (username): ")
            if paid_by not in bs.users:
                print(f"User '{paid_by}' does not exist.")
                continue
                
            amount = input("Amount: ₹")
            try:
                amount = float(amount)
            except ValueError:
                print("Invalid amount. Please enter a number.")
                continue
                
            description = input("Description: ")
            
            participant_input = input("Participants (comma-separated, leave blank for all): ")
            if participant_input.strip():
                participants = [p.strip() for p in participant_input.split(',')]
            else:
                participants = list(bs.users)
                
            print(bs.add_expense(paid_by, amount, description, participants))
            
        elif choice == '3':
            print(bs.get_expense_summary())
            
        elif choice == '4':
            settlements = bs.calculate_balances()
            if not settlements:
                print("No settlements needed. Everyone is even.")
            else:
                print("\nSettlements:")
                for s in settlements:
                    print(f"{s['from']} pays ₹{s['amount']:.2f} to {s['to']}")
                    
        elif choice == '5':
            if not bs.users:
                print("No users added yet.")
                continue
                
            username = input("Enter username: ")
            result = bs.get_user_expenses(username)
            
            if isinstance(result, str):
                print(result)
            else:
                print(f"\nExpense summary for {result['username']}:")
                print(f"Total paid: ₹{result['total_paid']:.2f}")
                print(f"Total owed: ₹{result['total_owed']:.2f}")
                print(f"Net balance: ₹{result['net_balance']:.2f}")
                
                if result['net_balance'] > 0:
                    print(f"{result['username']} is owed ₹{result['net_balance']:.2f}")
                elif result['net_balance'] < 0:
                    print(f"{result['username']} owes ₹{abs(result['net_balance']):.2f}")
                else:
                    print(f"{result['username']} is even")
        
        elif choice == '6':
            if not bs.expenses:
                print("No expenses added yet.")
                continue
            
            # Display available expenses
            print("\nAvailable expenses:")
            for expense in bs.expenses:
                print(f"{expense['id']}: {expense['description']} - ₹{expense['amount']}")
            
            expense_id = input("Enter expense ID to categorize: ")
            try:
                expense_id = int(expense_id)
            except ValueError:
                print("Invalid ID. Please enter a number.")
                continue
            
            category = input("Enter category (e.g., Food, Rent, Utilities): ")
            print(bs.categorize_expense(expense_id, category))
                
        elif choice == '7':
            print("Thank you for using AI Automated Bill Splitter!")
            break
            
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    run_cli()