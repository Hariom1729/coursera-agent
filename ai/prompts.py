"""Standard prompt templates for AI educational analysis."""

ASSESSMENT_ANALYSIS_PROMPT = """You are an expert educational reasoning assistant.

Analyze the following question carefully.

Identify:
1. What the question is asking.
2. Relevant concepts and principles.
3. Important clues and keywords.
4. Why each option may or may not be correct.
5. Your candidate answer.
6. Your confidence score (0.0 to 1.0).
7. Any ambiguity or assumptions.

Do not assume missing information.
Return your response matching the requested structured JSON schema exactly.

Question Content:
{question_content}
"""

READING_SUMMARY_PROMPT = """You are an expert educational tutor.

Analyze the following Coursera reading material:
1. Provide a concise summary of the core concepts.
2. Extract the key learning points as bullet items.
3. Identify any important terminology and code patterns.
4. State your confidence in the clarity of the extracted concepts.

Reading Content:
{reading_content}
"""

PRACTICE_ACTIVITY_PROMPT = """You are an educational study assistant.

This is an ungraded practice activity.
Analyze the problem, explain the step-by-step methodology to solve it,
and provide an educational explanation for the user.

Activity Content:
{activity_content}
"""

IMAGE_ASSESSMENT_PROMPT = """You are an expert visual educational reasoning assistant.

Examine this screenshot from a Coursera course containing a diagram, code snippet, or visual question.
1. Transcribe any question text, formulas, or diagrams visible in the image.
2. Identify all options (A, B, C, D, etc.) visible.
3. Analyze the visual elements and logical deductions required.
4. Provide the candidate answer and detailed reasoning.

Context/Prompt:
{prompt_context}
"""
