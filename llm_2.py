from flask import Flask, request, jsonify, render_template_string
from werkzeug.utils import secure_filename
import fitz  
import os
import openai
import uuid
import re

app = Flask(__name__)

#  dictionary and a list of chunks
pdf_texts = {}
pdf_chunks = []

# OpenAI API key 
openai.api_key = "sk-proj-q0cd6SvAEg4kqOr2z7UBT3BlbkFJpf05aKcQhN3B56vjY4wp"  

# HTML template 
html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>AI...LLM Chatbot (कुछ भी मांगो)</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #f4f4f9;
            color: #333;
            margin: 0;
            padding: 0;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        h1 {
            color: #4CAF50;
        }
        form {
            background: #fff;
            padding: 20px;
            margin: 20px 0;
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
            border-radius: 8px;
            width: 300px;
        }
        input[type="file"],
        input[type="text"],
        input[type="submit"] {
            width: 100%;
            padding: 10px;
            margin: 10px 0;
            border: 1px solid #ccc;
            border-radius: 4px;
        }
        input[type="submit"] {
            background-color: #4CAF50;
            color: #fff;
            border: none;
            cursor: pointer;
        }
        input[type="submit"]:hover {
            background-color: #45a049;
        }
        #message {
            margin-top: 20px;
            padding: 10px;
            border-radius: 4px;
            display: none;
            background: #e0f7fa;
        }
        #response {
            margin-top: 20px;
            padding: 20px;
            border-radius: 8px;
            background: #e0f7fa;
            width: 80%;
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
        }
        .response-content {
            white-space: pre-wrap; /* Ensure the response text is properly formatted */
        }
        #reset-button {
            display: none;
            margin-top: 20px;
            padding: 10px;
            background-color: #f44336;
            color: #fff;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }
        #reset-button:hover {
            background-color: #e53935;
        }
    </style>
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script>
        $(document).ready(function() {
            // Handle PDF upload
            $('form[action="/upload"]').on('submit', function(event) {
                event.preventDefault();
                var formData = new FormData(this);
                $.ajax({
                    url: '/upload',
                    type: 'POST',
                    data: formData,
                    contentType: false,
                    processData: false,
                    success: function(response) {
                        $('#message').text(response.message).show();
                    },
                    error: function() {
                        $('#message').text('An error occurred while uploading the PDF.').show();
                    }
                });
            });

            // Handle question query
            $('form[action="/query"]').on('submit', function(event) {
                event.preventDefault();
                var formData = $(this).serialize();
                $.ajax({
                    url: '/query',
                    type: 'POST',
                    data: formData,
                    success: function(response) {
                        $('#response').html('<div class="response-content">' + response.response + '</div>').show();
                        $('#reset-button').show(); // Show the reset button
                        $('html, body').animate({ scrollTop: $(document).height() }, 'slow');
                    },
                    error: function() {
                        $('#response').text('An error occurred while fetching the answer.').show();
                    }
                });
            });

            // Handle reset button click
            $('#reset-button').on('click', function() {
                $('#query').val(''); // Clear the query input
                $('#response').hide().html(''); // Clear and hide the response box
                $(this).hide(); // Hide the reset button
            });
        });
    </script>
</head>
<body>
    <h1>AI...LLM Chatbot (कुछ भी मांगो)</h1>
    <form action="/upload" enctype="multipart/form-data" method="post">
        <input type="file" name="file">
        <input type="submit" value="Upload PDF">
    </form>
    <div id="message"></div>
    <form action="/query" method="post">
        <label for="query">Query:</label>
        <input type="text" id="query" name="query" placeholder="Ask a question about the PDF content...">
        <input type="submit" value="Ask Question">
    </form>
    <button id="reset-button">Reset</button>
    <div id="response"></div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(html_template)

@app.route('/upload', methods=['POST'])
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({"message": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"message": "No selected file"}), 400
    
    if file:
        filename = secure_filename(file.filename)
        file_id = str(uuid.uuid4())  # unique ID for this file
        file.save(filename)
        pdf_text = extract_text_from_pdf(filename)
        pdf_texts[file_id] = pdf_text
        
        
        pdf_chunks.extend(split_text_into_chunks(pdf_text))
        
        os.remove(filename)
        return jsonify({"message": "PDF uploaded and text extracted successfully.", "file_id": file_id})

def extract_text_from_pdf(file_path: str) -> str:
    doc = fitz.open(file_path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def split_text_into_chunks(text: str, chunk_size: int = 1000) -> list:
    """
    Splits the text into smaller chunks of a specified size.
    """
    chunks = []
    for i in range(0, len(text), chunk_size):
        chunks.append(text[i:i + chunk_size])
    return chunks

@app.route('/query', methods=['POST'])
def query_pdf():
    if not pdf_chunks:
        return jsonify({"message": "No PDFs uploaded yet."}), 400
    
    query = request.form['query']
    relevant_chunks = retrieve_relevant_chunks(query)
    response = get_llm_response(query, " ".join(relevant_chunks))
    return jsonify({"response": response})

def retrieve_relevant_chunks(query: str) -> list:
    """
    Retrieves the most relevant text chunks based on the query.
    """
   
    relevant_chunks = []
    for chunk in pdf_chunks:
        if re.search(re.escape(query), chunk, re.IGNORECASE):
            relevant_chunks.append(chunk)
    return relevant_chunks[:5]  

def get_llm_response(query: str, context: str) -> str:
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"Context: {context}\n\nQuestion: {query}"}
        ]
    )
    return response.choices[0].message['content'].strip()

if __name__ == '__main__':
    app.run(debug=True)
