import random
from openai import OpenAI
# from server.keys import *
import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")
CLOUDFLARE_API_KEY = os.getenv("CLOUDFLARE_API_KEY")

# Mode control using getter/setter
_mode = "cloudflare"  # default

def get_mode():
    global _mode
    return _mode

def set_mode(new_mode, cf_gen_model=None, cf_sml_model=None, cf_emb_model=None):
    global _mode, client, completion_model, completion_model_sml, embedding_model
    _mode = new_mode
    client, completion_model, completion_model_sml, embedding_model = api_mode(_mode, cf_gen_model, cf_sml_model, cf_emb_model)

# API
local_client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
openai_client = OpenAI(api_key=OPENAI_API_KEY)
cloudflare_client = OpenAI(base_url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/v1", api_key = CLOUDFLARE_API_KEY)


# Embedding Models
local_embedding_model = "nomic-ai/nomic-embed-text-v1.5-GGUF"
cloudflare_embedding_model = "@cf/baai/bge-base-en-v1.5"
openai_embedding_model = "text-embedding-3-small"

# Notice how this model is not running locally. It uses an OpenAI key.
gpt4o = [
        {
            "model": "gpt-4o",
            "api_key": OPENAI_API_KEY,
            "cache_seed": random.randint(0, 100000),
        }
]

# Notice how this model is running locally. Uses local server with LMStudio
llama3 = [
        {
            "model": "lmstudio-community/Meta-Llama-3-8B-Instruct-GGUF", #change this to point to a new model
            'api_key': 'any string here is fine',
            'api_type': 'openai',
            'base_url': "http://127.0.0.1:1234",
            "cache_seed": random.randint(0, 100000),
        }
]

# Notice how this model is running locally. Uses local server with LMStudio
devstral = [
        {
            "model": "unsloth/Devstral-Small-2505-GGUF", #change this to point to a new model
            'api_key': 'any string here is fine',
            'api_type': 'openai',
            'base_url': "http://127.0.0.1:1234",
            "cache_seed": random.randint(0, 100000),
        }
]


# This is a cloudflare model
cloudflare_model = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"

# Define what models to use according to chosen "mode"
def api_mode (mode, cf_gen_model=None, cf_sml_model=None, cf_emb_model=None):
    if mode == "local":
        client = local_client
        completion_model = llama3[0]['model']
        completion_model_sml = 'mradermacher/Apriel-5B-Instruct-llamafied.i1'
        embedding_model = local_embedding_model
        return client, completion_model, completion_model_sml, embedding_model
    
    if mode == "cloudflare":
        client = cloudflare_client
        completion_model = cf_gen_model if cf_gen_model else cloudflare_model
        completion_model_sml = cf_sml_model if cf_sml_model else cloudflare_model
        embedding_model = cf_emb_model if cf_emb_model else cloudflare_embedding_model
        return client, completion_model, completion_model_sml, embedding_model
    
    elif mode == "openai":
        client = openai_client
        completion_model = gpt4o[0]['model']
        completion_model_sml = gpt4o[0]['model']
        embedding_model = openai_embedding_model

        return client, completion_model, completion_model_sml, embedding_model
    else:
        raise ValueError("Please specify if you want to run local or openai models")

client, completion_model, completion_model_sml, embedding_model = api_mode(_mode)