# AIA25-Studio-Agent Group 4

Herein we present the AIA Studio Agent for Group 4, an LLM that helps designers understand the cost and valuation impacts of their decision.

___

## Project Structure

The project follows a modular directory structure, which allows for easy extension and customization.

```
AIA25-Studio-Agent-Group4/
│
├── llm_calls.py            # Contains all the calls to the LLM API with different system prompts.
├── llm_query.py            # Contains the llm_query method used by the agents.
├── populate_database.py    # Function to build your chromaDB.
├── logger_setup.py         # Logging for debugging.
├── streamlit_gui.py        # The main streamlit app to run.
├── gh_server.py            # A Flask App server that answers requests.
│
├── ifc_viewer_vite/        # The ifc viewer files.
|
├── project_utils/          # Utility functions.
│   ├──  rag_utils.py       # Functions related to Retrieval-Augmented Generation (RAG).
│   ├──  ifc_processing.py  # Functions for processing ifc files
│   └──  ifc_utils.py       # Functions for interacting with ifc files.         
│
├── server/                 # Server-side logic.
│   └── config.py           # Contains the logic to decide if the project runs with a local or cloud LLM.
|
├── models/                 # The RAG reranking model.
│
├── valuation_model/        # The valuation model files.
│
├── chroma/                 # Directory for vector store knowledge databases.

```

## Getting Started

### Installation

To get started, clone this repository to your local machine:

```bash
git clone https://github.com/your-username/aia25-studio-agent.git
cd aia25-studio-agent
```

Install pipenv and activate the pipenv shell

```bash
pip install pipenv
pipenv shell
```

Install npm packages in the ifc_viewer_vite folder
```bash
cd ifc_viewer_vite
npm install
cd ..
```

Put your knowledge base pdfs and markdown files into a `./source_data` folder and build the vectorDB

```bash
python populate_database.py
```

Run the app using streamlit

```bash
streamlit run ./streamlit_gui.py
```

you can also select the pipenv shell in vs code (hit F1 in windows, command+P in macOS, and then 'select python interpreter')

### Configuration

1. **API Keys**  
   - create a `.env` file in the project folder and populate it with your keys for the following values:
    LLAMA_PARSE_KEY
    OPENAI_API_KEY
    CLOUDFLARE_ACCOUNT_ID
    CLOUDFLARE_API_KEY 
   - Add your API keys or authentication credentials here. This file is not uploaded to GitHub for security reasons.

2. **Local or Cloud LLM Configuration**  
   - In the `server/config.py` file, you will find the logic to switch between using a local LLM or a cloud-based LLM.  
   - Customize this file to select the appropriate LLM for your project. You can add any new local models in this configuration file.
   - For running locally you will need to install and run LM Studio with the following models (currently):
      - nomic-ai/nomic-embed-text-v1.5-GGUF
      - lmstudio-community/Meta-Llama-3-8B-Instruct-GGUF
      - mradermacher/Apriel-5B-Instruct-llamafied.i1