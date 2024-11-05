import streamlit as st
from pydantic import BaseModel
from mem0 import Memory
from educhain import Educhain
from langchain import LLMChain
from openai import OpenAI
import os

# Set up configuration
config = {
    "graph_store": {
        "provider": "neo4j",
        "config": {
            "url": "neo4j+s://bb3b5969.databases.neo4j.io",
            "username": "neo4j",
            "password": "YT__sW785DiB_M9BBKkWWh7XTv-23mfB05RvMgwvCAI"
        }
    },
    "version": "v1.1"
}

m = Memory.from_config(config_dict=config)

# Initialize Memory, Educhain, and LLM instances
educhain = Educhain(api_key=OPENAI_API_KEY)
llm = OpenAI(api_key=OPENAI_API_KEY)

# Pydantic models for structured data handling
class QuizResult(BaseModel):
    question: str
    correct_answer: str
    user_answer: str
    is_correct: bool

class TopicAnalysis(BaseModel):
    topic: str
    questions: list[QuizResult]

class ExpertiseLevel(BaseModel):
    topic: str
    level: str

# Class for managing GRE Geometry quiz
class GREGeometryQuiz:
    def __init__(self, memory, educhain, llm, student_id):
        self.memory = memory
        self.educhain = educhain
        self.llm = llm
        self.student_id = student_id

    def generate_questions(self, topic):
        return self.educhain.create_questions(
            subject="GRE Geometry",
            topic=topic,
            difficulty="Medium",
            num_questions=5
        )

    def analyze_results(self, quiz_results):
        categorized_results = {"Lines and Angles": [], "Circles": [], "Triangles": []}
        
        for result in quiz_results:
            topic_prompt = f"Categorize the following question to one of these topics: Lines and Angles, Circles, or Triangles.\nQuestion: {result.question}"
            response = self.llm.complete(prompt=topic_prompt)
            topic = response.strip()
            if topic in categorized_results:
                categorized_results[topic].append(result)
        
        return [TopicAnalysis(topic=topic, questions=questions) for topic, questions in categorized_results.items()]

    def evaluate_expertise(self, categorized_results):
        expertise_levels = {}
        
        for topic_analysis in categorized_results:
            correct_count = sum(1 for q in topic_analysis.questions if q.is_correct)
            total_questions = len(topic_analysis.questions)
            accuracy = (correct_count / total_questions) * 100 if total_questions > 0 else 0
            
            if accuracy >= 80:
                expertise_levels[topic_analysis.topic] = "Expert"
            elif accuracy >= 50:
                expertise_levels[topic_analysis.topic] = "Intermediate"
            else:
                expertise_levels[topic_analysis.topic] = "Newbie"
        
        # Update expertise levels in memory
        self.memory.update("Student", self.student_id, {"expertise_levels": expertise_levels})
        return [ExpertiseLevel(topic=topic, level=level) for topic, level in expertise_levels.items()]

    def attempt_quiz(self):
        quiz_results = []
        
        for topic in ["Lines and Angles", "Circles", "Triangles"]:
            questions = self.generate_questions(topic)
            st.subheader(f"--- {topic} Quiz ---")
            for question in questions:
                st.write(question["text"])
                user_answer = st.text_input(f"Your Answer for question: {question['text']}", key=question['text'])
                is_correct = user_answer.lower() == question["answer"].lower()
                quiz_results.append(QuizResult(
                    question=question["text"],
                    correct_answer=question["answer"],
                    user_answer=user_answer,
                    is_correct=is_correct
                ))

        categorized_results = self.analyze_results(quiz_results)
        expertise_levels = self.evaluate_expertise(categorized_results)

        # Display updated expertise levels
        st.write("### Updated Expertise Levels")
        for level in expertise_levels:
            st.write(f"{level.topic} Expertise Level: {level.level}")

# Streamlit App UI
st.title("GRE Geometry Quiz")
st.write("Test your knowledge on GRE Geometry Topics: Lines and Angles, Circles, and Triangles!")

# Input for custom Student ID
student_id = st.text_input("Enter your Student ID:")
if student_id:
    # Initialize quiz with the provided student ID
    quiz = GREGeometryQuiz(m, educhain, llm, student_id)

    # Button to start the quiz
    if st.button("Start Quiz"):
        quiz.attempt_quiz()
else:
    st.warning("Please enter your Student ID to begin.")
