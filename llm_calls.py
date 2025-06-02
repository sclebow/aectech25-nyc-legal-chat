import server.config as config  
from cost_data.rsmeans_utils import get_cost_data
from project_utils.rag_utils import rag_call_alt

# Routing Functions Below
from project_utils import rag_utils, ifc_utils

# Remove global rsmeans_df and all references to load_rsmeans_data

# Routing & Filtering Functions
def classify_input(message: str) -> str:
    """
    Classify if the user message is related to architecture/buildings or not.
    Returns "Related" for architecture-related queries, otherwise "Refuse to answer".
    """
    response = config.client.chat.completions.create(
        model=config.completion_model,
        messages=[
            {"role": "system", "content": 
                "Your task is to classify if the user message is related to buildings and architecture or not. "
                "Output only a single word: If related, output 'Related'; if not, output 'Refuse to answer'."},
            {"role": "user", "content": message}
        ],
        temperature=0.0,  # Lower temperature for deterministic output
    )
    return response.choices[0].message.content.strip()

# # Design Ideation & Concept Functions
# def generate_concept(initial_info: str) -> str:
#     """
#     Generate a short, imaginative concept statement for a building design based on initial info.
#     Useful for early-stage creative brainstorming.
#     """
#     system_prompt = (
#         "You are a visionary designer at a leading architecture firm.\n"
#         "Your task is to craft a short, poetic and imaginative concept for a building design, based on the given information.\n"
#         "- Weave the provided details into a bold and evocative idea, like the opening lines of a story.\n"
#         "- Keep it one paragraph, focusing on mood and atmosphere rather than technical details.\n"
#         "- Avoid generic descriptions; use vivid imagery and emotional resonance."
#     )
#     user_prompt = f"What is the concept for this building?\nInitial information: {initial_info}"
#     response = config.client.chat.completions.create(
#         model=config.completion_model,
#         messages=[
#             {"role": "system", "content": system_prompt},
#             {"role": "user", "content": user_prompt}
#         ],
#         temperature=0.8,  # Higher temperature for more creative output
#     )
#     return response.choices[0].message.content.strip()

# def extract_attributes(description: str) -> str:
#     """
#     Extract key design attributes (shape, theme, materials) from a text description.
#     Returns a JSON string with fields "shape", "theme", "materials".
#     """
#     system_prompt = (
#         "You are a keyword extraction assistant.\n"
#         "# Instructions:\n"
#         "Extract relevant keywords from the given building description, categorized into three fields: shape, theme, materials.\n"
#         "Provide the output as a JSON object with exactly those keys.\n"
#         "# Rules:\n"
#         "- If a category has no relevant info, use \"None\" as the value.\n"
#         "- Separate multiple keywords with commas in a single string.\n"
#         "- Output JSON only, no explanation or extra text."
#     )
#     user_prompt = f"GIVEN DESCRIPTION:\n{description}"
#     response = config.client.chat.completions.create(
#         model=config.completion_model,
#         messages=[
#             {"role": "system", "content": system_prompt},
#             {"role": "user", "content": user_prompt}
#         ],
#         temperature=0.0,  # Lower temperature for more deterministic output
#     )
#     return response.choices[0].message.content.strip()

# def create_question(theme: str) -> str:
#     """
#     Create an open-ended question for further exploration, based on a given theme (e.g., a design theme).
#     This can be used to prompt the knowledge base or user for more input.
#     """
#     system_prompt = (
#         "You are a thoughtful research assistant specializing in architecture.\n"
#         "Your task is to formulate an open-ended question related to the theme provided, inviting deeper exploration.\n"
#         "- The question should connect to architectural examples or theory (e.g., notable projects, historical context) related to the theme.\n"
#         "- Keep it open-ended and intellectually curious, so it could be answered with detailed insights.\n"
#         "- Do not include any extra text, just the question itself."
#     )
#     user_prompt = theme  # The theme or topic from which to derive a question
#     response = config.client.chat.completions.create(
#         model=config.completion_model,
#         messages=[
#             {"role": "system", "content": system_prompt},
#             {"role": "user", "content": user_prompt}
#         ],
#         temperature=0.3,  # Adjust temperature for more or less creative responses
#     )
#     return response.choices[0].message.content.strip()

# # Group 4 Prompts:

# Cost Estimation & ROI Analysis Functions
def analyze_cost_tradeoffs(query: str) -> str:
    """
    Analyze cost trade-offs based on the user's query.
    E.g., comparing two design options or the impact of a design change on cost/ROI.
    """
    system_prompt = (
        "You are an expert architectural cost consultant.\n"
        "# Task:\n"
        "Given a scenario or query, analyze and compare the cost trade-offs between the design options or changes described. Consider both initial construction costs and long-term financial impacts (such as ROI, maintenance, or operational costs) if relevant.\n"
        "# Instructions:\n"
        "- Break down each option or change, explaining how it affects construction cost (e.g., cost per area, material and/or labor differences) and potential changes to the project's value.\n"
        "- Highlight the pros and cons of each option: which is more expensive upfront, which may save money over time, and any relevant risks or benefits.\n"
        "- Use any specific numbers given in the query; if none are given, provide reasoned estimates or qualitative comparisons.\n"
        "- Clearly state any assumptions for your estimates (e.g., unit costs, rates, location, or market conditions).\n"
        "- Structure your answer logically (e.g., Option A vs Option B, or Before vs After change), and quantify differences where possible.\n"
        "- Conclude with a recommendation or summary of which option is cost-favorable and why, if asked for advice.\n"
        "- Always mention that actual costs can vary by project and location, and the comparison is based on typical scenarios.\n"
        "# Example:\n"
        "Query: Should we use steel or timber for the main structure?\n"
        "Output: Steel framing typically costs 10-20% more than timber for similar spans, but offers greater durability and fire resistance. Timber is less expensive upfront and can be installed faster, reducing labor costs. However, steel may have lower maintenance costs over the building's life. In most urban markets, timber is more cost-effective for low-rise buildings, while steel is preferred for high-rise or long-span structures. Actual costs depend on local material prices and labor rates." # TODO fact-check this example
    )
    # (Optionally, I think we might be able to retrieve relevant data here via rag_call_alt if needed to inform the comparison.)
    response = config.client.chat.completions.create(
        model=config.completion_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ],
        temperature=0.5,  # Adjust temperature for more or less creative responses
    )
    return response.choices[0].message.content.strip()

# def analyze_roi_sensitivity(query: str) -> str:
#     """
#     Analyze ROI sensitivity given a scenario in the user's query.
#     Describes how changes in inputs (cost, revenue, etc.) affect the return on investment.
#     """
#     system_prompt = (
#         "You are a financial analyst for architecture projects, focusing on ROI sensitivity.\n"
#         "# Task:\n"
#         "Given a scenario or query, explain how the project's return on investment (ROI) or other financial metrics would change if key variables (such as construction cost, rent, interest rate, or occupancy) increase or decrease.\n"
#         "# Instructions:\n"
#         "- Identify the main variables mentioned in the query that could impact ROI.\n"
#         "- For each variable, describe how changes (e.g., +10% cost, -10% revenue) would affect ROI or payback period.\n"
#         "- Use approximate calculations if possible (e.g., \"ROI drops from 15% to ~12% if cost rises 10%\"), or provide qualitative analysis if no numbers are given.\n"
#         "- Clearly state any assumptions you make (such as base ROI, cost, or revenue figures).\n"
#         "- Highlight which variables have the greatest impact on ROI, if relevant.\n"
#         "- End with a note that these are scenario estimates for planning, not exact predictions, and that actual results may vary by project and market.\n"
#         "# Example:\n"
#         "Query: What happens to ROI if construction costs rise by 10% and rents fall by 5%?\n"
#         "Output: Assuming a base ROI of 15%, a 10% increase in construction costs would reduce ROI to approximately 13%. If rents also fall by 5%, ROI could drop further to around 11%. ROI is generally more sensitive to changes in revenue than to moderate cost overruns. Actual impacts depend on the project's financial structure and local market conditions." # TODO fact-check this example
#     )
#     response = config.client.chat.completions.create(
#         model=config.completion_model,
#         messages=[
#             {"role": "system", "content": system_prompt},
#             {"role": "user", "content": query}
#         ],
#         temperature=0.5,  # Adjust temperature for more or less creative responses
#     )
#     return response.choices[0].message.content.strip()

# def assess_material_impact(query: str) -> str:
    """
    Evaluate how different material or structural choices impact cost (and possibly ROI or schedule).
    """
    system_prompt = (
        "You are a building materials cost expert, specializing in evaluating the impact of material and structural choices on project cost, ROI, and schedule.\n"
        "# Task:\n"
        "Given a query comparing materials or systems, analyze and compare their effects on initial construction cost, long-term costs (maintenance, durability), schedule, and ROI if relevant.\n"
        "# Instructions:\n"
        "- For each material or system mentioned, discuss:\n"
        "    - Initial cost differences (e.g., per area, percentage difference, or qualitative comparison if no data).\n"
        "    - Long-term implications: for example, durability, maintenance, insurance, resale value, and sustainability if relevant.\n"
        "    - Effects on construction schedule (e.g., faster/slower installation).\n"
        "    - Any impact on ROI or lifecycle cost, if applicable.\n"
        "- Clearly state any assumptions or typical benchmarks you use.\n"
        "- Note context factors: local availability, labor skill, incentives, or code requirements that might influence the choice.\n"
        "- Structure your answer by material/system, then provide a concluding comparison or recommendation.\n"
        "- Always add a caveat that market prices and impacts vary by region and project, so the comparison is general.\n"
        "# Example:\n"
        "Query: Compare cross-laminated timber (CLT) and reinforced concrete for a mid-rise building.\n"
        "Output: CLT typically costs 5-15% more per square foot than reinforced concrete in most markets, but can reduce construction time by up to 30% due to prefabrication. CLT offers sustainability benefits and lower embodied carbon, but may require additional fireproofing and has higher insurance costs in some regions. Concrete is more durable and widely available, with lower long-term maintenance. The best choice depends on project priorities, local expertise, and regulatory context. Actual costs and benefits will vary by location." # TODO fact-check this example
    )
    response = config.client.chat.completions.create(
        model=config.completion_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ],
        temperature=0.3,  # Adjust temperature for more or less creative responses
    )
    return response.choices[0].message.content.strip()

def classify_question_type(message: str) -> str:
    """
    Returns the category of the query: Cost Benchmark, ROI Analysis, Design-Cost Comparison, Value Engineering, or Project Data Lookup.
    """
    system_prompt = (
        "You are a query classification agent for a building project assistant.\n"
        "Classify the user's query into one of the following categories:\n"
        "1. Cost Benchmark\n"
        "2. ROI Analysis\n"
        "3. Design-Cost Comparison\n"
        "4. Value Engineering\n"
        "5. Project Data Lookup\n"
        "Return only the category name.\n\n"
        "Examples:\n"
        "Query: What is the typical cost per sqft for concrete in NYC?\nOutput: Cost Benchmark\n"
        "Query: How much would I save by replacing glass with stone on the facade?\nOutput: Design-Cost Comparison\n"
        "Query: If rents fall by 10%, what happens to ROI?\nOutput: ROI Analysis\n"
        "Query: How can I lower construction costs without reducing quality?\nOutput: Value Engineering\n"
        "Query: How many units does my current project support and what’s the total cost of concrete?\nOutput: Project Data Lookup"
    )

    response = config.client.chat.completions.create(
        model=config.completion_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ],
        temperature=0.0,
    )
    return response.choices[0].message.content.strip()

agent_prompt_dict = {
    "analyze cost tradeoffs": """
    You are a cost consultant.
    Analyze trade-offs between different materials or design choices mentioned.
    Compare based on construction cost, longevity, and typical ROI impacts.

    Example:
    Query: Should we use cross-laminated timber or reinforced concrete for the structure?
    Output: CLT costs $320/sqft vs concrete at $280/sqft. CLT may reduce construction time by 15%, but has higher insurance costs. Concrete offers better durability.
    """,


    "analyze roi sensitivity": """
    You are a financial analyst.
    Evaluate how changes in construction cost, rent, or occupancy affect ROI.
    Provide scenario-based sensitivity analysis.

    Example:
    Query: What happens if construction costs go up by 10%?
    Output: ROI decreases from 12% to ~10.5%, assuming stable rents and no other changes.
    """,
    "get cost benchmarks": """
    You are a cost benchmark assistant.
    Provide standard cost per sqft values or material unit prices from industry data.
    Tailor output to context (location, building type) if given.

    Example:
    Query: What is the average cost per sqft for office buildings in London?
    Output: £400–£550/sqft, depending on spec and location (2023 estimate).
    """,


    "suggest cost optimizations": """
    You are a value engineering assistant.
    Suggest practical ways to reduce project costs while maintaining design intent.
    Focus on materials, layout, structural systems.

    Example:
    Query: How can we reduce cost by 10% without changing the layout?
    Output:
    1. Replace curtain wall with punched window system (~8% savings).
    2. Use modular bathrooms (~2–3% savings).
    """,

    
    "analyze project data inputs": """
    You are a project insight analyst.
    Use IFC/CSV and data encoding outputs to extract cost-related insights based on available quantities.
    Return findings like concrete volume cost, or unit type ratios.

    Example:
    Query: What is the total concrete cost for this project?
    Output: Based on 500 m³ at $120/m³, total cost = $60,000.
    """
}

def run_llm_query(system_prompt: str, user_input: str, stream: bool = False, max_tokens: int = 1500):
    import server.config as config
    if not stream:
        response = config.client.chat.completions.create(
            model=config.completion_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ],
            temperature=0.0,
            max_tokens=max_tokens,
        )
        return str(response.choices[0].message.content).strip()
    else:
        response = config.client.chat.completions.create(
            model=config.completion_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ],
            temperature=0.0,
            max_tokens=max_tokens,
            stream=True,
        )
        def generator():
            for chunk in response:
                delta = getattr(chunk.choices[0], 'delta', None)
                if delta and hasattr(delta, 'content') and delta.content:
                    yield delta.content
        return generator()

def get_project_data_answer(query: str) -> str:
    prompt = ("You are an assistant that analyzes project data inputs from an IFC file."
              "You have access to a function that returns statistics about the project elements."
              "Project elements in the IFC file include IfcWall, IfcSlab, IfcColumn, IfcBeam, IfcRoof, IfcStair, IfcDoor, IfcWindow, and IfcCurtainWall."
              "Provide a list of which elements are needed to answer the question."
              "Provide only the list of elements in a comma separated list, no other text."
              f"User's question: {query}"
    )
    response = run_llm_query(system_prompt=prompt, user_input=query)
    if response:
        stats = ifc_utils.get_shape_statistics(response.strip()) 
        following_prompt = (
            "You are a project data analysis assistant."
            "Answer the user's question using the following project data statistics"
            f"User's question: {query}"
            f"{response} statistics: {stats}."
        )
        return following_prompt
    else:
        return "No relevant project data found."

def get_cost_benchmark_answer(query: str, stream: bool = False, use_rag: bool = False, collection=None, ranker=None, max_tokens: int = 1500):
    """
    Answer a cost benchmark question using both RSMeans data and a tailored LLM prompt.
    If RSMeans data is found, include a summary table and a short LLM-generated explanation referencing the data.
    If not, fallback to LLM only.
    If use_rag is True, use the RAG pipeline to answer and return (answer, sources).
    """
    if use_rag and collection is not None and ranker is not None:
        # Use RAG pipeline for cost benchmark
        agent_prompt = agent_prompt_dict["get cost benchmarks"]
        answer, sources = rag_call_alt(query, collection, ranker, agent_prompt=agent_prompt, max_context_length=max_tokens)
        return answer, sources
    result = get_cost_data(query)
    if hasattr(result, 'empty') and not result.empty:
        summary_md = result[['Masterformat Section Code', 'Section Name', 'Name', 'Unit', 'Total Incl O&P']].to_markdown(index=False)
        system_prompt = (
            "You are a cost benchmark assistant. "
            "Given the following RSMeans cost data (in markdown table format) and the user's question, provide a concise, clear answer. "
            "Summarize the typical cost per unit, mention any relevant range, and note that actual costs may vary by project and location. "
            "If multiple items are shown, explain the range and what affects it. "
            "Always explicitly list out any assumptions you are making (such as location, year, unit, or scope). "
            "Do not invent numbers; use only the data provided."
        )
        user_input = f"User question: {query}\n\nRSMeans data (markdown table):\n{summary_md}"
        if not stream:
            explanation = run_llm_query(system_prompt, user_input, max_tokens=max_tokens)
            return f"**RSMeans Data:**\n\n{summary_md}\n\n**Interpretation:**\n{explanation}"
        else:
            def generator():
                yield f"**RSMeans Data:**\n\n{summary_md}\n\n**Interpretation:**\n"
                for chunk in run_llm_query(system_prompt, user_input, stream=True, max_tokens=max_tokens):
                    yield chunk
            return generator()
    else:
        prompt = (
            agent_prompt_dict["get cost benchmarks"] + "\nAlways explicitly list out any assumptions you are making (such as location, year, unit, or scope)."
        )
        return run_llm_query(system_prompt=prompt, user_input=query, stream=stream, max_tokens=max_tokens)

def classify_data_sources(message: str, data_sources: dict) -> dict:
    """
    Classify the user message into one of the five core data sources.
    Returns a dictionary with boolean values indicating which data sources are relevant.
    """
    system_prompt = (
        "You are a data source classification agent for a building project assistant.\n"
        "Classify the user's query into one or more of the following data sources:\n"
        + "\n".join([f"{key}: {value}" for key, value in data_sources.items()]) + "\n"
        "Return a comma-separated list of the relevant data sources, or 'None' if none apply.\n\n"
        "Examples:\n"
        "Query: What is the typical cost per sqft for concrete in NYC?\nOutput: rsmeans\n"
        "Query: How many units does my current project support and what’s the total cost of concrete?\nOutput: project data, rsmeans\n"
        "Query: What is the value of this building based on its size and type?\nOutput: value model\n"
        "Query: How can I reduce construction costs without changing the layout?\nOutput: knowledge base, cost model\n"
        "Query: What is the total concrete cost for this project?\nOutput: project data, rsmeans\n"
    )

    response = config.client.chat.completions.create(
        model=config.completion_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ],
        temperature=0.0,
    )
    
    classification = response.choices[0].message.content.strip()
    if classification.lower() == "none":
        return {key: False for key in data_sources.keys()}
    
    # Split the classification into a list and create a dictionary with boolean values
    classified_sources = classification.split(", ")
    return {key: (key in classified_sources) for key in data_sources.keys()}

def get_rsmeans_context(message: str) -> str:
    """
    Get the RSMeans context for the user message.
    Returns a string with the RSMeans data or a prompt to use RSMeans.
    """
    # Here we could implement a more complex logic to fetch relevant RSMeans data
    # For now, we just return a prompt to use RSMeans
    return "" # Placeholder


def get_ifc_context(message: str) -> str:
    """
    Get the IFC context for the user message.
    Returns a string with the IFC data or a prompt to use IFC.
    """
    # Here we could implement a more complex logic to fetch relevant IFC data
    # For now, we just return a prompt to use IFC
    return "" # Placeholder


def get_project_data_context(message: str) -> str:
    """
    Get the project data context for the user message.
    Returns a string with the project data or a prompt to use project data.
    """
    # Here we could implement a more complex logic to fetch relevant project data
    # For now, we just return a prompt to use project data
    return "" # Placeholder


def get_knowledge_base_context(message: str) -> str:
    """
    Get the knowledge base context for the user message.
    Returns a string with the knowledge base data or a prompt to use the knowledge base.
    """
    # Here we could implement a more complex logic to fetch relevant knowledge base data
    # For now, we just return a prompt to use the knowledge base
    return "" # Placeholder


def get_value_model_context(message: str) -> str:
    """
    Get the value model context for the user message.
    Returns a string with the value model data or a prompt to use the value model.
    """
    # Here we could implement a more complex logic to fetch relevant value model data
    # For now, we just return a prompt to use the value model
    return "" # Placeholder


def get_cost_model_context(message: str) -> str:
    """
    Get the cost model context for the user message.
    Returns a string with the cost model data or a prompt to use the cost model.
    """
    # Here we could implement a more complex logic to fetch relevant cost model data
    # For now, we just return a prompt to use the cost model
    return "" # Placeholder


def route_query_to_function(message: str, collection=None, ranker=None, use_rag: bool=False, stream: bool = False, max_tokens: int = 1500):
    """
    Classify the user message into one of the five core categories and route it to the appropriate response function.
    If stream=True, returns a generator for streaming output.
    """
    data_sources = {
        "rsmeans": "This is a database for construction cost data, including unit costs for various materials and labor.",
        "ifc": "This is a database for a building model in IFC format, which includes detailed information about the building's components and quantities.",
        "project data": "This is a database for project data, which includes volumes, areas, and quantities of building elements.",
        "knowledge base": "This is a knowledge base for architecture and construction, which includes general information about design, materials, and construction practices.",
        "value model": "This is a machine learning model that predicts the value of a building based some of its features, such as size, and type.",
        "cost model": "This is a machine learning model that predicts the cost of a building based on some of its features, such as size, and type.",
    }

    # Run the query through the classification function
    data_sources_needed_dict = classify_data_sources(message, data_sources)

    # Debugging output
    print(f"Data sources needed: {data_sources_needed_dict}")

    # Create a data context dictionary based on the classification
    data_context = {}

    if data_sources_needed_dict["rsmeans"]:
        data_context["rsmeans"] = get_rsmeans_context(message)
    if data_sources_needed_dict["ifc"]:
        data_context["ifc"] = get_ifc_context(message)
    if data_sources_needed_dict["project data"]:
        data_context["project data"] = project_data_context
    if data_sources_needed_dict["knowledge base"]:
        data_context["knowledge base"] = get_knowledge_base_context(message)
    if data_sources_needed_dict["value model"]:
        data_context["value model"] = get_value_model_context(message)
    if data_sources_needed_dict["cost model"]:
        data_context["cost model"] = get_cost_model_context(message)

    

    # classification = classify_question_type(message).lower()
    # print(classification)

    # match classification:
    #     case x if "cost benchmark" in x:
    #         answer = get_cost_benchmark_answer(message, stream=stream, use_rag=use_rag, collection=collection, ranker=ranker, max_tokens=max_tokens)
    #         if use_rag:
    #             return answer  # already (answer, sources)
    #         else:
    #             return answer
    #     case x if "roi analysis" in x:
    #         prompt = agent_prompt_dict["analyze roi sensitivity"]
    #     case x if "design-cost comparison" in x:
    #         prompt = agent_prompt_dict["analyze cost tradeoffs"]
    #     case x if "value engineering" in x:
    #         prompt = agent_prompt_dict["suggest cost optimizations"]
    #     case x if "project data lookup" in x:
    #         # prompt = agent_prompt_dict["analyze project data inputs"]
    #         prompt = get_project_data_answer(message)
    #     case _:
    #         if use_rag:
    #             return ("I'm sorry, I cannot process this request. Please ask a question related to cost, ROI, or project data.", None)
    #         else:
    #             return "I'm sorry, I cannot process this request. Please ask a question related to cost, ROI, or project data."
    # if use_rag:
    #     (answer, source) = rag_call_alt(message, collection, ranker, agent_prompt=prompt, max_context_length=max_tokens)
    #     return (answer, source)
    # else:
    #     return run_llm_query(system_prompt=prompt, user_input=message, stream=stream, max_tokens=max_tokens)