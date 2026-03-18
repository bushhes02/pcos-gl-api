from flask import Flask, request, jsonify
from flask_cors import CORS
import csv

# Create Flask app
app = Flask(__name__)
CORS(app)

# Load databases from CSV
food_macros = {}
food_gl = {}
food_swaps_raw = []

# Load food macros
with open('food_macros.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        food_macros[row['food_name'].lower()] = row

# Load GL values
with open('food_gl_values.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        food_gl[row['food_name'].lower()] = row

# Load swaps
with open('food_swaps.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        food_swaps_raw.append(row)

# GL calculation function (FIXED: Added minimum cap)
def calculate_gl(carbs, protein, fat, fiber):
    GL = 19.27 + (0.39 * carbs) - (0.21 * fat) - (0.01 * protein**2) - (0.01 * fiber**2)
    return max(0, round(GL, 1))  # Never return negative GL

# Search food function
def search_food(food_name, amount_grams):
    food_lower = food_name.lower().strip()
    
    if food_lower not in food_macros:
        return None
    
    per_100g = food_macros[food_lower]
    multiplier = amount_grams / 100
    
    return {
        'name': str(per_100g['food_name']),
        'amount_g': float(amount_grams),
        'carbs': float(per_100g['carbs_per_100g']) * multiplier,
        'protein': float(per_100g['protein_per_100g']) * multiplier,
        'fat': float(per_100g['fat_per_100g']) * multiplier,
        'fiber': float(per_100g['fiber_per_100g']) * multiplier
    }

# Find alternatives function
def find_alternatives(food_name):
    food_lower = food_name.lower().strip()
    
    # Find swaps for this food
    swaps = [s for s in food_swaps_raw if s['original_food'].lower() == food_lower]
    
    if not swaps:
        return []
    
    # Get original food GL
    if food_lower not in food_gl:
        return []
    
    original_gl = float(food_gl[food_lower]['sydney_gl'])
    
    alternatives = []
    for swap in swaps:
        alt_name = swap['alternative_food'].lower()
        
        if alt_name in food_gl:
            alt_gl = float(food_gl[alt_name]['sydney_gl'])
            improvement = round(((original_gl - alt_gl) / original_gl) * 100, 1)
            
            alternatives.append({
                'name': str(swap['alternative_food']),
                'sydney_gl': float(alt_gl),
                'improvement_percent': float(improvement)
            })
    
    return sorted(alternatives, key=lambda x: x['sydney_gl'])

# API endpoint
@app.route('/analyze-meal', methods=['POST'])
def analyze_meal_api():
    try:
        data = request.json
        meal_items = data.get('meal_items', [])
        
        foods_in_meal = []
        total_carbs = 0
        total_protein = 0
        total_fat = 0
        total_fiber = 0
        
        for item in meal_items:
            food_name = item.get('food_name')
            grams = item.get('grams')
            
            food_data = search_food(food_name, grams)
            
            if food_data:
                foods_in_meal.append(food_data)
                total_carbs += food_data['carbs']
                total_protein += food_data['protein']
                total_fat += food_data['fat']
                total_fiber += food_data['fiber']
        
        # Calculate GL
        meal_gl = calculate_gl(total_carbs, total_protein, total_fat, total_fiber)
        
        # Check for extreme macros (NEW: Warning system)
        warning = None
        if total_protein > 80:
            warning = "⚠️ High-protein meal (>80g). GL estimate may be less accurate."
        
        # Determine risk level
        if meal_gl < 10:
            risk = "Low"
            message = "Excellent for PCOS!"
        elif meal_gl < 20:
            risk = "Medium"
            message = "Acceptable"
        else:
            risk = "High"
            message = "May spike insulin"
        
        # Find suggestions
        suggestions = []
        for food in foods_in_meal:
            food_gl_val = calculate_gl(food['carbs'], food['protein'], food['fat'], food['fiber'])
            
            if food_gl_val > 10:
                alternatives = find_alternatives(food['name'])
                
                if alternatives:
                    suggestions.append({
                        'original_food': food['name'],
                        'alternatives': alternatives[:3]
                    })
        
        response = {
            'success': True,
            'meal_gl': float(meal_gl),
            'risk_level': risk,
            'message': message,
            'total_macros': {
                'carbs': float(round(total_carbs, 1)),
                'protein': float(round(total_protein, 1)),
                'fat': float(round(total_fat, 1)),
                'fiber': float(round(total_fiber, 1))
            },
            'foods': foods_in_meal,
            'suggestions': suggestions
        }
        
        # Add warning if present
        if warning:
            response['warning'] = warning
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
