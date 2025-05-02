# GAF Lead Generation Agent
The GAF Lead Generation Agent is a tool to allow users to find new leads for their B2B service target at roofing contractors. It contains both a dashboard with pre-generated lead quality analysis as well as a chat tool to allow users to further query for additional information that might assist in locating and further understanding potential leads. The agent uses RAG (Retrieval-Augmented Generation) functions with Pinecone integration to provide accurate, context-aware responses as well as a unique method of Value Extraction such that each contractor's company values are discovered and recorded for advanced lead quality evaluation.

Highlights
- Pre-generated Lead Quality Analysis and Explaination
- Chat integration for additional research and flexibility
- Context-aware conversation handling and memory
- Intelligent RAG retrieval system for accurate responses


## System Architecture/Design
![Architecture](https://github.com/user-attachments/assets/9f2cd0b4-d68a-4397-82de-de1fe41b7f90)

This flowchart shows the system's architecture including:
- Multi-layered content filters and response validators
- Retrieval process using RAG from different sources (Contractor Info, Values, and Insights)
- Chat loop flow from query processing and filtering to response generation and validation


# Interface Demo

## Dashboard
![PartSelectDemoScreenshotStart](https://github.com/user-attachments/assets/a9a7b120-0cd7-4e6b-b9c7-3fe613a88e20)


## Chat
![PartSelectDemoScreenshot](https://github.com/user-attachments/assets/bbd9602e-39c9-4b55-a4eb-a93e81d8f2a9)



### Installation
Install the required packages:
pip install -r backend\requirements.txt
npm install

Environment Variables
Create a .env file in the backend directory with the following variables:

- OPENAI_API_KEY=your deepseek api key
- PINECONE_API_KEY=your pinecone api key

Replace "your api key" with your actual API keys.

Note: Make sure to keep your .env file private and never commit it to version control.

# Data
The files and functions are provided should you wish to replicate the databases for RAG features (in pinecone or otherwise) within /data and /RAG respectively

Starting the Web Interface

To start the web interface:

npm start

Navigate to the backend directory:

cd backend

Start the server with hot reloading enabled:

uvicorn main:app --reload

Open your web browser and navigate to http://localhost:8000 to access the web interface.
