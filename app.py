from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
from crewai import Crew, Agent, Task
from docx import Document

load_dotenv()

app = Flask(__name__)

def extract_text_from_docx(file):
    document = Document(file)
    return "\n".join([para.text for para in document.paragraphs])

@app.route('/')
def home():
    return "Resume Writer AI App is running!"

@app.route('/process_resume', methods=['POST'])
def process_resume():
    uploaded_file = request.files['file']
    resume_text = extract_text_from_docx(uploaded_file)

    # Define your agents
    cv_extractor = Agent(
        role="CV Extractor",
        goal="Extract structured data",
        backstory="...",
        model="gpt-3.5-turbo",
        verbose=True,
        allow_delegation=False,
    )
    keyword_advisor = Agent(
        role="Keyword Advisor",
        goal="Recommend top 5 keywords",
        backstory="...",
        model="gpt-3.5-turbo",
        verbose=True,
        allow_delegation=False,
    )

    # Define tasks
    task1 = Task(
        description=f"Extract structured data from: {resume_text}",
        agent=cv_extractor,
        expected_output="..."
    )
    task2 = Task(
        description=f"Extract top 5 keywords from: {resume_text}",
        agent=keyword_advisor,
        expected_output="..."
    )

    # Run the Crew
    crew = Crew(agents=[cv_extractor, keyword_advisor], tasks=[task1, task2], verbose=True)
    results = crew.kickoff()

    return jsonify({"results": results})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
