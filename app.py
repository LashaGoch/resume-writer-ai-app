import os
from dotenv import load_dotenv
from docx import Document
from docxtpl import DocxTemplate
import json
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.shared import Pt, RGBColor
from crewai import Crew, Agent, Task
from flask import Flask, request, render_template, send_file, Response
from markdown import markdown
import re


# Load environment variables
load_dotenv()

app = Flask(__name__)

# Authentication credentials
USERNAME = "canary"
PASSWORD = "resume2025"

# Authentication function
def check_auth(username, password):
    """Check if a username/password combination is valid."""
    return username == USERNAME and password == PASSWORD

def authenticate():
    """Send a 401 response to prompt for credentials."""
    return Response(
        "Could not verify your access level for that URL.\n"
        "You have to login with proper credentials", 401,
        {"WWW-Authenticate": 'Basic realm="Login Required"'}
    )

@app.before_request
def require_auth():
    """Require authentication for all routes."""
    auth = request.authorization
    if not auth or not check_auth(auth.username, auth.password):
        return authenticate()
    

def extract_text_from_docx(file):
    document = Document(file)
    return "\n".join([para.text for para in document.paragraphs])


def clean_json_block(text: str) -> str:
    """Clean triple-backtick-wrapped JSON content."""
    text = text.strip()
    if text.startswith("```json"):
        return text[7:].strip("` \n")
    elif text.startswith("```"):
        return text.strip("` \n")
    return text

def pad_list(lst, length, filler=""):
    """Pad or truncate list to the desired length."""
    return lst + [filler] * (length - len(lst)) if len(lst) < length else lst[:length]


def render_new_format(context, template_filename="TraditionalFormat.docx", output_path="Final_Resume.docx"):
    try:
        # Get absolute paths
        base_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(base_dir, 'templates', template_filename)
        output_path = os.path.join(base_dir, output_path)
        
        print(f"Template path: {template_path}")
        print(f"Output path: {output_path}")
        
        doc = DocxTemplate(template_path)
        doc.render(context)
        doc.save(output_path)
        return True
    except Exception as e:
        print(f"Error in render_new_format: {e}")
        return False

def add_formatted_paragraph(doc, text, font_name='Calibri Light', font_size=Pt(10), line_spacing=Pt(12), space_after=Pt(1)):
    """
    Add a paragraph with proper formatting, handling bold text marked with asterisks.
    Text between ** or * will be formatted as bold.
    """
    para = doc.add_paragraph()
    para_format = para.paragraph_format
    para_format.line_spacing = line_spacing
    para_format.space_after = space_after
    
    # Find all text between asterisks for bold formatting
    # This regex finds text between ** or * (single or double asterisks)
    pattern = r'\*\*(.*?)\*\*|\*(.*?)\*'
    last_end = 0
    
    for match in re.finditer(pattern, text):
        # Add text before the match
        if match.start() > last_end:
            run = para.add_run(text[last_end:match.start()])
            run.font.name = font_name
            run.font.size = font_size
        
        # Add the bold text - either from group 1 (** **) or group 2 (* *)
        bold_text = match.group(1) if match.group(1) is not None else match.group(2)
        run = para.add_run(bold_text)
        run.font.name = font_name
        run.font.size = font_size
        run.bold = True
        
        last_end = match.end()
    
    # Add any remaining text after the last match
    if last_end < len(text):
        run = para.add_run(text[last_end:])
        run.font.name = font_name
        run.font.size = font_size
    
    return para



@app.route('/')
def home():
    return render_template('index.html')

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

    # Agent to extract name, contact, location
    name_generator = Agent(
        role="Name Generator",
        goal="Extract structured personal information from a resume in structured JSON format.",
        backstory="An expert at reading resumes and identifying core personal information including name, location, phone number, email, and LinkedIn.",
        model="gpt-4o",
        verbose=True,
        allow_delegation=False
    )

    # Agent to extract ATS-friendly keywords
    keyword_generator = Agent(
        role="Keyword Generator",
        goal="Extract top 5 ATS-optimized keywords from resume content in structured JSON format.",
        backstory="An expert in parsing resumes and selecting the most relevant and strategic keywords that improve applicant tracking system performance.",
        model="gpt-4o",
        verbose=True,
        allow_delegation=False
    )

    summary_writer = Agent(
        role="Summary Writer",
        goal="Generate a concise 3-paragraph professional summary from a resume in structured JSON format.",
        backstory="An expert in creating ATS-optimized summaries tailored to the candidate's background. Each paragraph must be a maximum of two lines.",
        model="gpt-4o",
        verbose=True,
        allow_delegation=False
    )

    expertise_writer = Agent(
        role="Areas of Expertise Writer",
        goal="Generate 9 expertise keywords in 3x3 format without repeating top ATS keywords in structured JSON format.",
        backstory="Crafts strong, diverse area of expertise sections for resumes using relevant industry terminology.",
        model="gpt-4o",
        verbose=True,
        allow_delegation=False
    )

    achievement_writer = Agent(
        role="Achievements Writer",
        goal="Write 3–5 measurable achievement bullet points in structured JSON format.",
        backstory="Creates concise, impactful resume bullet points that showcase quantifiable outcomes and career highlights.",
        model="gpt-4o",
        verbose=True,
        allow_delegation=False
    )


    experience_writer = Agent(
        role="Job Description Writer",
        goal="Generate clean, ATS-friendly job experience sections in structured JSON format.",
        backstory="Expert in resume writing who creates well-formatted, third-person professional experience entries. Each includes company info, title, dates, a brief summary, and 1–4 measurable achievements.",
        model="gpt-4o",
        verbose=True,
        allow_delegation=False
    )

    additional_exp_writer = Agent(
        role="Additional Experience Writer",
        goal="Return earlier work experience entries in structured JSON format.",
        backstory="Summarizes older work experience in a clean, compact structure including company, location, title, and dates.",
        model="gpt-3.5-turbo",
        verbose=True,
        allow_delegation=False
    )

    education_writer = Agent(
        role="Education Writer",
        goal="Extract and return education entries in structured JSON format.",
        backstory="An expert in parsing and formatting educational history for professional resumes.",
        model="gpt-3.5-turbo",
        verbose=True,
        allow_delegation=False
    )

    cert_writer = Agent(
        role="Certifications Writer",
        goal="Extract and return certification entries in structured JSON format.",
        backstory="Specialist in identifying and formatting certifications and credentials from resumes.",
        model="gpt-3.5-turbo",
        verbose=True,
        allow_delegation=False
    )
 

    # Define tasks
    tasks = [

        Task(
            description=(
                f"Extract the following fields from the resume delimited by < >:\n"
                f"1. Full Name\n"
                f"2. Location (City, State)\n"
                f"3. Phone Number\n"
                f"4. Email Address\n"
                f"5. LinkedIn URL\n\n"
                f"Resume:\n<{resume_text}>"
            ),
            agent=name_generator,
            expected_output=(
                "Return a JSON object with the following keys:\n"
                "{\n"
                '  "full_name": "Jasmine Taylor",\n'
                '  "location": "New York, NY",\n'
                '  "phone": "555-123-4567",\n'
                '  "email": "jasmine@example.com",\n'
                '  "LinkedIn": "linkedin.com/in/jasminetaylor"\n'
                "}"
            )
        ),

        Task(
            description=(
                f"Read the resume below (delimited by < >) and extract the top 5 keywords optimized for Applicant Tracking Systems (ATS). "
                f"These should be skills or phrases that match professional strengths and job market terminology.\n\n"
                f"Resume:\n<{resume_text}>"
            ),
            agent=keyword_generator,
            expected_output=(
                "Return a JSON list of exactly 5 strings, like:\n"
                '["Strategic Planning", "Cross-functional Leadership", "Data Analysis", "Agile Methodology", "Process Improvement"]'
            )
        ),

        Task(
            description=(
                f"Read the resume below (delimited by < >) and write a concise 3-paragraph professional summary. "
                f"Each paragraph should be a maximum of 2 lines.\n\n"
                f"Resume:\n<{resume_text}>"
            ),
            agent=summary_writer,
            expected_output=(
                "Return a JSON object with the following structure:\n\n"
                "{\n"
                '  "summaries": [\n'
                '    "Paragraph 1",\n'
                '    "Paragraph 2",\n'
                '    "Paragraph 3"\n'
                "  ]\n"
                "}\n\n"
                "Ensure each paragraph is complete, ATS-friendly, and aligned with modern resume standards."
            )
        ),

        Task(
            description=(
                f"From the resume below, generate 9 unique 'Areas of Expertise' keywords arranged for visual formatting in 3 columns and 3 rows. "
                f"Do not repeat the top keywords already used earlier. Keep all keywords concise and resume-appropriate.\n\n"
                f"Resume:\n<{resume_text}>"
            ),
            agent=expertise_writer,
            expected_output=(
                "Return a JSON object like this:\n"
                '{\n'
                '  "expertise_keywords": [\n'
                '    "Leadership", "Agile", "Data-Driven Strategy",\n'
                '    "Budget Management", "Digital Marketing", "Campaign Management",\n'
                '    "Brand Identity & Growth", "Product Innovation", "Project Management"\n'
                '  ]\n'
                '}\n\n'
                "Only include keyword phrases. No explanations, no formatting, no column titles."
            )
        ),

        Task(
            description=(
                f"Based on the resume content below (delimited by < >), write 3–5 bullet points describing notable professional achievements. "
                f"Each bullet must be measurable, impactful, and no more than 2 lines long.\n\n"
                f"Resume:\n<{resume_text}>"
            ),
            agent=achievement_writer,
            expected_output=(
                "Return a JSON object with this structure:\n"
                "{\n"
                '  "notable_achievements": [\n'
                '    "Achievement 1",\n'
                '    "Achievement 2",\n'
                '    "Achievement 3"\n'
                "  ]\n"
                "}\n\n"
                "Only return the JSON. Do not include commentary, headers, or formatting."
            )
        ),

        Task(
            description=(
                f"Use the resume below (delimited by < >) to write structured job descriptions for the 2 most recent roles. "
                f"For each role, include:\n"
                f"- Company name\n"
                f"- Location (City, State or Country)\n"
                f"- Title\n"
                f"- Dates of employment\n"
                f"- 2–3 line summary of responsibilities\n"
                f"- 1–4 achievement bullet points with metrics\n\n"
                f"Resume:\n<{resume_text}>"
            ),
            agent=experience_writer,
            expected_output=(
                "Return a JSON object with the following structure:\n\n"
                "{\n"
                '  "experience": [\n'
                "    {\n"
                '      "company": "Google",\n'
                '      "location": "Mountain View, CA",\n'
                '      "title": "Senior Program Manager",\n'
                '      "dates": "2021–Present",\n'
                '      "description": "Leads global programs and manages strategic initiatives to deliver scalable business results.",\n'
                '      "achievements": [\n'
                '        {"label": "Led", "text": "global implementation of OKRs across 7 regions."},\n'
                '        {"label": "Drove", "text": "$3M in savings via vendor consolidation."}\n'
                '        {"label": "Designed", "text": "a performance dashboard adopted by all departments within 6 months."}\n'
                '        {"label": "Secured", "text": " board approval for a major cross-functional restructuring."}\n'
                '      ]\n'
                "    },\n"
                "    ...\n"
                "  ]\n"
                "}"
            )
        ),

        Task(
            description=(
                f"From the resume below (delimited by < >), extract earlier/older work experience entries (not among the most recent 2–3 roles). "
                f"For each job, return:\n"
                f"- Company name\n"
                f"- Location (City, State)\n"
                f"- Job Title\n"
                f"- Dates of Employment\n\n"
                f"Resume:\n<{resume_text}>"
            ),
            agent=additional_exp_writer,
            expected_output=(
                "Return a JSON object in the following structure:\n\n"
                "{\n"
                '  "earlier_experience": [\n'
                "    {\n"
                '      "company": "Duke University",\n'
                '      "location": "Durham, North Carolina",\n'
                '      "title": "Project Coordinator (Time-Limited Grant)",\n'
                '      "dates": "Jan 2011 – Jan 2012"\n'
                "    },\n"
                "    ...\n"
                "  ]\n"
                "}\n\n"
                "Do not include responsibilities, bullet points, or extra commentary — just the structured entries."
            )
        ),

        Task(
            description=(
                f"From the resume below (delimited by < >), extract all education entries. "
                f"For each entry, return:\n"
                f"- Institution name\n"
                f"- Location (City, State or Online)\n"
                f"- Credential (e.g. degree, diploma)\n\n"
                f"Resume:\n<{resume_text}>"
            ),
            agent=education_writer,
            expected_output=(
                "Return a JSON object with this structure:\n\n"
                "{\n"
                '  "education": [\n'
                "    {\n"
                '      "institution": "Harvard University",\n'
                '      "location": "Cambridge, MA",\n'
                '      "credential": "Master of Business Administration"\n'
                "    },\n"
                "    ...\n"
                "  ]\n"
                "}"
            )
        ),

        Task(
            description=(
                f"From the resume below (delimited by < >), extract all professional certifications or credentials. "
                f"For each entry, return:\n"
                f"- Institution (e.g. issuing organization)\n"
                f"- Location (e.g. Online or city)\n"
                f"- Credential (e.g. certificate title)\n\n"
                f"Resume:\n<{resume_text}>"
            ),
            agent=cert_writer,
            expected_output=(
                "Return a JSON object with this structure:\n\n"
                "{\n"
                '  "certifications": [\n'
                "    {\n"
                '      "institution": "Project Management Institute",\n'
                '      "location": "Online",\n'
                '      "credential": "Project Management Professional (PMP)"\n'
                "    },\n"
                "    ...\n"
                "  ]\n"
                "}"
            )
        )
    ]

    # Run the crew
    crew = Crew(agents=[name_generator, keyword_generator, summary_writer, expertise_writer, 
        achievement_writer, experience_writer, additional_exp_writer, education_writer, cert_writer
    ], tasks=tasks, verbose=True)
    
    result = crew.kickoff()

    compiled_resume_text = ""
    for task in crew.tasks:
        if hasattr(task, 'output'):
            compiled_resume_text += f"\n\n{task.output}"

    # Clean up the compiled resume text
    try:
        # Load template
        template_path = os.path.join(os.path.dirname(__file__), 'templates', 'TraditionalFormat.docx')
        doc = DocxTemplate("templates/TraditionalFormat.docx")
        context = {}

        # Extract Data from Crew Tasks
        for task in crew.tasks:
            if hasattr(task, 'output') and task.output:
                raw = (
                    getattr(task.output, 'raw_output', None)
                    or getattr(task.output, 'value', None)
                    or str(task.output)
                )
                cleaned = clean_json_block(raw)

                try:
                    parsed = json.loads(cleaned)
                    if isinstance(parsed, dict):
                        context.update(parsed)
                    elif isinstance(parsed, list) and task.agent.role == "Keyword Generator":
                        context["top_keywords"] = parsed
                except Exception as e:
                    print(f"❌ Could not parse output from {task.agent.role}:\n{cleaned[:300]}\nError: {e}")

        # Pad All Context Fields Required by the Template
        context["summaries"] = pad_list(context.get("summaries", []), 3, "")
        context["expertise_keywords"] = pad_list(context.get("expertise_keywords", []), 9, "")
        context["notable_achievements"] = pad_list(context.get("notable_achievements", []), 3, "")

        # Nested structure for experience
        empty_achievement = {"label": "", "text": ""}
        default_experience = {
            "company": "", "location": "", "title": "", "dates": "", "description": "",
            "achievements": pad_list([], 4, empty_achievement)
        }
        experience_raw = context.get("experience", [])
        context["experience"] = pad_list(
            [exp if "achievements" in exp else {**exp, "achievements": []} for exp in experience_raw],
            2,
            default_experience
        )
        for exp in context["experience"]:
            exp["achievements"] = pad_list(exp.get("achievements", []), 4, empty_achievement)

        # Optional sections
        for key in ["earlier_experience", "education", "certifications"]:
            context[key] = context.get(key, [])

        # Final Validation and Render
        required_keys = ["experience", "earlier_experience", "education", "certifications"]
        missing = [k for k in required_keys if k not in context]
        if missing:
            print(f"⚠️ Missing fields in context: {missing}")
        else:
            output_path = os.path.join(os.path.dirname(__file__), 'Final_Resume.docx')
            doc.render(context)
            doc.save(output_path)
            print("✅ Resume rendered and saved as Final_Resume.docx")

    except Exception as e:
        print(f"Error processing template: {e}")

    # Return the template as before
    compiled_resume_html = markdown(compiled_resume_text)
    return render_template('result.html', compiled_resume_html=compiled_resume_html)
    # return render_template('result.html', compiled_resume_text=compiled_resume_text)
    # Build context for the new format (replace with actual extraction logic)



@app.route('/download_new_format')
def download_new_format():
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(base_dir, "Final_Resume.docx")
        
        if not os.path.exists(file_path):
            return "Resume file not found. Please process your resume first.", 404
            
        return send_file(
            file_path,
            as_attachment=True,
            download_name="Final_Resume.docx",
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
    except Exception as e:
        print(f"Error downloading file: {e}")
        return f"Error downloading file: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
