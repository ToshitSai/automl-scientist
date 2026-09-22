import os
import json
import re
from typing import Dict, Any, Optional, List
from backend.llm import query_llm
from database.store import store
import backend.config

INTENT_CATEGORIES = [
    "CONFIRM_PENDING_ACTION",
    "RESEARCH_FOLLOWUP",
    "RESEARCH_CONTROL",
    "EXPLANATION",
    "CODING",
    "DEEP_RESEARCH",
    "DATA_ANALYSIS",
    "DOCUMENT_ANALYSIS",
    "RESEARCH_START",
    "REPORT_REQUEST",
    "TECHNICAL_DETAILS",
    "CASUAL_CHAT",
]

# --------------------------------------------------------------------------- #
# System prompts
# --------------------------------------------------------------------------- #
# General-purpose assistant prompt (see owner directive §10). The assistant must
# answer the user's actual question directly and completely, and must NOT force
# the conversation into the ML/research workflow.
GENERAL_ASSISTANT_SYSTEM_PROMPT = (
    "You are a highly capable general-purpose AI assistant. Answer the user's "
    "actual question directly, completely, and clearly in natural English. "
    "Address every part of the question (for example, both 'what it is' and "
    "'why it is used'). Do NOT mention datasets, model training, experiments, "
    "hypotheses, or research studies unless the user explicitly asks about them, "
    "and do NOT force the conversation into machine learning. Never invent "
    "facts, results, sources, or capabilities — if you are not sure, say so. "
    "Be concise but complete."
)

CODING_SYSTEM_PROMPT = (
    "You are an expert programmer. Provide correct, clean, runnable code that "
    "directly solves the user's request, followed by a brief explanation of how "
    "it works. Do NOT mention datasets, model training, or research unless the "
    "user asks. Never invent library behaviour you are unsure about."
)

# --------------------------------------------------------------------------- #
# ML / data-science concept knowledge base (used for routing AND answers).
# --------------------------------------------------------------------------- #
CONCEPT_KNOWLEDGE = {
    "python": "Python is a high-level, open-source programming language widely used in artificial intelligence, machine learning, data science, and web development due to its clean syntax and extensive ecosystem of libraries like PyTorch, TensorFlow, and Scikit-Learn.",
    "artificial intelligence": "Artificial Intelligence (AI) is technology that enables computers and machines to simulate human intelligence—such as understanding language, recognizing visual patterns, learning from experience, and solving complex problems.",
    "ai": "Artificial Intelligence (AI) is technology that enables computers and machines to simulate human intelligence—such as understanding language, recognizing visual patterns, learning from experience, and solving complex problems.",
    "machine learning": "Machine Learning (ML) is a branch of artificial intelligence where algorithms automatically detect patterns in data to make predictions or decisions without being explicitly programmed for every scenario.",
    "ml": "Machine Learning (ML) is a branch of artificial intelligence where algorithms automatically detect patterns in data to make predictions or decisions without being explicitly programmed for every scenario.",
    "deep learning": "Deep Learning is a subset of machine learning based on multi-layered artificial neural networks. It is particularly effective at processing complex, high-dimensional unstructured data like images, audio, and natural language.",
    "neural network": "An artificial neural network is a machine learning model inspired by biological brains. It consists of connected layers of nodes (neurons) that learn hierarchical representations of input data.",
    "neural networks": "An artificial neural network is a machine learning model inspired by biological brains. It consists of connected layers of nodes (neurons) that learn hierarchical representations of input data.",
    "recall": "Recall measures the proportion of actual positive cases that a model successfully detected. High recall ensures that very few critical positive cases escape undetected.",
    "precision": "Precision measures how many of the positive predictions made by a model were actually correct. High precision ensures that false positive alarms are minimized.",
    "f1": "The F1 Score is the harmonic mean of precision and recall. It provides a single balanced metric for evaluating classification models, especially on imbalanced datasets.",
    "f1 score": "The F1 Score is the harmonic mean of precision and recall. It provides a single balanced metric for evaluating classification models, especially on imbalanced datasets.",
    "auc": "AUC (Area Under the ROC Curve) measures a classification model's overall ability to distinguish between positive and negative cases across all possible decision thresholds.",
    "pr-auc": "PR-AUC (Precision-Recall Area Under Curve) evaluates precision vs. recall across decision thresholds, making it an ideal performance metric for severely imbalanced datasets.",
    "roc": "The ROC curve plots the True Positive Rate against the False Positive Rate at various classification thresholds to illustrate model diagnostic capability.",
    "xgboost": "XGBoost (Extreme Gradient Boosting) is an optimized open-source library that implements gradient boosted decision trees designed for speed, scalability, and high tabular predictive accuracy.",
    "gradient boosting": "Gradient Boosting is an ensemble machine learning technique that builds decision trees sequentially, where each new tree aims to minimize the errors made by previous trees.",
    "overfitting": "Overfitting occurs when a model learns noise and specific details of training data too closely, resulting in stellar performance on training data but poor generalization to new, unseen test data.",
    "underfitting": "Underfitting happens when a model is too simple to capture the underlying patterns in data, leading to poor predictive performance on both training and testing datasets.",
    "baseline": "A baseline model is a simple initial benchmark (such as Logistic Regression or a Decision Tree) used to establish a performance floor before evaluating more complex algorithms.",
    "training": "Training is the process of feeding data to a machine learning model so that it learns patterns by gradually adjusting its internal parameters, which lets it make predictions on new, unseen data.",
    "dataset": "A dataset is a structured collection of data—usually rows of records described by columns of features—that is used to train, validate, and test machine learning models.",
    "data": "Data is a collection of facts, measurements, or observations—often organized into rows and columns—that a machine learning model learns patterns from.",
    "model": "In machine learning, a model is a mathematical function that learns patterns from data so it can make predictions or decisions about new, unseen inputs.",
    "sql": "SQL (Structured Query Language) is a standard language for storing, querying, and managing data held in relational databases. It is important because almost every application needs to persist and retrieve data, and SQL provides a consistent, declarative way to filter, join, aggregate, and update that data across virtually all relational database systems.",
    "c++": "C++ is a high-performance, general-purpose programming language that extends C with object-oriented features; it is widely used for system software, game engines, and performance-critical applications.",
    "c": "C is a general-purpose procedural programming language known for its efficiency and low-level memory access, forming the foundation for many later languages including C++.",
    "confusion matrix": "A confusion matrix is a table that compares a model's predicted labels against the true labels, breaking results into true positives, false positives, true negatives, and false negatives.",
    "false positive": "A false positive is a prediction error where the model incorrectly flags a negative case as positive—such as marking a legitimate transaction as fraud.",
    "false negative": "A false negative is a prediction error where the model misses an actual positive case—such as failing to flag a genuinely fraudulent transaction.",
    "feature": "A feature is an individual measurable property or column of the data (such as transaction amount) used as input to help a model make its prediction.",
}

# --------------------------------------------------------------------------- #
# General-knowledge base for ordinary (non-ML) questions. These entries are
# accurate, self-contained answers used as a deterministic fallback when no LLM
# provider is reachable (e.g. the serverless deployment has no API key). They
# are looked up by subject, NOT used for whole-word routing, so common phrasing
# does not get mis-routed.
# --------------------------------------------------------------------------- #
GENERAL_KNOWLEDGE = {
    "javascript": "JavaScript is a high-level programming language used mainly to make websites interactive and dynamic. While HTML provides a page's structure and CSS controls its appearance, JavaScript adds behavior — responding to clicks, validating forms, updating content without a reload, animations, and fetching data from servers. It runs natively in every web browser, and with runtimes like Node.js it is also used for server-side/backend development, APIs, mobile apps (e.g. React Native), and desktop apps. Its presence in all browsers and its large ecosystem of libraries and frameworks (React, Vue, Angular) are why it is one of the most widely used languages in the world.",
    "java": "Java is a high-level, object-oriented programming language designed for portability: source code is compiled to bytecode that runs on any device with a Java Virtual Machine (JVM), following the 'write once, run anywhere' principle. It is widely used for enterprise and backend systems, Android app development, large-scale distributed systems, and financial services, and is valued for its stability, strong static typing, and extensive standard library.",
    "html": "HTML (HyperText Markup Language) is the standard markup language used to structure content on the web. It uses tags to define elements such as headings, paragraphs, links, images, and forms. HTML provides a page's structure, CSS controls its appearance, and JavaScript adds interactivity; browsers read HTML and render it into the page you see.",
    "css": "CSS (Cascading Style Sheets) is the language used to describe how HTML elements are displayed. It controls layout, colors, fonts, spacing, responsiveness, and animation, separating a page's presentation from its structure. 'Cascading' means styles can be inherited and overridden based on specificity and order. With HTML (structure) and JavaScript (behavior), CSS is a core technology of the web.",
    "recursion": "Recursion is a technique where a function solves a problem by calling itself on a smaller version of that problem. Every recursive function needs a base case (a condition that stops the recursion) and a recursive case (which reduces the problem toward the base case). Common examples include factorials, tree traversal, and the Fibonacci sequence. Recursion often makes divide-and-conquer or self-similar problems clearer than loops, but each call uses stack memory, so very deep recursion can be slower or cause a stack overflow.",
    "gravity": "Gravity is the force of attraction between objects that have mass. The more mass an object has, the stronger its pull, and the force weakens with distance. On Earth, gravity gives objects weight and makes them fall at about 9.8 m/s². Newton described it as a universal force between masses; Einstein's general relativity later explained it as the curvature of spacetime caused by mass and energy. Gravity keeps planets in orbit around the Sun, the Moon around Earth, and holds galaxies together.",
    "photosynthesis": "Photosynthesis is the process by which green plants, algae, and some bacteria convert light energy — usually from the Sun — into chemical energy stored in glucose. Using chlorophyll, they take in carbon dioxide (CO₂) from the air and water (H₂O) from the soil and, with light energy, produce glucose (C₆H₁₂O₆) while releasing oxygen (O₂) as a by-product. The overall reaction is 6CO₂ + 6H₂O + light → C₆H₁₂O₆ + 6O₂. It is the foundation of most food chains and the main source of oxygen in Earth's atmosphere.",
    "internet": "The Internet is a global network of interconnected computers that communicate using standardized protocols, mainly TCP/IP. Data is split into packets that are routed independently across many networks and reassembled at the destination. Services such as the World Wide Web, email, and file transfer run on top of it — the Web specifically uses HTTP(S) to link documents (pages) via URLs. Routers direct traffic and DNS translates human-readable names into IP addresses. In short, the Internet is the underlying infrastructure, and the Web is one service that runs over it.",
    "world wide web": "The World Wide Web (the Web) is a system of interlinked documents and resources accessed over the Internet. Proposed by Tim Berners-Lee in 1989, it uses HTML to write pages, URLs to address and link them, and HTTP to transfer them; browsers request pages and render them. The Web is one of the main services running on top of the Internet, which is the underlying network.",
    "http": "HTTP (HyperText Transfer Protocol) is the protocol used to transfer data on the World Wide Web. A client (usually a browser) sends a request to a server using methods like GET (fetch data) or POST (submit data), and the server replies with a status code (e.g. 200 OK, 404 Not Found) and often a body such as an HTML page or JSON. HTTPS is the encrypted version, using TLS to protect data in transit.",
    "telephone": "The telephone was invented by Alexander Graham Bell, who was awarded the first U.S. patent for it in March 1876. His design converted sound into an electrical signal that traveled over a wire and was turned back into sound at the other end. Several inventors — including Elisha Gray and Antonio Meucci — developed related devices around the same time and there were patent disputes, but Bell is credited with the first practical telephone and its foundational patent.",
    "algorithm": "An algorithm is a finite, well-defined sequence of steps for solving a problem or performing a computation. It takes inputs, processes them through those steps, and produces an output. Algorithms are the foundation of all software and are judged by correctness and efficiency, usually expressed as time and space complexity (e.g. O(n log n)). Examples include sorting (quicksort, merge sort), searching (binary search), and graph traversal (BFS, DFS).",
    "data structure": "A data structure is a way of organizing and storing data so it can be used efficiently. Different structures suit different tasks: arrays and lists for ordered collections, hash tables/maps for fast key-value lookup, stacks and queues for last-in-first-out and first-in-first-out access, and trees and graphs for hierarchical or networked relationships. Choosing the right data structure is key to writing fast, memory-efficient programs.",
    "database": "A database is an organized collection of structured data stored electronically so it can be created, read, updated, and deleted efficiently. Relational databases (like PostgreSQL or MySQL) store data in tables of rows and columns and are queried with SQL; NoSQL databases (like MongoDB) use documents, key-values, or graphs for more flexible schemas. Databases let applications persist data and run fast, reliable queries.",
    "api": "An API (Application Programming Interface) is a set of rules and protocols that lets different software systems communicate. It defines the requests you can make, how to make them, and the responses you'll get, so one program can use another's functionality without knowing its internals. Web APIs commonly use HTTP with JSON (REST) or GraphQL. APIs let developers build on existing services — maps, payments, authentication — instead of rebuilding them.",
    "git": "Git is a distributed version control system that tracks changes to files (usually source code) over time. It lets multiple people collaborate, records the full history of changes, and supports branching and merging so work can proceed in parallel. Because every clone holds the full history, Git works offline and is resilient. It underpins platforms like GitHub, GitLab, and Bitbucket.",
    "operating system": "An operating system (OS) is system software that manages a computer's hardware and software resources and provides common services for programs. It handles memory, processes (multitasking and scheduling), files and storage, device drivers, and security/permissions, and offers a user interface (GUI or command line). Examples include Windows, macOS, Linux, Android, and iOS. Applications run on top of the OS rather than talking to hardware directly.",
    "linux": "Linux is a family of open-source operating systems built around the Linux kernel, first released by Linus Torvalds in 1991. It manages hardware and runs software on everything from phones (Android) and servers to supercomputers and embedded devices. Because it is open source, anyone can inspect, modify, and distribute it; it is packaged into distributions like Ubuntu, Debian, Fedora, and Red Hat, and it is especially dominant on servers and in cloud infrastructure.",
    "computer": "A computer is an electronic device that processes data according to a set of instructions called a program. Its main parts are the CPU (which performs calculations and logic), memory/RAM (fast temporary storage), storage such as a disk or SSD (persistent data), and input/output devices. Software runs on this hardware to do everything from simple arithmetic to complex applications and networking.",
    "cpu": "The CPU (Central Processing Unit) is the part of a computer that executes a program's instructions. It performs arithmetic and logical operations, moves data, and controls other components, following a fetch–decode–execute cycle. Modern CPUs have multiple cores and caches, letting them run many instructions per second and several tasks in parallel. It is often called the 'brain' of the computer.",
}

# Combined knowledge used for ANSWER lookup (longest key first so specific
# multi-word/punctuated terms win over their substrings).
KNOWLEDGE: Dict[str, str] = {**CONCEPT_KNOWLEDGE, **GENERAL_KNOWLEDGE}
_KNOWLEDGE_KEYS_SORTED = sorted(KNOWLEDGE.keys(), key=len, reverse=True)

# Concept keys used for ROUTING (word-boundary match). Kept to the specific
# ML/technical terms so common general phrasing is not mis-routed by substring.
_CONCEPT_KEYS_SORTED = sorted(CONCEPT_KNOWLEDGE.keys(), key=len, reverse=True)


def _whole_word_pattern(key: str) -> str:
    left = r'(?<![a-z0-9])' if key[0].isalnum() else r'(?<!\S)'
    right = r'(?![a-z0-9])'
    return left + re.escape(key) + right


def match_concept(message: str) -> Optional[str]:
    """Return the longest known CONCEPT key appearing in the message as a whole
    token. Uses alphanumeric look-arounds (not naive substring search) so that
    'ai' does NOT match inside 'training'/'failure', and punctuated keys like
    'c++' and 'pr-auc' still match against the raw message."""
    text = (message or "").lower()
    for key in _CONCEPT_KEYS_SORTED:
        if re.search(_whole_word_pattern(key), text):
            return key
    return None


def lookup_known_answer(message: str, topic: Optional[str] = None) -> Optional[str]:
    """Find an accurate built-in answer for the message's subject.

    Order: exact topic match -> longest whole-word knowledge key present in the
    message. This lets 'what is javascript and why it is used' resolve to the
    'javascript' entry even though the extracted topic has a trailing clause.
    """
    if topic and topic.lower() in KNOWLEDGE:
        return KNOWLEDGE[topic.lower()]
    text = (message or "").lower()
    for key in _KNOWLEDGE_KEYS_SORTED:
        if re.search(_whole_word_pattern(key), text):
            return KNOWLEDGE[key]
    return None


def _grounded_followup(message: str, best_metric: str, completed: List[Dict[str, Any]], err: Optional[Dict[str, Any]]) -> str:
    """Build an honest follow-up answer from REAL stored results only.

    Used when no LLM provider is reachable. Never invents numbers: every metric
    quoted comes from the project's completed baselines / error analysis.
    """
    msg = (message or "").lower()
    if not completed:
        return (
            "I don't have finished model results for this study yet, so I can't give a "
            "grounded answer. Once the first models complete I'll explain their behaviour "
            "using the real metrics."
        )

    def _score(b):
        m = b.get('metrics', {}) or {}
        return m.get('pr_auc', m.get('f1', 0)) or 0

    ranked = sorted(completed, key=_score, reverse=True)
    top = ranked[0]
    tm = top.get('metrics', {}) or {}

    if any(w in msg for w in ["poor", "fail", "bad", "miss", "worse", "low", "underperform"]):
        fn = (err or {}).get('falseNegativesCount')
        fp = (err or {}).get('falsePositivesCount')
        parts = ["The weaker models mostly miss rare positive cases, which is expected under severe class imbalance."]
        if fn is not None and fp is not None:
            parts.append(f"On the held-out data the error analysis recorded {fn} false negatives and {fp} false positives.")
        parts.append(
            f"The strongest model so far, {top.get('name')}, reached recall {tm.get('recall')} and "
            f"PR-AUC {tm.get('pr_auc')}, which reduces but does not fully eliminate those misses."
        )
        return " ".join(parts)

    if any(w in msg for w in ["better", "best", "why did", "choose", "chose", "top", "win"]):
        if len(ranked) > 1:
            second = ranked[1]
            sm = second.get('metrics', {}) or {}
            return (
                f"{top.get('name')} performed best on the primary metric "
                f"(PR-AUC {tm.get('pr_auc')}, recall {tm.get('recall')}), ahead of "
                f"{second.get('name')} (PR-AUC {sm.get('pr_auc')}, recall {sm.get('recall')}). "
                f"Gradient-boosted trees capture non-linear feature interactions that the simpler "
                f"linear baseline misses, which is why it leads on imbalanced data."
            )
        return (
            f"{top.get('name')} is the strongest model so far with PR-AUC {tm.get('pr_auc')} "
            f"and recall {tm.get('recall')}."
        )

    return (
        f"So far the best model is {top.get('name')} with PR-AUC {tm.get('pr_auc')}, "
        f"recall {tm.get('recall')} and precision {tm.get('precision')} "
        f"(overall best metric: {best_metric}). Ask me about a specific model, the errors it "
        f"makes, or the next experiment and I'll answer from those results."
    )

CONFIRMATION_PHRASES = [
    "yes", "yes do it", "do it", "go ahead", "sure", "okay", "ok",
    "continue", "continue please", "let's do it", "lets do it", "start",
    "proceed", "try it", "do that", "sounds good", "please do", "yeah", "yep",
    "yes please", "do it please", "please do that", "that sounds good", "yes do that", "ok do it", "yup", "do it now"
]

def get_session(session_id: Optional[str]) -> Dict[str, Any]:
    return store.get_session(session_id or "default-session")

def extract_topic(message: str) -> Optional[str]:
    # Prefer an exact known-concept match (handles 'c++', 'pr-auc', 'f1', and
    # avoids the 'ai'-inside-'training' substring trap).
    concept = match_concept(message)
    if concept:
        return concept

    msg_clean = re.sub(r'[^\w\s]', '', message.strip().lower())
    match = re.search(r"(?:what is|what are|what's|explain|define|tell me about)\s+(.+)", msg_clean)
    if match:
        extracted = match.group(1).strip().rstrip('?').strip()
        if extracted:
            return extracted

    return None


# --------------------------------------------------------------------------- #
# Task-type detection (owner directive §1, §7). These helpers classify the SHAPE
# of the request so the router can pick general Q&A vs coding vs research, etc.
# --------------------------------------------------------------------------- #
_INTERROGATIVE_STARTS = (
    "what", "why", "how", "who", "when", "where", "which", "is", "are", "was",
    "were", "do", "does", "did", "can", "could", "will", "would", "should",
    "explain", "define", "describe", "compare", "tell me",
)

_RESEARCH_TRIGGERS = (
    "research", "investigate", "look into", "deep dive", "literature",
    "compare papers", "compare these papers", "compare sources", "compare the",
    "state of the art", "latest developments", "recent developments",
    "latest research", "survey the", "find papers",
)

_ML_SIGNALS = (
    "dataset", "data set", "model", "fraud", "predict", "churn", "train",
    "classify", "classification", "regression", "accuracy", "machine learning",
    " ml", "tabular", "feature", "label", "anomaly", "forecast",
)

_CODING_PATTERNS = [
    r"\b(write|create|make|give me|generate)\b[^.]*\b(program|code|function|script|class|app|application|snippet)\b",
    r"\b(implement|debug|fix|refactor|optimize)\b[^.]*\b(code|function|program|script|bug|error|class)\b",
    r"\b(program|function|script|class|code)\b[^.]*\b(to|that)\b",
    r"\breverse a string\b", r"\bfizz ?buzz\b", r"\bsort (a|the) list\b",
    r"\bwrite (a|me|some)\b[^.]*\b(in|using)\b[^.]*\b(python|javascript|java|c\+\+|sql|html|css)\b",
]

_DATA_ANALYSIS_TRIGGERS = (
    "analyze this csv", "analyse this csv", "analyze the csv", "analyze this dataset",
    "analyze my data", "analyze the data", "clean this data", "explore this dataset",
    "data analysis", "analyze this table", "eda on",
)

_DOCUMENT_TRIGGERS = (
    "summarize this pdf", "summarise this pdf", "read this pdf", "this document",
    "summarize the document", "summarize this document", "analyze this document",
    "extract from pdf", "this pdf", "summarize these notes", "read my resume",
)

# Topics that are programming languages / code-ish, so a bare "show me an
# example" follow-up should produce code rather than a prose definition.
_CODE_LANGUAGES = {
    "python", "javascript", "java", "c++", "c", "sql", "html", "css", "git", "linux",
}

_EXAMPLE_REQUEST_RE = re.compile(r"\b(show|give|provide|write)\b[^.]*\b(example|sample|demo)\b")
_BARE_EXAMPLES = {"example", "an example", "examples", "show me", "demo", "show me one", "one example"}


def _is_example_request(msg_clean: str, msg_clean_nopunct: str) -> bool:
    return bool(_EXAMPLE_REQUEST_RE.search(msg_clean)) or msg_clean_nopunct in _BARE_EXAMPLES


def detect_question_type(message: str) -> str:
    """Light-weight question-shape classifier (owner directive §7)."""
    m = (message or "").strip().lower()
    if any(re.search(p, m) for p in _CODING_PATTERNS):
        return "coding"
    if any(t in m for t in _RESEARCH_TRIGGERS):
        return "research"
    if m.startswith(("compare", "difference between", "vs", "versus")) or " vs " in m or " versus " in m:
        return "comparison"
    if m.startswith(("why", "how come")):
        return "why"
    if m.startswith("how"):
        return "how"
    if m.startswith(("who", "when", "where", "which")):
        return "factual"
    if m.startswith(("what is", "what are", "what's", "define", "what does")):
        return "definition"
    if m.startswith(("explain", "describe", "tell me about")):
        return "explanation"
    return "other"


def _has_coding_intent(msg_clean: str) -> bool:
    return any(re.search(p, msg_clean) for p in _CODING_PATTERNS)


def classify_intent(
    message: str,
    active_project_id: Optional[str] = None,
    session_id: Optional[str] = None,
    payload_pending_action: Optional[Dict[str, Any]] = None,
    payload_last_topic: Optional[str] = None
) -> str:
    """
    Task router (owner directive §1). Classifies a user message into exactly one
    intent using a strict priority order that keeps GENERAL questions general and
    only starts research when the user actually asks for it:

      0. RESEARCH_CONTROL (bare stop/pause/resume while a study is active)
      1. CONFIRM_PENDING_ACTION (pure affirmation only)
      1b.RESEARCH_START (explicit Hugging Face dataset URL)
      2. CODING (write/implement/debug code)
      3. DEEP_RESEARCH / RESEARCH_START (explicit research verbs; ML -> dataset flow)
      4. DATA_ANALYSIS / DOCUMENT_ANALYSIS
      5. EXPLANATION (general Q&A: concept, definitional, or any interrogative)
      6. RESEARCH_FOLLOWUP (only with an ACTIVE project that the message references)
      7. RESEARCH_CONTROL ("try another approach", ...)
      8. REPORT_REQUEST
      9. TECHNICAL_DETAILS
      10.RESEARCH_START (ML verbs: improve/predict/detect/train/fraud ...)
      11.CASUAL_CHAT (greetings / non-informative)
      12.LLM intent fallback
      13.default -> EXPLANATION (general assistant)
    """
    msg_clean = message.strip().lower()
    msg_clean_nopunct = re.sub(r'[^\w\s]', '', msg_clean).strip()

    sess = get_session(session_id)
    last_topic = payload_last_topic or sess.get("last_topic")
    pending_action = payload_pending_action or sess.get("pending_action")

    concept = match_concept(message)
    definitional = msg_clean.startswith(
        ("what is", "what are", "what's", "whats", "explain", "define",
         "what does", "tell me about", "describe")
    )
    interrogative = msg_clean.startswith(_INTERROGATIVE_STARTS)
    # References to the active study (as opposed to a general concept).
    project_ref = any(kw in msg_clean for kw in [
        "the model", "this model", "your model", "my model", "our model",
        "the result", "these result", "best model", "the report", "performance",
        "the experiment", "the dataset", "this dataset", "the baseline",
        "the results", "those results", "that approach", "this approach",
    ])

    # 0. Bare control verbs win while a study is active so "Continue"/"Stop"
    #    resume/halt research instead of being read as a generic confirmation.
    if active_project_id and msg_clean_nopunct in (
        "stop", "pause", "resume", "continue", "halt", "cancel",
        "stop research", "pause research", "resume research",
    ):
        return "RESEARCH_CONTROL"

    # 1. CONFIRM_PENDING_ACTION — ONLY for messages that are purely an
    #    affirmation. "ok what is python" must NOT be treated as a confirmation.
    confirm_exact = msg_clean_nopunct in CONFIRMATION_PHRASES
    confirm_pattern = bool(re.fullmatch(
        r"(yes|yeah|yep|yup|sure|ok|okay|go ahead|proceed|please do|do it|"
        r"sounds good|that sounds good|let'?s do it|lets do it|try it|do that|"
        r"run it|start)(\s+(please|do it|go ahead|now|that|it|sounds good|"
        r"let'?s do it|okay|ok|yes|yeah))*[.!]*",
        msg_clean.strip(),
    ))
    if confirm_exact or confirm_pattern:
        return "CONFIRM_PENDING_ACTION"

    # 1b. Explicit Hugging Face reference (URL or owner/name) => research start.
    if "huggingface.co/datasets" in msg_clean or "hf.co/datasets" in msg_clean:
        return "RESEARCH_START"

    # 2. CODING — "write a python program to reverse a string", "implement X".
    if _has_coding_intent(msg_clean):
        return "CODING"

    # 3. Explicit research request. ML/prediction goals use the real dataset
    #    workflow (RESEARCH_START); general web/literature research is its own
    #    intent so it is handled honestly instead of launching a dataset search.
    if any(t in msg_clean for t in _RESEARCH_TRIGGERS):
        if any(s in msg_clean for s in _ML_SIGNALS):
            return "RESEARCH_START"
        return "DEEP_RESEARCH"

    # 3b. Imperative ML/prediction task ("improve this model using my dataset",
    #     "predict churn"). This must beat EXPLANATION even when the sentence
    #     contains concept words like "model"/"dataset". Questions ("how does a
    #     model detect fraud?") stay general via the interrogative guard.
    ml_action = any(w in msg_clean for w in [
        "improve", "optimize", "optimise", "train", "predict", "forecast",
        "detect", "tune", "build a model", "build me a model",
    ])
    if ml_action and not (definitional or interrogative) and any(
        s in msg_clean for s in ["dataset", "model", "ml", "machine learning",
                                 "accuracy", "fraud", "churn", "data"]
    ):
        return "RESEARCH_START"

    # 4. Data / document analysis requests.
    if any(t in msg_clean for t in _DATA_ANALYSIS_TRIGGERS):
        return "DATA_ANALYSIS"
    if any(t in msg_clean for t in _DOCUMENT_TRIGGERS):
        return "DOCUMENT_ANALYSIS"

    # 4b. Self-referential capability / greeting questions are casual chat, not a
    #     general-knowledge question about the world (so they must not be routed
    #     to EXPLANATION just because they start with "what").
    greetings = ["hi", "hello", "hey", "hi!", "hello!", "hey!", "greetings",
                 "good morning", "good afternoon", "good evening"]
    if (msg_clean in greetings
            or "what can you do" in msg_clean
            or "what do you do" in msg_clean
            or "who are you" in msg_clean
            or msg_clean_nopunct in ("help", "help me")):
        return "CASUAL_CHAT"

    # 4c. A bare "show me an example" follow-up resolves against the current
    #     topic: if we were just discussing a programming language, produce code;
    #     otherwise treat it as a general explanation about that topic (§23).
    if _is_example_request(msg_clean, msg_clean_nopunct):
        if last_topic and str(last_topic).lower() in _CODE_LANGUAGES:
            return "CODING"
        return "EXPLANATION"

    # 5. EXPLANATION (general Q&A). Any concept, definitional phrasing, or
    #    interrogative is answered directly — UNLESS it explicitly references the
    #    active study's model/results (that is a follow-up, handled below).
    if (concept or definitional or interrogative) and not (active_project_id and project_ref):
        return "EXPLANATION"

    # 6. RESEARCH_FOLLOWUP — only with an ACTIVE project that the message actually
    #    references (project nouns or a pronoun). A bare "why"/"how" with a stale
    #    last_topic must NOT hijack a general question (owner directive §13).
    followup_kw = [
        "why", "how come", "useful", "fail", "failed", "choose", "chose",
        "worse", "better", "miss", "improve", "result", "results",
    ]
    pronoun_ref = any(p in msg_clean for p in ["it ", "its ", "this ", "that ", "these ", "those ", "they ", "them "])
    if active_project_id and (project_ref or pronoun_ref) and any(kw in msg_clean for kw in followup_kw):
        return "RESEARCH_FOLLOWUP"

    # 7. RESEARCH_CONTROL ("try another approach", "run another experiment", ...)
    control_cmds = [
        "try another model", "try another approach", "run another experiment",
        "next experiment", "another approach", "another experiment",
        "stop research", "try a different", "try something else",
    ]
    if any(cmd in msg_clean for cmd in control_cmds):
        return "RESEARCH_CONTROL"
    if msg_clean_nopunct in ("stop", "pause", "resume", "continue"):
        return "RESEARCH_CONTROL"

    # 8. REPORT_REQUEST
    report_cmds = ["show report", "view report", "download report", "show me the report",
                   "get report", "the report", "see the report", "final report"]
    if any(cmd in msg_clean for cmd in report_cmds):
        return "REPORT_REQUEST"

    # 9. TECHNICAL_DETAILS
    tech_cmds = ["show details", "technical details", "view logs", "show logs", "view code"]
    if any(cmd in msg_clean for cmd in tech_cmds):
        return "TECHNICAL_DETAILS"

    # 10. RESEARCH_START ("improve credit-card fraud detection", "predict churn")
    if any(word in msg_clean for word in ["improve", "optimize", "predict", "forecast", "detect", "train", "fraud"]):
        return "RESEARCH_START"

    # 11. CASUAL_CHAT fast-path
    greetings = ["hi", "hello", "hey", "hi!", "hello!", "hey!", "greetings", "good morning", "good afternoon", "good evening"]
    if msg_clean in greetings or "what can you do" in msg_clean or "who are you" in msg_clean or "help" in msg_clean:
        return "CASUAL_CHAT"

    # 11b. Non-informative input (emoji-only, punctuation/symbols) is casual chat.
    if not msg_clean_nopunct:
        return "CASUAL_CHAT"

    # 12. LLM Intent Fallback
    try:
        system_prompt = (
            "Classify user intent into EXACTLY ONE: CONFIRM_PENDING_ACTION, "
            "EXPLANATION, CODING, DEEP_RESEARCH, DATA_ANALYSIS, DOCUMENT_ANALYSIS, "
            "RESEARCH_START, RESEARCH_FOLLOWUP, RESEARCH_CONTROL, REPORT_REQUEST, "
            "TECHNICAL_DETAILS, CASUAL_CHAT."
        )
        user_prompt = f"User Input: \"{message}\"\nCategory:"
        llm_res = query_llm(user_prompt, system_prompt)
        if llm_res:
            clean = llm_res.strip().upper().replace('"', '').replace("'", "")
            for cat in INTENT_CATEGORIES:
                if cat in clean:
                    return cat
    except Exception:
        pass

    # 13. Default to the general assistant rather than a greeting, so substantive
    #     messages get a real answer (or an honest "I'm not sure") instead of
    #     being bounced into the research workflow.
    return "EXPLANATION"


def _honest_unknown(subject: str) -> str:
    """Honest fallback (owner directive §18): never invent, never force research."""
    subj = (subject or "that").strip()
    return (
        f"I don't want to guess about \"{subj}\". I couldn't reach an assistant "
        f"model to answer that reliably and it isn't in my built-in knowledge, so "
        f"I don't have enough information to answer it accurately right now."
    )


def _general_answer(message: str, topic: Optional[str]) -> str:
    """Answer a general question: built-in knowledge -> LLM -> honest fallback.

    No research/dataset/training language is injected (owner directive §2/§3).
    """
    known = lookup_known_answer(message, topic)
    if known:
        return known
    prompt = (
        f"Answer the user's question directly and completely in natural English.\n"
        f"Question: \"{message}\""
    )
    llm_answer = query_llm(prompt, GENERAL_ASSISTANT_SYSTEM_PROMPT)
    if llm_answer and llm_answer.strip():
        return llm_answer.strip()
    return _honest_unknown(topic or message)


def handle_intent_message(
    message: str,
    active_project_id: Optional[str] = None,
    session_id: Optional[str] = None,
    payload_pending_action: Optional[Dict[str, Any]] = None,
    payload_last_topic: Optional[str] = None
) -> Dict[str, Any]:
    """
    Handles conversational user messages with context awareness, pronoun
    resolution, and pending-action execution. General questions get general
    answers; research is started only when the user actually asks for it.
    """
    sid = session_id or "default-session"
    sess = get_session(sid)
    store.update_session(sid, {"last_user_message": message})

    if payload_pending_action is not None:
        if payload_pending_action:
            store.set_pending_action(
                sid,
                action_type=payload_pending_action.get("type"),
                topic=payload_pending_action.get("topic"),
                query=payload_pending_action.get("query"),
                project_id=payload_pending_action.get("projectId")
            )
        else:
            store.clear_pending_action(sid)

    if payload_last_topic:
        store.update_session(sid, {"last_topic": payload_last_topic})

    if active_project_id:
        store.update_session(sid, {"active_project_id": active_project_id})

    # Re-fetch session after updating state
    sess = get_session(sid)
    intent = classify_intent(message, active_project_id, sid, payload_pending_action, payload_last_topic)
    msg_clean = message.strip().lower()

    print(f"[INTENT ROUTER] Session: {sid} | Message: '{message}' | Intent: '{intent}' | Pending Action: {sess.get('pending_action')}")

    # 1. CONFIRM_PENDING_ACTION
    if intent == "CONFIRM_PENDING_ACTION":
        pending = sess.get("pending_action") or payload_pending_action

        if pending:
            p_type = pending.get("type")
            p_topic = pending.get("topic") or "this topic"
            p_query = pending.get("query") or f"Investigate {p_topic}"
            p_proj = pending.get("projectId") or active_project_id

            store.clear_pending_action(sid)

            if p_type == "START_RESEARCH":
                return {
                    "intent": intent,
                    "response": f"Absolutely. I'll investigate {p_topic} for you.",
                    "action": "START_RESEARCH",
                    "researchQuery": p_query,
                    "projectId": None,
                    "pendingAction": None,
                    "lastTopic": sess.get("last_topic")
                }
            elif p_type == "NEXT_EXPERIMENT":
                return {
                    "intent": intent,
                    "response": "Got it. Formulating and executing another research experiment...",
                    "action": "NEXT_EXPERIMENT",
                    "projectId": p_proj,
                    "pendingAction": None,
                    "lastTopic": sess.get("last_topic")
                }
            elif p_type == "SHOW_REPORT":
                return {
                    "intent": intent,
                    "response": "Here is the scientific research report compiling our verified experimental findings.",
                    "action": "SHOW_REPORT",
                    "projectId": p_proj,
                    "pendingAction": None,
                    "lastTopic": sess.get("last_topic")
                }

        # Confirmed but NO pending action existed: ask what they want (do NOT
        # assume research, and do NOT repeat the greeting). Owner directive §11.
        return {
            "intent": intent,
            "response": "Sure — what would you like me to do?",
            "action": "NONE",
            "projectId": active_project_id,
            "pendingAction": None,
            "lastTopic": sess.get("last_topic")
        }

    # 2. EXPLANATION (general Q&A) — answer the question, nothing else.
    elif intent == "EXPLANATION":
        topic = extract_topic(message)
        # Prefer a known knowledge key as the canonical topic for context.
        known = lookup_known_answer(message, topic)
        if known is not None:
            for key in _KNOWLEDGE_KEYS_SORTED:
                if re.search(_whole_word_pattern(key), msg_clean):
                    topic = key
                    break

        answer = _general_answer(message, topic)

        # A general answer is NOT an offer to do research. Clear any stale pending
        # action so a later "yes do it" does not launch unrelated research
        # (owner directive §12).
        store.clear_pending_action(sid)
        if topic:
            store.update_session(sid, {"last_topic": topic.lower()})
        store.update_session(sid, {"last_assistant_message": answer})

        return {
            "intent": intent,
            "taskType": detect_question_type(message),
            "response": answer,
            "action": "NONE",
            "projectId": active_project_id,
            "pendingAction": None,
            "lastTopic": (topic.lower() if topic else sess.get("last_topic"))
        }

    # 3. CODING — generate code via the LLM; honest fallback if none reachable.
    elif intent == "CODING":
        store.clear_pending_action(sid)
        last_topic = payload_last_topic or sess.get("last_topic")
        # For a bare follow-up ("show me a simple example"), pull in the current
        # topic so the code is about what we were just discussing (§23).
        ctx_line = ""
        if last_topic and _is_example_request(msg_clean, re.sub(r'[^\w\s]', '', msg_clean).strip()):
            ctx_line = f"The user is asking for an example about {last_topic}.\n"
        prompt = (
            f"Solve the following programming request with correct, runnable code "
            f"and a brief explanation.\n{ctx_line}Request: \"{message}\""
        )
        code_answer = query_llm(prompt, CODING_SYSTEM_PROMPT)
        if not (code_answer and code_answer.strip()):
            code_answer = (
                "I can help write that, but I couldn't reach a code-capable model "
                "just now, so I won't guess at an implementation. Please try again "
                "in a moment, or make sure an LLM provider is connected."
            )
        else:
            code_answer = code_answer.strip()
        store.update_session(sid, {"last_assistant_message": code_answer, "last_topic": (last_topic or "coding")})
        return {
            "intent": intent,
            "taskType": "coding",
            "response": code_answer,
            "action": "NONE",
            "projectId": active_project_id,
            "pendingAction": None,
            "lastTopic": (last_topic or "coding")
        }

    # 4. DEEP_RESEARCH — explicit research request that is NOT an ML/dataset task.
    #    Web/literature research is not wired into this deployment; be honest
    #    rather than fabricating a browse or sources (owner directive §18).
    elif intent == "DEEP_RESEARCH":
        store.clear_pending_action(sid)
        goal = re.sub(r"https?://\S+", "", message).strip()
        resp_text = (
            f"You've asked me to research: {goal}.\n\n"
            "In-depth web and literature research isn't wired into this deployment "
            "yet, so I won't pretend to browse or invent sources. If your goal is a "
            "machine-learning or prediction problem, I can run the real research "
            "workflow — find a suitable dataset on Hugging Face, then train and "
            "compare models with verified metrics. Just describe the prediction "
            "problem or paste a dataset link. For live web research, that capability "
            "still needs to be built."
        )
        store.update_session(sid, {"last_assistant_message": resp_text, "last_topic": goal.lower()})
        return {
            "intent": intent,
            "taskType": "research",
            "response": resp_text,
            "action": "NONE",
            "projectId": active_project_id,
            "pendingAction": None,
            "lastTopic": goal.lower()
        }

    # 5. DATA_ANALYSIS — point at the real tabular workflow.
    elif intent == "DATA_ANALYSIS":
        store.clear_pending_action(sid)
        resp_text = (
            "I can analyze tabular data through the ML research workflow. Upload a "
            "CSV/Parquet file or paste a Hugging Face dataset link, tell me what you "
            "want to predict or find, and I'll inspect the data and then train and "
            "compare models with real metrics."
        )
        store.update_session(sid, {"last_assistant_message": resp_text})
        return {
            "intent": intent,
            "taskType": "data_analysis",
            "response": resp_text,
            "action": "NONE",
            "projectId": active_project_id,
            "pendingAction": None,
            "lastTopic": sess.get("last_topic")
        }

    # 6. DOCUMENT_ANALYSIS — not implemented; honest guidance.
    elif intent == "DOCUMENT_ANALYSIS":
        store.clear_pending_action(sid)
        resp_text = (
            "Document and PDF analysis isn't wired into this deployment yet, so I "
            "can't read an uploaded file. If you paste the text here, I can summarize "
            "it or answer questions about it when an assistant model is connected."
        )
        store.update_session(sid, {"last_assistant_message": resp_text})
        return {
            "intent": intent,
            "taskType": "document_analysis",
            "response": resp_text,
            "action": "NONE",
            "projectId": active_project_id,
            "pendingAction": None,
            "lastTopic": sess.get("last_topic")
        }

    # 7. RESEARCH_FOLLOWUP (context & pronoun resolution about the active study)
    elif intent == "RESEARCH_FOLLOWUP":
        last_topic = payload_last_topic or sess.get("last_topic")

        # Handle "why is that/it useful?" for Python or other recent topic
        if "useful" in msg_clean and last_topic == "python":
            resp_text = (
                "Python is particularly useful in AI research because its clean syntax allows researchers to rapidly construct and test algorithms, "
                "while its unmatched library ecosystem (PyTorch, TensorFlow, Scikit-Learn, NumPy) provides battle-tested building blocks for model training and evaluation."
            )
            store.update_session(sid, {"last_assistant_message": resp_text})
            return {
                "intent": intent,
                "response": resp_text,
                "action": "NONE",
                "projectId": active_project_id,
                "pendingAction": sess.get("pending_action"),
                "lastTopic": last_topic
            }

        # Active Project Followup — grounded in the project's REAL results.
        proj = store.get_project(active_project_id) if active_project_id else None
        best_model = (proj.get('bestModel') if proj else None) or "the current best model"
        best_metric = (proj.get('bestMetric') if proj else None) or "N/A"

        baselines = store.get_baselines(active_project_id) if active_project_id else []
        err = store.get_error_analysis(active_project_id) if active_project_id else None
        completed = [b for b in baselines if b.get('status') == 'COMPLETED' and b.get('metrics')]

        context_str = (
            f"Project Objective: {(proj.get('objective') if proj else 'Active Research')}\n"
            f"Best Model: {best_model}\nBest Metric: {best_metric}\nLast Topic: {last_topic}\n"
        )

        sys_prompt = "You are AI Scientist answering questions about an active research study or ML topic. Provide a clear, human-readable 2-4 sentence answer grounded only in the supplied context."
        prompt = f"Context:\n{context_str}\nUser Question: '{message}'"

        answer = query_llm(prompt, sys_prompt)
        if not answer:
            answer = _grounded_followup(message, best_metric, completed, err)

        store.update_session(sid, {"last_assistant_message": answer})
        return {
            "intent": intent,
            "response": answer,
            "action": "NONE",
            "projectId": active_project_id,
            "pendingAction": sess.get("pending_action"),
            "lastTopic": last_topic
        }

    # 8. RESEARCH_START (ML/dataset research workflow)
    elif intent == "RESEARCH_START":
        from backend.hf_datasets import parse_hf_reference
        topic = message.strip()
        hf_ref = parse_hf_reference(message)
        clean_goal = re.sub(r"https?://\S+", "", topic).strip() or topic
        store.update_session(sid, {"last_topic": clean_goal, "pending_action": None})

        resp_text = f"I'll look for datasets that could help with: {clean_goal}"
        store.update_session(sid, {"last_assistant_message": resp_text})

        return {
            "intent": intent,
            "response": resp_text,
            "action": "START_RESEARCH",
            "researchQuery": clean_goal,
            "hfRef": hf_ref,
            "projectId": None,
            "pendingAction": None,
            "lastTopic": clean_goal
        }

    # 9. RESEARCH_CONTROL
    elif intent == "RESEARCH_CONTROL":
        store.clear_pending_action(sid)
        if "stop" in msg_clean or "pause" in msg_clean:
            if active_project_id:
                store.set_control_signal(active_project_id, "STOP")
            return {
                "intent": intent,
                "response": "I've stopped the active research pipeline as requested.",
                "action": "STOP_RESEARCH",
                "projectId": active_project_id,
                "pendingAction": None,
                "lastTopic": sess.get("last_topic")
            }
        elif "continue" in msg_clean or "resume" in msg_clean:
            if active_project_id:
                store.set_control_signal(active_project_id, "RUN")
            return {
                "intent": intent,
                "response": "Resuming the active research pipeline...",
                "action": "RESUME_RESEARCH",
                "projectId": active_project_id,
                "pendingAction": None,
                "lastTopic": sess.get("last_topic")
            }
        else:
            return {
                "intent": intent,
                "response": "Got it. Formulating and executing another research experiment...",
                "action": "NEXT_EXPERIMENT",
                "projectId": active_project_id,
                "pendingAction": None,
                "lastTopic": sess.get("last_topic")
            }

    # 10. REPORT_REQUEST
    elif intent == "REPORT_REQUEST":
        store.clear_pending_action(sid)
        return {
            "intent": intent,
            "response": "Here is the scientific research report compiling our verified experimental findings.",
            "action": "SHOW_REPORT",
            "projectId": active_project_id,
            "pendingAction": None,
            "lastTopic": sess.get("last_topic")
        }

    # 11. TECHNICAL_DETAILS
    elif intent == "TECHNICAL_DETAILS":
        return {
            "intent": intent,
            "response": "Opening technical details panel...",
            "action": "SHOW_TECHNICAL",
            "projectId": active_project_id,
            "pendingAction": sess.get("pending_action"),
            "lastTopic": sess.get("last_topic")
        }

    # 12. CASUAL_CHAT
    store.clear_pending_action(sid)
    if "what can you do" in msg_clean or "help" in msg_clean:
        content = (
            "I'm a general-purpose AI assistant with a built-in autonomous ML "
            "research workflow. 👋\n\n"
            "I can answer everyday questions, explain concepts, help with coding "
            "and analysis, and — when you ask for it — research a machine-learning "
            "problem: find a real dataset, train models, compare results, and "
            "explain what I find."
        )
    elif "hello" in msg_clean:
        content = "Hello! 👋 What can I help you with?"
    else:
        content = "Hi! 👋 What would you like help with?"

    store.update_session(sid, {"last_assistant_message": content})

    return {
        "intent": "CASUAL_CHAT",
        "response": content,
        "action": "NONE",
        "projectId": active_project_id,
        "pendingAction": None,
        "lastTopic": sess.get("last_topic")
    }
