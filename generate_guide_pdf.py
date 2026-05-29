import os
import subprocess
import sys

# Install fpdf2 if not already present
try:
    from fpdf import FPDF
except ImportError:
    print("Installing fpdf2 library to generate PDF...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "fpdf2"])
    from fpdf import FPDF

class VivaGuidePDF(FPDF):
    def header(self):
        # Arial bold 15
        self.set_font('helvetica', 'B', 15)
        # Title
        self.cell(0, 10, 'AgriSense: Smart Irrigation & Machine Learning System', ln=True, align='C')
        self.set_font('helvetica', 'I', 10)
        self.cell(0, 5, 'College Project Examination & Viva Preparation Guide', ln=True, align='C')
        # Line break
        self.ln(5)
        # Draw a horizontal line
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def footer(self):
        # Position at 1.5 cm from bottom
        self.set_y(-15)
        # Arial italic 8
        self.set_font('helvetica', 'I', 8)
        # Page number
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}} | Prepared for AgriSense Examination', align='C')

    def chapter_title(self, num, title):
        self.set_font('helvetica', 'B', 12)
        # Background color
        self.set_fill_color(220, 240, 220)
        # Title
        self.cell(0, 8, f'{num}. {title}', ln=True, fill=True)
        self.ln(4)

    def question_block(self, q_num, question, answer):
        self.set_font('helvetica', 'B', 10)
        # Write Question
        self.multi_cell(0, 5, f'Q{q_num}: {question}')
        self.ln(1)
        self.set_font('helvetica', '', 10)
        # Write Answer
        self.multi_cell(0, 5, f'Ans: {answer}')
        self.ln(4)

# Create PDF instance
pdf = VivaGuidePDF()
pdf.alias_nb_pages()
pdf.add_page()

# Title Page Section
pdf.set_font('helvetica', 'B', 16)
pdf.set_text_color(34, 139, 34) # Forest Green
pdf.cell(0, 15, 'AGRISENSE VIVA STUDY GUIDE', ln=True, align='C')
pdf.set_text_color(0, 0, 0)
pdf.ln(2)

# SECTION 1: System Overview
pdf.chapter_title('1', 'System Architecture & Core Logic')
pdf.set_font('helvetica', '', 10)
overview_text = (
    "AgriSense is a smart, IoT-enabled, closed-loop irrigation system. It consists of an ESP32 edge microcontroller "
    "connected to various physical sensors (soil moisture, temperature, flame detection, and GPS) that feeds data "
    "to a Flask Web Server hosted in the cloud. The web server runs a Machine Learning model (Random Forest Classifier) "
    "to make watering recommendations, checks external weather APIs to conserve water if rain is forecast, and stores "
    "data securely on a cloud-based serverless Postgres database (Neon) for real-time dashboard display."
)
pdf.multi_cell(0, 5, overview_text)
pdf.ln(5)

# SECTION 2: Tech Stack Choice
pdf.chapter_title('2', 'Technology Stack Justification')
justifications = [
    ("Python & Flask", "Flask is a lightweight micro-framework, making it extremely fast to set up and ideal for IoT APIs. We chose Python because the system runs a Machine Learning model (Random Forest). Writing the server in Python allows us to run the API and execute ML predictions in the same codebase natively."),
    ("Neon PostgreSQL", "SQLite databases are file-based and get erased daily on Render's temporary containers. Neon Postgres provides secure, free, and permanent relational storage in the cloud. SQL is ideal because sensor telemetry is highly structured time-series data."),
    ("HTML, CSS & JavaScript", "Standard web technologies keep the dashboard lightweight, fast to load, and easy to render dynamically using AJAX polling without client-side compilers like React."),
    ("Render Hosting", "Render provides free cloud hosting connected directly to GitHub, automating deployment via Git commits and making it 24/7 accessible from anywhere.")
]

for title, desc in justifications:
    pdf.set_font('helvetica', 'B', 10)
    pdf.cell(0, 5, f' - {title}:', ln=True)
    pdf.set_font('helvetica', '', 10)
    pdf.multi_cell(0, 5, desc)
    pdf.ln(2)
pdf.ln(3)

# SECTION 3: Top 15 Viva Questions
pdf.chapter_title('3', 'Top 15 Predicted Viva Questions & Answers')

qa_list = [
    ("What is the role of Machine Learning in this project?", 
     "Instead of using hardcoded rules (like 'turn pump on if moisture < 30%'), we use a Machine Learning Classifier. It analyzes moisture and temperature history to classify if irrigation is needed (1) or not (0), making the system smarter and adaptive to climate trends over time."),
    
    ("Why did you choose the Random Forest Classifier?", 
     "Random Forest is an ensemble learning method using multiple decision trees. It is highly robust, prevents overfitting, handles non-linear relationships between soil moisture and ambient temperature well, and has high classification accuracy with low compute requirements."),
    
    ("How does the 'Fallback Mode' work if a sensor fails?", 
     "If the soil moisture sensor returns out-of-bounds values (e.g. less than 0% or greater than 100%), the backend enters 'Fallback Mode'. It triggers an alert and uses historical telemetry and temperature degradation patterns to estimate the soil dryness, continuing irrigation safely."),
    
    ("What is the purpose of the Open-Meteo Weather API integration?", 
     "To conserve water. If the ML model recommends turning the pump ON, the server queries the Open-Meteo forecast API using the station's GPS coordinates. If there is a >60% probability of rain in the next 24 hours, the server overrides the prediction and cancels the irrigation cycle."),
    
    ("Why did you use Neon Postgres instead of local SQLite?", 
     "Render's free tier uses temporary containers; any local SQLite file would be deleted when the container restarts daily. Neon Postgres runs in the cloud, keeping our user credentials, alert logs, and sensor history permanently saved."),
    
    ("How does the ESP32 connect and send data to the server?", 
     "The ESP32 connects to a Wi-Fi network using the WiFi.h library. It gathers sensor readings, formats them as a JSON payload, and executes an HTTP POST request to the server's public endpoint (/api/sensor) every 10 seconds."),
    
    ("How is user authentication secured on the website?", 
     "User credentials are secured using cryptographic password hashing (via Werkzeug's security helpers). The database never stores plain-text passwords, only hashes, protecting user accounts from data leaks."),
    
    ("What happens if the ESP32 goes offline?", 
     "The Flask server runs a background watchdog thread. If no telemetry is received from the ESP32 for more than 5 minutes, it flags the device status as 'Offline / Failing', writes an alert to the database, and sends an SMTP email notification to the operator."),
    
    ("How does the GPS module work and what is the fallback if it loses lock?", 
     "The Neo-6M GPS module feeds coordinates to the TinyGPS++ library on the ESP32. If there is no satellite lock (e.g. indoors), the ESP32 fails to send coordinates, and the server automatically falls back to geolocating the ESP32's connection IP via the IP-API service."),
    
    ("Why does the backend run background threads?", 
     "We use Python's threading library to prevent blocking. Tasks like reverse geocoding, sending email alerts, and retraining the ML model take time and would slow down the API response if run synchronously. Threading keeps the system highly responsive."),
    
    ("What baud rates are used in the ESP32 hardware configuration?", 
     "We use 115200 bps for the primary Hardware Serial 0 interface (used for PC debugging) and 9600 bps for the Hardware Serial 2 interface (used to communicate with the Neo-6M GPS module)."),
    
    ("How does the soil moisture sensor map analog values to percentage?", 
     "The soil moisture sensor is an analog probe. We calibrated it by reading raw values: 4095 in dry air (0%) and 1500 fully wet in water (100%). The ESP32 code maps these raw readings into a standard 0 to 100% scale using the map() function."),
    
    ("What happens when the dashboard receives a fire warning?", 
     "If the flame sensor registers heat, the server overrides all logic, turns the pump ON immediately to extinguish the fire, flags a Critical Fire warning on the UI, and dispatches an urgent email alert via SMTP."),
    
    ("What is the role of gunicorn in the Render deployment?", 
     "Flask's built-in server is only for local development and is single-threaded. Gunicorn (Green Unicorn) is a production-grade Python WSGI HTTP server that manages multiple worker processes to handle web traffic efficiently in the cloud."),
    
    ("How does the frontend dashboard get live updates?", 
     "A JavaScript polling interval (in main.js) executes an AJAX GET request to the backend's /api/live_data endpoint every few seconds. It parses the JSON response and updates the UI DOM and charts dynamically without reloading.")
]

for i, (q, a) in enumerate(qa_list, 1):
    # Check if we need to add a page to avoid awkward cuts
    if pdf.get_y() > 250:
        pdf.add_page()
    pdf.question_block(i, q, a)

# Save PDF file
output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'viva_preparation_guide.pdf')
pdf.output(output_path)
print(f"PDF Guide generated successfully at: {output_path}")
