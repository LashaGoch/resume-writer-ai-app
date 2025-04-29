import os
from flask import Flask, request, render_template_string
from dotenv import load_dotenv
from docx import Document
from crewai import Crew, Agent, Task

# Load environment variables
load_dotenv()

app = Flask(__name__)

def extract_text_from_docx(file):
    document = Document(file)
    return "\n".join([para.text for para in document.paragraphs])

# Simple HTML page for uploading
UPLOAD_FORM = """
<!DOCTYPE html>
<html>
<head>
    <title>Resume Writer AI</title>
</head>
<body>
    <h1>Resume Writer AI 📄</h1>
    <form method="POST" action="/process" enctype="multipart/form-data">
        <input type="file" name="file" accept=".docx" required>
        <button type="submit">Upload and Process</button>
    </form>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(UPLOAD_FORM)

@app.route('/process', methods=['POST'])
def process_resume():
    uploaded_file = request.files.get('file')
    if not uploaded_file:
        return "No file uploaded", 400

    # Extract text from uploaded resume
    resume_text = extract_text_from_docx(uploaded_file)

    # Initialize OpenAI key (needed internally by CrewAI)
    openai_api_key = os.getenv('OPENAI_API_KEY')
    if not openai_api_key:
        return "OpenAI API Key not found!", 500

    # Define CrewAI agents
    cv_extractor = Agent(
        role="CV Extractor",
        goal="Extract structured data",
        backstory="Professional resume analyzer.",
        model="gpt-3.5-turbo",
        verbose=True,
        allow_delegation=False,
    )
    keyword_advisor = Agent(
        role="Keyword Advisor",
        goal="Suggest top 5 resume keywords",
        backstory="ATS keyword optimization expert.",
        model="gpt-3.5-turbo",
        verbose=True,
        allow_delegation=False,
    )

    # Define tasks
    task1 = Task(
        description=f"Extract experience, skills, education from this resume:\n\n{resume_text}",
        agent=cv_extractor,
        expected_output="Structured JSON with sections."
    )
    task2 = Task(
        description=f"Find 5 keywords to optimize resume ATS:\n\n{resume_text}",
        agent=keyword_advisor,
        expected_output="Top 5 keywords list."
    )

    # Run the crew
    crew = Crew(agents=[cv_extractor, keyword_advisor], tasks=[task1, task2], verbose=True)
    results = crew.kickoff()

    # Show results in browser
    if not isinstance(results, str):
        results = str(results)

    return f"<h2>✅ Resume Processed Successfully!</h2><pre>{results}</pre>"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
