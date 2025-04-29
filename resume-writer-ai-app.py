import streamlit as st
import warnings
import os
from docx import Document
from dotenv import load_dotenv
from crewai import Crew, Agent, Task

# Ignore warnings
warnings.filterwarnings('ignore')

# Load environment variables
load_dotenv()

# --- Function to read a Word (.docx) file ---
def extract_text_from_docx(uploaded_file):
    document = Document(uploaded_file)
    return "\n".join([para.text for para in document.paragraphs])

# --- Streamlit App ---
st.title("📄 Resume Writer AI")
st.write("Upload your resume (.docx) and let the AI analyze it.")

uploaded_file = st.file_uploader("Upload Resume (.docx)", type=["docx"])

if uploaded_file:
    uploaded_resume_text = extract_text_from_docx(uploaded_file)

    openai_api_key = os.getenv('OPENAI_API_KEY')
    if not openai_api_key:
        st.error("❌ OpenAI API Key not found. Please set it in your environment variables.")
        st.stop()

    # --- Define the Agents ---
    cv_extractor = Agent(
        role="CV Extractor",
        goal="Extract structured data from resume text",
        backstory="You are a professional CV parser. You read and structure resumes into clearly defined parts like experience, skills, education.",
        verbose=True,
        allow_delegation=False,
        model="gpt-3.5-turbo"
    )

    keyword_advisor = Agent(
        role="Keyword Advisor",
        goal="Recommend top 5 keywords based on the resume using the custom GPT",
        backstory="You specialize in job-matching keywords to help pass ATS.",
        verbose=True,
        allow_delegation=False,
        model="gpt-3.5-turbo"
    )

    # --- Define the Tasks ---
    task1 = Task(
        description=f"Extract structured data (experience, skills, education, certifications, etc.) from the following resume:\n\n{uploaded_resume_text}",
        agent=cv_extractor,
        expected_output="A structured JSON object containing experience, skills, education, and certifications."
    )

    task2 = Task(
        description=f"Based on the resume content, suggest 5 best ATS keywords. Resume:\n\n{uploaded_resume_text}",
        agent=keyword_advisor,
        expected_output="Top 5 keywords most relevant to the resume content."
    )

    # --- Create the Crew ---
    crew = Crew(
        agents=[cv_extractor, keyword_advisor],
        tasks=[task1, task2],
        verbose=True
    )

    if st.button("🚀 Process Resume"):
        with st.spinner("Running Resume Writer AI..."):
            results = crew.kickoff()

            # Display Results
            if not isinstance(results, str):
                results = str(results)
            st.success("✅ Resume Processing Complete!")
            st.markdown("### Final CV Output")
            st.markdown(results)

