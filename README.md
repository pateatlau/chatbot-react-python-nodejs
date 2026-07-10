# Basic Chatbot (React + FastAPI)

A full-stack streaming chatbot project with:

- Frontend: React + TypeScript + Vite
- Backend: FastAPI (Python)
- LLM providers: OpenAI and Gemini (switchable via environment variables)

## Repository Structure

- `backend/` - FastAPI API server and provider adapters
- `frontend/` - React client with streaming UI
- `docs/` - planning notes (ignored by git in this repo setup)

## Features

- Non-streaming endpoint: `POST /api/chat`
- Streaming SSE endpoint: `POST /api/chat/stream`
- Health endpoint: `GET /api/health`
- Provider abstraction: switch between OpenAI/Gemini without frontend changes

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Node.js 20+ (24 works)
- npm

## Quick Start

### 1) Backend

```bash
cd backend
cp .env.example .env
# Fill in API keys in .env
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

### 2) Frontend

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Frontend default URL: `http://localhost:5173`

Backend default URL: `http://localhost:8000`

## Provider Switching

In `backend/.env`:

- `LLM_PROVIDER=openai` or `LLM_PROVIDER=gemini`
- set provider-specific key/model values

Examples:

```dotenv
LLM_PROVIDER=openai
OPENAI_MODEL=gpt-4o-mini
```

```dotenv
LLM_PROVIDER=gemini
GEMINI_MODEL=gemini-3.1-flash-lite
```

Then restart backend.

## API Overview

### Health

```http
GET /api/health
```

Example response:

```json
{
  "status": "ok",
  "provider": "gemini",
  "version": "0.1.0"
}
```

### Non-streaming chat

```http
POST /api/chat
Content-Type: application/json
```

Body:

```json
{
  "messages": [{ "role": "user", "content": "What is FastAPI?" }]
}
```

### Streaming chat (SSE)

```http
POST /api/chat/stream
Content-Type: application/json
```

Returns `text/event-stream` with frames: `start`, `delta`, `end`, and `error`.

## Development Commands

### Backend

```bash
cd backend
uv run pytest -q
```

### Frontend

```bash
cd frontend
npm run test
npm run lint
npm run build
```

## Notes

- Keep API keys in local `.env` files only.
- Rotate keys immediately if exposed.
