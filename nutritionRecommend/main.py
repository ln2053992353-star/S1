import operator
import re
import os, torch, json
import time
from typing import Annotated, List, TypedDict, Union
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from sentence_transformers import SentenceTransformer
import chromadb

# --- 1. Environment Configuration ---
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
model_id = "jinaai/jina-embeddings-v5-text-small"

# ARK (Volcano Engine) API config
ARK_API_KEY = "ark-5a78d6a7-41e6-4691-99ae-587fe5ced4b7-2ccc8"
ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
ARK_MODEL = "ep-20260426233528-lt7pn"

## database
client = chromadb.PersistentClient(path="../database/embeddingDB")
collection = client.get_collection(name="yeast_products_v5_expert")
print(f"Successfully opened database! Current record count: {collection.count()}")


# --- 2. Define State ---
class AgentState(TypedDict):
    raw_input: str  # Original user colloquial input
    refined_input: str  # Professional functional description after Node 1 translation
    refined_queries: List[str]  # Biochemical tags extracted after Node 2
    verification_score: int  # Verification score
    verification_rules: str  # Verification feedback suggestions
    search_results: List[dict]  # Database matching results
    iteration_count: int  # Loop counter
    final_recommendation: str  # Final output content


# --- 3. Initialize LLM (ARK / Volcano Engine) ---
llm = ChatOpenAI(
    model=ARK_MODEL,
    temperature=0.1,
    max_retries=3,
    api_key=ARK_API_KEY,
    base_url=ARK_BASE_URL,
)

embed_model = SentenceTransformer(
    model_id,
    device="cuda" if torch.cuda.is_available() else "cpu",
    trust_remote_code=True,
    model_kwargs={"trust_remote_code": True}
)

# --- 4. Define Node Functions ---

def translation_refiner(state: AgentState) -> AgentState:
    """Node 0.1: Functional Translation - Handling negative state conversion"""
    iteration = state.get("iteration_count", 0)

    system_prompt = """You are a professional expert in nutritional biochemistry and biomedical translation.
    Task: Translate colloquial user inputs (specifically negative physiological deficits) into standardized [Positive Functional Requirements].
    "If a match for specific biomolecules is identified, output the molecule names and their corresponding functions separately in the following structured format: 
    'Molecules: [Name1, Name2]; Functions: [Summary of specific effects]'. For example: 'Molecules: Glucose, Fatty acids; Functions: Energy-providing substrates and carbon sources for metabolism'."    
    Output Requirement: Only output the translated requirements, separated by commas, without any explanation.
    If a specific molecule name cannot be determined, provide a functional description, such as 'substances with xxx functions'.

    If the input is identified as a specific substance (e.g., 'I need glucose' or 'glucose'), output only the substance name.
    """
    # if failed in verify site，add the content to Prompt
    if iteration > 0 and state.get("verification_rules"):
        feedback = f"\n\n[attention]：Refinement required: The last output did not meet the passing threshold. Review the following feedback: {state['verification_rules']}. Please regenerate the translation"
        human_content = f"Original input: {state['raw_input']}{feedback}"
    else:
        human_content = state["raw_input"]
    res = llm.invoke([("system", system_prompt), ("human", human_content)])

    return {
        "refined_input": res.content.strip(),
        "iteration_count": iteration + 1
    }

def translation_verifier(state: AgentState) -> AgentState:
    """Node 0.2: Translation Verification - Ensuring the conversion from negative to positive is complete"""
    system_prompt = """
**Evaluation Criteria for Translation Accuracy**:

1.  **State Alleviation**: If the original input is a negative symptom, does the translated expression provide a functional solution or biological mechanism to mitigate that state?
2.  **Functional Alignment**: If the input describes a desired function, does the translation accurately map it to professional biochemical terminology?
3.  **Identity Clause**: If the input is identified as a specific chemical substance, the translation SHOULD remain identical to the input; do not penalize for lack of paraphrasing.
4.  **Database Context**: Since the backend is a "Yeast Products Database," prioritize professional terminology (e.g., metabolites, enzymes) but maintain a reasonable tolerance for synonymous biological descriptions.

**Output Format**: score@reason (Score range 0-10; 8+ is passing).
"""

    user_content = f"Original: {state['raw_input']}\nTranslated: {state['refined_input']}"
    res = llm.invoke([("system", system_prompt), ("human", user_content)])

    content = res.content.strip()

    # Initialize default values
    score = 0
    rules = "Parsing failed: Model did not return data in the correct format"

    # --- Safety Parsing Logic ---
    if "@" in content:
        parts = content.split("@")
        try:
            score_match = re.search(r'\d+', parts[0])
            if score_match:
                score = int(score_match.group())

            if len(parts) > 1:
                rules = parts[1].strip()
        except Exception:
            pass
    else:
        score_match = re.search(r'\d+', content)
        if score_match:
            score = int(score_match.group())
        rules = content

    return {"verification_score": score, "verification_rules": rules}

def semantic_refiner(state: AgentState):
    """Node 1: Tag Extraction - Converting to biochemical professional terminology"""
    prompt = f"Based on the functional requirement '{state['refined_input']}', extract biochemical professional tags. Output as comma-separated English keywords, maximum 20."
    res = llm.invoke(prompt)
    tags = [t.strip() for t in res.content.split(",")]
    return {"refined_queries": tags, "iteration_count": state.get("iteration_count", 0)}

def alignment_verifier(state: AgentState):
    """Node 2: Alignment Verification (Biochemical Alignment)"""
    system_prompt = """You are a senior scientific reviewer in the fields of biochemistry and synthetic biology.
    Please compare [User Original Requirement] with [Extracted Tags] to evaluate their professionalism and consistency.

    ### 1. Core Processing Flow:
    - **State Identification**: First, determine if the user input contains a negative state (e.g., "poor spirit", "tired", "anxious", "allergy").
    - **Intent Conversion**: If it is a negative state, it must be converted into a positive requirement for "improving/eliminating that state" (e.g., poor spirit/tired -> anti-fatigue, CNS stimulant; insomnia -> sedative, sleep aid).
    - **Alignment Verification**: Evaluate whether the [Extracted Tags] achieve the "converted" positive requirement through professional terminology.

    ### 2. Decision Criteria (Strictly Enforced):
    - **Professional Terminology Recognition**:
        - **Qualified Tags**: Chemical names (Alpha-Terpineol), classification names (Monoterpenoid), pharmacological effects (Anticonvulsant), metabolic pathways (Mevalonate pathway), application areas (Perfume, Repellent), etc.
        - **Unqualified Tags (0 points)**: Purely sensory colloquialisms (e.g., "smells good", "no energy"), descriptive short sentences. Tags containing unnecessary reduplication or repetitive labels will be judged as unqualified.
    - **Consistency Scoring**:
        - 10 points: Tags are all professional terms and perfectly cover the converted positive intent.
        - 8-9 points: Terms are professional, but there are very minor coverage deviations.
        - 1-7 points: Terms are professional, but severely miss the core converted requirement.
        - 0 points: Contains any "unqualified tags" or fails to complete the conversion from negative state to positive requirement.

    ### 3. Output Format Requirements:
    - **Format**: Score@Scoring Details@Sorted Tags
    - **Tag Sorting Rules**:
        - Sort by matching degree from high to low.
        - For negative states, priority follows: **Direct Physiological Regulation > Key Metabolic Pathway > Auxiliary Regulatory Hormones**.
        - Example: For "hunger", the order is: Nutrition Intake > Intestinal Peristalsis > Hormonal Regulation.
    """

    user_content = f"Original Requirement: {state['refined_input']}\nExtracted Tags: {state['refined_queries']}"
    res = llm.invoke([("system", system_prompt), ("human", user_content)])

    match = re.search(r"(\d+)\s*@\s*([^@]+)@?\s*(.*)", res.content)
    score = int(match.group(1)) if match else 0
    return {"verification_score": score, "verification_rules": match.group(2) if match else "Format Error"}

def dynamic_retriever(state: AgentState) -> AgentState:
    """
    Node: Vector Database Retrieval
    Function: Uses Jina-v5 to convert tags into vectors and retrieves Top-K results from the local library.
    """
    query_text = state["refined_input"]
    # 2. Generate query vector (using retrieval task adapter)
    query_vec = embed_model.encode(
        [query_text],
        task="retrieval",
        convert_to_numpy=True
    ).tolist()

    # 3. Retrieve from database (Top 3 candidates)
    results = collection.query(
        query_embeddings=query_vec,
        n_results=5
    )

    # 4. Format retrieval results and store in State
    candidates = []
    for i in range(len(results['documents'][0])):
        candidates.append({
            "name": results['metadatas'][0][i].get('product_name', 'Unknown'),
            "description": results['documents'][0][i],
            "metadata": results['metadatas'][0][i],
            "similarity": 1 - results['distances'][0][i]  # Semantic similarity
        })

    return {"search_results": candidates}

def fitness_evaluator(state: AgentState) -> AgentState:
    """
    Node: Llama Expert Verification (Direct Output Version)
    Function: Evaluates all candidates and returns structured JSON; no longer triggers retry loops.
    """
    # Basic check: If no results were retrieved
    if not state.get("search_results"):
        return {
            "final_recommendation": json.dumps({"error": "No candidate substances retrieved"}, ensure_ascii=False),
            "verification_score": 0
        }

    # Initialize strong logic LLM (prompt-based JSON, not native json_mode)
    verifier_llm = ChatOpenAI(
        model=ARK_MODEL,
        temperature=0.1,
        api_key=ARK_API_KEY,
        base_url=ARK_BASE_URL,
    )

    evaluation_list = []

    # --- 1. Iterate and evaluate all candidate records ---
    for candidate in state["search_results"]:
        display_name = candidate['metadata'].get('product_name') or candidate['name'] or "Unknown Substance"

        prompt = f"""
        You are an expert proficient in biochemistry. Please compare [User Requirement] with the [Candidate Record] in the database.

        [User Requirement]: "{state['refined_input']}"
        [Candidate Name]: "{display_name}"
        [Detailed Description]: "{candidate['description']}"

        Requirements:
        1. Determine if the substance can solve the user's requirement from a physiological or biochemical pathway.
        2. If the names match exactly (including abbreviations/isomers), give 100 points.
        3. If it partially satisfies or is highly relevant, give 1-99 points based on the match degree.

        You MUST output ONLY a raw JSON object on a single line. No markdown, no code fences, no extra text.
        Format: {{"score": integer, "reason": "brief reason"}}
        """

        try:
            response = verifier_llm.invoke(prompt)
            raw = response.content.strip()

            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1] if "\n" in raw else raw[3:]
                if raw.endswith("```"):
                    raw = raw[:-3]
                raw = raw.strip()

            res_json = json.loads(raw)

            evaluation_list.append({
                "product_name": display_name,
                "score": int(res_json.get("score", 0)),
                "reason": res_json.get("reason", "No clear reason"),
                "doi": candidate['metadata'].get('source_doi', 'N/A'),
                "similarity_score": round(candidate.get('similarity', 0), 4)
            })

        except Exception as e:
            evaluation_list.append({
                "product_name": display_name,
                "score": 0,
                "reason": f"Expert evaluation parsing failed: {str(e)}",
                "doi": candidate['metadata'].get('source_doi', 'N/A')
            })

    # --- 2. Sort Results ---
    evaluation_list.sort(key=lambda x: x['score'], reverse=True)

    # --- 3. Directly return results ---
    return {
        "final_recommendation": json.dumps(evaluation_list, ensure_ascii=False),
        "verification_score": evaluation_list[0]['score'] if evaluation_list else 0,
        "search_results": state["search_results"]
    }

def output_formatter(state: AgentState):
    """
    Final Node: Format and output recommendation results
    """

    try:
        results = json.loads(state["final_recommendation"])
    except:
        print("Error: Unable to parse evaluation results.")
        return

    # 2. Map descriptions for quick lookup via product_name
    description_map = {
        (res['metadata'].get('product_name') or res['name']): (
            res.get('description'))
        for res in state["search_results"]
    }

    # 3. Filter products meeting the standard (>= 70)
    recommended_items = [item for item in results if item['score'] >= 70]

    print("\n" + "=" * 50)
    print("🧬 Biochemical Product Recommendation Report")
    print("=" * 50 + "\n")

    if not recommended_items:
        print(
            "⚠️ No products met the recommendation standard (score >= 70). Showing the highest-scoring product in the database:\n")
        display_list = results[:1] if results else []
    else:
        display_list = recommended_items

    # 4. Loop print format
    for item in display_list:
        name = item['product_name']
        score = item['score']
        sim_score = item.get('similarity_score', 'N/A')
        reason = item['reason']
        doi = item['doi']
        desc = description_map.get(name, "No detailed description available")

        print(f"[Product Name]: {name}")
        print(f"[Evaluation Score]: {score}")
        print(f"[Semantic Similarity]: {sim_score}")
        print(f"[Recommendation Reason]: {reason}")
        print(f"[Functional Description]: {desc}")
        print(f"[DOI]: {doi}")
        print("-" * 30)

    return state

# --- 5. Build Transition Logic ---

def check_trans(state: AgentState):
    """
    翻译校验路由逻辑：
    1. 分数 >= 8: 通过，进入检索
    2. 分数 < 8 且 尝试次数 < 3: 失败，返回重试 (携带反馈)
    3. 尝试次数 >= 3: 停止，告知用户
    """
    score = state.get("verification_score", 0)
    count = state.get("iteration_count", 0)

    if score >= 8:
        return "pass"

    if count < 3:
        print(f"--- FAILED! (Trial #{count}), retrying with feedback... ---")
        return "retry"

    return "abort"


def abort_node(state: AgentState):
    """当尝试多次仍无法精准翻译时，引导用户"""
    print("Unable to identify your requirements accurately.")
    msg = f"After multiple attempts, the system could not translate '{state['raw_input']}' into precise biochemical requirements. We suggest providing a more specific description (e.g., mentioning specific metabolic issues, symptoms, or target substances)."
    return {"final_recommendation": msg}

def check_align(state: AgentState):
    return "pass" if state["verification_score"] >= 8 else "fail"


def check_final(state: AgentState):
    if state.get("final_recommendation"): return "end"
    return "stop" if state["iteration_count"] < 3 else "stop"

# --- 6. Build Workflow ---

workflow = StateGraph(AgentState)

workflow.add_node("trans_refiner", translation_refiner)
workflow.add_node("trans_verifier", translation_verifier)
workflow.add_node("retriever", dynamic_retriever)
workflow.add_node("evaluator", fitness_evaluator)
workflow.add_node("formatter", output_formatter)
workflow.add_node("abort_exit", abort_node)

workflow.set_entry_point("trans_refiner")
workflow.add_edge("trans_refiner", "trans_verifier")

workflow.add_conditional_edges(
    "trans_verifier",
    check_trans,
    {
        "pass": "retriever",    # 分数达标，去检索
        "retry": "trans_refiner", # 分数不达标且次数未满，带反馈重试
        "abort": "abort_exit"     # 超过3次，直接退出
    }
)

# workflow.add_conditional_edges("trans_verifier", check_trans, {"pass": "retriever", "fail": "trans_refiner"})
workflow.add_edge("retriever", "evaluator")
workflow.add_edge("evaluator", "formatter")
workflow.add_edge("formatter", END)
app = workflow.compile()

# --- 7. Run Test ---
if __name__ == "__main__":
    test_input = {"raw_input": "我想做玻璃", "iteration_count": 0}
    for output in app.stream(test_input):
        print(output)
