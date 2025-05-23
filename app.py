import os
from dotenv import load_dotenv
from docx import Document
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

def write_text_to_docx(text, file_path):
    doc = Document()

    # Add full name (Calibri Light, 18pt)
    full_name = "Full Name"  # Replace with actual full name if available
    name_paragraph = doc.add_paragraph()
    name_run = name_paragraph.add_run(full_name)
    name_run.font.name = 'Calibri Light'
    name_run.font.size = Pt(18)
    name_paragraph.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

    # Add job title (Calibri Light, 17pt, blue color)
    job_title = "Job Title"  # Replace with actual job title if available
    title_paragraph = doc.add_paragraph()
    title_run = title_paragraph.add_run(job_title)
    title_run.font.name = 'Calibri Light'
    title_run.font.size = Pt(17)
    title_run.font.color.rgb = RGBColor(0, 112, 192)  # Blue color
    title_paragraph.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

    # Split the text into sections based on titles
    sections = text.split("\n\n")
    for section in sections:
        section = section.strip()
        if not section:
            continue

        # Check for section titles and format them
        if section.startswith("**Summary**"):
            heading = doc.add_heading("Summary", level=1)
            heading_run = heading.runs[0]
            heading_run.font.name = 'Calibri Light'
            heading_run.font.size = Pt(12.5)
            
            # Extract and clean summary content
            clean_content = section.replace("**Summary**", "").strip()
            
            # Look for paragraphs separated by blank lines
            paragraphs = []
            current_para = []
            
            # Split by lines first
            lines = clean_content.split('\n')
            for line in lines:
                line = line.strip()
                if not line and current_para:  # Empty line and we have content
                    paragraphs.append(' '.join(current_para))
                    current_para = []
                elif line:  # Non-empty line
                    current_para.append(line)
            
            # Don't forget to add the last paragraph if there is one
            if current_para:
                paragraphs.append(' '.join(current_para))
            
            # If we somehow didn't get at least one paragraph, fall back to the original method
            if not paragraphs:
                paragraphs = [clean_content]
            
            # Format each paragraph
            for paragraph_text in paragraphs:
                if not paragraph_text:
                    continue
                
                add_formatted_paragraph(doc, paragraph_text, space_after=Pt(6))

        elif section.startswith("**Areas of Expertise**"):
            heading = doc.add_heading("Areas of Expertise", level=1)
            heading_run = heading.runs[0]
            heading_run.font.name = 'Calibri Light'
            heading_run.font.size = Pt(12.5)
            expertise_keywords = section.replace("**Areas of Expertise**", "").strip().split("\n")
            for keyword in expertise_keywords:
                add_formatted_paragraph(doc, keyword, space_after=Pt(0))

        elif section.startswith("**Notable Achievements**"):
            heading = doc.add_heading("Notable Achievements", level=1)
            heading_run = heading.runs[0]
            heading_run.font.name = 'Calibri Light'
            heading_run.font.size = Pt(12.5)
            achievements = section.replace("**Notable Achievements**", "").strip().split("\n")
            for ach in achievements:
                add_formatted_paragraph(doc, ach)

        elif section.startswith("**Professional Experience**"):
            heading = doc.add_heading("Professional Experience", level=1)
            heading_run = heading.runs[0]
            heading_run.font.name = 'Calibri Light'
            heading_run.font.size = Pt(12.5)
            experience_entries = section.replace("**Professional Experience**", "").strip().split("\n")
            for entry in experience_entries:
                # Use the add_formatted_paragraph function with special handling for this section
                para = add_formatted_paragraph(doc, entry)
                # If the entire entry isn't bold, make it bold (company names, etc.)
                if len(para.runs) == 1 and not para.runs[0].bold:
                    para.runs[0].bold = True

        elif section.startswith("**Additional Experience**"):
            heading = doc.add_heading("Additional Experience", level=1)
            heading_run = heading.runs[0]
            heading_run.font.name = 'Calibri Light'
            heading_run.font.size = Pt(12.5)
            additional_experience_entries = section.replace("**Additional Experience**", "").strip().split("\n")
            for entry in additional_experience_entries:
                add_formatted_paragraph(doc, entry)

        elif section.startswith("**Education**"):
            heading = doc.add_heading("Education", level=1)
            heading_run = heading.runs[0]
            heading_run.font.name = 'Calibri Light'
            heading_run.font.size = Pt(12.5)
            education_entries = section.replace("**Education**", "").strip().split("\n")
            for edu in education_entries:
                add_formatted_paragraph(doc, edu)

        elif section.startswith("**Certifications**"):
            heading = doc.add_heading("Certifications", level=1)
            heading_run = heading.runs[0]
            heading_run.font.name = 'Calibri Light'
            heading_run.font.size = Pt(12.5)
            certifications = section.replace("**Certifications**", "").strip().split("\n")
            for cert in certifications:
                add_formatted_paragraph(doc, cert)
            
            # Add extra space after Certifications section
            spacing_para = doc.add_paragraph()
            spacing_para.paragraph_format.space_after = Pt(12)  # Add extra spacing

        elif section.startswith("**Languages**"):
            heading = doc.add_heading("Languages", level=1)
            heading_run = heading.runs[0]
            heading_run.font.name = 'Calibri Light'
            heading_run.font.size = Pt(12.5)
            languages_text = section.replace("**Languages:**", "").strip()
            add_formatted_paragraph(doc, languages_text)

        else:
            # Add any other content as normal text
            add_formatted_paragraph(doc, section)

    # Save the document
    doc.save(file_path)

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
    output_path = "new.docx"
    
    # Slice only relevant part of resume for education
    #education_section = resume_text.split("EDUCATION")[1]

    # Slice only relevant part of resume for experience
    #experience_section = resume_text.split("EXPERIENCE")[1]
    
    # Initialize OpenAI key (needed internally by CrewAI)
    openai_api_key = os.getenv('OPENAI_API_KEY')
    if not openai_api_key:
        return "OpenAI API Key not found!", 500

    # Define CrewAI agents
    keyword_generator = Agent(
        role="Keyword Generator Expert",
        goal="Suggest top 5 ATS-proof keywords based on resume and job title.",
        backstory="An expert in optimizing resumes for applicant tracking systems.",
        model="gpt-4o",
        verbose=True,
        allow_delegation=False
    )

    summary_writer = Agent(
        role="Senior Writer for Summary Section",
        goal="Create a three-paragraph ATS-proof summary from the resume. Max two lines on each paragraph.",
        backstory="Writes concise professional summaries tailored to job title.",
        model="gpt-4o",
        verbose=True,
        allow_delegation=False
    )

    expertise_writer = Agent(
        role="Senior Writer for Areas of Expertise Section",
        goal="Generate 9 expertise keywords in 3 columns, 3 rows format.",
        backstory="Suggests strong area of expertise keywords for resumes.",
        model="gpt-4o",
        verbose=True,
        allow_delegation=False
    )

    achievement_writer = Agent(
        role="Senior Writer for Achievements Section",
        goal="Write 3–5 measurable achievements bullet points.",
        backstory="Creates bullet points that demonstrate quantifiable success.",
        model="gpt-4o",
        verbose=True,
        allow_delegation=False
    )

    experience_writer = Agent(
        role="Senior Job Description Writer",
        goal="Create job descriptions for 3 most recent roles with company info, title, dates, summary, and measurable impact in bullet points.",
        backstory="Expert in writing clean and structured work experience entries for resumes. Do not use first person style.",
        model="gpt-4o",
        verbose=True,
        allow_delegation=False
    )

    additional_exp_writer = Agent(
        role="Senior Writer for Additional Experience Section",
        goal="List older work experience entries in two-line format.",
        backstory="List past work experiences in a compact and clear way.",
        model="gpt-4o",
        verbose=True,
        allow_delegation=False
    )

    education_writer = Agent(
        role="Senior Writer for Education Section",
        goal="List education, one per line.",
        backstory="Summarizes education for resumes.",
        model="gpt-4o",
        verbose=True,
        allow_delegation=False
    )

    cert_writer = Agent(
        role="Senior Writer for Certifications Section",
        goal="List certifications, one per line.",
        backstory="List certifications for resumes.",
        model="gpt-4o",
        verbose=True,
        allow_delegation=False
    )

    language_writer = Agent(
        role="Senior Writer for Language Section",
        goal="List known languages in a single line.",
        backstory="Formats multilingual proficiencies.",
        model="gpt-4o",
        verbose=True,
        allow_delegation=False
    )
 

    # Define tasks
    tasks = [
        Task(
            description=f"Given the following resume, generate the top 5 keywords that are optimized for applicant tracking systems (ATS).\n\nResume:\n{resume_text}",
            agent=keyword_generator,
            expected_output="A list of 5 ATS-optimized keywords.\n"
            "The top header must include: Full name, city/state (or location), phone number, email, and LinkedIn – all in one or two compact lines.\n"
            "The professional title must be bold and centered directly under the contact info.\n"
            "On the next line, add 4–5 ATS-optimized keywords in a single line spaced with •."
        ),
        Task(
            description=f"Using the resume, write a 3-paragraph professional summary. Each paragraph should be two lines max. Format your response with a blank line between each paragraph.\n\nResume:\n{resume_text}",
            agent=summary_writer,
            expected_output="Three short paragraphs summarizing the candidate, with a blank line between each paragraph.\n"
            "Create title in bold: **Summary**\n\n"
            "First paragraph\n\n"
            "Second paragraph\n\n"
            "Third paragraph"
        ),
        Task(
            description=f"Based on the resume, generate 9 'Areas of Expertise' keywords formatted in 3 columns and 3 rows. Do not repeat the keywords generated by keyword_generator agent.\n\nResume:\n{resume_text}",
            agent=expertise_writer,
            expected_output="Nine keywords in a 3x3 grid format without column titles.\n"
            "Create title in bold: Areas of Expertise. This section is a grid with 9 keywords, arranged in 3 columns and 3 rows, center-aligned or evenly spaced with '•'."
        ),
        Task(
            description=f"From the following resume, write 3–5 bullet points describing notable achievements. Each bullet must be measurable and max 2 lines.\n\nResume:\n{resume_text}",
            agent=achievement_writer,
            expected_output="3–5 short bullet points describing notable achievements with metrics or impact.\n"
            "Bullet points must begin with a bolded action keyword, followed by a colon and a 1–2 line measurable accomplishment.\n"          
            "Create title in bold: Notable Achievements." 
        ),
        Task(
            description=f"Use this resume to create job descriptions for the 3 most recent roles. For each: line 1 is Company, City, Country; line 2 is Job Title and Dates; followed by a 2-3 line summary and 1–3 bullet points of achievements.\n\nResume:\n{resume_text}",
            agent=experience_writer,
            expected_output="3 job experiences formatted as described.\n"
            "Create  title in bold: Professional Experience.\n"
            "   - Line 1: Company Name – City, Country\n"
            "   - Line 2: Job Title | Start Date – End Date\n"
            "   - Followed by a 2–3 line responsibility summary\n"
            "   - Then 1–3 bullet points of achievements, each starting with a bolded keyword."
        ),
        Task(
            description=f"Summarize other job experience in the resume using a 2-line format per job. Do not add extra lines or job responsibilities.\n\nResume:\n{resume_text}",
            agent=additional_exp_writer,
            expected_output="Older jobs in 2-line format (company + role + dates).\n"
             "Create title in bold: Additional Experience. Only two lines.\n"
            "   - Line 1: Company – City, Country. Company in bold.\n"
            "   - Line 2: Job Title | Start Date – End Date. Job Title in bold.\n"
            "   - Do not add extra content beyond these lines."
        ),
        Task(
            description=f"Extract education from this resume. Format each entry on one line.\n\nResume:\n{resume_text}",
            agent=education_writer,
            expected_output= "Each education entry is on one line: University • Degree.\n"
            "Create title in bold: Education."
        ),
        Task(
            description=f"Extract certifications from this resume. Format each entry on one line.\n\nResume:\n{resume_text}",
            agent=cert_writer,
            expected_output= "Full name of certifications listed, one per line.\n"
            "Create title in bold: Certifications"
        ),
        Task(
            description=f"List all languages mentioned in the following resume on one line.\n\nResume:\n{resume_text}",
            agent=language_writer,
            expected_output="Languages should be listed in one single line, near the bottom. Start with 'Languages:' in bold"
        )

        ]

    # Run the crew
    crew = Crew(agents=[keyword_generator, summary_writer, expertise_writer, achievement_writer,
        experience_writer, additional_exp_writer, education_writer, cert_writer, language_writer
    ], tasks=tasks, verbose=True)
    
    result = crew.kickoff()

    compiled_resume_text = ""
    for task in crew.tasks:
        if hasattr(task, 'output'):
            compiled_resume_text += f"\n\n{task.output}"

    write_text_to_docx(str(compiled_resume_text).strip(), output_path)
    compiled_resume_html = markdown(compiled_resume_text)
    return render_template('result.html', compiled_resume_html=compiled_resume_html)
    #return render_template('result.html', compiled_resume_text=compiled_resume_text)

@app.route('/download')
def download():
    return send_file("new.docx", as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
