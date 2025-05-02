import React, { useState, useEffect, useRef } from "react";
import "./ChatWindow.css";
import { getAIMessage, resetChat } from "../api/api";
import { marked } from "marked";

// Function to extract YouTube video ID from URL
const getYouTubeVideoId = (url) => {
  if (!url) return null;
  const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|&v=)([^#&?]*).*/;
  const match = url.match(regExp);
  return (match && match[2].length === 11) ? match[2] : null;
};

// Function to process content and embed videos
const processContent = (content) => {
  const lines = content.split('\n');
  
  const processedLines = lines.map(line => {
    // Check if line contains a YouTube URL
    const youtubeRegex = /https?:\/\/(www\.)?(youtube\.com|youtu\.be)\/[^\s]+/g;
    const match = line.match(youtubeRegex);
    
    if (match) {
      const url = match[0];
      const videoId = getYouTubeVideoId(url);
      if (videoId) {
        // Return both the line with the URL and the embed
        return `${line}
<div class="video-container"><iframe width="480" height="200" src="https://www.youtube.com/embed/${videoId}" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe></div>`;
      }
    }
    return line;
  });

  // Join lines back together and convert markdown
  return marked(processedLines.join('\n')).replace(/<p>|<\/p>/g, "");
};

function ChatWindow() {

  const defaultMessage = [{
    role: "assistant",
    content: "Welcome to GAF Contractor Intelligence!\nI'm here to help you identify and connect with qualified roofing contractors in our database. \nI can assist you with:\n- Finding contractors by location (state, city)\n- Filtering by ratings and reviews\n- Identifying contractors with specific certifications (like Master Elite)\n- Providing business details and contact information\n- Sharing customer review highlights and years in business\nHow can I help you find the right roofing contractors today?"
  }];

  const [messages, setMessages] = useState(defaultMessage);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
      scrollToBottom();
  }, [messages, isLoading]);

  const handleSend = async (input) => {
    if (input.trim() !== "" && !isLoading) {
      // Set user message
      setMessages(prevMessages => [...prevMessages, { role: "user", content: input }]);
      setInput("");
      setIsLoading(true);

      // Call API & set assistant message
      const newMessage = await getAIMessage(input);
      setIsLoading(false);
      setMessages(prevMessages => [...prevMessages, newMessage]);
    }
  };

  const handleReset = async () => {
    if (!isLoading) {
      setIsLoading(true);
      const resetMessage = await resetChat();
      setIsLoading(false);
      setMessages([resetMessage]);
      setInput("");
    }
  };

  return (
    <div className="messages-container">
      {messages.map((message, index) => (
        <div key={index} className={`${message.role}-message-container`}>
          {message.content && (
            <div className={`message ${message.role}-message`}>
              <div dangerouslySetInnerHTML={{__html: processContent(message.content)}}></div>
            </div>
          )}
        </div>
      ))}
      {isLoading && (
        <div className="assistant-message-container">
          <div className="message assistant-message typing-indicator">
            <span></span>
            <span></span>
            <span></span>
          </div>
        </div>
      )}
      <div ref={messagesEndRef} />
      <div className="input-area">
        <div className="input-container">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={isLoading ? "Waiting for response..." : "Type a message..."}
          onKeyPress={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !isLoading) {
              handleSend(input);
              e.preventDefault();
            }
          }}
          rows="3"
        />
        <button 
          className="send-button" 
          onClick={() => handleSend(input)}
          disabled={isLoading}
        >
          Send
        </button>
        <button 
          className="reset-button" 
          onClick={handleReset}
          disabled={isLoading}
        >
          Reset Chat
        </button>
        </div>
      </div>
    </div>
  );
}

export default ChatWindow;
