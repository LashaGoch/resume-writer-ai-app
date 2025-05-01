import os
from dotenv import load_dotenv
from docx import Document
from docx.shared import Pt
from crewai import Crew, Agent, Task
from flask import Flask, request, render_template_string, send_file

# Load environment variables
load_dotenv()

app = Flask(__name__)

def extract_text_from_docx(file):
    document = Document(file)
    return "\n".join([para.text for para in document.paragraphs])

def write_text_to_docx(text, file_path):
    doc = Document()
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Calibri'
    font.size = Pt(10)

    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if block.startswith("▪") or block.startswith("•") or block.startswith("-"):
            para = doc.add_paragraph(style='List Bullet')
            para.add_run(block)
        else:
            doc.add_paragraph(block)

    doc.save(file_path)

UPLOAD_FORM = """
<!DOCTYPE html>
<html>
<head><title>Resume Writer AI</title></head>
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
    output_path = "new.docx"
    
    # Slice only relevant part of resume for education
    education_section = resume_text.split("EDUCATION")[1]

    # Slice only relevant part of resume for experience
    experience_section = resume_text.split("EXPERIENCE")[1]
    
    # Initialize OpenAI key (needed internally by CrewAI)
    openai_api_key = os.getenv('OPENAI_API_KEY')
    if not openai_api_key:
        return "OpenAI API Key not found!", 500

    # Define CrewAI agents
    keyword_generator = Agent(
        role="Keyword Generator",
        goal="Extract top 5 ATS-proof keywords from resume and job title.",
        backstory="An expert in optimizing resumes for applicant tracking systems.",
        model="gpt-4o",
        verbose=True,
        allow_delegation=False
    )

    summary_writer = Agent(
        role="Summary Writer",
        goal="Create a three-paragraph ATS-proof summary from the resume. Max two lines on each paragraph.",
        backstory="Writes concise professional summaries tailored to job positions.",
        model="gpt-4o",
        verbose=True,
        allow_delegation=False
    )

    expertise_writer = Agent(
        role="Areas of Expertise Writer",
        goal="Generate 9 expertise keywords in 3 columns, 3 rows format.",
        backstory="Crafts strong area of expertise sections for resumes.",
        model="gpt-4o",
        verbose=True,
        allow_delegation=False
    )

    achievement_writer = Agent(
        role="Achievements Writer",
        goal="Write 3–5 measurable achievement bullet points.",
        backstory="Creates bullet points that demonstrate quantifiable success.",
        model="gpt-4o",
        verbose=True,
        allow_delegation=False
    )

    experience_writer = Agent(
        role="Job Description Writer",
        goal="Create job descriptions for 2–3 most recent roles with company info, title, dates, summary, and measurable bullet points.",
        backstory="Expert in writing clean and structured work experience entries for resumes. Do not use first person style.",
        model="gpt-4o",
        verbose=True,
        allow_delegation=False
    )

    additional_exp_writer = Agent(
        role="Additional Experience Writer",
        goal="List older work experience entries in two-line format.",
        backstory="List earlier work in a compact and clear way.",
        model="gpt-3.5-turbo",
        verbose=True,
        allow_delegation=False
    )

    education_writer = Agent(
        role="Education Writer",
        goal="List education, one per line.",
        backstory="Summarizes education for resumes.",
        model="gpt-3.5-turbo",
        verbose=True,
        allow_delegation=False
    )

    cert_writer = Agent(
        role="Certifications Writer",
        goal="List certifications, one per line.",
        backstory="List credentials for resumes.",
        model="gpt-3.5-turbo",
        verbose=True,
        allow_delegation=False
    )

    language_writer = Agent(
        role="Language Writer",
        goal="List known languages in a single line.",
        backstory="Formats multilingual proficiencies.",
        model="gpt-3.5-turbo",
        verbose=True,
        allow_delegation=False
    )

    proofreader = Agent(
        role="ATS Proofreader",
        goal="Proofread and ensure text is optimized for ATS.",
        backstory="Ensures resumes are clean, accurate, and ATS-friendly.",
        model="gpt-3.5-turbo",
        verbose=True,
        allow_delegation=False
    )
    

    # Define tasks
    tasks = [
        Task(
            description=f"Given the following resume, generate the top 5 keywords that are optimized for applicant tracking systems (ATS).\n\nResume:\n{resume_text}",
            agent=keyword_generator,
            expected_output="A list of 5 ATS-optimized keywords."
        ),
        Task(
            description=f"Using the resume below, write a 3-paragraph professional summary. Each paragraph should be two lines max.\n\nResume:\n{experience_section}",
            agent=summary_writer,
            expected_output="Three short paragraphs summarizing the candidate."
        ),
        Task(
            description=f"Based on the resume below, generate 9 'Areas of Expertise' keywords formatted in 3 columns and 3 rows. Do not repeat the keywords generated by keyword_generator agent.\n\nResume:\n{experience_section}",
            agent=expertise_writer,
            expected_output="Nine keywords in a 3x3 grid format without column titles."
        ),
        Task(
            description=f"From the following resume, write 3–5 bullet points describing notable achievements. Each bullet must be measurable and max 2 lines.\n\nResume:\n{experience_section}",
            agent=achievement_writer,
            expected_output="3–5 short achievement bullet points with metrics or impact."
        ),
        Task(
            description=f"Use this resume to create job descriptions for the 2–3 most recent roles. For each: line 1 is Company, City, Country; line 2 is Job Title and Dates; followed by a 2-3 line summary and 1–3 bullet points of achievements.\n\nResume:\n{experience_section}",
            agent=experience_writer,
            expected_output="2–3 job experiences formatted as described."
        ),
        Task(
            description=f"Summarize other job experience in the resume below using a 2-line format per job. Do not add extra lines or job responsibilities.\n\nResume:\n{experience_section}",
            agent=additional_exp_writer,
            expected_output="Older jobs in 2-line format (company + role + dates)."
        ),
        Task(
            description=f"Extract education from this resume. Format each entry on one line.\n\nResume:\n{education_section}",
            agent=education_writer,
            expected_output="List of education entries, one per line."
        ),
        Task(
            description=f"Extract certifications from this resume. Format each entry on one line.\n\nResume:\n{resume_text}",
            agent=cert_writer,
            expected_output="List of certifications with full name and easily identifiable, one per line."
        ),
        Task(
            description=f"List all languages mentioned in the following resume on one line.\n\nResume:\n{resume_text}",
            agent=language_writer,
            expected_output="Single-line summary of languages that starts with Languages:"
        ),
        Task(
            description=f"Proofread this resume and make sure it's grammatically correct, has implied first person style, does not use I, and it is  ATS-friendly",
            agent=proofreader,
            expected_output="Polished version of the resume, optimized for ATS."
        )
        ]

    # Run the crew
    crew = Crew(agents=[keyword_generator, summary_writer, expertise_writer, achievement_writer,
        experience_writer, additional_exp_writer, education_writer, cert_writer, language_writer, proofreader
    ], tasks=tasks, verbose=True)
    
    result = crew.kickoff()

    # Show results in browser
    compiled_resume_text = result.output if hasattr(result, 'output') else str(result)
    write_text_to_docx(compiled_resume_text, output_path)
    
    return f"""
        <div style='font-family: Calibri, sans-serif; padding: 20px;'>
            <h2>✅ Resume Processed Successfully!</h2>
            <a href='/download' download>📥 Download New Resume</a>
            <pre style='white-space: pre-wrap; font-size: 14px; color: #333;'>{compiled_resume_text}</pre>
        </div>
    """

@app.route('/download')
def download():
    return send_file("new.docx", as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
