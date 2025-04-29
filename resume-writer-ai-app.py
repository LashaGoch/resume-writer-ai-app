import streamlit as st
import warnings
import os
from docx import Document
from crewai import Crew, Agent, Task
from dotenv import load_dotenv
from openai import OpenAI

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
st.write("Upload your resume (.docx) to enhance and analyze it with AI agents.")

uploaded_file = st.file_uploader("Upload Resume (.docx)", type=["docx"])

if uploaded_file:
    uploaded_resume_text = extract_text_from_docx(uploaded_file)

    # Debugging API Key (optional)
    openai_api_key = os.getenv('OPENAI_API_KEY')
    if not openai_api_key:
        st.error("❌ OpenAI API Key not found. Please set it in your environment variables.")
        st.stop()

    # --- Define the Agents ---
    cv_extractor = Agent(
        role="CV Extractor",
        goal="Extract structured data from resume text",
        backstory="You are a professional CV parser. You read and structure resumes into clearly defined parts like experience, skills, education.",
        model="gpt-3.5-turbo",
        allow_delegation=False,
        verbose=True
    )

    keyword_advisor = Agent(
        role="Keyword Advisor",
        goal="Recommend top 5 keywords based on the resume using the custom GPT",
        backstory="You specialize in job-matching keywords. You use the Resume Keyword Advisor GPT to find best 5 terms to help the resume pass ATS.",
        model="gpt-3.5-turbo",
        allow_delegation=False,
        verbose=True
    )

    # --- Define the Tasks ---
    task1 = Task(
        description=f"Extract structured data (experience, skills, education, certifications, etc.) from the following resume:\n\n{uploaded_resume_text}",
        agent=cv_extractor,
        expected_output="A structured JSON object containing experience, skills, education, and certifications."
    )

    task2 = Task(
        description=f"Based on the resume content, use this GPT to extract 5 resume keywords: https://chatgpt.com/g/g-5cMD7LP1t-resume-keyword-advisor. Input text:\n\n{uploaded_resume_text}",
        agent=keyword_advisor,
        expected_output="A list of the top 5 keywords most relevant to the resume content."
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

