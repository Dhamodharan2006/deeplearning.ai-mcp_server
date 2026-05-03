# DeepLearning.ai MCP Server

A robust, high-performance [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that provides AI assistants with structured, searchable access to the complete catalog of DeepLearning.ai courses. 

Built with resilience in mind, this server employs a highly fault-tolerant, 3-tiered data extraction pipeline, backed by an asynchronous SQLite cache to ensure instant retrieval for downstream AI models.

## 🚀 Key Features

- **Instant Semantic Search**: Query the full DeepLearning.ai course catalog instantly via local SQLite cache.
- **3-Tiered Extraction Pipeline**: 
  - **Tier 1 (Primary)**: Direct integration with DeepLearning.ai's Algolia Search API for lightning-fast, full-catalog retrieval in a single request.
  - **Tier 2 (Intelligent Fallback)**: LLM-driven browser automation using LangChain and Groq to navigate, wait for dynamic rendering, explicitly extract HTML course cards, and safely infer missing data.
  - **Tier 3 (Raw Fallback)**: Pure Playwright headless scraping with infinite-scroll stabilization logic.
- **Global LLM Topic Inference**: No course is ever left `"uncategorised"`. A built-in post-processing hook routes any missing topics to the Groq LLM to intelligently infer the category based on the course description.
- **Automated Cache Lifecycle**: Built-in background scheduling (`APScheduler`) silently updates the course cache on a configurable CRON schedule.
- **Rich Schema**: Standardizes raw web data into clean, typed structures (Title, URL, Topic, Level, Instructor, Description, Syllabus, Prerequisites).

## 🛠️ Technology Stack

- **Language**: Python 3.12+
- **Package Manager**: `uv` (Ultra-fast Python package installer)
- **MCP Framework**: `@modelcontextprotocol/sdk` (via Python `mcp` library)
- **Data Extraction**: 
  - `httpx` (Async HTTP client for Algolia API)
  - `playwright` (Async headless browser automation)
  - `langchain-groq` (Agentic web parsing and data inference)
- **Database**: `aiosqlite` (Async SQLite for local caching)
- **Scheduling**: `APScheduler` (Background cache invalidation and refresh)

## 📦 Available MCP Tools (6 Tools)

This server exposes 6 powerful tools to the connected AI client, split into Search/Exploration, Deep Dives, and Cache Management:

### 1. `search_courses`
Searches the cached course database. Matches against titles, topics, instructors, and descriptions. Includes flexible filtering by topic and level. 
*Always call this before `get_course_detail` to get a valid `course_id`.*

### 2. `get_course_detail`
Performs a deep dive into a single course. It navigates to the specific course page and uses LLM extraction to pull the full syllabus, lesson list, skills taught, prerequisites, total hours, and instructor bios. 
*Uses `course_id` obtained from `search_courses`.*

### 3. `list_topics`
Lists all available topics/categories on DeepLearning.ai along with the number of courses available in each. 
*Useful for exploring what's available or identifying valid topic slugs to use as filters.*

### 4. `recommend_courses`
An AI-native endpoint. Given a user's learning goal and optional background, it cross-references the entire SQLite database to recommend the best DeepLearning.ai courses in a suggested study order, complete with reasoning for each recommendation.

### 5. `refresh_cache`
Manually triggers an immediate background run of the 3-tier extraction pipeline to update the local SQLite database. Uses scope `'all'` for full updates. 
*Only call this when the user explicitly asks for fresh data.*

### 6. `get_cache_status`
Checks how fresh the local course cache is. Returns total courses stored, last refresh timestamp, and a clean array of all topics covered. 
*Call this first when asked about the 'latest' courses to decide whether a refresh is needed.*

## ⚙️ Setup & Installation

### 1. Prerequisites
- Python 3.11+
- `uv` installed (`pip install uv`)
- Node.js (for running the MCP Inspector)

### 2. Install Dependencies
```bash
uv sync
```

### 3. Environment Configuration
Copy the `.env.example` file to `.env`:
```bash
cp .env.example .env
```
Fill in the required environment variables:
```env
# Required for Tier 2 Fallback & Topic Inference
GROQ_API_KEY=your_groq_api_key

# ── Algolia (Public read-only credentials from deeplearning.ai) ───────────
ALGOLIA_APP_ID=Y5109WLMQW
ALGOLIA_API_KEY=9030ff79d3ba653535d5b66c26b56683
ALGOLIA_INDEX=courses_date_desc

# Server Config
CACHE_TTL_HOURS=24
CACHE_DB_PATH=data/courses.db
```

### 4. Playwright Initialization
Ensure Playwright browsers are installed for the fallback scrapers and deep-dive detail fetching:
```bash
uv run playwright install chromium
```

## 🔌 Connecting to LLM Clients (Claude Desktop & IDEs)

To use this MCP server with your favorite AI assistants, you must configure them to launch the server using `uv run`. 

*(Note: Replace `absolute_path_to_mcp_server_folder` with your actual absolute Downloaded project path)*

### Claude Desktop Configuration
Open your Claude Desktop configuration file. On Windows, this is located at `%APPDATA%\Claude\claude_desktop_config.json`. On Mac, it's `~/Library/Application Support/Claude/claude_desktop_config.json`.

Add the following configuration:

```json
{
  "mcpServers": {
    "deeplearning-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "absolute_path_to_mcp_server_folder",
        "run",
        "deeplearning-mcp"
      ]
    }
  }
}
```
*After saving, restart Claude Desktop. You will see a plug icon indicating the tools are available.*

### Cursor IDE Configuration
1. Open Cursor and navigate to **Settings** (`Ctrl + ,` or `Cmd + ,`).
2. Go to **Features** -> **MCP Servers**.
3. Click **+ Add new MCP server**.
4. Configure it as follows:
   - **Name**: `deeplearning-mcp`
   - **Type**: `command`
   - **Command**: `uv --directory "absolute_path_to_mcp_server_folder" run deeplearning-mcp`
5. Click Save. Cursor will connect to the server and make all 6 tools available to the Agent.

## 🧪 Testing & Validation

You can run the full suite using the MCP Inspector to interact with the server locally.

```bash
# Start the MCP Inspector
npx -y @modelcontextprotocol/inspector uv run deeplearning-mcp
```

This will launch a web interface at `http://localhost:5173` where you can manually invoke and test all 6 tools.

## 🏗️ Architecture & Approach

The core challenge in scraping `deeplearning.ai/courses` is that course cards are dynamically injected into the DOM via client-side JavaScript (powered by Algolia). 

To ensure stability, Implemented a Fallback Mechanism in `fetcher.py`:

1. **Direct API calls**: The application intercepts the undocumented Algolia App ID and API Keys from the site's network traffic. This allows us to bypass the browser entirely and fetch 100+ courses in <2 seconds.
2. **Agentic Fallback**: If DeepLearning.ai rotates their Algolia keys, the request throws a `403 Forbidden`. The system instantly catches this and spins up a Playwright instance, evaluates custom JS to parse explicit `URL` and `Badge` nodes, and hands the clean string blocks over to the Groq LLM to safely generate structured JSON.
3. **Dumb Fallback**: Should the LLM API fail, a robust while-loop executes raw JavaScript to physically scroll the page until the DOM size stabilizes, ensuring we capture all lazy-loaded elements.
4. **Data Standardization**: Regardless of which tier succeeds, the extracted list passes through `_fill_missing_topics`. Any course missing a topic is dynamically sent to the LLM to be perfectly categorized before hitting the database.

Data is then normalized, stripped of duplicates, and UPSERTed into an async SQLite database, guaranteeing that the MCP endpoints are always blazing fast and entirely decoupled from scraping latency.
