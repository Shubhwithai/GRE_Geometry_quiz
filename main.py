import streamlit as st
import plotly.express as px
import pandas as pd
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import ChatPromptTemplate
from educhain import Educhain
from mem0 import Memory
import json
import os
from datetime import datetime

# Pydantic models for quiz structure
class QuizResult(BaseModel):
    question: str
    result: str  # "correct" or "incorrect"

class TopicAnalysis(BaseModel):
    topic_category: str = Field(description="Specific Newton's Law topic (1st, 2nd, or 3rd Law)")
    questions: List[QuizResult]
    correct_count: int
    total_count: int
    accuracy: float = Field(description="Percentage of correct answers")

class TopicAnalysisList(BaseModel):
    analyses: List[TopicAnalysis] = Field(description="List of analyses for each Newton's Law topic")

class ExpertiseLevel(BaseModel):
    topic: str
    level: str = Field(description="Current expertise level (Beginner, Intermediate, or Advanced)")
    reasoning: str = Field(description="Explanation for the assigned level")

class ExpertiseLevelList(BaseModel):
    levels: List[ExpertiseLevel] = Field(description="List of expertise levels for each topic")

class StudentQuizResult(BaseModel):
    student_name: str
    timestamp: datetime
    topic: str
    accuracy: float
    level: str
    correct_count: int
    total_count: int

class NewtonsLawQuizApp:
    def __init__(self):
        self.educhain = Educhain()
        self.llm = ChatOpenAI(model="gpt-4o")
        self.memory = Memory.from_config(config_dict={
            "graph_store": {
                "provider": "neo4j",
                "config": {
                    "url": "neo4j+s://bb3b5969.databases.neo4j.io",
                    "username": "neo4j",
                    "password": "YT__sW785DiB_M9BBKkWWh7XTv-23mfB05RvMgwvCAI"
                }
            },
            "version": "v1.1"
        })
        
        # Initialize results storage
        if not os.path.exists('student_results'):
            os.makedirs('student_results')

    def generate_questions(self, topic: str, level: str, num_questions: int = 5) -> List[Dict]:
        instructions = f"""
        Generate {num_questions} multiple-choice questions on Newton's Laws of Motion.
        Topic: {topic}
        Level: {level}
        
        Requirements:
        - Questions should be {level.lower()} level
        - Include 4 options for each question
        - Focus on core concepts of Newton's laws
        - Provide clear and unambiguous correct answers
        """
        
        questions = self.educhain.qna_engine.generate_questions(
            topic=f"Newton's Laws - {topic}",
            num=num_questions,
            custom_instructions=instructions
        )
        
        formatted_questions = []
        for q in questions.questions:
            formatted_questions.append({
                "question": q.question,
                "options": q.options,
                "correct_answer": q.answer
            })
        
        return formatted_questions

    def evaluate_answer(self, question: Dict, user_answer: str) -> bool:
        return user_answer == question["correct_answer"]

    def analyze_results(self, results: List[bool], topic: str) -> Dict:
        correct_count = sum(results)
        total_count = len(results)
        accuracy = (correct_count / total_count * 100) if total_count > 0 else 0

        if accuracy < 60:
            level = "Beginner"
            reasoning = "Needs more practice with fundamental concepts"
        elif accuracy < 85:
            level = "Intermediate"
            reasoning = "Good understanding but room for improvement"
        else:
            level = "Advanced"
            reasoning = "Excellent mastery of the topic"

        return {
            "topic": topic,
            "correct_count": correct_count,
            "total_count": total_count,
            "accuracy": accuracy,
            "level": level,
            "reasoning": reasoning
        }

    def save_student_result(self, result: StudentQuizResult):
        filename = f"student_results/{result.student_name.lower().replace(' ', '_')}_results.json"
        
        existing_results = []
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                existing_results = json.load(f)
        
        new_result = {
            "student_name": result.student_name,
            "timestamp": result.timestamp.isoformat(),
            "topic": result.topic,
            "accuracy": result.accuracy,
            "level": result.level,
            "correct_count": result.correct_count,
            "total_count": result.total_count
        }
        existing_results.append(new_result)
        
        with open(filename, 'w') as f:
            json.dump(existing_results, f, indent=2)

    def get_student_history(self, student_name: str) -> List[Dict]:
        filename = f"student_results/{student_name.lower().replace(' ', '_')}_results.json"
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                return json.load(f)
        return []

def initialize_session_state():
    """Initialize all session state variables"""
    if 'quiz_app' not in st.session_state:
        st.session_state.quiz_app = NewtonsLawQuizApp()
    if 'current_question' not in st.session_state:
        st.session_state.current_question = 0
    if 'questions' not in st.session_state:
        st.session_state.questions = None
    if 'results' not in st.session_state:
        st.session_state.results = []
    if 'quiz_active' not in st.session_state:
        st.session_state.quiz_active = False
    if 'progress_data' not in st.session_state:
        st.session_state.progress_data = {}
    if 'current_topic' not in st.session_state:
        st.session_state.current_topic = None
    if 'submitted_answer' not in st.session_state:
        st.session_state.submitted_answer = False

def start_quiz(topic: str, num_questions: int):
    """Start a new quiz"""
    st.session_state.quiz_active = True
    st.session_state.current_question = 0
    st.session_state.results = []
    st.session_state.current_topic = topic
    st.session_state.submitted_answer = False
    
    current_level = st.session_state.progress_data.get(topic, {}).get('level', 'Beginner')
    st.session_state.questions = st.session_state.quiz_app.generate_questions(
        topic=topic,
        level=current_level,
        num_questions=num_questions
    )

def submit_answer():
    """Handle answer submission"""
    st.session_state.submitted_answer = True

def next_question():
    """Move to next question"""
    st.session_state.current_question += 1
    st.session_state.submitted_answer = False

# Add this function to display the quiz summary
def display_quiz_summary(analysis: Dict):
    st.subheader("Quiz Summary")
    st.write(f"**Topic:** {analysis['topic']}")
    st.write(f"**Correct Answers:** {analysis['correct_count']} out of {analysis['total_count']}")
    st.write(f"**Accuracy:** {analysis['accuracy']}%")
    st.write(f"**Expertise Level:** {analysis['level']}")
    st.write(f"**Reasoning:** {analysis['reasoning']}")

def end_quiz(student_name: str):
    """End the quiz and save results, then display summary"""
    # Analyze results for the current topic
    analysis = st.session_state.quiz_app.analyze_results(
        st.session_state.results, 
        st.session_state.current_topic
    )
    # Save the analysis data
    st.session_state.progress_data[st.session_state.current_topic] = analysis

    # Create and save student result
    student_result = StudentQuizResult(
        student_name=student_name,
        timestamp=datetime.now(),
        topic=st.session_state.current_topic,
        accuracy=analysis['accuracy'],
        level=analysis['level'],
        correct_count=analysis['correct_count'],
        total_count=analysis['total_count']
    )
    st.session_state.quiz_app.save_student_result(student_result)
    
    # Set quiz as inactive
    st.session_state.quiz_active = False
    
    # Display the quiz summary
    display_quiz_summary(analysis)

# Main function setup remains the same, only modified here for quiz summary at end

def main():
    st.set_page_config(page_title="Newton's Laws Mastery", layout="wide")
    
    initialize_session_state()
    
    st.markdown("<h3>🎯 Mastery Learning with mem0 & Educhain</h3>", unsafe_allow_html=True)
    
    student_name = st.text_input("Enter Student Name", key="student_name")
    if not student_name:
        st.warning("Please enter your name to begin")
        return
    
    st.markdown("""
    Master Newton's Laws concepts through adaptive quizzes powered by Educhain With Mem0!
    Track your progress and improve your expertise in:
    - Newton's 1st Law
    - Newton's 2nd Law
    - Newton's 3rd Law
    """)

    # Sidebar
    with st.sidebar:
        st.header("Quiz Controls")
        topic = st.selectbox("Select Topic", ["Newton's 1st Law", "Newton's 2nd Law", "Newton's 3rd Law"])
        
        # Display student's previous results
        st.subheader("Previous Results")
        student_history = st.session_state.quiz_app.get_student_history(student_name)
        if student_history:
            history_df = pd.DataFrame(student_history)
            history_df['timestamp'] = pd.to_datetime(history_df['timestamp'])
            st.line_chart(history_df.set_index('timestamp')['accuracy'])
        
        if not st.session_state.quiz_active:
            num_questions = st.slider("Number of Questions", 3, 10, 5)
            if st.button("Start Quiz"):
                start_quiz(topic, num_questions)

    # Quiz Area
    if st.session_state.quiz_active and st.session_state.questions:
        # Display progress
        progress = st.session_state.current_question / len(st.session_state.questions)
        st.progress(progress)
        
        # Display current question
        question = st.session_state.questions[st.session_state.current_question]
        st.write(f"Question {st.session_state.current_question + 1}: {question['question']}")
        options = question['options']
        selected_option = st.radio("Choose an answer", options, key="selected_answer")
        
        # Submit answer
        if not st.session_state.submitted_answer:
            if st.button("Submit Answer"):
                is_correct = st.session_state.quiz_app.evaluate_answer(question, selected_option)
                result = QuizResult(question=question['question'], result="correct" if is_correct else "incorrect")
                st.session_state.results.append(result.result == "correct")
                submit_answer()
        
        if st.session_state.submitted_answer:
            # Display result
            if st.session_state.results[-1]:
                st.success("Correct!")
            else:
                st.error("Incorrect!")
            if st.session_state.current_question < len(st.session_state.questions) - 1:
                if st.button("Next Question"):
                    next_question()
            else:
                if st.button("End Quiz"):
                    end_quiz(student_name)  # End quiz and show results

    # Display the summary if the quiz has ended
    if not st.session_state.quiz_active and 'progress_data' in st.session_state:
        last_topic = st.session_state.current_topic
        if last_topic and last_topic in st.session_state.progress_data:
            st.write("### Quiz Results")
            display_quiz_summary(st.session_state.progress_data[last_topic])

if __name__ == "__main__":
    main()
