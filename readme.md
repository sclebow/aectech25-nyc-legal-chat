# AIA25-Studio-Agent Group 4

Herein we present the AIA Studio Agent for Group 4, an LLM that helps designers understand the cost and valuation impacts of their decision.

___

## environment setup
we utilize *pipenv*, install pipenv using:
> pip install pipenv
you can then activate the pipenv shell using:
> pipenv shell
you can also select the pipenv shell in vs code (hit F1 in windows, command+P in macOS, and then 'select python interpreter')

___

Welcome to the AIA25-Studio-Agent template repository! This serves as a starting point for students in the AIA25-Studio class to create their design assistant copilots. The goal of the project is to orchestrate Large Language Models (LLMs) to assist in architectural design tasks. The assistant copilots can be connected to platforms such as Grasshopper in Rhino, Revit, or web apps, depending on your needs, but that is beyond the scope of this starting template.

## Project Structure

The project follows a modular directory structure, which allows for easy extension and customization.

```
AIA25-Studio-Agent/
│
├── llm_calls.py              # Contains all the calls to the LLM API with different system prompts.
├── main.py                   # The main pipeline that orchestrates calling LLM functions and contains business logic.
│
├── utils/                    # Utility functions.
│   ├──  rag_utils.py          # Functions related to Retrieval-Augmented Generation (RAG).
│   └── llm_calls.gh           # An example Grasshopper script calling this project as a Flask App.
│
├── server/                   # Server-side logic.
│   ├── keys.py               # API keys (not uploaded to GitHub, must be created locally).
│   ├── config.py             # Contains the logic to decide if the project runs with a local or cloud LLM.
│   └── gh_server.py          # A Flask App server that answers Grasshopper requests.
│
├── knowledge/                # Directory for knowledge databases.
│   └── embeddings.json       # Storage for embeddings.
```

## Getting Started

### Installation

To get started, clone this repository to your local machine:

```bash
git clone https://github.com/your-username/aia25-studio-agent.git
cd aia25-studio-agent
```

Then, install the required dependencies:

```bash
pip install -r requirements.txt
```

### Configuration

1. **API Keys**  
   - Navigate to the `server/` directory and create a `keys.py` file.  
   - Add your API keys or authentication credentials here. This file is not uploaded to GitHub for security reasons.

2. **Local or Cloud LLM Configuration**  
   - In the `server/config.py` file, you will find the logic to switch between using a local LLM or a cloud-based LLM.  
   - Customize this file to select the appropriate LLM for your project. You can add any new local models in this configuration file.

### Working with the Code

- **Adding New LLM Calls**  
  If you need to add new LLM calls, modify the `llm_calls.py` file. This file is where you define different system prompts and interface with the LLM API.

- **Creating New Knowledge Databases**  
  To add new knowledge databases (such as post-processed embeddings), place the new JSON files in the `knowledge/` directory. Modify `embeddings.json` or add new files To learn how to create the embeddings, visit my other repository [Knowledge-Pool-RAG](https://github.com/jomiguelcarv/LLM-Knowledge-Pool-RAG).

- **Main Pipeline**  
  The `main.py` file orchestrates the pipeline for calling LLM functions and integrating the responses into your design workflow. You can expand this file as needed to suit your design assistant copilot’s business logic.

- **Utility Functions**  
  The `utils/rag_utils.py` file contains functions related to Retrieval-Augmented Generation (RAG), useful for incorporating external knowledge into your LLM queries. You can add additional utility functions to extend the project’s capabilities.

### Customizing Your Assistant Copilot

Feel free to customize and extend this template to meet your specific design needs. The project structure is flexible, and you are encouraged to add new directories or files as necessary. However, be sure to keep the essential files organized and maintain the clear separation of concerns in the existing directory structure.
