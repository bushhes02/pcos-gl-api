from flask import Flask, request, jsonify
from flask_cors import CORS
import csv

# Create Flask app
app = Flask(__name__)
CORS(app)

# Load databases from CSV
def load_csv(filename):
    data = {}
    with open(filename, 'r') as f:
        reader = csv.DictReader(f) 
        for row in reader:
            data[row['food_name'].lower()] = row
    return data

food_macros = load_csv('food_macros.csv')
food_gl = load_csv('food_gl_values.csv')
food_swaps_raw = []
with open('food_swaps.csv', 'r') as f:
    reader = csv.DictReader(f) 
    for row in reader:
        food_swaps_raw.append(row)

# GL calculation function
def calculate_gl(carbs, protein, fat, fiber):
    GL = 19.27 + (0.39 * carbs) - (0.21 * fat) - (0.01 * protein**2) - (0.01 * fiber**2)
    return round(GL, 1)

# Search food function
def search_food(food_name, amount_grams):
    food_lower = food_name.lower().strip()
    match = food_macros[food_macros['food_name'].str.lower() == food_lower]
    
    if match.empty:
        return None
    
    per_100g = match.iloc[0]
    multiplier = amount_grams / 100
    
    return {
        'name': str(per_100g['food_name']),
        'amount_g': float(amount_grams),
        'carbs': float(round(per_100g['carbs_per_100g'] * multiplier, 1)),
        'protein': float(round(per_100g['protein_per_100g'] * multiplier, 1)),
        'fat': float(round(per_100g['fat_per_100g'] * multiplier, 1)),
        'fiber': float(round(per_100g['fiber_per_100g'] * multiplier, 1))
    }

# Find alternatives function
def find_alternatives(food_name):
    food_lower = food_name.lower().strip()
    swaps = food_swaps[food_swaps['original_food'].str.lower() == food_lower]
    
    if swaps.empty:
        return []
    
    original_gl_row = food_gl[food_gl['food_name'].str.lower() == food_lower]
    if original_gl_row.empty:
        return []
    
    original_gl = float(original_gl_row.iloc[0]['sydney_gl'])
    
    alternatives = []
    for _, swap in swaps.iterrows():
        alt_name = swap['alternative_food']
        alt_gl_row = food_gl[food_gl['food_name'].str.lower() == alt_name.lower()]
        
        if not alt_gl_row.empty:
            alt_gl = float(alt_gl_row.iloc[0]['sydney_gl'])
            improvement = round(((original_gl - alt_gl) / original_gl) * 100, 1)
            
            alternatives.append({
                'name': str(alt_name),
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
        
        meal_gl = calculate_gl(total_carbs, total_protein, total_fat, total_fiber)
        
        if meal_gl < 15:
            risk = "Low"
            message = "Excellent for PCOS!"
        elif meal_gl < 20:
            risk = "Medium"
            message = "Acceptable"
        else:
            risk = "High"
            message = "May spike insulin"
        
        suggestions = []
        for food in foods_in_meal:
            food_gl = calculate_gl(food['carbs'], food['protein'], food['fat'], food['fiber'])
            
            if food_gl > 10:
                alternatives = find_alternatives(food['name'])
                
                if alternatives:
                    suggestions.append({
                        'original_food': food['name'],
                        'alternatives': alternatives[:3]
                    })
        
        return jsonify({
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
        })
        
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
