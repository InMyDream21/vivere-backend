from __future__ import annotations
import ollama
import re

def generate_video_prompt_from_image(image_bytes: bytes) -> str:
    """
    Generate a video generation prompt from an image using Ollama's qwen3-vl:8b model.

    Args:
        image_bytes: Raw image bytes

    Returns:
        str: A prompt for image-to-video generation AI
    """
    response = ollama.chat(
        model="qwen3-vl:8b",
        messages=[
            {
                'role': 'user',
                'content': '''Analyze this image and create a detailed, emotional prompt for an image-to-video generation AI (like Runway, Pika, or Sora) to bring this memory to life.

IMPORTANT: Return ONLY the video generation prompt itself. Do not include:
- Explanations of why it works
- Instructions on how to use it
- Emojis or formatting like ### or 🎬
- Any commentary or additional context

Just return the direct, descriptive prompt that would be fed into the video AI tool.''',
                'images': [image_bytes]
            }
        ]
    )

    raw_content = response['message']['content']

    # Try to extract the core prompt if the model still includes extra content
    cleaned_prompt = _extract_core_prompt(raw_content)

    return cleaned_prompt


def _extract_core_prompt(text: str) -> str:
    """
    Extract the core video generation prompt from potentially verbose output.

    Args:
        text: Raw response text

    Returns:
        str: Extracted core prompt
    """
    # Remove markdown headers and emojis
    text = re.sub(r'#{1,6}\s+', '', text)
    text = re.sub(r'[\U0001F300-\U0001F9FF]+', '', text)

    # Try to find content between quotes (often the actual prompt)
    quote_match = re.search(r'"([^"]{50,})"', text, re.DOTALL)
    if quote_match:
        return quote_match.group(1).strip()

    # Try to find content in asterisks (another common format)
    asterisk_match = re.search(r'\*"([^"]{50,})"\*', text, re.DOTALL)
    if asterisk_match:
        return asterisk_match.group(1).strip()

    # Look for sections that seem like explanations and remove them
    # Remove "Why this works" sections
    text = re.sub(r'(?i)(why this works|how to use|key features|context|note).*$', '', text, flags=re.DOTALL)

    # Remove bullet point lists and numbered lists that explain features
    lines = text.split('\n')
    filtered_lines = []
    skip_section = False

    for line in lines:
        # Skip sections that start with explanatory markers
        if re.match(r'^\s*[-*•]\s+\*\*', line) or re.match(r'^\s*\d+\.\s+\*\*', line):
            skip_section = True
            continue

        # Stop skipping if we hit an empty line
        if not line.strip():
            skip_section = False
            filtered_lines.append(line)
            continue

        if not skip_section:
            filtered_lines.append(line)

    cleaned = '\n'.join(filtered_lines).strip()

    # If we still have content, return it; otherwise return original
    return cleaned if cleaned and len(cleaned) > 20 else text.strip()

