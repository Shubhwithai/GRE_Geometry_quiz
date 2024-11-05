import streamlit as st
import pandas as pd
from typing import List, Dict
from pydantic import BaseModel, Field
from educhain import Educhain
from mem0 import Memory
from datetime import datetime

class QuizResult(BaseModel):
    question: str
    result: str  # "correct" or "incorrect"

class TopicAnalysis(BaseModel):
    topic: str
    correct_count: int
    total_count: int
    accuracy: float
    level: str
    reasoning: str

class GREGeometryQuizApp:
    def __init__(self, student_name: str):
        self.student_name = student_name
        self.educhain = Educhain()
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
        self.topics = ["Lines and Angles", "Circles", "Triangles"]
        self.progress_data: Dict[str, TopicAnalysis] = {}
        self.user_id = f"user_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    def generate_questions(self, topic: str, level: str, num_questions: int = 5) -> List[Dict]:
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
        
        questions = self.educhain.qna_engine.generate_questions(
            topic=f"GRE Geometry - {topic}",
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

    def analyze_results(self, results: List[bool], topic: str) -> TopicAnalysis:
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

        return TopicAnalysis(
            topic=topic,
            correct_count=correct_count,
            total_count=total_count,
            accuracy=accuracy,
            level=level,
            reasoning=reasoning
        )

    def update_memory(self, topic: str, level: str):
        self.memory.add(
            f"{self.student_name}'s expertise level for {topic}: {level}",
            user_id=self.user_id
        )

def main():
    st.set_page_config(page_title="GRE Geometry Master", layout="wide")
    
    # Get student name
    student_name = st.text_input("Enter your name:", "Student")
    quiz_app = GREGeometryQuizApp(student_name)

    # App title and description
    st.title(f"🎯 GRE Geometry Master - {quiz_app.student_name}")
    st.markdown("""
    Master GRE geometry concepts through adaptive quizzes powered by Educhain!
    """)

    # Sidebar for topic selection and quiz control
    with st.sidebar:
        st.header("Quiz Controls")
        topic = st.selectbox("Select Topic", quiz_app.topics)
        
        if "current_question" not in st.session_state:
            st.session_state.current_question = 0
        if "results" not in st.session_state:
            st.session_state.results = []
        if "quiz_active" not in st.session_state:
            st.session_state.quiz_active = False

        if not st.session_state.quiz_active:
            num_questions = st.slider("Number of Questions", 3, 10, 5)
            if st.button("Start Quiz"):
                st.session_state.quiz_active = True
                st.session_state.current_question = 0
                st.session_state.results = []

                # Get current level from progress data or default to Beginner
                current_level = quiz_app.progress_data.get(topic, TopicAnalysis(
                    topic=topic,
                    correct_count=0,
                    total_count=0,
                    accuracy=0,
                    level="Beginner",
                    reasoning="Needs more practice with fundamental concepts"
                )).level

                # Generate questions using Educhain
                with st.spinner("Generating questions..."):
                    st.session_state.current_questions = quiz_app.generate_questions(
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
                is_correct = quiz_app.evaluate_answer(question, answer)
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
                    analysis = quiz_app.analyze_results(st.session_state.results, topic)
                    quiz_app.progress_data[topic] = analysis
                    quiz_app.update_memory(topic, analysis.level)
                    st.session_state.quiz_active = False
                    st.rerun()

    # Display results and progress
    if not st.session_state.quiz_active and quiz_app.progress_data:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Latest Quiz Results")
            analysis = quiz_app.progress_data[topic]
            st.metric("Accuracy", f"{analysis.accuracy:.1f}%")
            st.metric("Level", analysis.level)
            st.write(f"**Reasoning:** {analysis.reasoning}")

        with col2:
            st.subheader("Progress Visualization")
            df = pd.DataFrame([
                {
                    'Topic': t,
                    'Accuracy': data.accuracy,
                    'Level': data.level
                }
                for t, data in quiz_app.progress_data.items()
            ])
            
            fig = px.bar(df, x='Topic', y='Accuracy',
                        color='Level',
                        title='Performance by Topic',
                        labels={'Accuracy': 'Accuracy (%)'})
            st.plotly_chart(fig)

    # Memory Overview
    if quiz_app.progress_data:
        st.markdown("---")
        st.subheader("📊 Learning Journey")
        memory_results = quiz_app.memory.search(
            f"What are {quiz_app.student_name}'s current expertise levels?",
            user_id=quiz_app.user_id
        )
        st.json(memory_results)


if __name__ == "__main__":
    main()
