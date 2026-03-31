"""
AI-powered services for course content intelligence.
Phase 2 MVP: Rule-based quiz generation from lesson content.
Future: LLM integration (OpenAI, Anthropic, etc.)
"""
import re
from decimal import Decimal
from typing import List, Dict, Any
from .models import Competency, Lesson


class AIQuizGenerator:
    """
    Generate quiz questions from lesson content.
    MVP: Keyword extraction + rule-based MCQ generation
    """
    
    @staticmethod
    def extract_key_phrases(text: str, max_phrases: int = 10) -> List[str]:
        """
        Extract key phrases from text using simple heuristics.
        - Capitalize sequences (potential terms)
        - Words in lists/bullets
        - Emphasized text (bold/italic)
        
        Args:
            text: HTML or plain text content
            max_phrases: Maximum number of phrases to extract
            
        Returns:
            List of key phrases
        """
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Extract capitalized multi-word sequences
        capitalized = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
        
        # Extract bullet/numbered list items
        list_items = re.findall(r'(?:^|\n)\s*[-•*]\s*(.+?)(?=\n|$)', text, re.MULTILINE)
        list_items += re.findall(r'(?:^|\n)\s*\d+\.\s*(.+?)(?=\n|$)', text, re.MULTILINE)
        
        # Combine and deduplicate
        phrases = list(set(capitalized + list_items))
        
        # Sort by frequency/length and return top phrases
        phrases.sort(key=len, reverse=True)
        return phrases[:max_phrases]
    
    @staticmethod
    def generate_mcq_from_phrase(phrase: str, context_text: str = "") -> Dict[str, Any]:
        """
        Generate a multiple choice question from a key phrase.
        
        Args:
            phrase: Key phrase to create a question about
            context_text: Full lesson text for generating distractors
            
        Returns:
            Dict with question structure (ready to create Question object)
        """
        # Simple question templates
        templates = [
            f"What is {phrase}?",
            f"Which of the following best describes {phrase}?",
            f"{phrase} is primarily used for:",
            f"In the context of this lesson, {phrase} refers to:",
        ]
        
        # For MVP, use first template
        question_text = templates[0]
        
        # Generate plausible distractors
        # In MVP, these are simple variations; future: LLM-based generation
        distractors = [
            f"A variant of {phrase}",
            f"A related but different concept from {phrase}",
            f"The opposite of {phrase}",
        ]
        
        return {
            "question_text": question_text,
            "correct_answer": f"The definition or explanation of {phrase}",
            "distractors": distractors,
            "explanation": f"Based on the lesson content about {phrase}.",
        }
    
    @classmethod
    def suggest_quiz_from_lesson(cls, lesson: Lesson, num_questions: int = 5) -> Dict[str, Any]:
        """
        Generate suggested quiz questions for a lesson.
        
        Args:
            lesson: Lesson object with content_html
            num_questions: Number of questions to generate
            
        Returns:
            Dict with quiz metadata and suggested questions
        """
        if not lesson.content_html:
            return {
                "status": "error",
                "message": "Lesson has no content_html; cannot generate quiz"
            }
        
        # Extract key phrases
        phrases = cls.extract_key_phrases(lesson.content_html, max_phrases=num_questions)
        
        if not phrases:
            return {
                "status": "error",
                "message": "Could not extract key phrases from lesson content"
            }
        
        # Generate questions
        suggested_questions = []
        for i, phrase in enumerate(phrases, 1):
            question_data = cls.generate_mcq_from_phrase(phrase, lesson.content_html)
            question_data['order'] = i
            suggested_questions.append(question_data)
        
        return {
            "status": "success",
            "quiz_title": f"Quiz for {lesson.title}",
            "quiz_description": f"Auto-generated quiz from lesson content. Review and edit before publishing.",
            "num_questions": len(suggested_questions),
            "suggested_questions": suggested_questions,
            "competencies": []  # To be filled by teacher mapping
        }


class CompetencyExtractor:
    """
    Extract competencies from lesson content.
    Phase 2 MVP: Keyword-based extraction.
    """
    
    @staticmethod
    def infer_competencies_from_content(lesson: Lesson, course_competencies: List[Competency]) -> List[Competency]:
        """
        Infer relevant competencies for a lesson based on content.
        
        Args:
            lesson: Lesson object
            course_competencies: List of Competency objects in the course
            
        Returns:
            List of matching Competency objects
        """
        if not lesson.content_html:
            return []
        
        # Extract keywords from lesson
        keywords = CompetencyExtractor._extract_keywords(lesson.content_html)
        
        # Match keywords to competency names/descriptions
        matched = []
        for competency in course_competencies:
            comp_text = (competency.name + " " + competency.description).lower()
            for keyword in keywords:
                if keyword.lower() in comp_text:
                    matched.append(competency)
                    break
        
        return matched
    
    @staticmethod
    def _extract_keywords(text: str) -> List[str]:
        """Extract simple keywords from text"""
        text = re.sub(r'<[^>]+>', '', text)
        words = text.lower().split()
        # Filter: remove common words, keep nouns (simple heuristic)
        common = {'the', 'a', 'an', 'and', 'or', 'is', 'are', 'was', 'were', 'be', 'been'}
        keywords = [w.strip('.,!?;:') for w in words if w.lower() not in common and len(w) > 3]
        return list(set(keywords))[:20]  # Return unique, top 20
