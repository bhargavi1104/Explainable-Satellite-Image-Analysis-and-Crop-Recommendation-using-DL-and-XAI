from flask import Flask,render_template,redirect,request,url_for, send_file,session, Response, jsonify
from fpdf import FPDF
import io
import mysql.connector, os
import pandas as pd
import numpy as np
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image
from ultralytics import YOLO
import cv2
import datetime  # Added import for datetime
import random
import json
from translations import TRANSLATIONS
import datetime

# --- MAPPING FOR CLEAN TRANSLATION KEYS ---
internal_mapping = {
    "water": "water", "river": "water", "lake": "water", "pond": "water",
    "agriculture": "agriculture", "farmland": "agriculture", "crop": "agriculture", "field": "agriculture",
    "urban": "urban", "building": "urban", "residential": "urban", "structure": "urban",
    "forest": "forest", "tree": "forest", "green": "forest",
    "dry": "dry", "arid": "dry", "barren": "dry",
    "paddy": "paddy", "rice": "paddy", "sugarcane": "sugarcane", "wheat": "wheat",
    "maize": "maize", "sorghum": "sorghum", "cotton": "cotton", "soybean": "soybean",
    "mustard": "mustard", "millet": "pearl_millet", "pearl millet": "pearl_millet"
}

# --- EXPANDED AGRI KNOWLEDGE FOR BOT ---
AGRI_KNOWLEDGE = {
    "paddy": {
        "duration": "120 to 150 days",
        "water": "High (1200-2500mm). Needs standing water.",
        "pesticides": "Stem borer and Rice Blast protection.",
        "usage": "Global staple food, rice bran oil, and industrial starch.",
        "priority_note": "A staple crop perfect for detected agriculture-lands with water access."
    },
    "sugarcane": {
        "duration": "12 to 18 months",
        "water": "Very High (1500-3000mm).",
        "pesticides": "Chlorpyriphos for termites.",
        "usage": "Sugar production, ethanol biofuel, and paper pulp (bagasse).",
        "priority_note": "Long-term high-return crop for stable water zones."
    },
    "wheat": {
        "duration": "120 to 150 days",
        "water": "Moderate (450-650mm). Critical at flowering.",
        "pesticides": "Sulfur-based fungicides for rust.",
        "usage": "Flour for bread/rotis, pasta, and animal feed.",
        "priority_note": "Primary Rabi season crop for detected agriculture fields."
    },
    "maize": {
        "duration": "90 to 110 days",
        "water": "Moderate (500-800mm). Avoid waterlogging.",
        "pesticides": "Stem borer and Fall Armyworm control.",
        "usage": "Corn flour, poultry feed, and industrial corn syrup.",
        "priority_note": "Strong Kharif priority due to high adaptability and biomass."
    },
    "cotton": {
        "duration": "160 to 180 days",
        "water": "Moderate (700-1300mm).",
        "pesticides": "IPM for bollworms.",
        "usage": "Textile industry, cottonseeds for oil, and cattle cake.",
        "priority_note": "Classic choice for areas with reliable drainage and sun."
    },
    "soybean": {
        "duration": "90 to 110 days",
        "water": "Moderate (450-700mm).",
        "pesticides": "Girdle beetle and pod borer protection.",
        "usage": "Soybean oil, high-protein soy chunks, and tofu.",
        "priority_note": "Best for improving soil nitrogen via rotation."
    },
    "mustard": {
        "duration": "105 to 130 days",
        "water": "Low to Moderate. Resilient.",
        "pesticides": "Aphid management in winter.",
        "usage": "Cooking oil, condiments, and organic fertilizer.",
        "priority_note": "High-margin oilseed alternate for dry agriculture zones."
    },
    "pearl_millet": {
        "duration": "75 to 90 days",
        "water": "Low (400-600mm). Drought tolerant.",
        "pesticides": "Downy mildew protection.",
        "usage": "Nutritious gluten-free grain, fodder, and birdseed.",
        "priority_note": "Drought-resilient priority for detected Dry lands."
    }
}

app = Flask(__name__)
app.secret_key = 'admin'

mydb = mysql.connector.connect(
    host="127.0.0.1",
    user="root",
    password="Bharu@123",
    port="3306",
    database='satilite'
)

mycursor = mydb.cursor()

def executionquery(query,values):
    mycursor.execute(query,values)
    mydb.commit()
    return

def retrivequery1(query,values):
    mycursor.execute(query,values)
    data = mycursor.fetchall()
    return data

def retrivequery2(query):
    mycursor.execute(query)
    data = mycursor.fetchall()
    return data

@app.context_processor
def inject_translate():
    lang = session.get('lang', 'en')
    def translate(key, default=None):
        # If key not found in chosen lang, try default, else fallback to key itself
        val = TRANSLATIONS.get(lang, TRANSLATIONS['en']).get(key)
        if val: return val
        return default if default is not None else key
    return dict(_t=translate, current_lang=lang)

@app.route('/set_language/<lang>')
def set_language(lang):
    if lang in TRANSLATIONS:
        session['lang'] = lang
    return redirect(request.referrer or url_for('index'))


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():

    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']

        if username == "admin" and password == "admin":
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            return render_template('admin_login.html',
                                   error="Invalid Admin Credentials")

    return render_template('admin_login.html')

@app.route('/admin_dashboard')
def admin_dashboard():

    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    users = retrivequery2("SELECT name, email, phone FROM users")

    predictions = retrivequery2("""
        SELECT user_email, image_name, predicted_image, 
               detected_classes, recommended_crop, created_at
        FROM predictions ORDER BY created_at DESC
    """)

    # --- ANALYTICS DATA GENERATION ---
    class_stats = {}
    recommend_stats = {}
    
    for row in predictions:
        # Aggregate Land Features (classes)
        try:
            detected = json.loads(row[3]) if row[3] else {}
            for cls_name, count in detected.items():
                class_stats[cls_name] = class_stats.get(cls_name, 0) + count
        except:
            pass
            
        # Aggregate Crop Recommendations
        try:
            crops = json.loads(row[4]) if row[4] else []
            for crop in crops:
                recommend_stats[crop] = recommend_stats.get(crop, 0) + 1
        except:
            pass

    # Sort stats for better visualization (top 10)
    sorted_class_stats = dict(sorted(class_stats.items(), key=lambda item: item[1], reverse=True)[:10])
    sorted_recommend_stats = dict(sorted(recommend_stats.items(), key=lambda item: item[1], reverse=True)[:10])

    return render_template(
        'admin_dashboard.html',
        users=users,
        predictions=predictions,
        class_stats=json.dumps(sorted_class_stats),
        recommend_stats=json.dumps(sorted_recommend_stats),
        total_users=len(users),
        total_predictions=len(predictions)
    )

@app.route('/admin_user/<email>')
def admin_user_predictions(email):

    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    user = retrivequery1(
        "SELECT name, email, phone FROM users WHERE email=%s",
        (email,)
    )

    predictions = retrivequery1(
        """
        SELECT original_image,
               predicted_image,
               detected_classes,
               recommended_crop,
               created_at
        FROM predictions
        WHERE user_email=%s
        ORDER BY created_at DESC
        """,
        (email,)
    )

    return render_template(
        'admin_user_predictions.html',
        user=user[0],
        predictions=predictions
    )

@app.route('/logout')
def logout():
    session.pop('name', None)
    return redirect(url_for('index'))

@app.route('/admin_logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('admin_login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Capture language from form if present, else use session
        form_lang = request.form.get('lang')
        if form_lang in TRANSLATIONS:
            session['lang'] = form_lang

        name = request.form['name']
        phone = request.form['phone']
        email = request.form['email']
        password = request.form['password']
        c_password = request.form['c_password']
        
        # Check if passwords match
        if password != c_password:
            return render_template('register.html', message="Confirm password does not match!")
        
        # Retrieve existing emails
        query = "SELECT email FROM users"
        email_data = retrivequery2(query)
        
        # Create a list of existing emails
        email_data_list = [i[0] for i in email_data]
        
        # Check if the email already exists
        if email in email_data_list:
            return render_template('register.html', message="Email already exists!")

        # Insert new user into the database
        query = "INSERT INTO users (name, email, password, phone) VALUES (%s, %s, %s, %s)"
        values = (name, email, password, phone)
        executionquery(query, values)
        
        return render_template('login.html', message="Successfully Registered!")
    
    return render_template('register.html')
    



@app.route('/login', methods=["GET", "POST"])
def login():

    if request.method == "POST":
        # Capture language from login form
        form_lang = request.form.get('lang')
        if form_lang in TRANSLATIONS:
            session['lang'] = form_lang

        email = request.form['email']
        password = request.form['password']

        query = "SELECT name, password FROM users WHERE email = %s"
        values = (email,)
        data = retrivequery1(query, values)

        if data:
            if password == data[0][1]:

                # ✅ STORE CORRECT SESSION VALUES
                session['user_email'] = email
                session['user_name'] = data[0][0]

                return redirect(url_for('home'))
            else:
                return render_template('login.html',
                                       message="Invalid Password")
        else:
            return render_template('login.html',
                                   message="Email does not exist")

    return render_template('login.html')

@app.route('/home')
def home():
    return render_template('home.html')


# Define the path where the uploaded images and predicted images will be saved
SAVED_IMAGES_FOLDER = os.path.join('static', 'saved_images')
PREDICTION_FOLDER = os.path.join('static', 'predicted_images')

# Create directories if they don't exist
os.makedirs(SAVED_IMAGES_FOLDER, exist_ok=True)
os.makedirs(PREDICTION_FOLDER, exist_ok=True)

# COMPREHENSIVE RECOMMENDATION RULES UPDATED
RECOMMENDATION_RULES = {
    # Water-related classes
    "water": {
        "recommend": "Paddy (Rice)",
        "explanation": "Rice requires standing water for optimal growth. This area is perfect for paddy cultivation with proper water management."
    },
    "water_body": {
        "recommend": "Rice or Aquaculture",
        "explanation": "Water bodies support rice cultivation or can be used for fish farming and aquatic vegetables."
    },
    "river": {
        "recommend": "Rice or Sugarcane",
        "explanation": "River banks are ideal for water-intensive crops like rice or sugarcane with proper irrigation channels."
    },
    "pond": {
        "recommend": "Rice or Fish Farming",
        "explanation": "Ponds can support paddy cultivation or be used for integrated fish farming systems."
    },
    "lake": {
        "recommend": "Rice cultivation",
        "explanation": "Lake areas provide consistent water source for rice farming throughout the growing season."
    },
    
    # Agricultural fields
    "wheat": {
        "recommend": "Wheat or Barley",
        "explanation": "Wheat-friendly conditions detected. Consider wheat cultivation with proper crop rotation for soil health."
    },
    "wheat_field": {
        "recommend": "Wheat",
        "explanation": "Detected wheat field indicates suitable soil conditions for continued wheat cultivation."
    },
    "maize": {
        "recommend": "Maize or Soybean",
        "explanation": "Maize fields indicate suitable soil. Continue maize or rotate with soybeans to improve nitrogen levels."
    },
    "maize_field": {
        "recommend": "Maize",
        "explanation": "Maize field detected. Ideal for maize cultivation with proper nutrient management."
    },
    "rice": {
        "recommend": "Rice or Wheat Rotation",
        "explanation": "Rice fields are well-suited for continued rice cultivation or wheat in rabi season."
    },
    "rice_field": {
        "recommend": "Rice",
        "explanation": "Rice field detected. Continue rice cultivation with proper water management."
    },
    "farmland": {
        "recommend": "Multiple Crops (Rice/Wheat/Pulses)",
        "explanation": "General farmland suitable for various crops based on season and soil conditions."
    },
    "agricultural": {
        "recommend": "Seasonal Crops",
        "explanation": "Agricultural land detected. Choose crops based on season: Kharif (June-Sept) or Rabi (Oct-Mar)."
    },
    "field": {
        "recommend": "Cereals (Wheat/Rice/Maize)",
        "explanation": "Open field suitable for cereal cultivation based on soil and water availability."
    },
    "crop": {
        "recommend": "Continue Current Crop with Rotation",
        "explanation": "Existing crops detected. Consider crop rotation to maintain soil health."
    },
    "farm": {
        "recommend": "Integrated Farming System",
        "explanation": "Farm area suitable for integrated crop-livestock farming system."
    },
    
    # Forest and vegetation
    "forest": {
        "recommend": "Agroforestry or Medicinal Plants",
        "explanation": "Forest areas support agroforestry systems. Consider shade-tolerant crops or medicinal plants."
    },
    "tree": {
        "recommend": "Fruit Trees or Agroforestry",
        "explanation": "Tree-covered areas suitable for fruit orchards or integrated agroforestry systems."
    },
    "vegetation": {
        "recommend": "Mixed Cropping System",
        "explanation": "Vegetated area suitable for mixed cropping with legumes and cereals."
    },
    "jungle": {
        "recommend": "Conservation Area",
        "explanation": "Dense jungle detected. Preserve biodiversity; consider sustainable non-timber forest products."
    },
    "green": {
        "recommend": "Vegetables or Pulses",
        "explanation": "Green area detected, suitable for vegetable cultivation or pulse crops."
    },
    
    # Dry and arid areas
    "dry": {
        "recommend": "Millets (Bajra/Jowar) or Pulses",
        "explanation": "Dry land conditions ideal for drought-resistant crops like millets or pulses."
    },
    "dry_land": {
        "recommend": "Drought-resistant Crops",
        "explanation": "Dry land requires crops like pearl millet, chickpea, or sorghum that need minimal water."
    },
    "arid": {
        "recommend": "Drought-resistant Millets",
        "explanation": "Arid land detected. Suitable for drought-resistant millets like pearl millet or finger millet."
    },
    "barren": {
        "recommend": "Soil Improvement First",
        "explanation": "Barren land needs soil improvement before cultivation. Consider green manure crops first."
    },
    
    # Built environment
    "building": {
        "recommend": "Kitchen Garden or Rooftop Farming",
        "explanation": "Building areas can support small-scale kitchen gardens or rooftop vegetable cultivation."
    },
    "house": {
        "recommend": "Home Gardening",
        "explanation": "Residential areas suitable for home gardens with vegetables and herbs."
    },
    "road": {
        "recommend": "Roadside Plantation",
        "explanation": "Road edges can support ornamental plants or fruit trees for urban greening."
    },
    "structure": {
        "recommend": "Container Gardening",
        "explanation": "Structures detected. Suitable for container gardening with vegetables or ornamental plants."
    },
    
    # Specialty crops
    "orchard": {
        "recommend": "Fruit Trees with Intercrops",
        "explanation": "Orchard areas can be optimized with fruit trees and suitable intercrops like vegetables."
    },
    "plantation": {
        "recommend": "Cash Crops (Tea/Coffee/Rubber)",
        "explanation": "Plantation areas suitable for perennial cash crops based on regional suitability."
    },
    "greenhouse": {
        "recommend": "High-value Vegetables/Flowers",
        "explanation": "Greenhouse structures ideal for controlled environment cultivation of high-value crops."
    },
    
    # Soil and terrain types
    "soil": {
        "recommend": "Soil Testing Recommended",
        "explanation": "Soil area detected. Conduct soil testing to determine specific crop suitability."
    },
    "clay": {
        "recommend": "Rice or Wheat",
        "explanation": "Clay soil retains moisture well, suitable for water-intensive crops like rice."
    },
    "sand": {
        "recommend": "Groundnut or Watermelon",
        "explanation": "Sandy soil drains quickly, ideal for crops like groundnut, watermelon, or potatoes."
    },
    "loam": {
        "recommend": "Most Crops (Versatile Soil)",
        "explanation": "Loamy soil is ideal for most crops including vegetables, cereals, and pulses."
    },
    "hill": {
        "recommend": "Terrace Farming or Horticulture",
        "explanation": "Hilly terrain suitable for terrace farming with crops like tea, coffee, or fruits."
    },
    "mountain": {
        "recommend": "Horticulture or Forestry",
        "explanation": "Mountainous area suitable for horticulture crops or sustainable forestry."
    },
    
    # Seasonal recommendations
    "kharif": {
        "recommend": "Rice, Maize, Cotton, Soybean",
        "explanation": "Kharif season (June-September) crops that require more water and warm conditions."
    },
    "rabi": {
        "recommend": "Wheat, Barley, Mustard, Chickpea",
        "explanation": "Rabi season (October-March) crops that require cooler temperatures."
    },
    
    # Default and common classes
    "land": {
        "recommend": "Soil Testing Recommended",
        "explanation": "General land area detected. Conduct soil testing for specific crop recommendations."
    },
    "area": {
        "recommend": "Consult Agricultural Expert",
        "explanation": "General area detected. Specific recommendations require detailed soil and climate analysis."
    },
    "region": {
        "recommend": "Local Adapted Crops",
        "explanation": "Regional analysis needed. Consult local agricultural department for best crops."
    }
}

# Function to get recommendation with smart matching
def get_recommendation_for_class(class_name):
    """
    Get recommendation for a detected class, with fallback for partial matches
    Returns: dict with 'recommend' and 'explanation' keys
    """
    # Clean and normalize class name
    class_name_lower = class_name.lower().strip()
    
    # 1. Try exact match first
    if class_name_lower in RECOMMENDATION_RULES:
        return RECOMMENDATION_RULES[class_name_lower]
    
    # 2. Try if any key is contained in class name
    for key in RECOMMENDATION_RULES:
        if key in class_name_lower:
            return RECOMMENDATION_RULES[key]
    
    # 3. Try if class name is contained in any key
    for key in RECOMMENDATION_RULES:
        if class_name_lower in key:
            return RECOMMENDATION_RULES[key]
    
    # 4. Check for common patterns
    water_keywords = ['water', 'river', 'pond', 'lake', 'stream', 'canal']
    field_keywords = ['field', 'farm', 'agricultural', 'crop', 'cultivation']
    forest_keywords = ['forest', 'tree', 'jungle', 'wood', 'grove']
    dry_keywords = ['dry', 'arid', 'barren', 'desert', 'drought']
    building_keywords = ['building', 'house', 'structure', 'road', 'urban']
    
    if any(keyword in class_name_lower for keyword in water_keywords):
        return RECOMMENDATION_RULES["water"]
    elif any(keyword in class_name_lower for keyword in field_keywords):
        return RECOMMENDATION_RULES["field"]
    elif any(keyword in class_name_lower for keyword in forest_keywords):
        return RECOMMENDATION_RULES["forest"]
    elif any(keyword in class_name_lower for keyword in dry_keywords):
        return RECOMMENDATION_RULES["dry"]
    elif any(keyword in class_name_lower for keyword in building_keywords):
        return RECOMMENDATION_RULES["building"]
    
    # 5. Default fallback with class-specific message
    return {
        "recommend": "Soil Testing & Expert Consultation Required",
        "explanation": f"'{class_name}' detected. This land type requires detailed soil analysis and climate assessment. Please consult with an agricultural expert for site-specific recommendations."
    }

# Function to get current season for smart recommendations
def get_current_season():
    month = datetime.datetime.now().month

    season_map = {
        6: "Kharif", 7: "Kharif", 8: "Kharif", 9: "Kharif",
        10: "Rabi", 11: "Rabi", 12: "Rabi", 1: "Rabi",
        2: "Zaid", 3: "Zaid", 4: "Zaid", 5: "Zaid"
    }

    return season_map.get(month, "Unknown")
# Load model once at startup (IMPORTANT for performance)
yolo_model = YOLO('best.pt')

@app.route('/prediction', methods=['GET', 'POST'])
def prediction():

    if request.method == 'POST':
        # Capture language from form if present
        form_lang = request.form.get('lang')
        if form_lang in TRANSLATIONS:
            session['lang'] = form_lang

        # 1️⃣ File existence check
        if 'file' not in request.files:
            return render_template(
                'prediction.html',
                error="⚠️ This is not a satellite image.",
                file_name=None
            )

        myfile = request.files['file']
        filename = myfile.filename

        # 2️⃣ Strict .jpg check
        if not filename.lower().endswith('.jpg'):
            return render_template(
                'prediction.html',
                error="Invalid image. Only satellite images are allowed for upload.",
                file_name=None
            )

        # 3️⃣ Save temporarily
        save_path = os.path.join(SAVED_IMAGES_FOLDER, filename)
        myfile.save(save_path)

        # 4️⃣ Validate actual image
        img = cv2.imread(save_path)
        if img is None:
            os.remove(save_path)
            return render_template(
                'prediction.html',
                error="⚠️ Invalid or corrupted image.",
                file_name=None
            )

        # 5️⃣ Validate resolution (640x640 only)
        height, width, channels = img.shape
        if width != 640 or height != 640:
            os.remove(save_path)
            return render_template(
                'prediction.html',
                error="⚠️ Image must be exactly 640x640 resolution.",
                file_name=None
            )

        # 🚀 6️⃣ YOLO Prediction (Model already loaded globally)
        results = yolo_model.predict(
            save_path,
            conf=0.25,
            iou=0.45,
            save=False,
            show=False
        )

        # 7️⃣ Save predicted image
        predicted_img = results[0].plot()
        prediction_filename = f"pred_{filename}"
        prediction_path = os.path.join(PREDICTION_FOLDER, prediction_filename)

        cv2.imwrite(prediction_path, predicted_img)

        # 8️⃣ Count detected classes safely
        class_counts = {}

        if results[0].boxes is not None and len(results[0].boxes.cls) > 0:
            for class_id in results[0].boxes.cls:
                class_name = yolo_model.names[int(class_id)]
                class_counts[class_name] = class_counts.get(class_name, 0) + 1

        # 9️⃣ If nothing detected
        if not class_counts:
            return render_template(
                'prediction.html',
                error="⚠️ No agricultural land features detected.",
                original_image=filename,
                prediction_image=prediction_filename
            )

        # 🔥 10️⃣ Advanced XAI Recommendation (Feature-Based Only)
        xai_system = XAIRecommendationSystem()
        xai_recommendations = xai_system.generate_xai_recommendations(class_counts)

        # Translate detected class_counts keys for display (keep original keys for DB)
        lang_for_display = session.get('lang', 'en')
        t_dict_display = TRANSLATIONS.get(lang_for_display, TRANSLATIONS['en'])
        translated_class_counts = {}
        for k, v in class_counts.items():
            translated_key = t_dict_display.get(k.lower(), k.capitalize())
            translated_class_counts[translated_key] = v

        import json

        # === TRANSLATION FOR ALL USERS ===
        lang = session.get('lang', 'en')
        t_dict = TRANSLATIONS.get(lang, TRANSLATIONS['en'])

        internal_mapping = {
            'water': 'water', 'agriculture': 'agriculture', 'urban': 'urban', 'forest': 'forest', 'dry': 'dry',
            'Paddy (Rice)': 'paddy', 'Rice': 'rice', 'Wheat': 'wheat', 'Maize': 'maize', 'Sorghum': 'sorghum',
            'Pearl Millet (Bajra)': 'pearl_millet', 'Finger Millet (Ragi)': 'ragi', 'Chickpea': 'chickpea',
            'Lentil': 'lentil', 'Groundnut': 'groundnut', 'Sunflower': 'sunflower', 'Cotton': 'cotton',
            'Soybean': 'soybean', 'Mustard': 'mustard', 'Sugarcane (Irrigated)': 'sugarcane', 'Sugarcane': 'sugarcane',
            'Banana': 'banana', 'Lotus': 'lotus', 'Water Chestnut': 'water_chestnut', 'Taro (Colocasia)': 'taro',
            'Water Spinach': 'water_spinach', 'Rooftop Vegetables': 'rooftop_vegetables', 'Microgreens': 'microgreens',
            'Hydroponic Lettuce': 'hydroponic_lettuce', 'Spinach': 'spinach', 'Coriander': 'coriander',
            'Mint': 'mint', 'Cherry Tomato': 'cherry_tomato', 'Capsicum': 'capsicum', 'Strawberry (Container)': 'strawberry',
            'Agroforestry System': 'agroforestry', 'Black Pepper': 'black_pepper', 'Cardamom': 'cardamom',
            'Turmeric': 'turmeric', 'Ginger': 'ginger', 'Medicinal Plants': 'medicinal_plants', 'Coffee': 'coffee',
            'Pigeon Pea': 'pigeon_pea', 'Castor': 'castor', 'Sesame': 'sesame', 'Cluster Bean': 'cluster_bean'
        }

        for rec in xai_recommendations:
            # CLEAN CLASS NAMES (strip dashes/spaces for mapping robustness)
            raw_land = rec["detected_land_type"].strip().rstrip('-').strip()
            land_key = internal_mapping.get(raw_land.lower(), raw_land.lower())
            translated_land = t_dict.get(land_key, raw_land)

            if lang != 'en' and translated_land.lower() != raw_land.lower():
                rec["detected_land_type_translated"] = f"{translated_land} ({raw_land})"
            else:
                rec["detected_land_type_translated"] = translated_land

            # Translate crop name — Localized (English)
            english_crop = rec["primary_recommendation"]
            crop_key = internal_mapping.get(english_crop, english_crop)
            local_crop = t_dict.get(crop_key, english_crop)
            
            if lang != 'en' and local_crop != english_crop:
                rec["primary_recommendation_translated"] = f"{local_crop} ({english_crop})"
            else:
                rec["primary_recommendation_translated"] = english_crop

            # Translate implementation steps to chosen language
            translated_steps = []
            for step_key in rec.get("implementation_steps", []):
                translated_steps.append(t_dict.get(step_key, step_key))
            rec["implementation_steps_translated"] = translated_steps

            # Default market fields (overridden below for logged-in users)
            rec.setdefault("market_price", "₹1,500")
            rec.setdefault("market_harvest", "₹1,800")
            rec.setdefault("market_trend", "stable")
            rec.setdefault("market_url", "https://agmarknet.gov.in/")

        if 'user_email' in session:

            # 🚀 Add Market Prices for Mandi Tracker (Current & Future Projection)
            MARKET_PRICES = {
                "Paddy (Rice)": {"price": "₹2,300", "harvest": "₹2,600", "trend": "up", "url": "https://agmarknet.gov.in/"},
                "Rice": {"price": "₹2,300", "harvest": "₹2,600", "trend": "up", "url": "https://agmarknet.gov.in/"},
                "Wheat": {"price": "₹2,275", "harvest": "₹2,550", "trend": "up", "url": "https://agmarknet.gov.in/"},
                "Maize": {"price": "₹1,960", "harvest": "₹2,100", "trend": "down", "url": "https://agmarknet.gov.in/"},
                "Sorghum": {"price": "₹2,970", "harvest": "₹3,200", "trend": "stable", "url": "https://agmarknet.gov.in/"},
                "Pearl Millet (Bajra)": {"price": "₹2,350", "harvest": "₹2,600", "trend": "up", "url": "https://agmarknet.gov.in/"},
                "Sugarcane": {"price": "₹355", "harvest": "₹380", "trend": "stable", "url": "https://agmarknet.gov.in/"},
                "Cotton": {"price": "₹6,620", "harvest": "₹7,200", "trend": "down", "url": "https://agmarknet.gov.in/"},
                "Soybean": {"price": "₹4,600", "harvest": "₹5,100", "trend": "up", "url": "https://agmarknet.gov.in/"},
                "Mustard": {"price": "₹5,450", "harvest": "₹6,100", "trend": "up", "url": "https://agmarknet.gov.in/"},
                "Cherry Tomato": {"price": "₹2,500", "harvest": "₹2,800", "trend": "up", "url": "https://agmarknet.gov.in/"},
                "Taro (Colocasia)": {"price": "₹1,800", "harvest": "₹2,100", "trend": "up", "url": "https://agmarknet.gov.in/"},
                "Microgreens": {"price": "₹12,000", "harvest": "₹14,000", "trend": "up", "url": "https://agmarknet.gov.in/"},
                "Hydroponic Lettuce": {"price": "₹8,000", "harvest": "₹9,500", "trend": "stable", "url": "https://agmarknet.gov.in/"}
            }
            
            for rec in xai_recommendations:
                full_crop_name = rec["primary_recommendation"]
                clean_crop_name = full_crop_name.split('(')[0].strip()
                price_data = MARKET_PRICES.get(clean_crop_name, {"price": "₹1,500", "harvest": "₹1,800", "trend": "stable", "url": "https://agmarknet.gov.in/"})
                
                if "Paddy" in clean_crop_name or "Rice" in clean_crop_name:
                    price_data = MARKET_PRICES.get("Paddy (Rice)", price_data)

                rec["market_price"] = price_data["price"]
                rec["market_harvest"] = price_data["harvest"]
                rec["market_trend"] = price_data["trend"]
                rec["market_url"] = price_data.get("url", "https://agmarknet.gov.in/")

            user_email = session.get('user_email')
            detected_json = json.dumps(class_counts)
            recommended_json = json.dumps([rec["primary_recommendation"] for rec in xai_recommendations])

            query = "INSERT INTO predictions (user_email, image_name, predicted_image, detected_classes, recommended_crop) VALUES (%s, %s, %s, %s, %s)"
            values = (user_email, filename, prediction_filename, detected_json, recommended_json)
            executionquery(query, values)

            print("Prediction saved for:", user_email)
            
        return render_template(
            'prediction.html',
            prediction="Prediction successful",
            file_name=filename,
            original_image=filename,
            prediction_image=prediction_filename,
            class_counts=translated_class_counts,
            xai_recommendations=xai_recommendations
        )

    return render_template('prediction.html')


@app.route('/my_predictions')
def my_predictions():

    if 'user_email' not in session:
        return redirect(url_for('login'))

    user_email = session['user_email']

    print("Fetching for:", user_email)

    query = """
        SELECT image_name, predicted_image,
               detected_classes, recommended_crop, created_at
        FROM predictions
        WHERE user_email = %s
        ORDER BY created_at DESC
    """

    values = (user_email,)
    data = retrivequery1(query, values)

    print("Rows found:", len(data))

    import json
    lang = session.get('lang', 'en')
    t_dict = TRANSLATIONS.get(lang, TRANSLATIONS['en'])

    formatted = []

    for row in data:
        # row[2]: detected_classes, row[3]: recommended_crop
        try:
            raw_classes = json.loads(row[2]) if row[2] else {}
        except (ValueError, TypeError):
            # Fallback for legacy plain-text data
            raw_classes = {item.strip(): "N/A" for item in str(row[2]).split(',')} if row[2] else {}

        try:
            raw_crops = json.loads(row[3]) if row[3] else []
        except (ValueError, TypeError):
            # Fallback for legacy plain-text data
            raw_crops = [item.strip() for item in str(row[3]).split(',')] if row[3] else []
        
        # Translate classes (with dash stripping)
        translated_classes = {}
        for cname, count in raw_classes.items():
            clean_cname = cname.strip().rstrip('-').strip()
            ckey = internal_mapping.get(clean_cname.lower(), clean_cname.lower())
            t_cname = t_dict.get(ckey, clean_cname.capitalize())
            translated_classes[t_cname] = count
            
        # Translate crops (History Page: format as Localized (English))
        translated_crops = []
        for crop in raw_crops:
            ckey = internal_mapping.get(crop, crop)
            lcrop = t_dict.get(ckey, crop)
            if lang != 'en' and lcrop != crop:
                translated_crops.append(f"{lcrop} ({crop})")
            else:
                translated_crops.append(crop)

        formatted.append({
            "image_name": row[0],
            "predicted_image": row[1],
            "detected_classes": translated_classes,
            "recommended_crop": translated_crops,
            "created_at": row[4]
        })

    return render_template(
        'user_predictions.html',
        predictions=formatted,
        user_name=session.get('user_name', 'User')
    )

@app.route('/download_report')
def download_report():
    if 'user_email' not in session:
        return redirect(url_for('login'))

    user_email = session['user_email']
    user_name = session['user_name']

    # 1. Fetch the latest prediction for this user
    query = """
        SELECT image_name, predicted_image, detected_classes, recommended_crop, created_at
        FROM predictions 
        WHERE user_email = %s 
        ORDER BY created_at DESC LIMIT 1
    """
    data = retrivequery1(query, (user_email,))

    if not data:
        return "No prediction found to generate report."

    row = data[0]
    img_name = row[0]
    pred_img_name = row[1]
    detected = json.loads(row[2]) if row[2] else {}
    crops = json.loads(row[3]) if row[3] else []
    date_str = str(row[4])

    # 2. Generate PDF using localized strings (with Unicode support)
    lang = session.get('lang', 'en')
    t_dict = TRANSLATIONS.get(lang, TRANSLATIONS['en'])
    
    # Use bundled Google Noto Sans fonts for Indic script support
    font_dir = os.path.join(app.root_path, 'static', 'fonts')
    
    pdf = FPDF()
    
    # Mapping for fonts
    font_map = {
        'te': ('NotoSansTelugu', os.path.join(font_dir, 'NotoSansTelugu-Regular.ttf')),
        'hi': ('NotoSansDevanagari', os.path.join(font_dir, 'NotoSansDevanagari-Regular.ttf')),
        'ta': ('NotoSansTamil', os.path.join(font_dir, 'NotoSansTamil-Regular.ttf')),
        'ml': ('NotoSansMalayalam', os.path.join(font_dir, 'NotoSansMalayalam-Regular.ttf'))
    }

    current_font = "Helvetica"
    if lang in font_map:
        font_name, font_path = font_map[lang]
        if os.path.exists(font_path):
            pdf.add_font(font_name, "", font_path, uni=True)
            current_font = font_name

    pdf.add_page()
    pdf.set_font(current_font, "", 12)

    # --- Header ---
    pdf.set_fill_color(15, 27, 109) # Navy Blue
    pdf.rect(0, 0, 210, 40, 'F')
    
    pdf.set_font(current_font, "B", 16)
        
    pdf.set_text_color(255, 255, 255)
    pdf.set_y(10)
    pdf.cell(0, 10, t_dict.get('pdf_report_title', "AGROVISION-XAI: SATELLITE ANALYSIS REPORT"), ln=True, align='C')
    
    pdf.set_font(current_font, "", 10)
        
    gen_for = t_dict.get('pdf_generated_for', 'Generated for')
    pdf.cell(0, 10, f"{gen_for}: {user_name} ({user_email})", ln=True, align='C')
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(45)
    
    pdf.set_font(current_font, "B", 12)
        
    analy_date = t_dict.get('pdf_analysis_date', 'Analysis Date')
    pdf.cell(0, 10, f"{analy_date}: {date_str}", ln=True)
    pdf.ln(5)

    # --- Image Comparison ---
    pdf.set_font(current_font, "B", 11)
        
    pdf.cell(95, 10, t_dict.get('pdf_orig_img', "Original Satellite Image"), align='C')
    pdf.cell(95, 10, t_dict.get('pdf_ai_img', "AI Prediction Overlay"), ln=True, align='C')
    
    # Check paths
    orig_path = os.path.join('static', 'saved_images', img_name)
    pred_path = os.path.join('static', 'predicted_images', pred_img_name)
    
    y_img = pdf.get_y()
    if os.path.exists(orig_path):
        pdf.image(orig_path, x=10, y=y_img, w=90, h=90)
    if os.path.exists(pred_path):
        pdf.image(pred_path, x=110, y=y_img, w=90, h=90)
    
    pdf.set_y(y_img + 95)
    pdf.ln(10)

    # --- Detected Features ---
    pdf.set_font(current_font, "B", 12)
        
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(0, 10, " " + t_dict.get('pdf_land_features', " Identified Land Features"), ln=True, fill=True)
    
    pdf.set_font(current_font, "", 10)
    pdf.ln(2)
    
    if detected:
        for cls, count in detected.items():
            # Apply dash stripping here too
            clean_cls = cls.strip().rstrip('-').strip()
            ckey = internal_mapping.get(clean_cls.lower(), clean_cls.lower())
            loc_cls = t_dict.get(ckey, clean_cls.title())
            pdf.cell(0, 7, f"- {loc_cls}: {count} instance(s) detected", ln=True)
    else:
        pdf.cell(0, 10, t_dict.get('pdf_no_features', "No specific geographical features identified."), ln=True)
    
    pdf.ln(10)

    # --- XAI Recommendations ---
    pdf.set_font(current_font, "B", 12)
        
    pdf.set_fill_color(25, 135, 84) # Success Green
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 10, " " + t_dict.get('pdf_crop_recs', " Intelligent Crop Recommendations (XAI-Driven)"), ln=True, fill=True)
    pdf.set_text_color(0, 0, 0)
    
    pdf.set_font(current_font, "I", 10)
    pdf.ln(2)
    
    if crops:
        for i, crop_name in enumerate(crops):
            pdf.set_font(current_font, "B", 10)
                
            # Localize crop name for PDF (Localized (English) format)
            # Remove brackets if already present
            base_crop = crop_name.split('(')[0].strip()
            ck_mapped = internal_mapping.get(base_crop.lower(), base_crop.lower())
            loc_crop = t_dict.get(ck_mapped, base_crop)
            
            if lang != 'en' and loc_crop != base_crop:
                display_crop = f"{loc_crop} ({base_crop})"
            else:
                display_crop = crop_name

            pdf.cell(0, 7, f"> {display_crop}", ln=True)
            
            pdf.set_font(current_font, "", 9)
            pdf.cell(0, 5, t_dict.get('pdf_rec_basis', "Recommendation based on detected soil moisture and regional land classification."), ln=True)
            pdf.ln(2)
    else:
        pdf.cell(0, 10, t_dict.get('pdf_consult_expert', "Consult an agricultural expert for this specific land profile."), ln=True)

    # --- Footer ---
    pdf.set_y(-30)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 10, "This report is generated using deep learning segmentation (YOLOv8) and Explainable AI (XAI).", ln=True, align='C')
    pdf.cell(0, 5, "Always verify findings with on-ground soil testing before large-scale investment.", ln=True, align='C')

    # Output to binary string
    output = pdf.output()
    
    # Prepare the byte stream
    byte_io = io.BytesIO(output)
    byte_io.seek(0)

    return send_file(
        byte_io,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f"AgroVision_Analysis_Report_{img_name}.pdf"
    )


# --- Redundant Knowledge base removed ---

@app.route('/agribot', methods=['POST'])
def agribot():
    user_msg = request.json.get('message', '').lower()
    user_email = session.get('user_email')
    
    # 1. Fetch Latest Analysis Data
    latest_query = "SELECT detected_classes, recommended_crop FROM predictions WHERE user_email = %s ORDER BY id DESC LIMIT 1"
    prediction_data = retrivequery1(latest_query, (user_email,))
    
    context_land = "general land"
    all_suggestions = []
    
    if prediction_data:
        det_json = json.loads(prediction_data[0][0]) if prediction_data[0][0] else {}
        context_land = ", ".join(det_json.keys()) if det_json else "general land"
        all_suggestions = json.loads(prediction_data[0][1]) if prediction_data[0][1] else []

    # 2. Friendly Response Logic
    lang = session.get('lang', 'en')
    t_dict = TRANSLATIONS.get(lang, TRANSLATIONS['en'])
    
    response = t_dict.get('bot_hello', "I am here to help! I am your Farmer Buddy. Can you ask me something specific about your field?")
    msg = user_msg.lower()

    # Identify target crop and priority
    target_crop = ""
    target_priority = 0
    
    # Try to match crop from message or use primary suggestion
    for i, s_crop in enumerate(all_suggestions):
        s_crop_clean = s_crop.lower().split('(')[0].strip()
        if s_crop_clean in msg or (not target_crop and i == 0):
            target_crop = s_crop_clean
            target_priority = i + 1
            if s_crop_clean in msg: break

    # Logic for Priority Questions
    if "priority" in msg or "rank" in msg or "best" in msg or "order" in msg:
        if all_suggestions:
            response = t_dict.get('bot_priority_intro', "Based on my analysis...").format(context_land=context_land)
            for i, c in enumerate(all_suggestions):
                p_suffix = t_dict.get('bot_priority_primary', ' (Primary)') if i == 0 else t_dict.get('bot_priority_rank', ' (Priority {rank})').format(rank=i+1)
                # Localize crop name in bot reply
                c_key = internal_mapping.get(c, c)
                loc_c = t_dict.get(c_key, c)
                response += f"**{i+1}. {loc_c}**{p_suffix}<br>"
            response += t_dict.get('bot_priority_footer', '')
        else:
            response = t_dict.get('bot_no_analysis', "Please upload an image first!")

    # Knowledge-based Responses
    elif ("why" in msg or "reason" in msg) and target_crop:
        p_note = AGRI_KNOWLEDGE.get(target_crop, {}).get("priority_note", "It matches the moisture levels we detected.")
        loc_crop = t_dict.get(internal_mapping.get(target_crop.title(), target_crop), target_crop.title())
        response = t_dict.get('bot_why_reason', "...").format(crop=loc_crop, reason=p_note, land=context_land)

    elif "water" in msg:
        if target_crop in AGRI_KNOWLEDGE:
            loc_crop = t_dict.get(internal_mapping.get(target_crop.title(), target_crop), target_crop.title())
            p_text = t_dict.get('bot_priority_primary', 'Primary') if target_priority == 1 else t_dict.get('bot_priority_rank', 'Priority {rank}').format(rank=target_priority)
            response = t_dict.get('bot_water_info', "...").format(crop=loc_crop, priority=p_text, water=AGRI_KNOWLEDGE[target_crop]['water'])
        else:
            response = t_dict.get('bot_no_extra_info', "Sorry, I can't provide detailed info yet.")

    elif "time" in msg or "grow" in msg or "day" in msg:
        if target_crop in AGRI_KNOWLEDGE:
            loc_crop = t_dict.get(internal_mapping.get(target_crop.title(), target_crop), target_crop.title())
            p_text = t_dict.get('bot_priority_primary', 'Primary') if target_priority == 1 else t_dict.get('bot_priority_rank', 'Priority {rank}').format(rank=target_priority)
            response = t_dict.get('bot_maturity_info', "...").format(crop=loc_crop, priority=p_text, duration=AGRI_KNOWLEDGE[target_crop]['duration'])
        else:
            response = t_dict.get('bot_no_extra_info', "Sorry, I can't provide detailed info yet.")

    elif "benefit" in msg or "use" in msg or "utility" in msg or "help" in msg:
        if target_crop in AGRI_KNOWLEDGE:
            loc_crop = t_dict.get(internal_mapping.get(target_crop.title(), target_crop), target_crop.title())
            response = t_dict.get('bot_usage_info', "...").format(crop=loc_crop, usage=AGRI_KNOWLEDGE[target_crop]['usage'])
        else:
            response = t_dict.get('bot_no_extra_info', "Sorry, I can't provide detailed info yet.")

    elif "pesticide" in msg or "medicine" in msg or "pest" in msg:
        if target_crop in AGRI_KNOWLEDGE:
            response = f"To protect your **{target_crop.title()}**, you should: {AGRI_KNOWLEDGE[target_crop]['pesticides']}"
        else:
            response = "I haven't been trained on pesticide recommendations for this crop yet. Please consult a local expert."

    # General Greetings
    elif "hello" in msg or "hi" in msg:
        response = _t('bot_hello')

    elif "work" in msg or "field" in msg:
        response = _t('bot_field_info').replace('{context_land}', context_land)

    return jsonify({"response": response})

class XAIRecommendationSystem:

    def __init__(self):
        self.crop_database = self._initialize_crop_database()

    # ----------------------------------------------------
    # Crop Database (Expanded)
    # ----------------------------------------------------
    def _initialize_crop_database(self):
        return {

            "water": [
                {"crop": "Paddy (Rice)", "confidence": 0.95},
                {"crop": "Lotus", "confidence": 0.88},
                {"crop": "Water Chestnut", "confidence": 0.86},
                {"crop": "Taro (Colocasia)", "confidence": 0.84},
                {"crop": "Water Spinach", "confidence": 0.83},
                {"crop": "Sugarcane (Irrigated)", "confidence": 0.82},
                {"crop": "Banana", "confidence": 0.80}
            ],

            "agriculture": [
                {"crop": "Rice", "confidence": 0.90},
                {"crop": "Wheat", "confidence": 0.88},
                {"crop": "Maize", "confidence": 0.87},
                {"crop": "Sorghum", "confidence": 0.85},
                {"crop": "Pearl Millet (Bajra)", "confidence": 0.84},
                {"crop": "Finger Millet (Ragi)", "confidence": 0.83},
                {"crop": "Chickpea", "confidence": 0.82},
                {"crop": "Lentil", "confidence": 0.81},
                {"crop": "Groundnut", "confidence": 0.80},
                {"crop": "Sunflower", "confidence": 0.79},
                {"crop": "Cotton", "confidence": 0.78},
                {"crop": "Soybean", "confidence": 0.77},
                {"crop": "Mustard", "confidence": 0.76},
                {"crop": "Vegetables (Tomato, Brinjal)", "confidence": 0.75}
            ],

            "urban": [
                {"crop": "Rooftop Vegetables", "confidence": 0.85},
                {"crop": "Microgreens", "confidence": 0.83},
                {"crop": "Hydroponic Lettuce", "confidence": 0.82},
                {"crop": "Spinach", "confidence": 0.80},
                {"crop": "Coriander", "confidence": 0.79},
                {"crop": "Mint", "confidence": 0.78},
                {"crop": "Cherry Tomato", "confidence": 0.77},
                {"crop": "Capsicum", "confidence": 0.76},
                {"crop": "Strawberry (Container)", "confidence": 0.74}
            ],

            "forest": [
                {"crop": "Agroforestry System", "confidence": 0.90},
                {"crop": "Black Pepper", "confidence": 0.85},
                {"crop": "Cardamom", "confidence": 0.84},
                {"crop": "Turmeric", "confidence": 0.83},
                {"crop": "Ginger", "confidence": 0.82},
                {"crop": "Medicinal Plants", "confidence": 0.80},
                {"crop": "Coffee", "confidence": 0.78}
            ],

            "dry": [
                {"crop": "Pearl Millet (Bajra)", "confidence": 0.92},
                {"crop": "Sorghum", "confidence": 0.90},
                {"crop": "Chickpea", "confidence": 0.88},
                {"crop": "Pigeon Pea", "confidence": 0.86},
                {"crop": "Castor", "confidence": 0.85},
                {"crop": "Sesame", "confidence": 0.83},
                {"crop": "Cluster Bean", "confidence": 0.82}
            ]
        }

    # ----------------------------------------------------
    # Main Recommendation Engine
    # ----------------------------------------------------
    def generate_xai_recommendations(self, detected_classes):

        recommendations = []

        for class_name, count in detected_classes.items():

            normalized = class_name.lower().replace("-", "_").replace(" ", "_")

            category = self._detect_category(normalized)

            if category:

                crop_pool = self.crop_database[category]

                # 🔥 RANDOM SELECTION
                selected_crop = random.choice(crop_pool)

                explanation = self._generate_explanation(category)

                recommendations.append({
                    "detected_land_type": class_name,
                    "detected_count": count,
                    "primary_recommendation": selected_crop["crop"],
                    "alternative_recommendations": [
                        c["crop"] for c in crop_pool
                        if c["crop"] != selected_crop["crop"]
                    ],
                    "confidence_score": round(
                        selected_crop["confidence"] * random.uniform(0.9, 1.05), 2
                    ),
                    "explanations": explanation,
                    "implementation_steps": self._generate_implementation_plan(selected_crop["crop"], category),
                    "icon": "🌱"
                })

            else:
                recommendations.append(self._default_recommendation(class_name, count))

        recommendations.sort(key=lambda x: x["confidence_score"], reverse=True)

        return recommendations

    # ----------------------------------------------------
    # Detect Category
    # ----------------------------------------------------
    def _detect_category(self, name):

        if any(k in name for k in ["water", "river", "lake", "pond"]):
            return "water"

        if any(k in name for k in ["agriculture", "farmland", "crop", "field"]):
            return "agriculture"

        if any(k in name for k in ["urban", "building", "residential", "structure"]):
            return "urban"

        if any(k in name for k in ["forest", "tree", "green"]):
            return "forest"

        if any(k in name for k in ["dry", "arid", "barren"]):
            return "dry"

        return None

    # ----------------------------------------------------
    # Generate Explanations
    # ----------------------------------------------------
    def _generate_explanation(self, category):

        explanations = {
            "water": {
                "primary": "exp_water_primary",
                "scientific": "exp_water_scientific",
                "economic": "exp_water_economic",
                "sustainability": "exp_water_sustainability",
                "risks": "exp_water_risks"
            },

            "agriculture": {
                "primary": "exp_agriculture_primary",
                "scientific": "exp_agriculture_scientific",
                "economic": "exp_agriculture_economic",
                "sustainability": "exp_agriculture_sustainability",
                "risks": "exp_agriculture_risks"
            },

            "urban": {
                "primary": "exp_urban_primary",
                "scientific": "exp_urban_scientific",
                "economic": "exp_urban_economic",
                "sustainability": "exp_urban_sustainability",
                "risks": "exp_urban_risks"
            },

            "forest": {
                "primary": "exp_forest_primary",
                "scientific": "exp_forest_scientific",
                "economic": "exp_forest_economic",
                "sustainability": "exp_forest_sustainability",
                "risks": "exp_forest_risks"
            },

            "dry": {
                "primary": "exp_dry_primary",
                "scientific": "exp_dry_scientific",
                "economic": "exp_dry_economic",
                "sustainability": "exp_dry_sustainability",
                "risks": "exp_dry_risks"
            }
        }

        return explanations.get(category)

    # ----------------------------------------------------
    # Default Recommendation
    # ----------------------------------------------------
    def _default_recommendation(self, class_name, count):

        return {
            "detected_land_type": class_name,
            "detected_count": count,
            "primary_recommendation": "Soil Testing Recommended",
            "alternative_recommendations": ["Consult Agricultural Expert"],
            "confidence_score": 0.50,
            "explanations": {
                "primary": "exp_default_primary",
                "scientific": "exp_default_scientific",
                "economic": "exp_default_economic",
                "sustainability": "exp_default_sustainability",
                "risks": "exp_default_risks"
            },
            "implementation_steps": [
                "step_default_1",
                "step_default_2"
            ],
            "icon": "🔍"
        }
    

        
    def _apply_seasonal_adjustment(self, class_name):
        """Adjust recommendation confidence based on season"""
        current_season = self.environmental_factors["season"]
        seasonal_suitability = {
            "water": {"kharif": 1.0, "rabi": 0.7, "zaid": 0.9},
            "wheat_field": {"kharif": 0.6, "rabi": 1.0, "zaid": 0.5},
            "maize_field": {"kharif": 1.0, "rabi": 0.8, "zaid": 0.9},
            "dry_land": {"kharif": 0.9, "rabi": 0.7, "zaid": 0.6}
        }
        
        return seasonal_suitability.get(class_name, {}).get(current_season, 0.8)
    
    def _apply_farmer_profile_adjustment(self, recommendations, profile):
        """Adjust recommendations based on farmer profile"""
        # In a full implementation, this would modify recommendations
        # based on labor availability, mechanization level, and investment capacity
        return recommendations
    
    def _get_seasonal_suitability(self, class_name):
        """Get seasonal suitability information"""
        suitability_map = {
            "water": "Best in Kharif season (June-September)",
            "wheat_field": "Best in Rabi season (October-March)",
            "maize_field": "Suitable for Kharif and Zaid seasons",
            "dry_land": "Adaptable to all seasons with proper management"
        }
        return suitability_map.get(class_name, "Consult local agricultural officer")
    
    def _generate_implementation_plan(self, crop, land_type):
        """Generate step-by-step implementation plan (returns translation keys)"""
        # Crop-specific plans
        crop_plans = {
            "Paddy (Rice)": ["step_paddy_1", "step_paddy_2", "step_paddy_3", "step_paddy_4", "step_paddy_5"],
            "Rice":         ["step_paddy_1", "step_paddy_2", "step_paddy_3", "step_paddy_4", "step_paddy_5"],
            "Wheat":        ["step_wheat_1", "step_wheat_2", "step_wheat_3", "step_wheat_4", "step_wheat_5"],
            "Pearl Millet (Bajra)": ["step_millet_1", "step_millet_2", "step_millet_3", "step_millet_4", "step_millet_5"],
            "Finger Millet (Ragi)": ["step_millet_1", "step_millet_2", "step_millet_3", "step_millet_4", "step_millet_5"],
            "Sorghum":      ["step_millet_1", "step_millet_2", "step_millet_3", "step_millet_4", "step_millet_5"],
        }
        if crop in crop_plans:
            return crop_plans[crop]

        # Land-type fallback plans (cover all categories)
        land_plans = {
            "water":       ["step_water_1", "step_water_2", "step_water_3", "step_water_4", "step_water_5"],
            "agriculture": ["step_agri_1",  "step_agri_2",  "step_agri_3",  "step_agri_4",  "step_agri_5"],
            "urban":       ["step_urban_1", "step_urban_2", "step_urban_3", "step_urban_4", "step_urban_5"],
            "forest":      ["step_forest_1","step_forest_2","step_forest_3","step_forest_4","step_forest_5"],
            "dry":         ["step_dry_1",   "step_dry_2",   "step_dry_3",   "step_dry_4",   "step_dry_5"],
        }
        return land_plans.get(land_type, ["step_default_1", "step_default_2"])
    
    def _get_recommendation_color(self, confidence):
        """Get color code based on confidence score"""
        if confidence >= 0.9:
            return "success"
        elif confidence >= 0.7:
            return "warning"
        else:
            return "info"
    
    def _get_crop_icon(self, crop):
        """Get icon for crop type"""
        icons = {
            "Paddy (Rice)": "🌾",
            "Wheat": "🌾",
            "Maize": "🌽",
            "Millets": "🌱",
            "Pulses": "🫘",
            "Fruit Trees": "🌳"
        }
        return icons.get(crop, "🌱")
    
    def _generate_default_recommendation(self, class_name, count):
        """Generate default recommendation for unknown classes"""
        return {
            "detected_land_type": class_name,
            "detected_count": count,
            "primary_recommendation": "Soil Testing Recommended",
            "alternative_recommendations": ["Consult Agricultural Expert"],
            "confidence_score": 0.5,
            "explanations": {
                "primary_explanation": "Uncommon land type detected",
                "scientific_basis": "Insufficient data for specific recommendation",
                "economic_rationale": "Soil analysis needed for optimal crop selection",
                "sustainability_aspects": "Precision agriculture approach recommended",
                "risk_assessment": "High uncertainty without soil testing"
            },
            "environmental_factors": self.environmental_factors,
            "implementation_steps": [
                "1. Conduct comprehensive soil testing",
                "2. Analyze water availability",
                "3. Consider local climatic conditions",
                "4. Consult with agricultural extension officer"
            ],
            "color_code": "secondary",
            "icon": "🔍"
        }
    
    def generate_visual_explanation(self, recommendations):
        """Generate visual XAI explanations for the interface"""
        visual_data = []
        
        for rec in recommendations:
            visual_data.append({
                "crop": rec["primary_recommendation"],
                "confidence": rec["confidence_score"],
                "color": rec["color_code"],
                "icon": rec["icon"],
                "factors": [
                    {"name": "Season Suitability", "value": 0.8},
                    {"name": "Soil Compatibility", "value": 0.9},
                    {"name": "Water Requirements", "value": 0.7},
                    {"name": "Economic Viability", "value": 0.85}
                ]
            })
        
        return visual_data

if __name__ == '__main__':
    app.run(debug = True)