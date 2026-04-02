# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run Commands

```bash
npm install              # Install JS dependencies
pip install -r backend/requirements.txt  # Install Python dependencies
npm run dev              # Dev mode: webpack-dev-server (localhost:3000) + Electron + Flask (localhost:5000)
npm run build            # Production webpack build → dist/
npm run start            # Build production bundle, then launch Electron
cd backend && python app.py  # Run Flask server standalone (for debugging)
```

## Architecture

Electron desktop app with a Python Flask backend. Electron spawns Flask as a child process on startup and waits for it to be ready before loading the window.

**Data flow**: User selects folder → Electron IPC (`preload.js`) → React calls Flask REST API → Flask scans images, generates thumbnails, writes `result.json` → React renders photo grid → User clicks "Start" → Flask processes photos (MediaPipe → Qwen LLM) → WebSocket pushes results per-photo → React updates grid in real-time.

**Dev vs Prod**: `app.isPackaged` in Electron main.js switches between `localhost:3000` (dev) and `dist/index.html` (prod). Dev mode opens DevTools automatically.

## Key Architecture Decisions

**State management (App.jsx)**: Photos stored as `photoNames: string[]` + `photoMap: Map<string, object>` + `photoVersion: number`. The Map allows updating a single photo without recreating the array. `photoVersion` is passed through `cellProps` to bust `react-window`'s internal cache — necessary because `Object.values(Map)` returns `[]` and the SDK's memoization would never invalidate otherwise.

**Virtual scrolling (PhotoGrid.jsx)**: Uses `react-window` v2 Grid. `cellProps` must contain only plain objects (not Map) because v2 uses `Object.values(cellProps)` as useMemo dependencies. CellRenderer uses `React.memo` and reads photos via `photoMapRef.current` (stable ref).

**Thumbnail system**: Flask generates thumbnails on first scan into `{folder}/.thumbnails/` (400px wide, JPEG). Frontend loads them via `file://` protocol (instant, no HTTP overhead). Original images served via Flask HTTP with Cache-Control headers for the detail panel preview. `ensure_thumbnails()` always runs for all images (skips existing).

**Mock LLM**: `USE_MOCK_LLM=true` (default) uses `mock_llm_response.py` which returns random results without calling any API. Set `USE_MOCK_LLM=false` and `QWEN_API_KEY=your-key` to use the real Qwen-3.5Plus API via DashScope.

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/photos` | POST | Initialize folder, generate thumbnails, return photo data |
| `/api/start` | POST | Start analysis pipeline (background thread) |
| `/api/cancel` | POST | Cancel running pipeline |
| `/api/retry/<filename>` | POST | Reset and re-process a single photo |
| `/api/update-result` | POST | Update photo result (from detail panel edits) |
| `/api/export` | POST | Copy photos to `合格/` and `需复核/` subfolders |
| `/api/thumb/<filepath>` | GET | Serve thumbnail (fallback to original) |
| `/api/image/<filepath>` | GET | Serve original image |

**WebSocket events**: `photo_update`, `pipeline_progress`, `pipeline_complete`, `pipeline_error`

## Environment Variables

- `FLASK_PORT` — Backend port (default: 5000)
- `USE_MOCK_LLM` — Use mock LLM responses (default: `true`)
- `QWEN_API_KEY` — DashScope API key for real LLM calls
- `FLASK_DEBUG` — Enable Flask debug mode
