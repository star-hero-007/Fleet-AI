import streamlit as st
from langchain_openai import ChatOpenAI
import httpx
import PyPDF2
import json
import os
from datetime import datetime
import uuid

CHAT_HISTORY_FILE = "chat_history.json"
USERS_FILE = "users.json"

SUPPORTED_LANGUAGES = {
    "English": "en",
    "Spanish": "es", 
    "French": "fr"
}

LANGUAGE_INSTRUCTIONS = {
    "English": "Respond in English",
    "Spanish": "Responde en español",
    "French": "Réponds en français"
}


def load_json_file(filename, default=[]):
    """Load data from JSON file"""
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        
    except Exception as e:
        st.error(f"Error loading {filename}: {str(e)}")
    return default

def save_json_file(filename, data):
    """Save data to JSON file"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    
    except Exception as e:
        st.error(f"Error saving {filename}: {str(e)}")
        return False


# Structure: {user_id: {filename: {"version": n, "text": content, "uploaded_at": timestamp}}}
document_store = {}


def initialize_users():
    """Initialize users data if not exists"""
    if not os.path.exists(USERS_FILE):
        save_json_file(USERS_FILE, {})

def create_user(username, password):
    """Create a new user"""
    users = load_json_file(USERS_FILE, {})
    if username in users:
        return False, "Username already exists"
    
    user_id = str(uuid.uuid4())
    users[username] = {
        "user_id": user_id,
        "password": password,  # In production, use proper hashing
        "created_at": datetime.now().isoformat(),
        "preferred_language": "English"
    }
    
    if save_json_file(USERS_FILE, users):
        document_store[user_id] = {}
        return True, "User created successfully"
    return False, "Failed to create user"

def authenticate_user(username, password):
    """Authenticate user"""
    users = load_json_file(USERS_FILE, {})
    if username in users and users[username]["password"] == password:
        return True, users[username]["user_id"], users[username]["preferred_language"]
    return False, None, None

def update_user_language(username, language):
    """Update user's preferred language"""
    users = load_json_file(USERS_FILE, {})
    if username in users:
        users[username]["preferred_language"] = language
        return save_json_file(USERS_FILE, users)
    return False

# Chat history management
def save_chat_history(user_id, question, answer, filename, version, language):
    """Save chat history to JSON"""
    chat_entry = {
        "user_id": user_id,
        "timestamp": datetime.now().isoformat(),
        "question": question,
        "answer": answer,
        "document": filename,
        "version": version,
        "language": language
    }
    
    chat_history = load_json_file(CHAT_HISTORY_FILE, [])
    chat_history.append(chat_entry)
    return save_json_file(CHAT_HISTORY_FILE, chat_history)

def get_user_chat_history(user_id):
    """Get chat history for specific user"""
    chat_history = load_json_file(CHAT_HISTORY_FILE, [])
    return [entry for entry in chat_history if entry["user_id"] == user_id]

# Function to extract text from PDF
def extract_text_from_pdf(uploaded_file):
    pdf_reader = PyPDF2.PdfReader(uploaded_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() or ""
    return text

#To ask question
def ask_question(question, reference="", filename="", version=1, language="English"):
    client = httpx.Client(verify=False)
    llm = ChatOpenAI(
        base_url="https://genailab.tcs.in",
        model='azure/genailab-maas-gpt-4o-mini',
        api_key="sk-hSU2Vxy5ndfsjW1MZDhMLA",
        http_client=client
    )
    
    language_instruction = LANGUAGE_INSTRUCTIONS.get(language, "Respond in English")
    
    prompt =f"""You are an AI assistant for AI Fleet Communication system.

REFERENCE DOCUMENTS:
Document: {filename} (Version: {version})
Content:
{reference}

USER QUESTION:
{question}

INSTRUCTIONS:
{language_instruction}
Answer the question based STRICTLY on the AI Fleet Communication reference documents provided above.
If the answer cannot be found in the reference content, you MUST respond with: "I don't know - this information is not available in the AI Fleet Communication documents."
Do not speculate, infer, or use any external knowledge beyond the provided reference documents.
Only provide answers that are directly supported by the reference content.
For fleet-related queries not covered in the documents, explicitly state that this specific fleet communication information is not available.
"""
    try:
        response = llm.invoke(prompt)
        return response.content
    except Exception as e:
        return f"Error: {str(e)}"

# Streamlit Interface

def main():
    st.title("AI Fleet Chatbot")
    
    # Initialize users file
    initialize_users()
    
    # Session state management
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    if 'username' not in st.session_state:
        st.session_state.username = None
    if 'current_language' not in st.session_state:
        st.session_state.current_language = "English"
    
    # Authentication section
    if not st.session_state.authenticated:
        st.header("User Login")
        
        tab1, tab2 = st.tabs(["Login", "Register"])
        
        with tab1:
            login_username = st.text_input("Username", key="login_user")
            login_password = st.text_input("Password", type="password", key="login_pass")
            
            if st.button("Login"):
                if login_username and login_password:
                    success, user_id, preferred_language = authenticate_user(login_username, login_password)
                    if success:
                        st.session_state.authenticated = True
                        st.session_state.user_id = user_id
                        st.session_state.username = login_username
                        st.session_state.current_language = preferred_language
                        st.success(f"Welcome back, {login_username}!")
                        st.rerun()
                    else:
                        st.error("Invalid username or password")
                else:
                    st.error("Please enter both username and password")
        
        with tab2:
            reg_username = st.text_input("Username", key="reg_user")
            reg_password = st.text_input("Password", type="password", key="reg_pass")
            reg_language = st.selectbox("Preferred Language", list(SUPPORTED_LANGUAGES.keys()))
            
            if st.button("Register"):
                if reg_username and reg_password:
                    success, message = create_user(reg_username, reg_password)
                    if success:
                        update_user_language(reg_username, reg_language)
                        st.success(message)
                    else:
                        st.error(message)
                else:
                    st.error("Please enter both username and password")
        
        return
    
    # Main application (authenticated users)
    st.header(f"Welcome, {st.session_state.username}!")
    
    # Language selection
    col1, col2 = st.columns([3, 1])
    with col2:
        selected_language = st.selectbox(
            "Response Language",
            list(SUPPORTED_LANGUAGES.keys()),
            index=list(SUPPORTED_LANGUAGES.keys()).index(st.session_state.current_language)
        )
        
        if selected_language != st.session_state.current_language:
            if update_user_language(st.session_state.username, selected_language):
                st.session_state.current_language = selected_language
                st.success(f"Language updated to {selected_language}")
                st.rerun()
        
        if st.button("Logout"):
            st.session_state.authenticated = False
            st.session_state.user_id = None
            st.session_state.username = None
            st.rerun()
    
    # Document upload section
    st.subheader("Document Management")
    uploaded_files = st.file_uploader(
        "Upload PDF files (multiple allowed)",
        type=["pdf"],
        accept_multiple_files=True,
        key="file_uploader"
    )

    # Initialize user's document store if not exists
    if st.session_state.user_id not in document_store:
        document_store[st.session_state.user_id] = {}

    if uploaded_files:
        for uploaded_file in uploaded_files:
            filename = uploaded_file.name
            text_content = extract_text_from_pdf(uploaded_file)

            # Update version
            if filename in document_store[st.session_state.user_id]:
                document_store[st.session_state.user_id][filename]["version"] += 1
            else:
                document_store[st.session_state.user_id][filename] = {
                    "version": 1, 
                    "text": text_content,
                    "uploaded_at": datetime.now().isoformat()
                }

            # Always keep latest text
            document_store[st.session_state.user_id][filename]["text"] = text_content
            st.success(f"Loaded {filename} (Version {document_store[st.session_state.user_id][filename]['version']})")

    # Display current documents
    if document_store[st.session_state.user_id]:
        st.subheader("Current Documents")
        for filename, doc_info in document_store[st.session_state.user_id].items():
            st.write(f"📄 **{filename}** (v{doc_info['version']}) - Uploaded: {doc_info['uploaded_at'][:10]}")

    # Q&A Section
    st.subheader("Ask Questions")
    question = st.text_input("Enter your question:")
    
    if question and document_store[st.session_state.user_id]:
        if st.button("Get Answer"):
            with st.spinner(f"Getting answer in {selected_language}..."):
                # Combine all documents as reference
                combined_reference = "\n\n".join(
                    [f"{fname} (v{doc['version']}):\n{doc['text'][:2000]}..." for fname, doc in document_store[st.session_state.user_id].items()]
                )
                answer = ask_question(
                    question,
                    reference=combined_reference,
                    filename=", ".join(document_store[st.session_state.user_id].keys()),
                    version=max(doc['version'] for doc in document_store[st.session_state.user_id].values()),
                    language=selected_language
                )
                
                # Save to chat history
                save_chat_history(
                    st.session_state.user_id,
                    question,
                    answer,
                    ", ".join(document_store[st.session_state.user_id].keys()),
                    max(doc['version'] for doc in document_store[st.session_state.user_id].values()),
                    selected_language
                )
            
            st.subheader("Answer:")
            st.write(answer)
    elif question and not document_store[st.session_state.user_id]:
        st.warning("Please upload PDF documents first to ask questions.")

    # Chat History Section
    st.subheader("Chat History")
    user_chat_history = get_user_chat_history(st.session_state.user_id)
    
    if user_chat_history:
        # Show latest first
        user_chat_history.reverse()
        
        for i, chat in enumerate(user_chat_history[:10]):  # Show last 10 chats
            with st.expander(f"Q: {chat['question'][:50]}... ({chat['timestamp'][:10]})"):
                st.write(f"**Question:** {chat['question']}")
                st.write(f"**Answer:** {chat['answer']}")
                st.write(f"**Document:** {chat['document']} (v{chat['version']})")
                st.write(f"**Language:** {chat['language']}")
                st.write(f"**Time:** {chat['timestamp'][:19]}")
    else:
        st.info("No chat history yet. Ask some questions to get started!")

if __name__ == "__main__":
    main()