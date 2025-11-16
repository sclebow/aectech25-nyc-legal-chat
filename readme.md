# ContractCadence

This project is an LLM assistant copilot designed to help architects write scope summaries and ask contract-related questions in natural language.  

## Installation

To install the necessary dependencies, run the following command:

```bash
pip install -r requirements.txt
```

We suggest using a virtual environment to manage dependencies.

## Usage

You will need to create a `.env` file in the root directory of the project to store your environment variables. At a minimum, you will need to set the following variables:

```
CLOUDFLARE_ACCOUNT_ID=your_cloudflare_account_id
CLOUDFLARE_API_KEY=your_cloudflare_api_key
```

To run the ContractCadence assistant, run the following command:

```bash
streamlit run main.py
```

This will start a local web server, and you can access the assistant through your web browser.

## Configuration

You can configure the assistant by modifying the `config.py` file.
This file contains various settings that control the behavior of the assistant, such as the model to use, the prompt templates, and other parameters.
