# AutoGen Dev/Reviewer Team with Streamlit UI

This repository contains a [Streamlit](https://streamlit.io) web application that provides a user interface for interacting with an [AutoGen](https://microsoft.github.io/autogen/stable/index.html) multi-agent team. The team consists of a Developer Agent and a Reviewer Agent who collaborate on code-related tasks based on user input.

> ✅ **Tested on Python 3.11**

## Features

* **AutoGen Integration:** Leverages the AutoGen framework for multi-agent interactions.
* **Developer/Reviewer Pattern:** Simulates a basic code development and review cycle.
* **Streamlit UI:** Provides a simple web interface for task input and viewing results.
* **Conversation Logging:** Optional tab to view the detailed turn-by-turn conversation between agents for debugging.

## Setup

1. **Clone the Repository:**

    ```bash
    git clone git@github.com:vbelouso/autogen-devsync.git
    cd autogen-devsync
    ```

2. **Create a Virtual Environment (Recommended):**

    ```bash
    python -m venv .venv
    source .venv/bin/activate
    ```

3. **Install Dependencies:**
    * Install the requirements:

        ```bash
        pip install -r requirements.txt
        ```

4. **Configure API Keys (Environment Variables):**
    * API keys **MUST** be provided as environment variables.
    * **Recommended Method (Local):**
        * Create a file named `.env` in the project root directory.
        * Add your API keys to this file, matching the names expected in `autogen_setup.py` (e.g.):

            ```dotenv
            DEV_AGENT_API_KEY=your_dev_agent_api_key_here
            REVIEW_AGENT_API_KEY=your_review_agent_api_key_here
            ```

    * **Alternative Methods:** You can also set environment variables directly in your terminal or use your deployment platform's secret management features. The required variable names are typically derived from the agent keys in `models.yaml` (e.g., `DEV_AGENT_API_KEY`, `REVIEW_AGENT_API_KEY`)

5. **Verify `models.yaml`:** Ensure your `models.yaml` file exists and contains the necessary model configurations, matching the structure expected by the Pydantic models in `model.py` (or `autogen_setup.py`).

## Running the App

1. Make sure your virtual environment is activated.
2. Ensure API keys are set via environment variables (or the `.env` file is present if using `python-dotenv`).
3. Run the Streamlit application:

    ```bash
    streamlit run streamlit_app.py
    ```

4. Open the URL provided by Streamlit (usually `http://localhost:8501`) in your web browser.
