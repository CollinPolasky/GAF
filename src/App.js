import React, { useState } from "react";
import "./App.css";
import ChatWindow from "./components/ChatWindow";
import ContractorList from "./components/ContractorList";
import logo from "./Magnifying_glass_icon.png";

function App() {
  const [isChatVisible, setIsChatVisible] = useState(false);

  const toggleChat = () => {
    setIsChatVisible(!isChatVisible);
  };

  return (
    <div className="App">
      <div className="heading">
        <img src={logo} alt="Magnifying Glass Logo" className="header-logo" />
        <div className="title">Lead Generation AI Assistant (Beta)</div>
        <div className="contact-info">
          <button 
            className="chat-toggle-button" 
            onClick={toggleChat}
          >
            {isChatVisible ? 'Close Chat' : 'Open Chat'}
          </button>
        </div>
      </div>
      
      <div className="main-content">
        {isChatVisible ? (
          <ChatWindow />
        ) : (
          <ContractorList />
        )}
      </div>
    </div>
  );
}

export default App;
