import cv2
import pytesseract
from PIL import Image
import re

# Set the path to your installed Tesseract executable
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def extract_expense_data_from_image(image_path):
    # Step 1: Read and preprocess image
    image = cv2.imread(image_path)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
    processed = cv2.bitwise_not(thresh)

    # Step 2: OCR
    temp_path = "temp_processed.png"
    cv2.imwrite(temp_path, processed)
    text = pytesseract.image_to_string(Image.open(temp_path))

    # Step 3: Parse into structured format
    return parse_expense_items(text)

def parse_expense_items(text):
    items = []
    lines = text.split('\n')

    # Sample category mapping (you can expand this)
    category_map = {
        'coffee': 'Beverages',
        'tea': 'Beverages',
        'mocha': 'Beverages',
        'cheesecake': 'Dessert',
        'cake': 'Dessert',
        'banana': 'Food',
        'choco': 'Dessert',
    }

    for line in lines:
        match = re.search(r'(.+?)\s+([\d]+\.\d{2})$', line)
        if match:
            item_name = match.group(1).strip()
            amount = float(match.group(2))

            # Infer category
            category = 'Uncategorized'
            for keyword in category_map:
                if keyword.lower() in item_name.lower():
                    category = category_map[keyword]
                    break

            items.append({
                'description': item_name,
                'amount': amount,
                'paid_by': 'Unknown',
                'participants': ['Unknown'],
                'category': category
            })

    return items

def add_expense_from_image():
    image_path = input("Enter the path to the receipt image: ")
    try:
        expense = extract_expense_data_from_image(image_path)
        print("\nExtracted expense:")
        for k, v in expense.items():
            print(f"{k}: {v}")
        # Integrate with your bill splitting logic here
    except Exception as e:
        print("Failed to process image:", e)
