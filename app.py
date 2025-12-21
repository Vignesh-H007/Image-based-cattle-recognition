import os
import io
import json
import sqlite3
# Added session and redirect
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from google import genai
from google.genai.errors import APIError
from PIL import Image
from pydantic import BaseModel, Field
from typing import List

def get_db_connection():
    conn = sqlite3.connect("users.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            password TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()

init_db()

app = Flask(__name__)
app.secret_key = "super_secret_cattle_key"  # required for sessions

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

    # simple hardcoded login (as requested)
    if email == "farmer123@gmail.com" and password == "123456":
        session["logged_in"] = True
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "fail"}), 401

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
    return render_template("records.html")

try:
    client = genai.Client()
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

if __name__ == '__main__':
    # Runs the app, listening on port 5000 by default
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))