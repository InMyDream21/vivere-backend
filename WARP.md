# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

---

# Agent Behavior Rules

These rules MUST be followed ALWAYS without exception.

## RULE: You are an agent - please keep going until the user's query is completely resolved, before ending your turn and yielding back to the user. Only terminate your turn when you are sure that the problem is solved.

## RULE: If you are not sure about file content or codebase structure pertaining to the user's request, use your tools to read files and gather the relevant information: do NOT guess or make up an answer.

## RULE: You MUST plan extensively before each function call, and reflect extensively on the outcomes of the previous function calls. DO NOT do this entire process by making function calls only, as this can impair your ability to solve the problem and think insightfully.

## RULE: External Library Documentation Requirements

- **ALWAYS Use Context7 Before Using External Libraries**

  - The agent MUST retrieve and review documentation via Context7 before implementing any code that uses an external library
  - This applies to ALL libraries not part of the standard language libraries
  - No exceptions - even for commonly known libraries like React, Express, or Lodash

- **Two-Step Documentation Retrieval Process**

  ```javascript
  // ✅ DO: ALWAYS follow this exact two-step process
  // Step 1: Resolve the library name to a Context7-compatible ID
  const libraryIdResponse =
    (await mcp_context7_resolve) -
    library -
    id({
      libraryName: "express",
    });

  // Step 2: Get the documentation using the resolved ID
  const docsResponse =
    (await mcp_context7_get) -
    library -
    docs({
      context7CompatibleLibraryID: libraryIdResponse.libraryId,
      tokens: 10000, // Adjust based on documentation needs
      topic: "routing", // Optional: focus on specific area
    });

  // ❌ DON'T: Skip the resolution step
  // ❌ DON'T: Use hardcoded library IDs
  // ❌ DON'T: Proceed with implementation without review
  ```

- **Never Skip Documentation Retrieval**

  - Documentation MUST be retrieved even for seemingly simple APIs
  - Do not rely on previously cached knowledge for current implementations
  - Never make assumptions about library interfaces, verify with current documentation

- **Document First, Implement Second**

  ```javascript
  // ✅ DO: Review documentation BEFORE writing implementation code
  // 1. Identify library need
  // 2. Retrieve documentation
  // 3. Review relevant sections
  // 4. THEN implement solution

  // ❌ DON'T: Implementation without documentation
  const app = express(); // WRONG - Documentation not retrieved first
  app.get("/", (req, res) => res.send("Hello"));
  ```

- **MUST Use Web Search When Documentation Is Unavailable**

  - If Context7 cannot provide documentation or returns insufficient information, the agent MUST use the web search tool
  - Always search for the most recent documentation as of mid-2025
  - Verify the library version against the latest available release

  ```javascript
  // ✅ DO: Fallback to web search when Context7 fails
  try {
    // First attempt to use Context7
    const libraryIdResponse =
      (await mcp_context7_resolve) -
      library -
      id({
        libraryName: "some-library",
      });

    const docsResponse =
      (await mcp_context7_get) -
      library -
      docs({
        context7CompatibleLibraryID: libraryIdResponse.libraryId,
      });

    // Check if documentation is insufficient
    if (!docsResponse.content || docsResponse.content.length < 100) {
      throw new Error("Insufficient documentation");
    }
  } catch (error) {
    // If Context7 fails or returns insufficient docs, use web search
    const webResults = await web_search({
      search_term: "some-library latest documentation api reference mid 2025",
      explanation: "Context7 documentation was unavailable or insufficient",
    });

    // Analyze multiple search results to get comprehensive information
    const latestDocs = webResults.filter(
      (result) =>
        result.includes("documentation") ||
        result.includes("api reference") ||
        result.includes("guide")
    );

    // Use these web results to guide implementation
  }

  // ❌ DON'T: Skip web search when Context7 fails
  // ❌ DON'T: Proceed with implementation without documentation
  // ❌ DON'T: Use outdated web search results (verify they're current as of mid-2025)
  ```

---

# Project: vivere-backend

## Overview

**Saran Tindak Lanjut ODD** (Dementia Care Conversation Coach)

A FastAPI-based backend service that uses Google's Gemini AI to generate empathetic conversation suggestions for caregivers and family members of people with dementia (Orang dengan Demensia - OdD). The service analyzes conversation transcripts and provides culturally-appropriate, Indonesian-language suggestions that validate feelings, redirect gently, or evoke positive memories.

**Repository**: https://github.com/Vivere-by-NetiZen/vivere-backend.git

## Environment Setup

### Required Environment Variables

- `GEMINI_API_KEY` (required): Your Google Gemini API key

Create a `.env` file in the project root:

```bash
GEMINI_API_KEY=your_api_key_here
```

### Python Setup

This project uses Python 3.x with FastAPI. Install dependencies:

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux

# Install dependencies (typically)
pip install fastapi uvicorn pydantic google-generativeai ollama
# OR if requirements.txt exists:
pip install -r requirements.txt
```

### Ollama Setup

The `/generate_video` endpoint requires Ollama to be installed and running locally:

```bash
# Install Ollama (macOS)
# Visit https://ollama.ai or use homebrew

# Pull the required model
ollama pull qwen3-vl:8b

# Verify Ollama is running
curl http://localhost:11434/api/tags
```

## Development Commands

### Running the Development Server

```bash
# Standard FastAPI development server with auto-reload
uvicorn main:app --reload

# Or specify host and port
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Testing the API

```bash
# Health check
curl http://localhost:8000/health

# Test suggestions endpoint
curl -X POST http://localhost:8000/suggestions \
  -H "Content-Type: application/json" \
  -d '{"transcript": "Your conversation transcript here..."}'

# Test initial questions endpoint (with image)
curl -X POST http://localhost:8000/initial-questions \
  -F "image=@/path/to/image.jpg"

# Test generate video endpoint (with image)
curl -X POST http://localhost:8000/generate_video \
  -F "image=@/path/to/image.jpg"
```

## Architecture

### Request Flow

#### Text-based Suggestions Flow
```
Client Request (transcript)
    ↓
POST /suggestions (routes.py)
    ↓
build_prompt() (prompt.py) → constructs empathetic prompt
    ↓
generate_suggestions() (gemini.py) → calls Gemini API
    ↓
extract_json() (utils.py) → parses JSON response
    ↓
SuggestionResponse (schemas.py) → returns structured data
```

#### Image-based Initial Questions Flow
```
Client Request (image file)
    ↓
POST /initial-questions (routes.py)
    ↓
generate_suggestions_for_image() (gemini.py) → calls Gemini Vision API
    ↓
extract_json() (utils.py) → parses JSON response
    ↓
InitialQuestionResponse (schemas.py) → returns question string
```

#### Video Prompt Generation Flow
```
Client Request (image file)
    ↓
POST /generate_video (routes.py)
    ↓
generate_video_prompt_from_image() (ollama_client.py) → calls Ollama qwen3-vl:8b
    ↓
_extract_core_prompt() (ollama_client.py) → cleans verbose output
    ↓
VideoPromptResponse (schemas.py) → returns video generation prompt
```

### Directory Structure

```
vivere-backend/
├── main.py              # FastAPI app initialization, CORS, router registration
├── app/
│   ├── config.py        # Configuration management, env vars
│   ├── routes.py        # API endpoints (/health, /suggestions, /initial-questions, /generate_video, /ws/audio)
│   ├── schemas.py       # Pydantic models (request/response)
│   ├── gemini.py        # Gemini API client wrapper (text & vision)
│   ├── ollama_client.py # Ollama API client for video prompt generation
│   ├── prompt.py        # Prompt engineering for dementia care
│   ├── utils.py         # JSON extraction utilities
│   └── speech_recognizer.py  # Google Cloud Speech-to-Text integration
└── .gitignore
```

### Key Components

#### `main.py`
- FastAPI application entry point
- Title: "Saran Tindak Lanjut ODD" v1.0.0
- CORS middleware configured for all origins (development setup)
- Router inclusion from `app.routes`

#### `app/config.py`
- Singleton configuration using `@lru_cache`
- Validates `GEMINI_API_KEY` is present
- Default model: `gemini-2.5-flash-lite`
- Raises `ValueError` if API key is missing

#### `app/routes.py`
- **GET `/health`**: Health check endpoint
- **POST `/suggestions`**: Main endpoint for text-based suggestions
  - Validates transcript length (min 20 chars)
  - Generates 4 suggestions max
  - Error handling for Gemini API failures and JSON parsing
- **POST `/initial-questions`**: Generate opening question from image
  - Accepts image uploads (JPEG, PNG, WebP, HEIC, HEIF)
  - Uses Gemini Vision API
  - Returns single empathetic opening question
- **POST `/generate_video`**: Generate video AI prompt from image
  - Accepts image uploads (JPEG, PNG, WebP, HEIC, HEIF)
  - Uses Ollama qwen3-vl:8b model
  - Returns cleaned video generation prompt
- **WebSocket `/ws/audio`**: Real-time audio transcription
  - Streams audio data for speech-to-text
  - Uses Google Cloud Speech API

#### `app/schemas.py`
- `SuggestionRequest`: Contains `transcript` field
- `SuggestionResponse`: Returns list of suggestion strings
- `InitialQuestionResponse`: Returns single `question` string
- `VideoPromptResponse`: Returns video generation `prompt` string

#### `app/gemini.py`
- Uses `from google import genai` (newer SDK)
- `generate_suggestions(prompt: str) -> str`: Text-based suggestion generation
- `generate_suggestions_for_image(image_bytes, content_type) -> str`: Vision-based question generation
  - Accepts image bytes and MIME type
  - Returns JSON with opening question for dementia care conversations
- Returns `<no_suggestion>` if response is empty
- Single client instance shared across requests

#### `app/ollama_client.py`
- Uses Ollama Python library for local LLM inference
- `generate_video_prompt_from_image(image_bytes) -> str`: Main function
  - Calls Ollama qwen3-vl:8b vision model
  - Instructs model to return only the video generation prompt
  - Applies post-processing to clean verbose output
- `_extract_core_prompt(text) -> str`: Cleaning utility
  - Removes markdown headers and emojis
  - Extracts quoted content (the actual prompt)
  - Filters out explanatory sections ("Why this works", "How to use")
  - Removes bullet point lists and numbered explanations
  - Returns clean, focused video generation prompt

#### `app/prompt.py`
- `build_prompt(transcription, locale, max_suggestions)`
- Constructs system prompt for dementia-sensitive conversation
- Key directives:
  - Empathetic, calm, validating tone
  - Avoid interrogating memory, blaming, or arguing
  - Grounding techniques for distress
  - Indonesian language with cultural sensitivity
- Returns structured JSON format

#### `app/utils.py`
- `extract_json(text: str) -> dict`
- Attempts direct JSON parsing first
- Falls back to regex extraction: `r"\{[\s\S]*\}"`
- Raises `ValueError` if no valid JSON found

## API Endpoints

### GET `/health`
Health check endpoint.

**Response**:
```json
{
  "status": "healthy"
}
```

### POST `/suggestions`
Generate conversation suggestions for dementia caregivers.

**Request**:
```json
{
  "transcript": "Full conversation transcript here..."
}
```

**Response**:
```json
{
  "suggestions": [
    "Suggestion 1...",
    "Suggestion 2...",
    "Suggestion 3...",
    "Suggestion 4..."
  ]
}
```

**Validation**:
- Transcript must be at least 20 characters
- Returns up to 4 suggestions
- Returns 400 if transcript too short
- Returns 500 if Gemini API fails or JSON parsing fails

### POST `/initial-questions`
Generate an empathetic opening question from an image to start a conversation with someone with dementia.

**Request**:
- Content-Type: `multipart/form-data`
- Body: `image` file (JPEG, PNG, WebP, HEIC, HEIF)

**Response**:
```json
{
  "question": "Pertanyaan pembuka yang ramah dan empatik berdasarkan gambar"
}
```

**Validation**:
- Image file required
- Supported formats: JPEG, PNG, WebP, HEIC, HEIF
- Returns 415 if unsupported media type
- Returns 400 if file is empty
- Returns 500 if Gemini Vision API fails or JSON parsing fails

### POST `/generate_video`
Generate a detailed prompt for image-to-video AI tools (like Runway, Pika, Sora) to bring a memory to life.

**Request**:
- Content-Type: `multipart/form-data`
- Body: `image` file (JPEG, PNG, WebP, HEIC, HEIF)

**Response**:
```json
{
  "prompt": "Cinematic slow-motion animation of a modern tech team huddle in a sunlit conference room. The scene 'comes alive' as subtle motion emerges..."
}
```

**Features**:
- Uses Ollama qwen3-vl:8b vision model locally
- Analyzes image content and emotional context
- Generates descriptive, cinematic prompts
- Automatically cleans verbose output (removes explanations, emojis, instructions)
- Returns only the core video generation prompt

**Validation**:
- Image file required
- Supported formats: JPEG, PNG, WebP, HEIC, HEIF
- Returns 415 if unsupported media type
- Returns 400 if file is empty
- Returns 500 if Ollama API fails

**Requirements**:
- Ollama must be running locally (`ollama serve`)
- Model must be pulled (`ollama pull qwen3-vl:8b`)

### WebSocket `/ws/audio`
Real-time audio transcription using Google Cloud Speech-to-Text.

**Connection**: WebSocket
**Protocol**: Binary audio frames + JSON control messages

**Usage**:
1. Connect to `ws://localhost:8000/ws/audio`
2. Send binary audio data (PCM format)
3. Receive JSON transcription updates:
```json
{
  "type": "transcript",
  "final": false,
  "text": "Partial transcript..."
}
```
4. Send stop signal:
```json
{
  "type": "stop"
}
```

## Important Notes

### Language & Cultural Context
- All prompts and responses are in **Indonesian (id-ID)**
- Culturally-sensitive approach for Indonesian families
- Non-medical, empathetic tone
- Focus on validation, gentle redirection, reminiscence, and grounding

### Dementia-Sensitive Design
- Avoid interrogating memory
- Never blame or argue with OdD
- Provide realistic reassurance
- Simple, clear language
- Validate emotions first

### Error Handling
- Transcript validation happens before API call
- Gemini API errors return HTTP 500 with descriptive messages
- JSON parsing failures are caught and reported
- Empty/invalid responses handled gracefully

### Current Limitations
- No test suite present (consider adding pytest tests)
- No dependency management file (requirements.txt, pyproject.toml)
- CORS allows all origins (should be restricted in production)
- No rate limiting or authentication
- Single Gemini model hardcoded
- `/generate_video` requires Ollama running locally (not cloud-based)
- Video prompt cleaning may need tuning for different model outputs

## Development Workflow

1. Always activate virtual environment before working
2. Set `GEMINI_API_KEY` in `.env` file
3. Ensure Ollama is running: `ollama serve` (for `/generate_video` endpoint)
4. Pull required Ollama model: `ollama pull qwen3-vl:8b`
5. Use `uvicorn main:app --reload` for development
6. Test endpoints with curl or Postman/Insomnia
7. Check logs for API responses (printed to console)
8. Validate prompt changes by reviewing output suggestions

## Troubleshooting

### `/generate_video` endpoint issues

**Problem**: "Connection refused" or Ollama errors
- **Solution**: Ensure Ollama is running (`ollama serve`)
- **Check**: `curl http://localhost:11434/api/tags` should return model list

**Problem**: Model not found error
- **Solution**: Pull the model: `ollama pull qwen3-vl:8b`
- **Verify**: `ollama list` should show `qwen3-vl:8b`

**Problem**: Video prompt contains too much explanation/gibberish
- **Solution**: The `_extract_core_prompt()` function handles this automatically
- **If persists**: Adjust regex patterns in `app/ollama_client.py`

### Image upload issues

**Problem**: 415 Unsupported Media Type
- **Solution**: Ensure image is JPEG, PNG, WebP, HEIC, or HEIF format
- **Check**: Verify Content-Type header in request

**Problem**: 400 Empty file error
- **Solution**: Ensure image file is not corrupted and has content
