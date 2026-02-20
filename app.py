import os
import io
import json
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from google import genai
from google.genai.errors import APIError
from PIL import Image
from pydantic import BaseModel, Field
from typing import List
from dotenv import load_dotenv
import psycopg2
import psycopg2.extras

def get_db_connection():
    return psycopg2.connect(
        os.getenv("DATABASE_URL"),
        sslmode="require"
    )

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) NOT NULL,
            password VARCHAR(255) NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cattles (
            id SERIAL PRIMARY KEY,
            cattle_type VARCHAR(50),
            cattle_name VARCHAR(100),
            breed VARCHAR(100),
            vet_visit VARCHAR(50),
            age VARCHAR(10),
            health_notes TEXT
        )
    """)

    conn.commit()
    cursor.close()
    conn.close()

init_db()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fallback_secret") # required for sessions

# -------------------------------------------------
# Login Page
# -------------------------------------------------
@app.route("/")
def login_page():
    return render_template("login.html")

# -------------------------------------------------
# Login Logic
# -------------------------------------------------
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    cursor.execute("SELECT * FROM users WHERE email = %s AND password = %s", (email, password))
    user = cursor.fetchone()
    
    cursor.close()
    conn.close()

    if user:
        session["logged_in"] = True
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "fail"}), 401

@app.route("/signup", methods=["POST"])
def signup():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO users (email, password) VALUES (%s, %s)",
            (email, password)
        )
        conn.commit()
        session["logged_in"] = True
        return jsonify({"status": "success"})

    except psycopg2.Error as e:
        return jsonify({"status": "fail", "message": str(e)}), 500

    finally:
        cursor.close()
        conn.close()

# -------------------------------------------------
# Logout
# -------------------------------------------------
@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login_page"))

# -------------------------------------------------
# Recognition Page (Protected)
# -------------------------------------------------
@app.route("/recognition")
def recognition_page():
    if not session.get("logged_in"):
        return redirect(url_for("login_page"))
    return render_template("index.html")

@app.route("/encylopedia")
def encylopedia_page():
    if not session.get("logged_in"):
        return redirect(url_for("login_page"))
    return render_template("encylopedia.html") 

@app.route("/records")
def record_page():
    if not session.get("logged_in"):
        return redirect(url_for("login_page"))
    
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT * FROM cattles")
    all_records = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template("records.html", records=all_records)

@app.route('/add_record', methods=['POST'])
def add_record():
    if not session.get("logged_in"):
        return jsonify({"status": "fail", "message": "Unauthorized"}), 401

    c_type = request.form.get('cattle_type')
    c_name = request.form.get('cattle_name')
    breed = request.form.get('breed')
    vet_visit = request.form.get('vet_visit')
    age = request.form.get('age')
    notes = request.form.get('health_notes')

    conn = get_db_connection()
    cursor = conn.cursor()
    query = """INSERT INTO cattles (cattle_type, cattle_name, breed, vet_visit, age, health_notes) 
               VALUES (%s, %s, %s, %s, %s, %s)"""
    cursor.execute(query, (c_type, c_name, breed, vet_visit, age, notes))
    conn.commit()
    cursor.close()
    conn.close()
    
    return jsonify({"status": "success"})

try:
    load_dotenv()
    client = genai.Client(api_key='AIzaSyCo-OAA5X-yktZoLR9ZoD3hrWIeU6GuBVI')
except Exception as e:
    print(f"Error initializing Gemini client: {e}")
    client = None

# ----------------------------------------------------------------------
# 2. Pydantic Structured Output Schema (Matches your HTML/JS requirements)
# ----------------------------------------------------------------------
class CattleAnalysis(BaseModel):
    """
    Structured output for detailed cattle analysis.
    """
    breed: str = Field(description="The specific breed of the cattle in the image (e.g., 'Jersey', 'Holstein', 'Angus').")
    milk_quality: List[str] = Field(description="A list of 2-3 key characteristics or typical uses for the milk from this breed.")
    temperature: List[str] = Field(description="A list of 2-3 key temperature or climate conditions this breed thrives in finally mention temerpature in degrees.")
    purpose_primary: str = Field(description=" 2- 3 lines of the primary purpose of this breed and how they can be used effeciently in agriculture(e.g., 'Dairy', 'Beef', 'Dual-Purpose', 'Draft').")
    purpose_secondary: str = Field(description="Confidence Score for the detection of the cattle and also what helped to identify the cattle (eg., 'holstein has black and white pattern').")
    diseases: str = Field(description="From the image, detect if the cattle is healthy or affected by any diseases return 2-3 lines : healthy if no diseases detected else return disease type,treatement,and causes.")
    region: str = Field(description="the region that identified cattle is originated,e.g gir is orginated from gujarat")
# ----------------------------------------------------------------------
# 3. Routes
# ----------------------------------------------------------------------

# CORRECT ROUTE: Uses render_template to serve the HTML from the 'templates' folder


# Route to handle the image upload and AI analysis
@app.route('/upload', methods=['POST'])
def upload_cattle_photo():
    """Handles image upload and calls the Gemini model for structured analysis."""
    
    if client is None:
        return jsonify({"success": False, "error": "Gemini API Client not initialized. Check your GEMINI_API_KEY environment variable."}), 500

    # The HTML/JS sends the file with the key 'file'
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No file part in the request."}), 400
    
    file = request.files['file']

    if file.filename == '':
        return jsonify({"success": False, "error": "No selected file."}), 400

    if file:
        try:
            # Read the file into an Image object
            img_bytes = file.read()
            image = Image.open(io.BytesIO(img_bytes))

            prompt_text = (
                "You are an expert livestock analyst. Analyze the provided image of the cattle. "
                "If the animal is identified as a goat or sheep, then the purpose of that cattle is meat in case of goat and wool production in case of sheep"
                "Identify the breed and provide a detailed analysis of its milk quality, ideal temperature/climate, and primary/secondary purposes. "
                "Your entire response MUST be a JSON object that strictly conforms to the provided schema."
            )
            
            # Call the Gemini API with the image and structured output config
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[prompt_text, image],
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=CattleAnalysis, 
                )
            )
            
            # Parse the guaranteed valid JSON output
            analysis_data = json.loads(response.text)
            
            return jsonify({
                "success": True,
                "output": analysis_data
            })

        except APIError as e:
            return jsonify({"success": False, "error": f"Gemini API Error: {str(e)}"}), 500
        except Exception as e:
            return jsonify({"success": False, "error": f"An unexpected error occurred: {str(e)}"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
