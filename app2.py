
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
    topic_category: str = Field(description="Specific geometry topic (Lines/Angles, Circles, or Triangles)")
    questions: List[QuizResult]
    correct_count: int
    total_count: int
    accuracy: float = Field(description="Percentage of correct answers")

class TopicAnalysisList(BaseModel):
    analyses: List[TopicAnalysis] = Field(description="List of analyses for each geometry topic")

class ExpertiseLevel(BaseModel):
    topic: str
    level: str = Field(description="Current expertise level (Beginner, Intermediate, or Advanced)")
    reasoning: str = Field(description="Explanation for the assigned level")

class ExpertiseLevelList(BaseModel):
    levels: List[ExpertiseLevel] = Field(description="List of expertise levels for each topic")

class GeometryQuizApp:
    def __init__(self):
        self.educhain = Educhain()
        self.llm = ChatOpenAI(model="gpt-4")
        self.memory = Memory.from_config(config_dict={
            "graph_store": {
                "provider": "neo4j",
                "config": {
                    "url": "neo4j+s://c6059d7b.databases.neo4j.io",
                    "username": "neo4j",
                    "password": "OOn7tXNU9_0AzyjRxUtu5ABwTrptg4A62bfgRZ77pNQ"
                }
            },
            "version": "v1.1"
        })

    def generate_questions(self, topic: str, level: str, num_questions: int = 5) -> List[Dict]:
        # Create custom instructions based on level and topic
        instructions = f"""
        Generate {num_questions} multiple-choice questions for GRE Geometry.
        Topic: {topic}
        Level: {level}
        
        Requirements:
        - Questions should be {level.lower()} level
        - Include 4 options for each question
        - Focus on core GRE geometry concepts
        - Provide clear and unambiguous correct answers
        """
        
        # Generate questions using Educhain
        questions = self.educhain.qna_engine.generate_questions(
            topic=f"GRE Geometry - {topic}",
            num=num_questions,
            custom_instructions=instructions
        )
        
        # Format questions for our app
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

    def update_memory(self, user_id: str, topic: str, level: str):
        self.memory.add(
            f"Updated expertise level for {topic}: {level}",
            user_id=user_id
        )

def main():
    st.set_page_config(page_title="GRE Geometry Master", layout="wide")
    
    # Initialize the quiz app
    if 'quiz_app' not in st.session_state:
        st.session_state.quiz_app = GeometryQuizApp()
    
    # Initialize session state variables
    if 'current_question' not in st.session_state:
        st.session_state.current_question = 0
    if 'results' not in st.session_state:
        st.session_state.results = []
    if 'quiz_active' not in st.session_state:
        st.session_state.quiz_active = False
    if 'progress_data' not in st.session_state:
        st.session_state.progress_data = {}
    if 'user_id' not in st.session_state:
        st.session_state.user_id = f"user_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # App title and description
    st.title("🎯 GRE Geometry Master")
    st.markdown("""
    Master GRE geometry concepts through adaptive quizzes powered by Educhain! 
    Track your progress and improve your expertise in:
    - Lines and Angles
    - Circles
    - Triangles
    """)

    # Sidebar for topic selection and quiz control
    with st.sidebar:
        st.header("Quiz Controls")
        topic = st.selectbox("Select Topic", ["Lines and Angles", "Circles", "Triangles"])
        
        if not st.session_state.quiz_active:
            num_questions = st.slider("Number of Questions", 3, 10, 5)
            if st.button("Start Quiz"):
                st.session_state.quiz_active = True
                st.session_state.current_question = 0
                st.session_state.results = []
                
                # Get current level from progress data or default to Beginner
                current_level = st.session_state.progress_data.get(topic, {}).get('level', 'Beginner')
                
                # Generate questions using Educhain
                with st.spinner("Generating questions..."):
                    st.session_state.current_questions = st.session_state.quiz_app.generate_questions(
                        topic=topic,
                        level=current_level,
                        num_questions=num_questions
                    )
                st.rerun()

    # Main quiz area
    if st.session_state.quiz_active:
        if st.session_state.current_question < len(st.session_state.current_questions):
            question = st.session_state.current_questions[st.session_state.current_question]
            
            # Display progress
            progress = st.session_state.current_question / len(st.session_state.current_questions)
            st.progress(progress)
            
            # Display question
            st.subheader(f"Question {st.session_state.current_question + 1}")
            st.write(question["question"])
            
            # Radio buttons for options
            answer = st.radio("Select your answer:", question["options"], key=f"q_{st.session_state.current_question}")
            
            # Submit button
            if st.button("Submit Answer"):
                is_correct = st.session_state.quiz_app.evaluate_answer(question, answer)
                st.session_state.results.append(is_correct)
                
                if is_correct:
                    st.success("Correct! 🎉")
                else:
                    st.error(f"Incorrect. The correct answer is: {question['correct_answer']}")
                
                st.session_state.current_question += 1
                if st.session_state.current_question < len(st.session_state.current_questions):
                    st.rerun()
                else:
                    # Analyze results and update memory
                    analysis = st.session_state.quiz_app.analyze_results(st.session_state.results, topic)
                    st.session_state.progress_data[topic] = analysis
                    st.session_state.quiz_app.update_memory(
                        st.session_state.user_id,
                        topic,
                        analysis['level']
                    )
                    st.session_state.quiz_active = False
                    st.rerun()

    # Display results and progress
    if not st.session_state.quiz_active and topic in st.session_state.progress_data:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Latest Quiz Results")
            analysis = st.session_state.progress_data[topic]
            st.metric("Accuracy", f"{analysis['accuracy']:.1f}%")
            st.metric("Level", analysis['level'])
            st.write(f"**Reasoning:** {analysis['reasoning']}")

        with col2:
            st.subheader("Progress Visualization")
            if st.session_state.progress_data:
                df = pd.DataFrame([
                    {
                        'Topic': t,
                        'Accuracy': data['accuracy'],
                        'Level': data['level']
                    }
                    for t, data in st.session_state.progress_data.items()
                ])
                
                fig = px.bar(df, x='Topic', y='Accuracy',
                            color='Level',
                            title='Performance by Topic',
                            labels={'Accuracy': 'Accuracy (%)'})
                st.plotly_chart(fig)

    # Memory Overview
    if st.session_state.progress_data:
        st.markdown("---")
        st.subheader("📊 Learning Journey")
        memory_results = st.session_state.quiz_app.memory.search(
            f"What are my current expertise levels?",
            user_id=st.session_state.user_id
        )
        st.json(memory_results)

    # Study resources
    st.markdown("---")
    st.subheader("📚 Study Resources")
    with st.expander("Key Concepts"):
        st.markdown("""
        ### Lines and Angles
        - Parallel lines and transversals
        - Complementary and supplementary angles
        - Angle relationships in geometric figures
        
        ### Circles
        - Radius, diameter, and circumference relationships
        - Arc length and sector area calculations
        - Tangent and secant properties
        - Inscribed and central angles
        
        ### Triangles
        - Triangle inequality theorem
        - Special triangles (30-60-90, 45-45-90)
        - Area and perimeter formulas
        - Similar and congruent triangles
        """)

if __name__ == "__main__":
    main()
